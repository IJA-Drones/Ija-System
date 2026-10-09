"""Read-only presentation of existing role capabilities in the editor's catalog.

This is not an authorization engine. Record scopes and business validations stay
in their original services. Agro is shown as a conditional capability of a role,
with the existing work flag explicitly identified in the UI. COVISA represents
the normal account form (visualizar + regiao COVISA), not its legacy literal.
"""

from types import SimpleNamespace

from app.modules.admin_dashboard.service import can_access_admin_panel, can_edit_admin_panel
from app.modules.agro.service import can_access_agro_panel, can_edit_agro_panel
from app.modules.agro.flight_logs_service import can_access_agro_flight_logs, can_import_agro_flight_logs
from app.modules.agenda_notificacoes.service import can_export_agenda
from app.modules.denuncias.service import can_access_denuncias
from app.modules.dji_flight_logs.service import can_access_dji_logs, can_import_dji_logs
from app.modules.feedback.service import can_access_feedback, can_open_support_ticket
from app.modules.gestao_ti.catalog import PERMISSION_CODES, PROFILE_CODES
from app.modules.painel_operacional.service import can_access_operational_panel
from app.modules.relatorios.service import can_access_relatorios_menu, can_access_relatorio_coleta_imagens
from app.shared.access import (
    GLOBAL_ADMIN_USER_TYPES, VEICULOS_SUPERVISOR_USER_TYPES,
    can_access_financeiro_panel, can_manage_financeiro_settings,
    is_admin_global_user, is_covisa_user, is_prefeitura_admin_user,
)


# Explicit lists in pilotos/equipes/equipamentos, veiculos, solicitacoes and
# drones_import/routes.py. These differ from the shared dashboard lists.
MANAGEMENT_ROLES = GLOBAL_ADMIN_USER_TYPES | {"operario", "operador", "prefeitura_admin"} | VEICULOS_SUPERVISOR_USER_TYPES
VEHICLE_MANAGEMENT_ROLES = GLOBAL_ADMIN_USER_TYPES | {"operario", "operador", "prefeitura_admin", "sup_veiculos"}
DRONE_IMPORT_ROLES = GLOBAL_ADMIN_USER_TYPES | {"operario", "operador", "prefeitura_admin"}
REQUEST_CREATE_ROLES = {"uvis", "dev", "diretor", "admin", "visualizar", "prefeitura_admin", "sup_veiculos", "sup_veiculo"}
OPERATIONAL_ROLES = {"piloto", "equipe_oceano"}


