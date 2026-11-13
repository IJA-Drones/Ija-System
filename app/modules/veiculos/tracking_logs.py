"""Reconcile observed GPS samples with recorded shifts, without changing logs."""
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import current_app, url_for
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import LogVeiculo
from app.modules.veiculos.service import (
    VEICULOS_LOGS_ALLOWED_TYPES, _apply_log_actor_scope,
)
from app.shared.access import normalize_role

BRAZIL = ZoneInfo("America/Sao_Paulo")


def local_iso(value):
    return value.replace(tzinfo=BRAZIL).isoformat() if value else None


def driver(log):
    name = log.condutor_nome or (log.piloto.nome_piloto if log.piloto else None)
    return {"name": name, "pilot_id": log.piloto_id, "log_id": log.id,
            "started_at": local_iso(log.data_registro)}


def load_logs(vehicle_ids, user, day, period=None):
    if not vehicle_ids:
        return {}
    # Include today's open shifts even when reviewing an earlier route. Closed
    # legacy shifts have no reliable end time and are linked by opening day only.
    day_start = period.start.replace(tzinfo=None) if period else datetime.combine(day, datetime.min.time())
    day_end = period.end.replace(tzinfo=None) if period else day_start + timedelta(days=1)
    query = LogVeiculo.query.options(joinedload(LogVeiculo.piloto)).filter(
        LogVeiculo.veiculo_id.in_(vehicle_ids),
        db.or_(
            LogVeiculo.km_final.is_(None),
            db.and_(LogVeiculo.data_registro < day_end,
                    db.or_(LogVeiculo.encerrado_em >= day_start,
                           LogVeiculo.data_registro >= day_start)),
        ),
    )
    if normalize_role(user.tipo_usuario) in {"piloto", "equipe_oceano"}:
        query = _apply_log_actor_scope(query, user)
    result = {}
    for log in query.order_by(LogVeiculo.data_registro.asc(), LogVeiculo.id.asc()):
        result.setdefault(log.veiculo_id, []).append(log)
    return result


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def _when(point):
    return datetime.fromisoformat(point["reported_at"].replace("Z", "+00:00"))


def gap_seconds():
    return max(300, 3 * int(current_app.config.get("REDGPS_POLL_INTERVAL_SECONDS", 60)))


def route_summary(points):
    """Odometer deltas when usable; straight-line estimates otherwise.

    Never bridge communication gaps, resets or implausible jumps. The presence
    of points alone does not prove complete coverage of the selected day.
    """
    distance = 0
    gaps = resets = 0
    estimated = False
    valid_edges = 0
    for index, point in enumerate(points):
        point["break_before"] = False
        point["geometry_break_before"] = False
        point["break_reason"] = None
        if index == 0:
            continue
        before = points[index - 1]
        elapsed = (_when(point) - _when(before)).total_seconds()
        if elapsed <= 0 or elapsed > gap_seconds() or point["is_demo"] != before["is_demo"]:
            point["break_before"] = True
            point["geometry_break_before"] = True
            point["break_reason"] = "gap"
            gaps += 1
            continue
        a, b = before["odometer_km"], point["odometer_km"]
        lat1, lat2 = math.radians(before["lat"]), math.radians(point["lat"])
        delta_lat = lat2 - lat1
        delta_lng = math.radians(point["lng"] - before["lng"])
        h = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
        geometry = 6371 * 2 * math.asin(math.sqrt(min(1, max(0, h))))
        measured = _number(a) and _number(b)
        delta = b - a if measured else geometry
        if delta < 0 or max(delta, geometry) > 200 * elapsed / 3600 + 0.1:
            resets += 1
            point["break_before"] = True
            point["geometry_break_before"] = geometry > 200 * elapsed / 3600 + 0.1
            point["break_reason"] = "gps_jump" if point["geometry_break_before"] else "odometer"
            continue
        distance += delta
        estimated |= not measured
        valid_edges += 1
    speeds = [p["speed_kmh"] for p in points if _number(p["speed_kmh"]) and p["speed_kmh"] >= 0]
    return {
        "sample_count": len(points), "first_at": points[0]["reported_at"] if points else None,
        "last_at": points[-1]["reported_at"] if points else None,
        "distance_km": round(distance, 2) if valid_edges else None,
        "distance_source": "estimated" if estimated else "odometer" if valid_edges else None,
        "max_speed_kmh": max(speeds, default=None), "gaps": gaps,
        "invalid_segments": resets, "gap_threshold_seconds": gap_seconds(),
        "is_demo": any(p["is_demo"] for p in points),
    }


