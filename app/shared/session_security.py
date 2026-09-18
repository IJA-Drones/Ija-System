"""Idle expiry using Flask's signed session, without database changes."""

import math
import secrets
import time

from flask import Blueprint, current_app, flash, jsonify, redirect, request, session, url_for
from flask_login import current_user, logout_user

from app.shared.password_policy import password_policy, security_enabled


SESSION_KEY = "_ija_security"
LOGIN_ENDPOINTS = {"auth.login", "auth.login_uvis_operacional", "auth.login_piloto_agro"}
bp = Blueprint("session_security", __name__)


def idle_seconds():
    test_seconds = current_app.config.get("SESSION_IDLE_TIMEOUT_SECONDS")
    if test_seconds is not None:
        return int(test_seconds)
    return int(current_app.config.get("SESSION_IDLE_TIMEOUT_MINUTES", 15)) * 60


def max_lifetime_seconds():
    hours = int(current_app.config.get("SESSION_MAX_LIFETIME_HOURS", 0))
    return hours * 3600 if hours else None


def start_security_session():
    if security_enabled():
        now = time.time()
        session[SESSION_KEY] = {
            "last_activity": now,
            "created_at": now,
            "csrf": secrets.token_urlsafe(32),
            "login_endpoint": request.endpoint if request.endpoint in LOGIN_ENDPOINTS else "auth.login",
        }


def _login_url():
    state = session.get(SESSION_KEY)
    endpoint = state.get("login_endpoint") if isinstance(state, dict) else None
    if endpoint not in LOGIN_ENDPOINTS:
        user_type = getattr(current_user, "tipo_usuario", None)
        endpoint = {
            "piloto_agro": "auth.login_piloto_agro",
            "equipe_uvis": "auth.login_uvis_operacional",
        }.get(user_type, "auth.login")
    return url_for(endpoint)


def _json_request():
    return (
        request.blueprint == "session_security"
        or request.is_json
        or "/api/" in request.path
        or request.headers.get("Sec-Fetch-Dest") == "empty"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    )


def _expire_session(reason):
    login_url = _login_url()
    current_app.logger.info("Sessão encerrada: usuario_id=%s motivo=%s", current_user.id, reason)
    logout_user()
    session.clear()
    # Keep Flask-Login's instruction to remove any old remember-me cookie.
    session["_remember"] = "clear"
    message = "Sua sessão expirou por inatividade. Entre novamente."
    if reason == "absolute_timeout":
        message = "Sua sessão atingiu o limite de duração. Entre novamente."
    if reason == "missing_session":
        message = "Entre novamente para iniciar uma sessão com a nova política de segurança."
    flash(message, "warning")
    if _json_request():
        return jsonify(error=message, code="session_expired", login_url=login_url), 401
    return redirect(login_url, code=303)


def _session_timing():
    state = session.get(SESSION_KEY)
    if not isinstance(state, dict) or not isinstance(state.get("csrf"), str) or not state["csrf"]:
        return None
    last_activity = state.get("last_activity")
    created_at = state.get("created_at")
    if (
        not isinstance(last_activity, (int, float)) or not math.isfinite(last_activity)
        or not isinstance(created_at, (int, float)) or not math.isfinite(created_at)
    ):
        return None
    now = time.time()
    if created_at > now + 5 or last_activity > now + 5 or last_activity < created_at:
        return None
    idle_remaining = idle_seconds() - (now - last_activity)
    maximum = max_lifetime_seconds()
    absolute_remaining = maximum - (now - created_at) if maximum is not None else None
    return {
        "expires_in": min(idle_remaining, absolute_remaining) if absolute_remaining is not None else idle_remaining,
        "absolute": absolute_remaining is not None and absolute_remaining <= idle_remaining,
        "absolute_expires_in": absolute_remaining,
    }


def _touch_session():
    session[SESSION_KEY] = {**session[SESSION_KEY], "last_activity": time.time()}


