from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.extensions import db
from app.models import ContratoAgro, OrdemServicoAgro, OrcamentoAgro


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Remove dados operacionais do Agro nas tabelas "
            "ordens_servico_agro, contratos_agro e orcamentos_agro."
        )
    )
    parser.add_argument(
        "--prefeitura-id",
        type=int,
        help="Limita a exclusao a uma prefeitura especifica.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Executa a exclusao. Sem esta flag o script roda apenas em modo de previa.",
    )
    return parser


def _apply_prefeitura_scope(query, model, prefeitura_id: int | None):
    if prefeitura_id is None:
        return query
    return query.filter(model.prefeitura_id == prefeitura_id)


def _count_rows(model, prefeitura_id: int | None) -> int:
    query = db.session.query(model)
    query = _apply_prefeitura_scope(query, model, prefeitura_id)
    return query.count()


def _collect_counts(prefeitura_id: int | None) -> dict[str, int]:
    return {
        "ordens_servico_agro": _count_rows(OrdemServicoAgro, prefeitura_id),
        "contratos_agro": _count_rows(ContratoAgro, prefeitura_id),
        "orcamentos_agro": _count_rows(OrcamentoAgro, prefeitura_id),
    }


def _print_counts(title: str, counts: dict[str, int]) -> None:
    print(title)
    for table_name, total in counts.items():
        print(f"  {table_name}: {total}")


def _delete_rows(prefeitura_id: int | None) -> dict[str, int]:
    deleted = {}

    os_query = _apply_prefeitura_scope(db.session.query(OrdemServicoAgro), OrdemServicoAgro, prefeitura_id)
    deleted["ordens_servico_agro"] = os_query.delete(synchronize_session=False)

    contratos_query = _apply_prefeitura_scope(db.session.query(ContratoAgro), ContratoAgro, prefeitura_id)
    deleted["contratos_agro"] = contratos_query.delete(synchronize_session=False)

    orcamentos_query = _apply_prefeitura_scope(db.session.query(OrcamentoAgro), OrcamentoAgro, prefeitura_id)
    deleted["orcamentos_agro"] = orcamentos_query.delete(synchronize_session=False)

    return deleted


def main() -> int:
    args = _build_parser().parse_args()
    app = create_app()

    with app.app_context():
        target_label = (
            f"prefeitura_id={args.prefeitura_id}"
            if args.prefeitura_id is not None
            else "todas as prefeituras"
        )
        print(f"Escopo selecionado: {target_label}")

        before_counts = _collect_counts(args.prefeitura_id)
        _print_counts("Contagem antes da operacao:", before_counts)

        if not args.confirm:
            print("Modo de previa finalizado. Rode novamente com --confirm para excluir.")
            return 0

        try:
            deleted_counts = _delete_rows(args.prefeitura_id)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        _print_counts("Linhas removidas:", deleted_counts)
        after_counts = _collect_counts(args.prefeitura_id)
        _print_counts("Contagem depois da operacao:", after_counts)
        print("Exclusao concluida com sucesso.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
