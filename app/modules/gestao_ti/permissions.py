"""Role capabilities only. This module never changes the user's identity or scope.

The existing guards remain the default until a profile is explicitly saved.
Selections are loaded once per request, without a process-wide authorization cache.
"""

import json
from fnmatch import fnmatchcase
from functools import wraps
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from flask import abort, current_app, g, has_app_context, has_request_context, request
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.extensions import db
from app.models import CentralTiAuditoria, CentralTiPerfilConfiguracao, CentralTiSelecao
from app.modules.gestao_ti.catalog import AREA_CODES, PERMISSION_CODES


POLICY = json.loads(Path(__file__).with_name("route_policy.json").read_text())
EXCLUSIONS = json.loads(Path(__file__).with_name("route_exclusions.json").read_text())
FIXED_ENDPOINTS = {"main.central_ti", "main.central_ti_salvar", "main.acessos_dashboard"}


def validate_route_policy(app):
    """New protected endpoints require an explicit, reviewable capability map."""
    for rule in app.url_map.iter_rules():
        endpoint = rule.endpoint
        if not endpoint.startswith("main.") or endpoint in EXCLUSIONS or endpoint in FIXED_ENDPOINTS:
            continue
        policy = POLICY.get(endpoint, {})
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            if method not in policy:
                raise ValueError(f"Central de TI: rota sem permissão definida: {endpoint} {method}")
            options = policy[method] if isinstance(policy[method], list) else [policy[method]]
            for code in options:
                valid = code[5:] in AREA_CODES if code.startswith("area:") else code in PERMISSION_CODES
                if not valid:
                    raise ValueError(f"Central de TI: permissão inválida em {endpoint}: {code}")


def enforcement_enabled():
    return (has_app_context() and current_app.config.get("CENTRAL_TI_ENABLED", False)
            and current_app.config.get("CENTRAL_TI_ENFORCE_PERMISSIONS", False))


def profile_code(user):
    role = (getattr(user, "tipo_usuario", "") or "").strip().lower()
    if role == "visualizar" and (getattr(user, "regiao", "") or "").strip().upper() == "COVISA":
        return "covisa"
    return role


def active_configuration(user):
    if not enforcement_enabled() or not getattr(user, "is_authenticated", False):
        return None
    code = profile_code(user)
    cache = g.setdefault("_central_ti_permissions", {}) if has_request_context() else {}
    if code in cache:
        return cache[code]
    try:
        row = db.session.get(CentralTiPerfilConfiguracao, code)
        result = None
        if row is not None:
            codes = {
                item[0] for item in db.session.query(CentralTiSelecao.codigo).filter_by(perfil_codigo=code).all()
            }
            neutral = (row.versao == 1 and row.atualizado_por_id is None and not codes
                       and db.session.query(CentralTiAuditoria.id).filter_by(
                           perfil_codigo=code, usuario_login="inicializacao_neon", usuario_id=None,
                           versao_anterior=0, versao_nova=1,
                       ).first() is not None)
            if not neutral:
                result = frozenset(codes)
        cache[code] = result
        return result
    except SQLAlchemyError:
        db.session.rollback()
        # Error pages may render the shared layout. Deny its controls without
        # recursively querying the unavailable table or restoring legacy grants.
        cache[code] = frozenset()
        current_app.logger.exception("Central de TI: não foi possível verificar permissões.")
        abort(503, description="Não foi possível verificar seu acesso. Tente novamente.")


def has_permission(user, permission, legacy=False):
    choices = active_configuration(user)
    if choices is None:
        return bool(legacy)
    if permission.startswith("area:"):
        return permission in choices
    area, module, _ = permission.split(".")
    return (f"area:{area}" in choices and f"{area}.{module}.consultar" in choices
            and permission in choices)


def any_permission(user, permissions, legacy=False):
    if active_configuration(user) is None:
        return bool(legacy)
    return any(has_permission(user, code) for code in permissions)


def capability(patterns):
    """Adapt a pure capability helper; never decorate identity or record checks."""
    codes = tuple(code for code in PERMISSION_CODES
                  if any(fnmatchcase(code, pattern) for pattern in patterns))
    codes += tuple(pattern for pattern in patterns if pattern.startswith("area:"))

    def decorate(function):
        @wraps(function)
        def check(user, *args, **kwargs):
            if active_configuration(user) is None:
                return function(user, *args, **kwargs)
            # On a module's page, an edit helper must not borrow a write
            # permission from a different module to turn off read-only mode.
            applicable = codes
            if has_request_context():
                options = route_options(request.endpoint, request.method, request.args) or ()
                modules = {code.rsplit(".", 1)[0] for code in options if not code.startswith("area:")}
                matching = tuple(code for code in codes if code.rsplit(".", 1)[0] in modules)
                if matching:
                    applicable = matching
            return any_permission(user, applicable)
        return check
    return decorate


def route_options(endpoint, method="GET", args=None):
    policy = POLICY.get(endpoint)
    if not policy:
        return None
    method = "GET" if method == "HEAD" else method
    value = policy.get(method)
    if value is None:
        return ()
    options = value if isinstance(value, list) else [value]
    if method == "GET" and str((args or {}).get("export", "")).lower() in {"1", "true", "yes", "xlsx", "csv", "pdf"}:
        options = [code.rsplit(".", 1)[0] + ".exportar" for code in options]
    return tuple(options)


def can_access_endpoint(user, endpoint, method="GET", args=None, legacy=True):
    choices = active_configuration(user)
    if choices is None:
        return bool(legacy)
    if endpoint in {"main.central_ti", "main.central_ti_salvar"}:
        return profile_code(user) in {"dev", "gestor_ti"}
    if endpoint in FIXED_ENDPOINTS or endpoint in EXCLUSIONS or endpoint.startswith(("auth.", "session_security.")) or endpoint == "static":
        return True
    options = route_options(endpoint, method, args)
    return options is not None and any_permission(user, options)