def current_rules(profile_code):
    if profile_code not in PROFILE_CODES:
        raise ValueError("Perfil desconhecido.")
    role = "visualizar" if profile_code == "covisa" else profile_code
    user = SimpleNamespace(tipo_usuario=role, regiao="COVISA" if profile_code == "covisa" else "",
                           trabalha_agro=True, suporte_operacional=False, suporte_tecnico=False)
    permissions = set()
    notes = {}

    def allow(module, actions):
        actions = actions.split()
        if actions:
            permissions.add(f"{module}.consultar")
        permissions.update(f"{module}.{action}" for action in actions)

    # gestor_ti is restricted by the main blueprint to the Central TI only.
    if role == "gestor_ti":
        allow("sistema.perfis", "consultar configurar")
    else:
        administrative = can_access_admin_panel(user)
        editable = can_edit_admin_panel(user)
        operational = role in OPERATIONAL_ROLES
        operational_os = operational or role in VEICULOS_SUPERVISOR_USER_TYPES
        if administrative or role in {"uvis", "equipe_uvis"}:
            allow("prefeitura.solicitacoes", "consultar")
        if role in REQUEST_CREATE_ROLES:
            allow("prefeitura.solicitacoes", "criar")
        if editable:
            allow("prefeitura.solicitacoes", "editar aprovar cancelar")
        if role == "uvis":
            allow("prefeitura.solicitacoes", "editar cancelar")
        if is_admin_global_user(user):
            allow("prefeitura.solicitacoes", "excluir")
        if administrative:
            allow("prefeitura.solicitacoes", "exportar")

        if administrative or operational or role in {"uvis", "equipe_uvis"}:
            allow("prefeitura.os", "consultar")
        if editable or operational or role == "uvis":
            allow("prefeitura.os", "editar")
        if operational_os or role == "equipe_uvis":
            allow("prefeitura.os", "concluir")
        if operational_os or editable:
            allow("prefeitura.os", "midias")
        if administrative:
            allow("prefeitura.os", "exportar")

        if administrative:
            allow("prefeitura.clientes", "consultar")
        if is_admin_global_user(user) or is_prefeitura_admin_user(user):
            allow("prefeitura.clientes", "criar editar excluir exportar")
        if role in MANAGEMENT_ROLES:
            allow("prefeitura.equipes", "consultar criar editar excluir")
            allow("prefeitura.equipamentos", "consultar criar editar excluir")
        elif role in {"regional", "visualizar", "uvis"}:
            allow("prefeitura.equipes", "consultar")
        if editable or role == "uvis":
            allow("prefeitura.equipes", "atribuir")
        if role == "uvis":
            allow("prefeitura.equipes", "criar editar excluir")
        if operational:
            allow("prefeitura.equipamentos", "consultar")
        if role in DRONE_IMPORT_ROLES:
            allow("prefeitura.equipamentos", "importar")

        if role in VEHICLE_MANAGEMENT_ROLES:
            allow("prefeitura.veiculos", "consultar criar editar excluir corrigir exportar")
        elif operational or role == "visualizar":
            allow("prefeitura.veiculos", "consultar")
        if operational or role == "sup_veiculos":
            allow("prefeitura.veiculos", "operar")
        if is_admin_global_user(user) or role in VEICULOS_SUPERVISOR_USER_TYPES:
            allow("prefeitura.checklists", "consultar editar corrigir")
        elif operational:
            allow("prefeitura.checklists", "consultar editar")
        if can_access_relatorios_menu(user) or can_access_relatorio_coleta_imagens(user):
            allow("prefeitura.relatorios", "consultar exportar")
        if administrative or operational or role in {"uvis", "equipe_uvis", "operador"}:
            allow("prefeitura.mapas", "consultar")
            if can_export_agenda(user):
                allow("prefeitura.mapas", "exportar")
        if can_access_denuncias(user):
            allow("prefeitura.denuncias", "consultar")
            if is_admin_global_user(user) or is_covisa_user(user):
                allow("prefeitura.denuncias", "encaminhar")
            elif role == "regional":
                allow("prefeitura.denuncias", "atribuir")

        if can_access_agro_panel(user):
            for module in ("clientes", "comercial", "mapeamentos", "os", "equipes", "equipamentos"):
                allow(f"agro.{module}", "consultar")
            allow("agro.comercial", "exportar")
            if can_edit_agro_panel(user):
                for module in ("clientes", "comercial", "equipes", "equipamentos"):
                    allow(f"agro.{module}", "criar editar excluir")
                allow("agro.mapeamentos", "editar concluir")
                allow("agro.os", "editar exportar")
                if role in DRONE_IMPORT_ROLES:
                    allow("agro.equipamentos", "importar")
            if is_admin_global_user(user):
                allow("agro.mapeamentos", "configurar")
                allow("agro.os", "excluir")
            if role != "admin":
                notes["agro"] = "Depende da habilitação Trabalha no Agro no cadastro do usuário."
        if can_access_agro_flight_logs(user):
            allow("agro.voos", "consultar exportar")
        if can_import_agro_flight_logs(user):
            allow("agro.voos", "importar editar")
        if administrative:
            allow("agro.talentos", "consultar")
            if can_edit_agro_panel(user):
                allow("agro.talentos", "criar editar excluir")
        if role == "piloto_agro":
            allow("agro.equipamentos", "consultar")
            allow("agro.mapeamentos", "consultar editar concluir")
            allow("agro.os", "consultar criar editar concluir")
            notes["agro"] = "Piloto ativo e vínculo com a equipe Agro; somente registros da equipe."

        if can_access_financeiro_panel(user):
            allow("financeiro.contas", "consultar criar editar excluir operar")
            allow("financeiro.caixa", "consultar operar")
            allow("financeiro.bancos", "consultar criar editar excluir operar")
            allow("financeiro.comprovantes", "consultar midias")
            allow("financeiro.relacionamentos", "consultar criar editar excluir")
            allow("financeiro.comercial", "consultar exportar")
            allow("financeiro.relatorios", "consultar exportar")
            if can_manage_financeiro_settings(user):
                allow("financeiro.configuracoes", "consultar configurar")
            notes["financeiro"] = "Empresa autorizada, caixa e competência continuam sendo validados."

        if is_admin_global_user(user):
            allow("sistema.usuarios", "consultar criar editar excluir")
        if role == "dev":
            allow("sistema.usuarios", "gerenciar")
            allow("sistema.perfis", "consultar configurar")
            allow("sistema.auditoria", "consultar exportar")
            allow("sistema.tecnico", "consultar operar importar")
        if can_access_feedback(user):
            allow("sistema.suporte", "consultar")
        if can_open_support_ticket(user):
            allow("sistema.suporte", "criar")
        if role == "dev":
            allow("sistema.suporte", "atender")
        if role in {"dev", "diretor"}:
            allow("sistema.estoque", "consultar criar editar excluir exportar")
        if can_access_operational_panel(user):
            allow("sistema.operacional", "consultar")
        if can_access_dji_logs(user):
            allow("sistema.tecnico", "consultar")
        if can_import_dji_logs(user):
            allow("sistema.tecnico", "importar")

    if not permissions <= PERMISSION_CODES:
        raise ValueError("Mapeamento atual contém opções ausentes no catálogo.")
    if role not in GLOBAL_ADMIN_USER_TYPES and any(code.startswith("prefeitura.") for code in permissions):
        notes["prefeitura"] = "O alcance depende de prefeitura, região, equipe e das regras de cada tela."
    return {"areas": sorted({code.split(".")[0] for code in permissions}),
            "permissions": sorted(permissions), "notes": notes}
