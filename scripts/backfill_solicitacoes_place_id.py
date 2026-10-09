import argparse
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.extensions import db
from app.models import OrdemServico, Solicitacao
from app.shared.place_id import clean_place_id, resolve_google_place_id_for_address


def _parse_ids(raw_value):
    if not raw_value:
        return []
    try:
        return sorted({int(value.strip()) for value in raw_value.split(",") if value.strip()})
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--ids deve conter apenas numeros separados por virgula.") from exc


def _parse_created_since(raw_value):
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--created-since deve estar no formato AAAA-MM-DD.") from exc


def parse_args():
    parser = argparse.ArgumentParser(
        description="Preenche Place ID de solicitacoes usando a API de geocodificacao do Google."
    )
    parser.add_argument("--ids", type=_parse_ids, help="IDs separados por virgula.")
    parser.add_argument(
        "--created-since",
        type=_parse_created_since,
        help="Seleciona solicitacoes criadas a partir da data AAAA-MM-DD.",
    )
    parser.add_argument("--flight-date-from", type=_parse_created_since)
    parser.add_argument("--flight-date-to", type=_parse_created_since)
    parser.add_argument("--limit", type=int, default=None, help="Limite de solicitacoes analisadas.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Efetiva um commit a cada quantidade informada de solicitacoes processadas.",
    )
    parser.add_argument(
        "--no-google",
        action="store_true",
        help="Usa apenas Place ID da origem ou do KML ja vinculado, sem chamar a API.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Grava os Place IDs resolvidos. Sem esta opcao, executa em modo de simulacao.",
    )
    args = parser.parse_args()
    has_flight_range = args.flight_date_from or args.flight_date_to
    if bool(args.flight_date_from) != bool(args.flight_date_to):
        parser.error("Informe --flight-date-from e --flight-date-to em conjunto.")
    if args.flight_date_from and args.flight_date_to < args.flight_date_from:
        parser.error("--flight-date-to nao pode ser anterior a --flight-date-from.")
    if not args.ids and not args.created_since and not has_flight_range:
        parser.error(
            "Informe --ids, --created-since ou o intervalo completo de datas dos voos."
        )
    if args.batch_size is not None and args.batch_size < 1:
        parser.error("--batch-size deve ser maior que zero.")
    if args.batch_size and not args.commit:
        parser.error("--batch-size somente pode ser usado junto com --commit.")
    return args


def main():
    args = parse_args()
    app = create_app()
    result = {
        "scanned": 0,
        "resolved": 0,
        "copied_from_origin": 0,
        "copied_from_linked_kml": 0,
        "google_requests": 0,
        "google_skipped": 0,
        "cache_hits": 0,
        "no_result": 0,
    }
    address_cache = {}

    with app.app_context():
        missing_place_id = func.length(func.trim(func.coalesce(Solicitacao.place_id, ""))) == 0
        query = (
            Solicitacao.query
            .options(
                joinedload(Solicitacao.origem_retorno),
                joinedload(Solicitacao.ordem_servico).joinedload(OrdemServico.dji_kml_route),
            )
            .filter(missing_place_id)
            .order_by(Solicitacao.data_criacao.desc(), Solicitacao.id.desc())
        )
        if args.ids:
            query = query.filter(Solicitacao.id.in_(args.ids))
        if args.created_since:
            query = query.filter(func.date(Solicitacao.data_criacao) >= args.created_since)
        if args.flight_date_from and args.flight_date_to:
            query = query.join(OrdemServico, OrdemServico.solicitacao_id == Solicitacao.id).filter(
                or_(
                    OrdemServico.data_aplicacao.between(
                        args.flight_date_from,
                        args.flight_date_to,
                    ),
                    Solicitacao.data_agendamento.between(
                        args.flight_date_from,
                        args.flight_date_to,
                    ),
                    func.date(OrdemServico.respondido_em).between(
                        args.flight_date_from,
                        args.flight_date_to,
                    ),
                )
            )
        if args.limit:
            query = query.limit(max(1, args.limit))

        solicitacoes = query.all()
        for solicitacao in solicitacoes:
            result["scanned"] += 1
            origin_place_id = clean_place_id(
                getattr(getattr(solicitacao, "origem_retorno", None), "place_id", None)
            )
            linked_kml = getattr(
                getattr(solicitacao, "ordem_servico", None),
                "dji_kml_route",
                None,
            )
            linked_kml_place_id = clean_place_id(getattr(linked_kml, "place_id", None))
            source_place_id = origin_place_id or linked_kml_place_id
            source_label = "origin" if origin_place_id else ("linked_kml" if linked_kml_place_id else "google")

            address_key = tuple(
                str(value or "").strip().lower()
                for value in (
                    solicitacao.cep,
                    solicitacao.logradouro,
                    solicitacao.numero,
                    solicitacao.bairro,
                    solicitacao.cidade,
                    solicitacao.uf,
                )
            )
            if source_place_id:
                resolved_place_id = source_place_id
            elif address_key in address_cache:
                resolved_place_id = address_cache[address_key]
                result["cache_hits"] += 1
                source_label = "cache"
            elif args.no_google:
                resolved_place_id = None
                result["google_skipped"] += 1
            else:
                result["google_requests"] += 1
                resolved_place_id = resolve_google_place_id_for_address(
                    cep=solicitacao.cep,
                    logradouro=solicitacao.logradouro,
                    numero=solicitacao.numero,
                    bairro=solicitacao.bairro,
                    cidade=solicitacao.cidade,
                    uf=solicitacao.uf,
                )
                address_cache[address_key] = resolved_place_id

            if not resolved_place_id:
                result["no_result"] += 1
                print(f"no_result solicitacao_id={solicitacao.id}", flush=True)
                if args.commit and args.batch_size and result["scanned"] % args.batch_size == 0:
                    db.session.commit()
                    print(
                        f"batch_committed processed={result['scanned']} "
                        f"resolved={result['resolved']}",
                        flush=True,
                    )
                continue

            result["resolved"] += 1
            if origin_place_id:
                result["copied_from_origin"] += 1
            elif linked_kml_place_id:
                result["copied_from_linked_kml"] += 1
            if args.commit:
                solicitacao.place_id = resolved_place_id
            print(
                f"resolved solicitacao_id={solicitacao.id} source={source_label}",
                flush=True,
            )
            if args.commit and args.batch_size and result["scanned"] % args.batch_size == 0:
                db.session.commit()
                print(
                    f"batch_committed processed={result['scanned']} "
                    f"resolved={result['resolved']}",
                    flush=True,
                )

        if args.commit:
            db.session.commit()
            if args.batch_size and result["scanned"] % args.batch_size:
                print(
                    f"batch_committed processed={result['scanned']} "
                    f"resolved={result['resolved']} final=true",
                    flush=True,
                )
        else:
            db.session.rollback()

    mode = "COMMIT" if args.commit else "DRY_RUN"
    print(f"BACKFILL_PLACE_ID_{mode}_DONE")
    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