def route_access(user, legacy):
    """Replace an existing capability guard, never an ownership/state guard."""
    if not has_request_context() or request.endpoint not in POLICY:
        return bool(legacy)
    return can_access_endpoint(user, request.endpoint, request.method, request.args, legacy=legacy)


def ui_url_allowed(user, url, method=None):
    if active_configuration(user) is None:
        return True
    parsed = urlsplit(str(url or ""))
    if parsed.netloc or not parsed.path.startswith("/"):
        return True
    adapter = current_app.url_map.bind_to_environ(request.environ)
    methods = [method] if method else ["GET", "POST", "PUT", "DELETE"]
    for candidate in methods:
        try:
            endpoint, _ = adapter.match(parsed.path, method=candidate)
        except HTTPException:
            continue
        args = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        return can_access_endpoint(user, endpoint, candidate, args)
    return False


def ui_guard(user, endpoints, legacy):
    if active_configuration(user) is None:
        return bool(legacy)
    return any(can_access_endpoint(user, endpoint, method)
               for endpoint in endpoints
               for method in (POLICY.get(endpoint) or {"GET": ""}))


def require_permission(user, code):
    if active_configuration(user) is not None and not has_permission(user, code):
        abort(403, description="Seu perfil não possui permissão para esta ação.")


def can_delegate_profile(actor, target_role):
    """A delegated account manager cannot create a more privileged account."""
    choices = active_configuration(actor)
    if choices is None or profile_code(actor) in {"dev", "diretor", "admin"}:
        return True
    if target_role in {"dev", "diretor", "admin", "gestor_ti"}:
        return False
    from types import SimpleNamespace
    from app.modules.gestao_ti.catalog import PROFILE_CODES
    from app.modules.gestao_ti.current_rules import current_rules
    if target_role not in PROFILE_CODES:
        return False
    target = active_configuration(SimpleNamespace(tipo_usuario=target_role, is_authenticated=True))
    if target is None:
        defaults = current_rules(target_role)
        target = set(defaults["permissions"]) | {"area:" + area for area in defaults["areas"]}
    return set(target) <= set(choices)


def can_manage_os_media(user, context):
    legacy = not context.get("modo_visualizacao", True)
    if active_configuration(user) is None:
        return legacy
    status = (getattr(context.get("solicitacao"), "status", "") or "").strip().upper()
    if status == "CANCELADO":
        return False
    if profile_code(user) in {"piloto", "equipe_oceano"} and status in {"CONCLUIDO", "CONCLUÍDO"}:
        return False
    return has_permission(user, "prefeitura.os.midias")


def invalidate_request_permissions():
    if has_request_context():
        g.pop("_central_ti_permissions", None)


def register_permission_security(bp):
    from flask import render_template
    from flask_login import login_required

    @bp.record_once
    def install_template_globals(state):
        from flask_login import current_user
        state.app.jinja_env.globals.update(
            central_ti_url_allowed=lambda url, method=None: ui_url_allowed(current_user, url, method),
            central_ti_permission=lambda code: has_permission(current_user, code),
            central_ti_ui_guard=lambda endpoints, legacy: ui_guard(current_user, endpoints, legacy),
            central_ti_media_allowed=lambda readonly, solicitation: can_manage_os_media(
                current_user, {"modo_visualizacao": readonly, "solicitacao": solicitation}),
        )

    @bp.before_request
    def enforce_capabilities():
        from flask_login import current_user
        invalidate_request_permissions()
        g.pop("_central_ti_team_ids", None)
        if not enforcement_enabled() or not current_user.is_authenticated:
            return
        if not can_access_endpoint(current_user, request.endpoint or "", request.method, request.args):
            abort(403, description="Seu perfil não possui permissão para esta função.")
        if request.method in {"POST", "PUT", "DELETE"} and request.endpoint in {
            "main.piloto_os_formulario_view", "main.admin_os_formulario_view",
            "main.uvis_os_formulario_view", "main.equipe_uvis_os_formulario_view", "main.atualizar",
        }:
            media_removal = any(request.form.get(key) in {"1", "true", "on"} for key in {
                "remover_imagem_principal", "remover_video", "limpar_outras_imagens",
            })
            if any(file.filename for file in request.files.values()) or media_removal:
                require_permission(current_user, "prefeitura.os.midias")

    @bp.get("/acessos", endpoint="acessos_dashboard")
    @login_required
    def access_home():
        return render_template("acessos_dashboard.html")

    @bp.after_request
    def expire_capability_cache(response):
        if enforcement_enabled():
            response.headers["Cache-Control"] = "private, no-store"
        invalidate_request_permissions()
        g.pop("_central_ti_team_ids", None)
        return response

    @bp.app_context_processor
    def inject_permissions():
        from flask_login import current_user
        from app.modules.gestao_ti.navigation import build_navigation
        from app.modules.usuarios.service import can_manage_admin_user
        active = active_configuration(current_user) is not None
        return {
            "central_ti_profile_active": active,
            "central_ti_navigation": build_navigation(current_user) if active else [],
            "central_ti_permission": lambda code: has_permission(current_user, code),
            "central_ti_url_allowed": lambda url, method=None: ui_url_allowed(current_user, url, method),
            "central_ti_ui_guard": lambda endpoints, legacy: ui_guard(current_user, endpoints, legacy),
            "central_ti_manage_account": lambda user: can_manage_admin_user(current_user, user),
        }
