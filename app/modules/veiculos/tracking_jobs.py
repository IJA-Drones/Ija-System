"""Bounded background refreshes; requests keep serving saved GPS samples."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import monotonic

from flask import current_app

from app.extensions import db
from app.modules.veiculos.redgps_history import import_redgps_history
from app.modules.veiculos.redgps_sync import sync_redgps

_registry_lock = Lock()


def _recover(app, vehicle_id, period):
    with app.app_context():
        try:
            sync_redgps()
            return import_redgps_history(period.day, app.config.get("REDGPS_HISTORY_TIMEZONE", "America/Sao_Paulo"),
                                        vehicle_ids=[vehicle_id], period=period)
        finally:
            db.session.remove()


def request_history_refresh(vehicle_id, period):
    """Return promptly; repeated authorized requests poll the same refresh.

    PostgreSQL advisory locking in the synchronizers coordinates other workers.
    No user objects, sessions or provider credentials are returned to callers.
    """
    app = current_app._get_current_object()
    key = (vehicle_id, period.start, period.end)
    now = monotonic()
    with _registry_lock:
        registry = app.extensions.setdefault("tracking_history_jobs", {})
        for old_key, entry in list(registry.items()):
            if entry["future"].done() and now - (entry["completed"] or now) > 300:
                del registry[old_key]
        entry = registry.get(key)
        if entry:
            future = entry["future"]
            if not future.done():
                return {"busy": True, "state": "running", "retry_after_ms": 1500}, 202
            try:
                result = future.result()
            except Exception:
                del registry[key]
                app.logger.warning("Atualização do histórico GPS indisponível; pontos salvos preservados.")
                return {"state": "error", "error": "Não foi possível atualizar o trajeto. Os pontos salvos foram mantidos."}, 502
            if not result.get("busy") and now - (entry["completed"] or now) < 60:
                return {**result, "state": "complete"}, 200
            del registry[key]
        # Keep only a small queue when a provider is slow or many periods change.
        if sum(not item["future"].done() for item in registry.values()) >= 4:
            return {"busy": True, "state": "queued", "retry_after_ms": 2500}, 202
        executor = app.extensions.get("tracking_history_executor")
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tracking-history")
            app.extensions["tracking_history_executor"] = executor
        future = executor.submit(_recover, app, vehicle_id, period)
        entry = {"future": future, "completed": None}
        registry[key] = entry
        future.add_done_callback(lambda _: entry.update(completed=monotonic()))
        return {"busy": True, "state": "running", "retry_after_ms": 1500}, 202
