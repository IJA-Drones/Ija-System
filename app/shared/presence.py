from datetime import datetime, timezone

from flask import current_app, request

from app.extensions import db
from app.models import UsuarioPresenca


def _utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _resolve_request_ip():
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for

    real_ip = (request.headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip

    return request.remote_addr or None


def should_track_presence():
    endpoint = (request.endpoint or "").strip().lower()
    path = (request.path or "").strip().lower()
    return not (
        path.startswith("/static/")
        or endpoint.startswith("static")
        or path in {"/healthz", "/healthz/full"}
    )


def record_user_presence(user, *, mark_login=False, mark_logout=False):
    if not should_track_presence():
        return

    user_id = getattr(user, "id", None)
    if not user_id:
        return

    now = _utcnow_naive()
    query_string = request.query_string.decode("utf-8", errors="ignore").strip() or None
    user_agent = (request.headers.get("User-Agent") or "").strip() or None
    referrer = (request.referrer or "").strip() or None

    try:
        presence = UsuarioPresenca.query.filter_by(usuario_id=user_id).first()
        if presence is None:
            presence = UsuarioPresenca(
                usuario_id=user_id,
                primeiro_acesso_em=now,
            )
            db.session.add(presence)

        presence.ultimo_acesso_em = now
        presence.ultimo_metodo = (request.method or "")[:10] or None
        presence.ultimo_endpoint = (request.endpoint or "")[:120] or None
        presence.ultimo_path = (request.path or "/")[:255]
        presence.ultimo_query_string = query_string
        presence.ip = _resolve_request_ip()
        presence.user_agent = user_agent
        presence.referrer = referrer[:255] if referrer else None

        if mark_login:
            presence.login_em = now
            presence.logout_em = None
        if mark_logout:
            presence.logout_em = now

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro ao registrar presenca de usuario.")
