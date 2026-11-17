"""A mesma política vale para a biblioteca e para cada download.

As permissões da Central de TI prevalecem sobre os guards legados, como nos
módulos de negócio. O catálogo não concede acesso a telas nem a registros.
"""
from dataclasses import dataclass

from flask import current_app

from app.modules.gestao_ti.permissions import (
    active_configuration, any_permission, has_permission, profile_code,
)


@dataclass(frozen=True)
class MaterialPolicy:
    area: str
    permissions: tuple[str, ...] = ()
    legacy: str = ""
    all_required: bool = False
    flag: str = ""


def _legacy(user, name):
    from app.shared.access import (
        is_admin_global_user, is_agro_finance_user, is_covisa_user,
        is_dev_user, is_prefeitura_admin_user, is_veiculos_supervisor,
    )
    role = profile_code(user)
    if name == "dev":
        return is_dev_user(user)
    if name == "maps":
        return not is_agro_finance_user(user) and role not in {"piloto_agro", "gestor_ti", "ortomosaico"}
    if name == "uvis_teams":
        return role == "uvis" or is_admin_global_user(user)
    if name in {"checklists", "vehicle_operation"}:
        return role in {"piloto", "equipe_oceano"} or is_veiculos_supervisor(user) or is_admin_global_user(user)
    if name == "tracking":
        from app.modules.veiculos.service import VEICULOS_ALLOWED_TYPES
        return (getattr(user, "tipo_usuario", "") or "").lower() in VEICULOS_ALLOWED_TYPES
    if name == "stock":
        return role in {"dev", "diretor", "manutencao"}
    if name == "maintenance":
        return role in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin", "manutencao"} or is_veiculos_supervisor(user)
    if name == "users":
        return is_admin_global_user(user)
    if name == "bugs":
        from app.modules.feedback.service import can_open_support_ticket
        return is_dev_user(user) or can_open_support_ticket(user)
    if name == "operational":
        from app.modules.painel_operacional.service import can_access_operational_panel
        return can_access_operational_panel(user)
    if name == "agro":
        from app.modules.agro.service import can_access_agro_panel
        return can_access_agro_panel(user)
    if name == "talents":
        from app.shared.access import ADMIN_PANEL_VIEW_TYPES, normalize_role
        return normalize_role(user.tipo_usuario) in ADMIN_PANEL_VIEW_TYPES
    if name == "finance":
        from app.shared.access import can_access_financeiro_panel
        return can_access_financeiro_panel(user)
    if name == "reports":
        from app.modules.relatorios.service import can_access_relatorios_menu
        return can_access_relatorios_menu(user)
    if name == "coordination":
        from app.modules.vigilancia.access import can_coordinate_field
        return can_coordinate_field(user)
    if name == "publications":
        from app.modules.acoes_publicas.service import allowed
        return allowed()
    if name == "complaints":
        from app.modules.denuncias.service import can_access_denuncias
        return can_access_denuncias(user)
    if name == "health":
        from app.modules.relatos_saude.service import allowed
        return allowed(user)
    if name == "settings":
        from app.modules.configuracoes.service import can_access_settings
        return can_access_settings(user)
    if name == "editing":
        from app.modules.admin_dashboard.service import can_edit_admin_panel
        return can_edit_admin_panel(user) or role in {"uvis", "piloto", "equipe_oceano", "equipe_uvis"}
    if name == "integrated":
        return _legacy(user, "coordination") and _legacy(user, "publications")
    return False


