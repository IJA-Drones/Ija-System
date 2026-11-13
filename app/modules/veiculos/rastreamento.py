from app.modules.gestao_ti.permissions import route_access
"""Fleet view backed by RedGPS position tables (or the Neon fixture)."""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import current_app, request, url_for
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import RastreamentoAlerta, RastreamentoHistorico, RastreamentoPosicao, Usuario, Veiculos, Equipe, EquipePiloto
from app.modules.veiculos.service import (
    EQUIPE_OCEANO_USER_TYPE,
    VEICULOS_ALLOWED_TYPES,
    VEICULOS_LOGS_ALLOWED_TYPES,
    _equipe_ids_do_piloto,
    _equipe_oceano_logada,
)
from app.modules.veiculos.redgps_sync import sync_redgps
from app.modules.veiculos.tracking_logs import load_logs, reconciliation
from app.modules.veiculos.tracking_period import parse_tracking_period
from app.shared.access import apply_prefeitura_scope, normalize_role


def scoped_tracking_vehicles(user):
    role = normalize_role(getattr(user, "tipo_usuario", None))
    if not route_access(user, role in VEICULOS_ALLOWED_TYPES):
        raise PermissionError

    query = Veiculos.query.options(joinedload(Veiculos.equipe).selectinload(Equipe.membros).joinedload(EquipePiloto.piloto)).filter(
        db.func.lower(db.func.coalesce(Veiculos.status, "")) != "inativo"
    )
    query = apply_prefeitura_scope(query, user, Veiculos.prefeitura_id)
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

    return query


def build_rastreamento_payload(user, *, sync_live=True):
    role = normalize_role(getattr(user, "tipo_usuario", None))
    query = scoped_tracking_vehicles(user)
    period = parse_tracking_period(request.args)
    vehicles = query.order_by(Veiculos.placa.asc(), Veiculos.id.asc()).all()
    vehicle_ids = [vehicle.id for vehicle in vehicles]
    supervisor_ids = {v.supervisor_usuario_id for v in vehicles if v.supervisor_usuario_id}
    responsible_names = {
        u.id: u.nome_uvis or u.login
        for u in db.session.query(Usuario.id, Usuario.nome_uvis, Usuario.login).filter(Usuario.id.in_(supervisor_ids)).all()
    } if supervisor_ids else {}
    sync = sync_redgps() if sync_live and vehicle_ids and request.args.get("cached") != "1" else {
        "enabled": bool(current_app.config.get("REDGPS_SYNC_ENABLED")),
        "poll_interval_seconds": current_app.config.get("REDGPS_POLL_INTERVAL_SECONDS", 60), "error": False}
    local_zone = ZoneInfo("America/Sao_Paulo")
    history_day = period.day
    start, end = period.utc_bounds()
    logs_by_vehicle = load_logs(vehicle_ids, user, history_day, period=period)
    selected = request.args.get("vehicle_id") or request.args.get("vehicle")
    if selected is not None:
        try:
            selected_id = int(selected)
        except (ValueError, TypeError):
            raise ValueError("Veículo inválido.") from None
        if selected_id not in vehicle_ids:
            raise PermissionError
        history_ids = [selected_id]
    else:
        history_ids = vehicle_ids[:1]

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
            .order_by(RastreamentoPosicao.is_demo.asc(), RastreamentoPosicao.reportado_em.desc(), RastreamentoPosicao.id.desc())
            .all()
        )
        for position in positions:
            positions_by_vehicle.setdefault(position.veiculo_id, position)

        histories = (
            RastreamentoHistorico.query
            .filter(RastreamentoHistorico.veiculo_id.in_(history_ids))
            .filter(db.or_(
                db.and_(RastreamentoHistorico.is_demo.is_(False),
                        RastreamentoHistorico.reportado_em >= start, RastreamentoHistorico.reportado_em < end),
                db.and_(RastreamentoHistorico.is_demo.is_(True),
                        RastreamentoHistorico.reportado_em >= period.start.replace(tzinfo=None),
                        RastreamentoHistorico.reportado_em < period.end.replace(tzinfo=None)),
            ))
            .order_by(RastreamentoHistorico.reportado_em.asc(), RastreamentoHistorico.id.asc())
            .all()
        )
        for point in histories:
            history_by_vehicle.setdefault(point.veiculo_id, []).append(point)
        for vehicle_id, points in history_by_vehicle.items():
            position = positions_by_vehicle.get(vehicle_id)
            if (position and not position.is_demo) or any(not point.is_demo for point in points):
                history_by_vehicle[vehicle_id] = [point for point in points if not point.is_demo]

        alerts = (
            RastreamentoAlerta.query
            .filter(RastreamentoAlerta.veiculo_id.in_(vehicle_ids))
            .order_by(RastreamentoAlerta.reportado_em.desc(), RastreamentoAlerta.id.desc())
            .all()
        )
        for alert in alerts:
            alerts_by_vehicle.setdefault(alert.veiculo_id, []).append(alert)

    def iso(value, utc=False):
        return value.isoformat() + ("Z" if utc else "") if value else None

    def position_payload(position):
        if not position:
            return None
        return {
            "lat": position.latitude,
            "lng": position.longitude,
            "speed_kmh": position.velocidade_kmh,
            "ignition": 1 if position.ignicao is True else 0 if position.ignicao is False else 2,
            "odometer_km": position.hodometro_km,
            "reported_at": position.reportado_em.replace(tzinfo=local_zone).isoformat() if position.is_demo else iso(position.reportado_em, utc=True),
            "address": position.endereco,
            "telemetry": position.telemetria or {},
        }

    def history_payload(point):
        return {
            "lat": point.latitude,
            "lng": point.longitude,
            "speed_kmh": point.velocidade_kmh,
            "ignition": 1 if point.ignicao is True else 0 if point.ignicao is False else 2,
            "odometer_km": point.hodometro_km,
            "reported_at": point.reportado_em.replace(tzinfo=local_zone).isoformat() if point.is_demo else iso(point.reportado_em, utc=True),
            "is_demo": bool(point.is_demo),
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
        titular = vehicle.equipe.piloto_titular if vehicle.equipe else None
        ploa_driver = {"name": titular.nome_piloto, "pilot_id": titular.id, "team_id": vehicle.equipe_id} if titular else None
        position = positions_by_vehicle.get(vehicle.id)
        history = [history_payload(point) for point in history_by_vehicle.get(vehicle.id, [])]
        linked = reconciliation(logs_by_vehicle.get(vehicle.id, []), history, history_day,
                                user, vehicle.id, datetime.now(local_zone).replace(tzinfo=None),
                                period=period if request.args.get("start") else None)
        payload_vehicles.append(
            {
                **linked,
                "history_loaded": vehicle.id in history_ids,
                "id": str(vehicle.id),
                "plate": vehicle.placa,
                "model": vehicle.modelo,
                "operation": vehicle.operacao,
                "fleet": vehicle.frota,
                "team": vehicle.equipe.nome_equipe if vehicle.equipe else "Sem equipe",
                "responsible": responsible_names.get(vehicle.supervisor_usuario_id)
                if vehicle.supervisor_usuario_id else (vehicle.responsavel or "").strip() or None,
                "ploa_driver": ploa_driver,
                "registered_km": vehicle.km_atual,
                "position": position_payload(position),
                "history": history,
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
            "synced_at": iso(latest_report, utc=not has_demo),
            "sync": sync,
        },
        "vehicles": payload_vehicles,
        "history_date": history_day.isoformat(),
        "history_period": period.payload(),
    }
