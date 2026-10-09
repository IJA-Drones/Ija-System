"""Editor for role permissions, with environment-controlled activation."""

import json
import secrets

from flask import abort, current_app, jsonify, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app.modules.gestao_ti.service import (
    ConfigurationConflict, build_editor_data, can_manage_central_ti, save_configurations,
)
from app.shared.access import normalize_role
from app.modules.gestao_ti.permissions import active_configuration, enforcement_enabled, invalidate_request_permissions


CSRF_SESSION_KEY = "_ija_central_ti_csrf"
MAX_PAYLOAD_BYTES = 262144
CENTRAL_ENDPOINTS = {"main.central_ti", "main.central_ti_salvar"}


def _require_access():
    if not current_app.config.get("CENTRAL_TI_ENABLED", False):
        abort(404)
    if not can_manage_central_ti(current_user):
        abort(403)


def _csrf_token():
    user_id = str(current_user.id)
    stored = session.get(CSRF_SESSION_KEY)
    if not isinstance(stored, dict) or stored.get("user") != user_id or not stored.get("token"):
        stored = {"user": user_id, "token": secrets.token_urlsafe(32)}
        session[CSRF_SESSION_KEY] = stored
    return stored["token"]


def _valid_csrf():
    stored = session.get(CSRF_SESSION_KEY)
    supplied = request.headers.get("X-Central-TI-CSRF", "")
    return (
        isinstance(stored, dict) and stored.get("user") == str(current_user.id)
        and isinstance(stored.get("token"), str) and bool(supplied)
        and secrets.compare_digest(stored["token"].encode("utf-8"), supplied.encode("utf-8"))
    )


def register_routes(bp):
    @bp.before_request
    def restrict_ti_manager_to_central():
        # Only the new TI profile is restricted here; existing profiles are unchanged.
        if (
            current_user.is_authenticated
            and normalize_role(getattr(current_user, "tipo_usuario", None)) == "gestor_ti"
            and active_configuration(current_user) is None
            and request.endpoint not in CENTRAL_ENDPOINTS
        ):
            abort(403)

    @bp.app_context_processor
    def inject_central_ti_access():
        return {"can_manage_central_ti": can_manage_central_ti}

    @bp.after_request
    def prevent_configuration_cache(response):
        if request.endpoint in CENTRAL_ENDPOINTS:
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.get("/central-ti", endpoint="central_ti")
    @login_required
    def central_ti():
        _require_access()
        try:
            data = build_editor_data()
        except SQLAlchemyError:
            current_app.logger.exception("Central de TI: falha ao carregar configurações.")
            return "Central de TI indisponível. Verifique a migração no ambiente autorizado.", 503
        data.update(save_url=url_for("main.central_ti_salvar"), csrf_token=_csrf_token(),
                    active=enforcement_enabled())
        return render_template("gestao_ti_central.html", central_ti_data=data)

    @bp.post("/central-ti/configuracoes", endpoint="central_ti_salvar")
    @login_required
    def central_ti_salvar():
        _require_access()
        # Always protected, even when global CSRF protection is not enabled yet.
        if not _valid_csrf():
            return jsonify(error="Recarregue a central e tente novamente.", code="csrf_invalid"), 403
        if not request.is_json:
            return jsonify(error="Envie a configuração em JSON."), 415
        if request.content_length is not None and request.content_length > MAX_PAYLOAD_BYTES:
            return jsonify(error="Configuração maior que o limite permitido."), 413
        raw = request.stream.read(MAX_PAYLOAD_BYTES + 1)
        if len(raw) > MAX_PAYLOAD_BYTES:
            return jsonify(error="Configuração maior que o limite permitido."), 413
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            return jsonify(error="Formato JSON inválido."), 400
        try:
            profiles = save_configurations(current_user, payload)
        except ConfigurationConflict as exc:
            return jsonify(error=str(exc), code="configuration_conflict"), 409
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except SQLAlchemyError:
            current_app.logger.exception("Central de TI: falha ao salvar configurações.")
            return jsonify(error="Não foi possível salvar. Tente novamente em instantes."), 503
        invalidate_request_permissions()
        return jsonify(ok=True, profiles=profiles, active_rules_changed=enforcement_enabled())
