import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.extensions import db
from app.models import DjiFlightKmlRoute, OrdemServico
from app.modules.dji_flight_logs import service


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--route-id-min", type=int, default=None)
    parser.add_argument("--route-id-max", type=int, default=None)
    return parser.parse_args()


def reason_from_details(score, details, second_score=None):
    parts = []
    if second_score is not None and score - second_score < 15:
        parts.append(f"ambiguo: diferenca para 2a OS foi {score - second_score:.0f} pontos")
    if details.get("time", 0) < 20:
        parts.append("data/horario fraco")
    if details.get("aircraft", 0) < 25:
        parts.append("drone/aeronave nao bateu")
    if details.get("pilot", 0) == 0:
        parts.append("piloto nao bateu")
    if details.get("geo", 0) < 22:
        distance = details.get("distance_meters")
        if distance is None:
            parts.append("sem coordenada comparavel")
        else:
            parts.append(f"distancia alta ({distance:.0f} m)")
    if not parts:
        parts.append("score abaixo da confianca automatica")
    return "; ".join(parts)


def main():
    args = parse_args()
    app = create_app()
    with app.app_context():
        linked_route_ids = db.session.query(OrdemServico.dji_kml_route_id).filter(
            OrdemServico.dji_kml_route_id.isnot(None)
        )
        query = DjiFlightKmlRoute.query.filter(~DjiFlightKmlRoute.id.in_(linked_route_ids))
        if args.route_id_min is not None:
            query = query.filter(DjiFlightKmlRoute.id >= args.route_id_min)
        if args.route_id_max is not None:
            query = query.filter(DjiFlightKmlRoute.id <= args.route_id_max)
        query = query.order_by(DjiFlightKmlRoute.id.asc())
        if args.limit:
            query = query.limit(args.limit)
        routes = query.all()

        print(f"total_unlinked={len(routes)}", flush=True)
        for route in routes:
            try:
                points = json.loads(route.points_json or "[]")
            except Exception:
                print(f"{route.id} | {route.route_code} | arquivo KML com pontos invalidos", flush=True)
                continue

            candidates = service._candidate_ordens_for_kml_route(route)
            if not candidates:
                print(f"{route.id} | {route.route_code} | sem OS candidata na janela de data (+/- 2 dias)", flush=True)
                continue

            scored = []
            for ordem in candidates:
                score, details = service._score_os_kml_match(ordem, route, points)
                scored.append((ordem, score, details))
            scored.sort(key=lambda item: item[1], reverse=True)

            best_ordem, best_score, best_details = scored[0]
            second_score = scored[1][1] if len(scored) > 1 else None
            reason = reason_from_details(best_score, best_details, second_score)
            print(
                f"{route.id} | {route.route_code} | melhor_os={best_ordem.solicitacao_id} "
                f"| score={best_score:.0f} | {reason}"
                ,
                flush=True,
            )


if __name__ == "__main__":
    main()
