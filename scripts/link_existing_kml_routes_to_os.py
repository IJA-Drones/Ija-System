import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.models import DjiFlightKmlRoute
from app.modules.dji_flight_logs.service import auto_link_existing_kml_routes_to_os


def parse_args():
    parser = argparse.ArgumentParser(
        description="Vincula rotas KML ja importadas as OS existentes usando o match automatico."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra os vinculos provaveis sem gravar no banco.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limita a quantidade de rotas KML pendentes analisadas.",
    )
    parser.add_argument(
        "--route-id-min",
        type=int,
        default=None,
        help="Processa apenas rotas KML com ID maior ou igual a este valor.",
    )
    parser.add_argument(
        "--route-id-max",
        type=int,
        default=None,
        help="Processa apenas rotas KML com ID menor ou igual a este valor.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Processa por faixas de route_id com este tamanho.",
    )
    parser.add_argument(
        "--resolve-place-id",
        action="store_true",
        help="Tenta preencher place_id das rotas KML sem place_id antes de vincular.",
    )
    return parser.parse_args()


def print_progress(status, route, ordem, score, details):
    if status == "linked":
        print(
            "linked route_id={route_id} route_code={route_code} ordem_id={ordem_id} "
            "os={identificador_os} score={score}".format(
                route_id=route.id,
                route_code=route.route_code,
                ordem_id=ordem.id,
                identificador_os=ordem.identificador_os or "",
                score=score,
            ),
            flush=True,
        )
    elif status == "error":
        print(f"error route_id={route.id} route_code={route.route_code}", flush=True)
    else:
        print(f"no_match route_id={route.id} route_code={route.route_code}", flush=True)


def main():
    args = parse_args()
    app = create_app()
    all_matches = []

    with app.app_context():
        mode = "DRY_RUN" if args.dry_run else "COMMIT"
        print(f"KML_OS_AUTO_LINK_{mode}_START", flush=True)
        if args.batch_size:
            min_id = args.route_id_min
            max_id = args.route_id_max
            if min_id is None:
                min_id = DjiFlightKmlRoute.query.order_by(DjiFlightKmlRoute.id.asc()).with_entities(DjiFlightKmlRoute.id).first()
                min_id = min_id[0] if min_id else 0
            if max_id is None:
                max_id = DjiFlightKmlRoute.query.order_by(DjiFlightKmlRoute.id.desc()).with_entities(DjiFlightKmlRoute.id).first()
                max_id = max_id[0] if max_id else 0

            result = {
                "scanned": 0,
                "linked": 0,
                "no_match": 0,
                "errors": 0,
                "place_resolved": 0,
                "matches": [],
            }
            batch_start = min_id
            while batch_start <= max_id:
                batch_end = min(batch_start + args.batch_size - 1, max_id)
                print(f"BATCH route_id={batch_start}-{batch_end} START", flush=True)
                batch_result = auto_link_existing_kml_routes_to_os(
                    limit=args.limit,
                    route_id_min=batch_start,
                    route_id_max=batch_end,
                    commit=not args.dry_run,
                    resolve_missing_place_id=args.resolve_place_id,
                    progress_callback=print_progress,
                )
                print(
                    "BATCH route_id={}-{} DONE scanned={} linked={} no_match={} errors={}".format(
                        batch_start,
                        batch_end,
                        batch_result["scanned"],
                        batch_result["linked"],
                        batch_result["no_match"],
                        batch_result["errors"],
                    ),
                    flush=True,
                )
                for key in ("scanned", "linked", "no_match", "errors", "place_resolved"):
                    result[key] += batch_result[key]
                result["matches"].extend(batch_result["matches"])
                all_matches.extend(batch_result["matches"])
                batch_start = batch_end + 1
        else:
            result = auto_link_existing_kml_routes_to_os(
                limit=args.limit,
                route_id_min=args.route_id_min,
                route_id_max=args.route_id_max,
                commit=not args.dry_run,
                resolve_missing_place_id=args.resolve_place_id,
                progress_callback=print_progress,
            )
            all_matches.extend(result["matches"])

    print(f"KML_OS_AUTO_LINK_{mode}_DONE")
    print(f"scanned={result['scanned']}")
    print(f"linked={result['linked']}")
    print(f"no_match={result['no_match']}")
    print(f"errors={result['errors']}")
    print(f"place_resolved={result.get('place_resolved', 0)}")

    for match in all_matches:
        details = match["details"]
        print(
            "route_id={route_id} route_code={route_code} ordem_id={ordem_id} "
            "os={identificador_os} score={score} time={time} aircraft={aircraft} "
            "pilot={pilot} place={place} address={address} geo={geo} "
            "distance_meters={distance_meters}".format(
                **match,
                time=details.get("time"),
                aircraft=details.get("aircraft"),
                pilot=details.get("pilot"),
                place=details.get("place"),
                address=details.get("address"),
                geo=details.get("geo"),
                distance_meters=details.get("distance_meters"),
            )
        )


if __name__ == "__main__":
    main()