def reconciliation(logs, points, day, user, vehicle_id, now, period=None):
    summary = route_summary(points)
    active = [log for log in logs if log.km_final is None and log.data_registro <= now]
    current_driver = driver(active[0]) if len(active) == 1 else None
    day_start = period.start.replace(tzinfo=None) if period else datetime.combine(day, datetime.min.time())
    day_end = period.end.replace(tzinfo=None) if period else day_start + timedelta(days=1)
    day_logs = [log for log in logs if log.data_registro < day_end and (
        (log.encerrado_em and log.encerrado_em >= day_start)
        or (log.km_final is None and log.data_registro <= now)
        or log.data_registro >= day_start
    )]
    rows = []
    point_logs = [[] for _ in points]
    for log in day_logs:
        begin = log.data_registro.replace(tzinfo=BRAZIL)
        closed = log.km_final is not None
        finish = log.encerrado_em.replace(tzinfo=BRAZIL) if closed and log.encerrado_em else (
            now.replace(tzinfo=BRAZIL) if not closed else None)
        indices = [i for i, p in enumerate(points) if finish and begin <= _when(p) <= finish]
        for i in indices:
            point_logs[i].append(log.id)
        samples = [dict(points[i]) for i in indices]
        observed = route_summary(samples)
        recorded = log.km_final - log.km_inicial if closed and _number(log.km_final) and _number(log.km_inicial) else None
        tolerance = max(2, abs(recorded or 0) * .05)
        reason = None
        if not closed:
            reason = "open"
        elif finish is None:
            reason = "unknown_end"
        elif recorded is None or recorded < 0 or finish < begin:
            reason = "invalid_log"
        elif begin.replace(tzinfo=None) < day_start or finish.replace(tzinfo=None) > day_end:
            reason = "outside_period" if period else "crosses_day"
        elif observed["is_demo"]:
            reason = "demo"
        elif len(samples) < 2:
            reason = "no_gps"
        elif ((_when(samples[0]) - begin).total_seconds() > gap_seconds()
              or (finish - _when(samples[-1])).total_seconds() > gap_seconds()
              or observed["gaps"] or observed["invalid_segments"]):
            reason = "partial_gps"
        elif observed["distance_source"] != "odometer":
            reason = "estimated_gps"
        rows.append({
            "id": log.id, "driver": driver(log), "started_at": local_iso(log.data_registro),
            "ended_at": local_iso(log.encerrado_em), "status": "closed" if closed else "open",
            "initial_km": log.km_inicial, "final_km": log.km_final,
            "recorded_km": round(recorded, 2) if recorded is not None else None,
            "gps": observed, "difference_km": None, "comparison": "inconclusive",
            "reason": reason, "tolerance_km": round(tolerance, 2),
        })
    overlapping = {log_id for ids in point_logs if len(ids) > 1 for log_id in ids}
    # Overlaps can exist even with no sample inside their intersection.
    for i, a in enumerate(day_logs):
        a_end = a.encerrado_em or (now if a.km_final is None else None)
        for b in day_logs[i + 1:]:
            b_end = b.encerrado_em or (now if b.km_final is None else None)
            if a_end and b_end and max(a.data_registro, b.data_registro) < min(a_end, b_end):
                overlapping.update((a.id, b.id))
    for row in rows:
        if row["id"] in overlapping:
            row["reason"] = "overlap"
        if row["reason"] is None:
            difference = round(row["gps"]["distance_km"] - row["recorded_km"], 2)
            row["difference_km"] = difference
            row["comparison"] = "difference" if abs(difference) > row["tolerance_km"] else "within_tolerance"
        row["url"] = url_for("main.veiculo_logs_detalhe", veiculo_id=vehicle_id,
                             _anchor=f"turnoHeader{row['id']}") if normalize_role(user.tipo_usuario) in VEICULOS_LOGS_ALLOWED_TYPES else None
    for p, ids in zip(points, point_logs):
        p["log_id"] = ids[0] if len(ids) == 1 else None
        match = next((row for row in rows if row["id"] == p["log_id"]), None)
        p["driver_name"] = match["driver"]["name"] if match else None
    closed_day = [row for row in rows if row["recorded_km"] is not None
                  and day_start <= datetime.fromisoformat(row["started_at"]).replace(tzinfo=None) < day_end
                  and row["ended_at"] and datetime.fromisoformat(row["ended_at"]).replace(tzinfo=None) <= day_end]
    summary.update({
        "date": day.isoformat(), "logs": rows,
        "recorded_km": round(sum(row["recorded_km"] for row in closed_day), 2) if closed_day else None,
        "unlinked_samples": sum(not ids for ids in point_logs),
        "differences": sum(row["comparison"] == "difference" for row in rows),
    })
    return {"driver": current_driver, "driver_conflict": len(active) > 1, "daily": summary}
