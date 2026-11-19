"""Retirada reversível de módulos da interface, sem alterar dados ou permissões."""

from copy import deepcopy

from flask import abort, current_app, request


VIGILANCIA_MODULES = frozenset({
    "prefeitura.vigilancia", "prefeitura.acoes_publicas", "prefeitura.relatos_saude",
})

# Apenas telas HTML. APIs, serviços, modelos e exportações continuam registrados.
VIGILANCIA_SCREENS = frozenset("main." + name for name in (
    "vigilancia", "vigilancia_sinan", "vigilancia_validacao", "vigilancia_importacoes",
    "vigilancia_campo", "vigilancia_risco", "vigilancia_resultados", "vigilancia_excluir",
    "vigilancia_planejamento", "vigilancia_migracao", "vigilancia_agente",
    "vigilancia_agentes", "vigilancia_pendentes", "alertas", "alertas_telegram",
    "integracoes_esus", "integracoes_esus_config", "acoes_listar", "acoes_nova",
    "acoes_editar", "acoes_previa", "portal_acoes", "portal_acao",
    "portal_relato_saude", "portal_relato_saude_recibo", "relatos_saude_listar",
    "relatos_saude_detalhe",
))


def vigilancia_ui_enabled():
    return bool(current_app.config.get("VIGILANCIA_UI_ENABLED", False))


def interface_endpoint_visible(endpoint):
    return vigilancia_ui_enabled() or endpoint not in VIGILANCIA_SCREENS


def interface_module_visible(module):
    return vigilancia_ui_enabled() or module not in VIGILANCIA_MODULES


def interface_permission_catalog(data):
    """Filtra a apresentação; preserva as seleções existentes ao salvar outro módulo."""
    if vigilancia_ui_enabled():
        return data
    visible = deepcopy(data)
    for area in visible["catalog"]:
        area["modules"] = [module for module in area["modules"]
                           if interface_module_visible(f"{area['id']}.{module[0]}")]
    visible["profiles"] = [profile for profile in visible["profiles"]
                           if profile["id"] != "agente_endemias"]
    return visible


def register_interface_visibility(bp):
    from app.shared.municipality_visibility import register_municipality_filters
    register_municipality_filters(bp)

    @bp.before_app_request
    def hide_archived_municipality_details():
        fields = {
            "main.admin_prefeitura_editar": "id",
            "main.configuracoes_documentos": "prefeitura_id",
            "main.configuracoes_contatos": "prefeitura_id",
            "main.configuracoes_email": "prefeitura_id",
        }
        field = fields.get(request.endpoint)
        if field:
            from flask_login import current_user
            if not current_user.is_authenticated:
                return
            from app.extensions import db
            from app.models import Prefeitura
            from app.shared.municipality_visibility import municipality_visible
            city = db.session.get(Prefeitura, request.view_args.get(field))
            if city is not None and not municipality_visible(city):
                abort(404)

    @bp.before_app_request
    def hide_retired_screens():
        if vigilancia_ui_enabled():
            return
        if not interface_endpoint_visible(request.endpoint):
            abort(404)

    @bp.app_context_processor
    def interface_context():
        return {
            "vigilancia_ui_enabled": vigilancia_ui_enabled(),
            "interface_permission_catalog": interface_permission_catalog,
        }
