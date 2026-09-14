"""Fleet view backed by RedGPS position tables (or the Neon fixture)."""

from flask import url_for
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import RastreamentoAlerta, RastreamentoHistorico, RastreamentoPosicao, Veiculos
from app.modules.veiculos.service import (
    EQUIPE_OCEANO_USER_TYPE,
    VEICULOS_ALLOWED_TYPES,
    VEICULOS_LOGS_ALLOWED_TYPES,
    _equipe_ids_do_piloto,
    _equipe_oceano_logada,
)
from app.shared.access import apply_prefeitura_scope, normalize_role


def build_rastreamento_payload(user):
    role = normalize_role(getattr(user, "tipo_usuario", None))
    if role not in VEICULOS_ALLOWED_TYPES:
        raise PermissionError

    query = Veiculos.query.options(joinedload(Veiculos.equipe)).filter(
        db.func.lower(db.func.coalesce(Veiculos.status, "")) != "inativo"
    )
    if role == EQUIPE_OCEANO_USER_TYPE:
        equipe = _equipe_oceano_logada(user)
        if not equipe:
            raise PermissionError
        # Legacy vehicles can have no prefeitura but still belong to this team.
        query = query.filter(Veiculos.equipe_id == equipe.id)
    else:
        query = apply_prefeitura_scope(query, user, Veiculos.prefeitura_id)
        if role == "piloto":
            query = query.filter(Veiculos.equipe_id.in_(_equipe_ids_do_piloto(user)))

    vehicles = query.order_by(Veiculos.placa.asc(), Veiculos.id.asc()).all()
    vehicle_ids = [vehicle.id for vehicle in vehicles]

    # The RedGPS synchronizer can append readings without changing the vehicle
    # cadastro.  Keep the latest reading and the route history separate so the
    # UI can show the online map and the route/Flashback views from the same API.
    positions_by_vehicle = {}
    history_by_vehicle = {}
    alerts_by_vehicle = {}
    if vehicle_ids:
        positions = (
            RastreamentoPosicao.query
            .filter(RastreamentoPosicao.veiculo_id.in_(vehicle_ids))
            .order_by(RastreamentoPosicao.reportado_em.desc(), RastreamentoPosicao.id.desc())
            .all()
        )
        for position in positions:
            positions_by_vehicle.setdefault(position.veiculo_id, position)

        histories = (
            RastreamentoHistorico.query
            .filter(RastreamentoHistorico.veiculo_id.in_(vehicle_ids))
            .order_by(RastreamentoHistorico.reportado_em.asc(), RastreamentoHistorico.id.asc())
            .all()
        )
        for point in histories:
            history_by_vehicle.setdefault(point.veiculo_id, []).append(point)

        alerts = (
            RastreamentoAlerta.query
            .filter(RastreamentoAlerta.veiculo_id.in_(vehicle_ids))
            .order_by(RastreamentoAlerta.reportado_em.desc(), RastreamentoAlerta.id.desc())
            .all()
        )
        for alert in alerts:
            alerts_by_vehicle.setdefault(alert.veiculo_id, []).append(alert)

    def iso(value):
        return value.isoformat() if value else None

    def position_payload(position):
        if not position:
            return None
        return {
            "lat": position.latitude,
            "lng": position.longitude,
            "speed_kmh": position.velocidade_kmh,
            "ignition": 1 if position.ignicao is True else 0 if position.ignicao is False else 2,
            "odometer_km": position.hodometro_km,
            "reported_at": iso(position.reportado_em),
            "address": position.endereco,
        }

    def history_payload(point):
        return {
            "lat": point.latitude,
            "lng": point.longitude,
            "speed_kmh": point.velocidade_kmh,
            "ignition": 1 if point.ignicao is True else 0 if point.ignicao is False else 2,
            "odometer_km": point.hodometro_km,
            "reported_at": iso(point.reportado_em),
        }

    def alert_payload(alert):
        return {
            "title": alert.tipo,
            "description": alert.mensagem,
            "severity": alert.severidade,
            "resolved": bool(alert.resolvido),
            "reported_at": iso(alert.reportado_em),
        }

    payload_vehicles = []
    for vehicle in vehicles:
        position = positions_by_vehicle.get(vehicle.id)
        payload_vehicles.append(
            {
                "id": str(vehicle.id),
                "plate": vehicle.placa,
                "model": vehicle.modelo,
                "operation": vehicle.operacao,
                "fleet": vehicle.frota,
                "team": vehicle.equipe.nome_equipe if vehicle.equipe else "Sem equipe",
                "registered_km": vehicle.km_atual,
                "position": position_payload(position),
                "history": [history_payload(point) for point in history_by_vehicle.get(vehicle.id, [])],
                "alerts": [alert_payload(alert) for alert in alerts_by_vehicle.get(vehicle.id, [])],
                "logs_url": url_for("main.veiculo_logs_detalhe", veiculo_id=vehicle.id)
                if role in VEICULOS_LOGS_ALLOWED_TYPES else None,
            }
        )

    has_demo = any(
        position and position.is_demo
        for position in positions_by_vehicle.values()
    ) or any(
        point.is_demo
        for points in history_by_vehicle.values()
        for point in points
    )
    latest_report = max(
        (position.reportado_em for position in positions_by_vehicle.values() if position),
        default=None,
    )
    return {
        "integration": {
            "provider": "RedGPS",
            "status": "test" if has_demo else "connected" if positions_by_vehicle else "pending",
            "source": "Neon · fixture fictícia" if has_demo else "RedGPS",
            "synced_at": iso(latest_report),
        },
        "vehicles": payload_vehicles,
    }
