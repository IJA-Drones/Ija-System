"""Opt-in CSRF protection for browser sessions, without database storage."""

import secrets

from flask import abort, current_app, jsonify, request, session
from flask_login import current_user


CSRF_SESSION_KEY = "_ija_csrf"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LOGIN_ENDPOINTS = {"auth.login", "auth.login_uvis_operacional", "auth.login_piloto_agro"}


def csrf_enabled():
    return bool(current_app.config.get("CSRF_PROTECTION_ENABLED", False))


def csrf_token():
    if not csrf_enabled():
        return ""
    token = session.get(CSRF_SESSION_KEY)
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def rotate_csrf_token():
    if csrf_enabled():
        session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)


def _csrf_failure():
    current_app.logger.warning("CSRF rejeitado: endpoint=%s metodo=%s", request.endpoint, request.method)
    if request.is_json or "/api/" in request.path or request.headers.get("Sec-Fetch-Dest") == "empty":
        return jsonify(error="Recarregue a página e tente novamente.", code="csrf_invalid"), 403
    abort(403, description="Recarregue a página e tente novamente.")


def enforce_csrf():
    if not csrf_enabled() or request.method not in UNSAFE_METHODS:
        return
    # Public endpoints without cookie authentication do not act on a user's
    # account. The three login forms are protected against login CSRF as well.
    if not current_user.is_authenticated and request.endpoint not in LOGIN_ENDPOINTS:
        return

    expected = session.get(CSRF_SESSION_KEY)
    supplied = (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or request.form.get("_csrf_token")
    )
    if (
        not isinstance(expected, str) or not expected
        or not isinstance(supplied, str)
        or not secrets.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8"))
    ):
        return _csrf_failure()


def register_csrf_security(app):
    if app.config.get("CSRF_PROTECTION_ENABLED"):
        if not app.secret_key or str(app.secret_key).startswith("dev-") or len(app.secret_key) < 32:
            raise ValueError("CSRF_PROTECTION_ENABLED exige SECRET_KEY fixa e com pelo menos 32 caracteres.")
    app.before_request(enforce_csrf)
    app.context_processor(lambda: {"csrf_token": csrf_token, "ija_csrf_enabled": csrf_enabled()})

    @app.after_request
    def csrf_page_cache_control(response):
        if csrf_enabled() and response.mimetype == "text/html":
            response.headers["Cache-Control"] = "private, no-store"
        return response
