"""Fixed, municipality-scoped access for the dedicated mapping account."""
from flask import abort, request
from flask_login import current_user

from app.shared.access import normalize_role

ORTHOMOSAIC_USER_TYPE = "ortomosaico"
ORTHOMOSAIC_ROLES = {"dev", "diretor", ORTHOMOSAIC_USER_TYPE}
ORTHOMOSAIC_ENDPOINTS = {
    "main.ortomosaicos", "main.ortomosaicos_listar",
    "main.ortomosaico_upload", "main.ortomosaico_transfer_start", "main.ortomosaico_transfer",
    "main.ortomosaico_status", "main.ortomosaico_retry", "main.ortomosaico_arquivo",
    "main.ortomosaico_original", "main.ortomosaico_curvas", "main.ortomosaico_jpeg",
    "main.ortomosaico_exportar", "main.ortomosaico_agua_calcular",
    "main.ortomosaico_areas", "main.ortomosaico_area_item", "main.ortomosaico_area_calcular",
    "main.ortomosaico_agua", "main.ortomosaico_agua_item",
}


def is_orthomosaic_user(user):
    return normalize_role(getattr(user, "tipo_usuario", "")) == ORTHOMOSAIC_USER_TYPE


def dedicated_endpoint_allowed(endpoint):
    return bool(endpoint and (
        endpoint in ORTHOMOSAIC_ENDPOINTS
        or endpoint in {"static", "main.inicio", "main.acessos_dashboard", "main.serve_sw",
                       "main.service_worker",
                       "main.login", "main.logout", "main.treinamentos", "main.treinamentos_arquivo"}
        or endpoint.startswith(("auth.", "session_security."))
    ))


def register_dedicated_security(bp):
    @bp.before_app_request
    def enforce_mapping_account():
        # Independent of Central TI configuration and of individual view decorators.
        if (current_user.is_authenticated and is_orthomosaic_user(current_user)
                and request.endpoint and not dedicated_endpoint_allowed(request.endpoint)):
            abort(403, description="Este perfil acessa somente ortomosaicos e curvas de nível.")
