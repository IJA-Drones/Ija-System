"""Persist GPS readings; coordinate polling across PostgreSQL workers."""
import math
import re
import threading
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.clients.redgps_client import RedGPSClient, RedGPSError
from app.extensions import db
from app.models import RastreamentoHistorico, RastreamentoPosicao, RastreamentoSincronizacao, Veiculos

_lock = threading.Lock()
_ADVISORY_LOCK = 724190071


def plate_key(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def number(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (ValueError, TypeError):
        return None


def normalize_position(row):
    lat, lng = number(row.get("Latitude")), number(row.get("Longitude"))
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    # This provider uses empty/zero GPS readings for devices without a fix.
    if lat == 0 and lng == 0:
        return None
    try:
        when = datetime.fromisoformat(str(row.get("ReportDate", "")).replace("Z", "+00:00"))
        when = when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when.astimezone(timezone.utc)
    except ValueError:
        return None
    if when.year < 2000 or when > datetime.now(timezone.utc) + timedelta(minutes=5):
        return None
    speed, odometer = number(row.get("GpsSpeed")), number(row.get("Odometer"))
    return {
        "latitude": lat, "longitude": lng,
        "velocidade_kmh": speed if speed is not None and speed >= 0 else None,
        "ignicao": {"0": False, "1": True}.get(str(row.get("Ignition"))),
        "hodometro_km": odometer / 1000 if odometer is not None and odometer >= 0 else None,
        "reportado_em": when.replace(tzinfo=None),
        "endereco": str(row.get("Domicilio") or "")[:255] or None,
    }


def _metadata(state, interval):
    return {
        "enabled": True,
        "poll_interval_seconds": interval,
        "last_success_at": state.sincronizado_em.isoformat() + "Z" if state and state.sincronizado_em else None,
        "error": bool(state and state.erro),
    }


def sync_redgps():
    """Poll at most once per interval, including failures; never commit caller work."""
    interval = max(60, int(current_app.config.get("REDGPS_POLL_INTERVAL_SECONDS", 60)))
    if not current_app.config.get("REDGPS_SYNC_ENABLED"):
        return {"enabled": False, "poll_interval_seconds": interval, "error": False}
    if not _lock.acquire(blocking=False):
        return {"enabled": True, "poll_interval_seconds": interval, "busy": True, "error": False}
    try:
        with Session(db.engine) as session, session.begin():
            if db.engine.dialect.name == "postgresql":
                acquired = session.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK}).scalar()
                if not acquired:
                    state = session.get(RastreamentoSincronizacao, 1)
                    return {**_metadata(state, interval), "busy": True}
            state = session.get(RastreamentoSincronizacao, 1)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if state and state.tentado_em and (now - state.tentado_em).total_seconds() < interval:
                return _metadata(state, interval)
            if state is None:
                state = RastreamentoSincronizacao(id=1)
                session.add(state)
            state.tentado_em = now
            client = current_app.extensions.get("redgps_client")
            if client is None:
                client = RedGPSClient(current_app.config)
                current_app.extensions["redgps_client"] = client
            try:
                rows = client.read("getdata")
            except RedGPSError as error:
                state.erro = str(error)
                current_app.logger.warning("Consulta RedGPS indisponível (%s).", state.erro)
                return _metadata(state, interval)

            # Only existing, unambiguous local registrations may receive data.
            by_plate = {}
            for vehicle in session.scalars(select(Veiculos)):
                if (vehicle.status or "").lower() == "inativo":
                    continue
                by_plate.setdefault(plate_key(vehicle.placa), []).append(vehicle)
            saved = unmatched = invalid = 0
            for row in rows:
                candidates = by_plate.get(plate_key(row.get("UnitPlate")), [])
                if len(candidates) != 1:
                    unmatched += 1
                    continue
                values = normalize_position(row)
                if values is None:
                    invalid += 1
                    continue
                vehicle = candidates[0]
                position = session.scalar(select(RastreamentoPosicao).where(
                    RastreamentoPosicao.veiculo_id == vehicle.id,
                    RastreamentoPosicao.is_demo.is_(False),
                    RastreamentoPosicao.provedor == "RedGPS",
                ).order_by(RastreamentoPosicao.reportado_em.desc()).limit(1))
                if position is None:
                    position = RastreamentoPosicao(veiculo_id=vehicle.id, prefeitura_id=vehicle.prefeitura_id,
                                                  provedor="RedGPS", is_demo=False)
                    session.add(position)
                if position.reportado_em is None or values["reportado_em"] >= position.reportado_em:
                    for key, value in values.items():
                        setattr(position, key, value)
                    position.prefeitura_id = vehicle.prefeitura_id
                # Stable reading identity makes retries/restarts idempotent.
                identity = f"redgps:{vehicle.id}:{values['reportado_em'].isoformat()}"
                exists = session.scalar(select(RastreamentoHistorico.id).where(
                    RastreamentoHistorico.chave_fixture == identity))
                if exists is None:
                    history = {key: value for key, value in values.items() if key != "endereco"}
                    session.add(RastreamentoHistorico(
                        veiculo_id=vehicle.id, prefeitura_id=vehicle.prefeitura_id,
                        provedor="RedGPS", is_demo=False, chave_fixture=identity, **history,
                    ))
                saved += 1
            state.erro = "posicoes_invalidas" if rows and not saved and invalid else None
            state.sincronizado_em = datetime.now(timezone.utc).replace(tzinfo=None)
            return {**_metadata(state, interval), "received": len(rows), "matched": saved,
                    "unmatched": unmatched, "invalid": invalid}
    except SQLAlchemyError:
        current_app.logger.warning("Sincronização RedGPS indisponível no banco; verifique conexão e migrações.")
        return {"enabled": True, "poll_interval_seconds": interval, "error": True}
    finally:
        _lock.release()
