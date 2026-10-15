"""Password age and short-lived renewal proof; legacy passwords remain exempt."""
import hashlib
import hmac
import secrets
import time
from datetime import timedelta

from flask import current_app, flash, jsonify, redirect, request, session
from flask_login import current_user, logout_user
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import PoliticaSenha
from app.shared.csrf_security import CSRF_SESSION_KEY
from app.shared.login_protection import utcnow

RENEWAL_KEY = "_ija_password_renewal"
PASSWORD_SESSION_KEY = "_ija_password_changed_at"
RENEWAL_SECONDS = 600
LOGIN_CHANNELS = {
    "principal": "auth.login",
    "uvis": "auth.login_uvis_operacional",
    "agro": "auth.login_piloto_agro",
}


def validity_days():
    policy = db.session.get(PoliticaSenha, 1)
    # create_all-based environments use the same default as the migration.
    return policy.validade_dias if policy is not None else 90


def password_expired(user):
    changed_at = getattr(user, "senha_alterada_em", None)
    return changed_at is not None and utcnow() >= changed_at + timedelta(days=validity_days())


def password_stamp(user):
    changed_at = getattr(user, "senha_alterada_em", None)
    return changed_at.isoformat() if changed_at is not None else None


def remember_password_version(user):
    session.pop(RENEWAL_KEY, None)
    session[PASSWORD_SESSION_KEY] = password_stamp(user)


def fingerprint(user):
    # Never put a password or its verifier in the client-side signed cookie.
    value = f"{user.id}:{user.senha_hash}:{password_stamp(user)}:{user.tipo_usuario}"
    secret = current_app.secret_key
    key = secret if isinstance(secret, bytes) else secret.encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def start_renewal(user, channel):
    session.clear()
    session["_remember"] = "clear"
    session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)
    session[RENEWAL_KEY] = {
        "user_id": user.id, "created_at": time.time(),
        "fingerprint": fingerprint(user), "channel": channel,
    }


def valid_renewal(state, user):
    if not isinstance(state, dict) or user is None:
        return False
    created = state.get("created_at")
    proof = state.get("fingerprint")
    if (not isinstance(created, (int, float)) or not 0 <= time.time() - created < RENEWAL_SECONDS
            or state.get("channel") not in LOGIN_CHANNELS
            or not isinstance(proof, str) or not hmac.compare_digest(proof, fingerprint(user))):
        return False
    if user.tipo_usuario == "piloto_agro":
        return bool(user.piloto_agro and user.piloto_agro.ativo)
    return True


def ensure_csrf():
    if not session.get(CSRF_SESSION_KEY):
        session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)
    return session[CSRF_SESSION_KEY]


def valid_csrf(supplied):
    expected = session.get(CSRF_SESSION_KEY)
    return (isinstance(expected, str) and bool(expected) and isinstance(supplied, str)
            and secrets.compare_digest(expected.encode(), supplied.encode()))


def enforce_password_expiration():
    if request.endpoint in {"static", "auth.logout", "main.logout", "healthz", "healthz_full"}:
        return
    if not current_user.is_authenticated:
        return
    try:
        stamp = password_stamp(current_user)
        changed = stamp is not None and session.get(PASSWORD_SESSION_KEY) != stamp
        expired = password_expired(current_user)
    except SQLAlchemyError:
        db.session.rollback()
        return "Não foi possível verificar a validade da senha. Tente novamente em instantes.", 503
    if not changed and not expired:
        return
    from app.shared.session_security import _json_request, _login_url

    login_url = _login_url()
    logout_user()
    session.clear()
    session["_remember"] = "clear"
    message = ("Sua senha venceu. Entre com a senha atual para definir uma nova."
               if expired else "Sua senha foi alterada. Entre novamente com a senha atual.")
    flash(message, "warning")
    if _json_request():
        return jsonify(code="password_expired" if expired else "password_changed",
                       error=message, login_url=login_url), 401
    return redirect(login_url, code=303)


def register_password_expiration(app):
    app.before_request(enforce_password_expiration)

    @app.after_request
    def password_cache_control(response):
        if (current_user.is_authenticated or request.blueprint == "auth"
                or response.status_code in {303, 401, 503}):
            response.headers["Cache-Control"] = "private, no-store"
        return response
