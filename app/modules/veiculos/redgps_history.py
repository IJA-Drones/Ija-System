"""Recover a provider day, including readings missed by the live poller.

The source timezone is required: history/get does not document UseUTCDate.
Confirm it with OLLOG before enabling recovery in the hosted environment.
"""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from time import monotonic

from flask import current_app
from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from app.clients.redgps_client import RedGPSClient
from app.extensions import db
from app.models import RastreamentoHistorico, Veiculos
from app.modules.veiculos.redgps_sync import _ADVISORY_LOCK, _lock, normalize_position, plate_key

def import_redgps_history(day, source_timezone, plates=None, vehicle_ids=None, period=None):
    if not current_app.config.get("REDGPS_SYNC_ENABLED"):
        raise ValueError("REDGPS_SYNC_ENABLED precisa estar habilitado.")
    source_zone = ZoneInfo(source_timezone)
    brazil = ZoneInfo("America/Sao_Paulo")
    today = datetime.now(brazil).date()
    if day > today:
        raise ValueError("Não é possível consultar um dia futuro.")
    start = period.start if period else datetime.combine(day, time.min, brazil)
    requested_end = period.end if period else start + timedelta(days=1)
    end = min(requested_end, datetime.now(brazil))
    if start >= end or requested_end - start > timedelta(days=15):
        raise ValueError("Selecione um período passado de até 15 dias.")
    utc_start = start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = end.astimezone(timezone.utc).replace(tzinfo=None)
    selected = {plate_key(plate) for plate in plates} if plates else None
    if not _lock.acquire(blocking=False):
        return {"busy": True, "inserted": 0}
    try:
        recent_imports = current_app.extensions.setdefault("redgps_history_recent_imports", {})
        cache_key = (tuple(sorted(vehicle_ids)), start, requested_end, source_timezone) if vehicle_ids else None
        if cache_key in recent_imports and monotonic() - recent_imports[cache_key][0] < 60:
            return {**recent_imports[cache_key][1], "cached": True}
        with Session(db.engine) as session, session.begin():
            if db.engine.dialect.name == "postgresql" and not session.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK}
            ).scalar():
                return {"busy": True, "inserted": 0}
            client = current_app.extensions.get("redgps_client") or RedGPSClient(current_app.config)
            current_app.extensions["redgps_client"] = client
            # Use the provider's actual device-to-plate mapping; never guess IMEIs.
            cached_units = current_app.extensions.get("redgps_units_cache")
            units = cached_units[1] if cached_units and monotonic() - cached_units[0] < 60 else client.read("getdata")
            current_app.extensions["redgps_units_cache"] = (monotonic(), units)
            by_plate, by_device = {}, {}
            for unit in units:
                key, device = plate_key(unit.get("UnitPlate")), str(unit.get("GpsIdentif") or "")
                by_plate.setdefault(key, []).append(device)
                by_device.setdefault(device, set()).add(key)
            local = {}
            for vehicle in session.scalars(select(Veiculos)):
                local.setdefault(plate_key(vehicle.placa), []).append(vehicle)
            counts = {"inserted": 0, "duplicate": 0, "invalid": 0, "vehicles": 0, "unmatched": 0}
            for key, vehicles in local.items():
                if selected is not None and key not in selected:
                    continue
                if vehicle_ids is not None and not any(vehicle.id in vehicle_ids for vehicle in vehicles):
                    continue
                devices = by_plate.get(key, [])
                if len(vehicles) != 1 or len(devices) != 1 or not devices[0] or len(by_device[devices[0]]) != 1:
                    counts["unmatched"] += 1
                    continue
                vehicle = vehicles[0]
                if (vehicle.status or "").lower() == "inativo":
                    continue
                rows = client.read_history(devices[0], start.astimezone(source_zone),
                                           (end - timedelta(seconds=1)).astimezone(source_zone))
                existing = set(session.scalars(select(RastreamentoHistorico.chave_fixture).where(
                    RastreamentoHistorico.veiculo_id == vehicle.id,
                    RastreamentoHistorico.reportado_em >= utc_start,
                    RastreamentoHistorico.reportado_em < utc_end,
                )))
                counts["vehicles"] += 1
                pending = []
                for row in rows:
                    # A reused GPS device must not attach another vehicle's trip.
                    if str(row.get("equipo") or "") != devices[0] or plate_key(row.get("patente")) != key:
                        counts["invalid"] += 1
                        continue
                    raw_date = str(row.get("fecha_reporte") or "")
                    try:
                        reported = datetime.strptime(raw_date, "%Y%m%d%H%M%S").replace(tzinfo=source_zone)
                    except ValueError:
                        counts["invalid"] += 1
                        continue
                    if not start <= reported.astimezone(brazil) < end:
                        counts["invalid"] += 1
                        continue
                    gmt = row.get("gmt")
                    if gmt is not None:
                        try:
                            if abs(float(gmt) * 3600 - reported.utcoffset().total_seconds()) > 1:
                                counts["invalid"] += 1
                                continue
                        except (ValueError, TypeError):
                            counts["invalid"] += 1
                            continue
                    values = normalize_position({
                        "Latitude": row.get("latitud"), "Longitude": row.get("longitud"),
                        "ReportDate": reported.astimezone(timezone.utc).isoformat(),
                        "GpsSpeed": row.get("velocidad"), "Ignition": row.get("ignicion"),
                        "Odometer": row.get("odometro"),
                    })
                    if values is None:
                        counts["invalid"] += 1
                        continue
                    identity = f"redgps:{vehicle.id}:{values['reportado_em'].isoformat()}"
                    if identity in existing:
                        counts["duplicate"] += 1
                        continue
                    values.pop("endereco")
                    values.pop("telemetria")
                    pending.append(dict(veiculo_id=vehicle.id, prefeitura_id=vehicle.prefeitura_id,
                                        provedor="RedGPS", is_demo=False, chave_fixture=identity, **values))
                    existing.add(identity)
                    counts["inserted"] += 1
                if pending:
                    session.execute(insert(RastreamentoHistorico.__table__), pending)
        if cache_key:
            recent_imports[cache_key] = (monotonic(), counts)
            if len(recent_imports) > 512:
                oldest = min(recent_imports, key=lambda key: recent_imports[key][0])
                del recent_imports[oldest]
        return counts
    finally:
        _lock.release()