VIGILANCE = MaterialPolicy("prefeitura", ("prefeitura.vigilancia.consultar",), "coordination", flag="VIGILANCIA_IMPORT_ENABLED")
SINAN = MaterialPolicy("prefeitura", ("prefeitura.vigilancia.consultar",), "coordination", flag="SINAN_ENABLED")
PUBLICATIONS = MaterialPolicy("prefeitura", ("prefeitura.acoes_publicas.consultar",), "publications", flag="ACOES_PUBLICAS_ENABLED")
INTEGRATED = MaterialPolicy("prefeitura", ("prefeitura.vigilancia.consultar", "prefeitura.acoes_publicas.consultar"), "integrated", all_required=True)
POLICIES = {
    "guia-geral": MaterialPolicy("prefeitura", ("sistema.tecnico.consultar", "sistema.usuarios.consultar", "prefeitura.vigilancia.consultar"), "dev", all_required=True),
    "manual-liraa": VIGILANCE, "manual-mapa": VIGILANCE, "manual-sinan": SINAN,
    "manual-publicacoes": PUBLICATIONS,
    "csv-territorio": VIGILANCE, "csv-amostra": VIGILANCE, "csv-visitas": VIGILANCE,
    "csv-sp-territorio": VIGILANCE, "csv-sp-amostra": VIGILANCE, "csv-sp-visitas": VIGILANCE,
    "csv-sinan": SINAN, "csv-sp-sinan": SINAN,
    "imagem-acao": PUBLICATIONS, "texto-acao": PUBLICATIONS,
    "kit-testes": INTEGRATED, "kit-testes-sp": INTEGRATED, "kit-instrucoes-sp": INTEGRATED,
    "atualizacoes-liraa-mapas": VIGILANCE,
    "atualizacoes-acoes-publicas": PUBLICATIONS,
    "atualizacoes-treinamentos": MaterialPolicy("common"),
    "guia-triagem-denuncias": MaterialPolicy("prefeitura", ("prefeitura.denuncias.consultar",), "complaints"),
    "guia-suspeitas-adoecimento": MaterialPolicy("prefeitura", ("prefeitura.relatos_saude.consultar",), "health"),
    "guia-assistente-cidadao": MaterialPolicy("prefeitura", ("prefeitura.denuncias.consultar",), "complaints"),
    "guia-contatos-municipais": MaterialPolicy("prefeitura", ("prefeitura.documentos.consultar",), "settings"),
    "guia-consultas-personalizadas": MaterialPolicy("prefeitura", ("prefeitura.relatorios.consultar",), "reports"),
    "guia-documentos-prefeitura": MaterialPolicy("prefeitura", ("prefeitura.documentos.consultar",), "settings"),
    "guia-protecao-login": MaterialPolicy("common"),
    "guia-expiracao-senhas": MaterialPolicy("common"),
    "guia-edicao-protegida": MaterialPolicy("prefeitura", ("prefeitura.solicitacoes.editar", "prefeitura.os.editar", "prefeitura.denuncias.encaminhar", "prefeitura.denuncias.atribuir", "prefeitura.denuncias.converter"), "editing"),
    "guia-novas-funcionalidades": INTEGRATED,
    "guia-sinan-implementacao": SINAN,
    "guia-liraa-iip-risco": VIGILANCE,
    "guia-liraa-csv-manual": VIGILANCE,
    "guia-atualizacoes-vigilancia": INTEGRATED,
    "guia-agenda-notificacoes": MaterialPolicy("prefeitura", ("prefeitura.mapas.consultar",), "maps"),
    "guia-equipes-acesso-uvis": MaterialPolicy("prefeitura", ("prefeitura.equipes.criar",), "uvis_teams"),
    "guia-checklists-semanais": MaterialPolicy("prefeitura", ("prefeitura.checklists.editar",), "checklists"),
    "guia-frota-turnos": MaterialPolicy("prefeitura", ("prefeitura.veiculos.operar",), "vehicle_operation"),
    "guia-rastreamento-veiculos": MaterialPolicy("prefeitura", ("prefeitura.veiculos.consultar",), "tracking"),
    "guia-estoque-pecas": MaterialPolicy("prefeitura", ("sistema.estoque.consultar",), "stock"),
    "guia-manutencao-equipamentos": MaterialPolicy("prefeitura", ("prefeitura.equipamentos.editar",), "maintenance"),
    "guia-central-ti-permissoes": MaterialPolicy("prefeitura", legacy="central_ti"),
    "guia-reporte-acompanhamento-bugs": MaterialPolicy("prefeitura", ("sistema.bugs.criar", "sistema.bugs.atender"), "bugs"),
    "guia-painel-operacional": MaterialPolicy("prefeitura", ("sistema.operacional.consultar",), "operational"),
    "guia-usuarios-prefeituras": MaterialPolicy("prefeitura", ("sistema.usuarios.consultar",), "users"),
    "guia-relatorios-operacionais": MaterialPolicy("prefeitura", ("prefeitura.relatorios.consultar",), "reports"),
    "guia-mapas-operacionais": MaterialPolicy("prefeitura", ("prefeitura.mapas.consultar",), "maps"),
    "guia-agro-comercial-operacao": MaterialPolicy("agro", ("agro.comercial.consultar", "agro.contratos.consultar", "agro.os.consultar"), "agro", all_required=True),
    "guia-banco-talentos-agro": MaterialPolicy("agro", ("agro.talentos.consultar",), "talents"),
    "guia-central-financeiro": MaterialPolicy("financeiro", ("area:financeiro",), "finance"),
    "guia-ortomosaicos": MaterialPolicy("prefeitura", legacy="orthomosaics"),
}


def can_read_material(user, material_id):
    policy = POLICIES.get(material_id)
    if policy is None or not getattr(user, "is_authenticated", False):
        return False
    if policy.area == "common":
        return True
    role = profile_code(user)
    if role == "agente_endemias":
        # Os tutoriais atuais de vigilância ensinam planejamento/importação,
        # não apenas o formulário de visita autorizado ao agente.
        return False
    if policy.legacy == "orthomosaics":
        from app.modules.ortomosaicos.access import ORTHOMOSAIC_ROLES, is_orthomosaic_user
        return role in ORTHOMOSAIC_ROLES and (not is_orthomosaic_user(user) or bool(
            getattr(user, "prefeitura_id", None) and getattr(getattr(user, "prefeitura", None), "ativa", False)))
    if role == "ortomosaico":
        return False
    if policy.legacy == "central_ti":
        from app.modules.gestao_ti.service import can_manage_central_ti
        return can_manage_central_ti(user)
    if policy.area == "agro":
        from app.modules.agro.service import can_access_agro_panel
        if not can_access_agro_panel(user):
            return False
    if policy.area == "financeiro":
        from app.shared.access import can_access_financeiro_panel
        if not can_access_financeiro_panel(user):
            return False
    if policy.flag and not current_app.config.get(policy.flag, policy.flag == "SINAN_ENABLED"):
        return False
    if policy is INTEGRATED and not all(current_app.config.get(flag, flag == "SINAN_ENABLED") for flag in (
            "VIGILANCIA_IMPORT_ENABLED", "SINAN_ENABLED", "ACOES_PUBLICAS_ENABLED")):
        return False
    if active_configuration(user) is None:
        return _legacy(user, policy.legacy)
    if policy.all_required:
        return all(has_permission(user, code) for code in policy.permissions)
    return any_permission(user, policy.permissions)
