"""Apply DJI Cloud API battery OSD reports to existing scoped equipment."""
import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.extensions import db
from app.models import Baterias, Drones, Equipamentos
from app.modules.equipamentos.baterias import battery_snapshot, parse_cycle_count, record_battery_update, resolve_battery_tenant
from app.modules.equipamentos.controles import drone_prefeitura


def _serial(value):
    return value.strip().upper() if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9-]{1,100}', value.strip()) else None


def _read_cycles(payload, now):
    if len(payload) > 1_000_000:
        return None, {}
    try:
        report = json.loads(payload)
        timestamp = report['timestamp']
        batteries = report['data']['battery']['batteries']
        if type(timestamp) is not int or timestamp <= 0 or not isinstance(batteries, list):
            return None, {}
        reported_at = datetime.fromtimestamp(timestamp / 1000, timezone.utc).replace(tzinfo=None)
    except (KeyError, TypeError, ValueError, OSError, OverflowError, RecursionError):
        return None, {}
    if reported_at > now + timedelta(minutes=1):
        return None, {}

    cycles = {}
    for battery in batteries:
        if not isinstance(battery, dict) or not (serial := _serial(battery.get('sn'))):
            continue
        try:
            count = parse_cycle_count(battery.get('loop_times'))
        except ValueError:
            continue
        if cycles.setdefault(serial, count) != count:
            cycles[serial] = None
    return reported_at, {serial: count for serial, count in cycles.items() if count is not None}


def sync_battery_cycles(aircraft_serial, payload, *, now=None):
    """Receive one report from an authorized aircraft topic. Return the number of updated batteries."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    serial = _serial(aircraft_serial)
    reported_at, reports = _read_cycles(payload, now)
    if not serial or not reports:
        return 0

    aircraft = Drones.query.filter(func.upper(func.trim(Drones.numero_serie)) == serial).limit(2).all()
    if len(aircraft) != 1:
        return 0
    try:
        prefeitura_id = drone_prefeitura(aircraft[0])
    except ValueError:
        return 0

    # The hardware reports may include borrowed batteries. Match by recorded
    # serial and municipality while leaving the equipment assignments intact.
    batteries = db.session.execute(select(Baterias).where(
        func.upper(func.trim(Baterias.numero_serie)).in_(reports),
        db.or_(Baterias.prefeitura_id == prefeitura_id, Baterias.prefeitura_id.is_(None)),
    ).order_by(Baterias.id).with_for_update(of=Equipamentos)).scalars().unique().all()
    eligible = {}
    for battery in batteries:
        try:
            if resolve_battery_tenant(existing=battery) == prefeitura_id:
                eligible.setdefault(_serial(battery.numero_serie), []).append(battery)
        except ValueError:
            continue

    updated = 0
    for serial, matches in eligible.items():
        if len(matches) != 1:
            continue
        battery = matches[0]
        count = reports[serial]
        latest = battery.ciclos_atualizados_em
        if latest and (reported_at <= latest or count == battery.ciclo):
            continue
        if battery.ciclo is not None and count < battery.ciclo:
            continue
        before = battery_snapshot(battery)
        battery.ciclo = count
        record_battery_update(battery, user=None, before=before, tipo='sincronizacao_dji',
                              confirm_cycles=True, cycles_observed_at=reported_at)
        updated += 1
    db.session.commit()
    return updated