def enforce_idle_timeout():
    if not security_enabled() or request.endpoint == "static" or request.path.startswith("/static/"):
        return
    if request.path in {"/healthz", "/healthz/full"} or not current_user.is_authenticated:
        return

    timing = _session_timing()
    if timing is None:
        return _expire_session("missing_session")
    if timing["expires_in"] <= 0:
        return _expire_session("absolute_timeout" if timing["absolute"] else "idle_timeout")

    # Polling, uploads and other background requests must not renew the session.
    # HTML navigation also supports users whose browser has JavaScript disabled.
    is_navigation = request.headers.get("Sec-Fetch-Mode") == "navigate" or (
        not request.headers.get("Sec-Fetch-Dest")
        and request.accept_mimetypes.best == "text/html"
    )
    if request.blueprint != "session_security" and is_navigation and request.method in {"GET", "POST"}:
        _touch_session()


def _status_response():
    timing = _session_timing()
    return jsonify(expires_in=max(0, timing["expires_in"]), absolute=timing["absolute"],
                   absolute_expires_in=timing["absolute_expires_in"], login_url=_login_url())


@bp.get("/auth/session-status")
def status():
    if not security_enabled():
        return jsonify(error="Controle de sessão desativado."), 404
    if not current_user.is_authenticated:
        return jsonify(code="session_expired", login_url=url_for("auth.login")), 401
    return _status_response()


@bp.post("/auth/session-activity")
def activity():
    if not security_enabled():
        return jsonify(error="Controle de sessão desativado."), 404
    if not current_user.is_authenticated:
        return jsonify(code="session_expired", login_url=url_for("auth.login")), 401
    expected = session[SESSION_KEY]["csrf"]
    supplied = request.headers.get("X-Session-CSRF", "")
    if not secrets.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8")):
        return jsonify(error="Não foi possível validar a atividade da sessão."), 403
    _touch_session()
    return _status_response()


def _template_security():
    if not security_enabled() or not current_user.is_authenticated:
        return {"ija_security": None}
    timing = _session_timing()
    return {"ija_security": {
        "expires_in": max(0, timing["expires_in"]),
        "idle_timeout_seconds": idle_seconds(),
        "absolute": timing["absolute"],
        "absolute_expires_in": timing["absolute_expires_in"],
        "csrf": session[SESSION_KEY]["csrf"],
        "status_url": url_for("session_security.status"),
        "activity_url": url_for("session_security.activity"),
        "login_url": _login_url(),
        "password": password_policy(),
    }}


def register_session_security(app):
    if app.config.get("SECURITY_CONTROLS_ENABLED"):
        if not app.secret_key or str(app.secret_key).startswith("dev-") or len(app.secret_key) < 32:
            raise ValueError("SECURITY_CONTROLS_ENABLED exige SECRET_KEY fixa e com pelo menos 32 caracteres.")
        test_seconds = app.config.get("SESSION_IDLE_TIMEOUT_SECONDS")
        if test_seconds is not None:
            if not (app.debug or app.testing):
                raise ValueError("SESSION_IDLE_TIMEOUT_SECONDS é permitido apenas em DEBUG ou TESTING.")
            try:
                test_seconds = int(test_seconds)
            except (TypeError, ValueError) as exc:
                raise ValueError("SESSION_IDLE_TIMEOUT_SECONDS deve ser um número inteiro.") from exc
            if not 5 <= test_seconds <= 59:
                raise ValueError("SESSION_IDLE_TIMEOUT_SECONDS deve estar entre 5 e 59.")
            app.config["SESSION_IDLE_TIMEOUT_SECONDS"] = test_seconds
        for name, default, minimum, maximum in (
            ("SESSION_IDLE_TIMEOUT_MINUTES", 15, 1, 1440),
            ("SESSION_MAX_LIFETIME_HOURS", 0, 0, 168),
            ("PASSWORD_MIN_LENGTH", 15, 8, 128),
        ):
            try:
                value = int(app.config.get(name, default))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} deve ser um número inteiro.") from exc
            if not minimum <= value <= maximum:
                raise ValueError(f"{name} deve estar entre {minimum} e {maximum}.")
            app.config[name] = value

    app.before_request(enforce_idle_timeout)
    app.context_processor(_template_security)
    app.register_blueprint(bp)

    @app.after_request
    def security_cache_control(response):
        if security_enabled() and (
            current_user.is_authenticated or request.blueprint == "session_security"
            or response.status_code == 303
        ):
            response.headers["Cache-Control"] = "no-store"
        return response
