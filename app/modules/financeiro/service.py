"""Authorized company catalog with persisted identity and branding overrides.

Explicit company registration includes independent identity, fiscal data and branding.
Financial records remain restricted to the legacy IJA workspace.
"""

from app.modules.agro.service import can_access_agro_finance_panel
from app.shared.access import can_access_financeiro_panel, can_manage_financeiro_settings
from app.shared.formatters import format_documento
from app.models import FinanceiroEmpresaPerfil


FINANCEIRO_MENU = (
    ("Painel financeiro", "bi-bar-chart", "agro_financeiro_dashboard", {}, False),
    ("Contas", "bi-wallet2", "agro_financeiro_contas", {}, False),
    ("Relatório Geral", "bi-clipboard-data", "agro_relatorio_contas_geral", {}, False),
    ("Comprovantes", "bi-receipt-cutoff", "agro_contratos_comprovantes", {}, False),
    ("Caixa Diário", "bi-journal-text", "agro_caixa_diario", {}, False),
    ("Recebíveis", "bi-receipt", "agro_contas_receber_listar", {"origem": "recebivel"}, False),
    ("Contas a Receber", "bi-cash-stack", "agro_contas_receber_listar", {}, False),
    ("Nova Entrada Manual", "bi-plus-circle", "agro_financeiro_entrada_novo", {}, False),
    ("Contas a Pagar", "bi-credit-card-2-front", "agro_contas_pagar_listar", {}, False),
    ("Nova Saída Manual", "bi-plus-circle", "agro_financeiro_saida_novo", {}, False),
    ("Bancos", "bi-bank", "agro_bancos_listar", {}, False),
    ("Conciliação Bancária", "bi-bank2", "agro_bancos_conciliacao", {}, False),
    ("Configurações", "bi-sliders", "agro_financeiro_configuracoes", {}, True),
    ("Categorias", "bi-tags", "agro_financeiro_categorias_listar", {}, True),
)


def build_financeiro_empresas(user):
    can_open_ija = can_access_agro_finance_panel(user)
    cnpj = "11111111000111"
    empresas = [{
        "slug": "ija",
        "nome": "IJA",
        "sigla": "IJA",
        "razao_social": "IJA",
        "cnpj": cnpj,
        "cnpj_formatado": format_documento(cnpj),
        "operacao": "Agro",
        "disponivel": can_open_ija,
        "demonstracao": True,
    }]
    perfis = {perfil.empresa_slug: perfil for perfil in FinanceiroEmpresaPerfil.query.all()}
    for perfil in perfis.values():
        if perfil.empresa_slug != "ija" and perfil.cadastrada:
            empresas.append({
                "slug": perfil.empresa_slug, "nome": perfil.nome, "razao_social": perfil.razao_social,
                "cnpj": perfil.cnpj, "sigla": (perfil.nome or "")[:3].upper(),
                "cnpj_formatado": format_documento(perfil.cnpj), "operacao": "Cadastro da empresa",
                "disponivel": can_access_financeiro_panel(user), "demonstracao": False,
            })
    for empresa in empresas:
        perfil = perfis.get(empresa["slug"])
        empresa["tem_logo"] = bool(perfil and perfil.tem_logo)
        if perfil:
            for campo in ("nome", "razao_social", "cnpj"):
                if getattr(perfil, campo):
                    empresa[campo] = getattr(perfil, campo)
            empresa["cnpj_formatado"] = format_documento(empresa["cnpj"])
            empresa["demonstracao"] = not bool(perfil.cnpj)
            empresa["sigla"] = empresa["nome"][:3].upper()
    return empresas


def build_financeiro_menu(user, empresa):
    from app.modules.gestao_ti.permissions import active_configuration, can_access_endpoint
    # Existing Agro records are available only through IJA until company storage
    # and data scopes have been modeled; another card must not expose these data.
    if not empresa or not empresa["disponivel"] or not can_access_financeiro_panel(user):
        return []
    settings = {"label": "Configurações", "icon": "bi-sliders",
                "endpoint": "main.financeiro_empresa_configuracoes", "params": {"empresa_slug": empresa["slug"]}}
    configured = active_configuration(user) is not None
    if empresa["slug"] != "ija":
        allowed = (can_access_endpoint(user, settings["endpoint"], args=settings["params"])
                   if configured else can_manage_financeiro_settings(user))
        return [settings] if allowed else []
    consultas = [
        {"label": "Clientes e Fornecedores", "icon": "bi-people-fill", "endpoint": "main.financeiro_empresa_relacionamentos", "params": {"empresa_slug": empresa["slug"]},
         "collapse_id": "menuRelacionamentosFinanceiro",
         "active_endpoints": {"main.financeiro_empresa_relacionamentos", "main.financeiro_empresa_clientes", "main.financeiro_empresa_fornecedores", "main.agro_fornecedores_listar", "main.agro_fornecedor_novo", "main.agro_fornecedor_editar"},
         "children": [{"label": label, "icon": icon, "endpoint": "main.financeiro_empresa_" + area, "params": {"empresa_slug": empresa["slug"]}}
                      for area, label, icon in (("relacionamentos", "Visão Geral", "bi-grid-1x2-fill"), ("clientes", "Clientes", "bi-people-fill"), ("fornecedores", "Fornecedores", "bi-buildings-fill"))]},
        {"label": "Comercial", "icon": "bi-briefcase", "endpoint": "main.financeiro_empresa_comercial", "params": {"empresa_slug": empresa["slug"]},
         "collapse_id": "menuComercialFinanceiro", "active_endpoints": {"main.financeiro_empresa_comercial"},
         "children": [{"label": label, "icon": icon, "endpoint": "main.financeiro_empresa_comercial", "params": {"empresa_slug": empresa["slug"], "aba": aba}}
                      for aba, label, icon in (("orcamentos", "Orçamentos", "bi-file-earmark-text-fill"), ("mapeamentos", "Mapeamentos", "bi-map-fill"), ("contratos", "Contratos", "bi-file-earmark-text-fill"))]},
    ]
    menu = consultas + [{"label": label, "icon": icon, "endpoint": "main." + endpoint, "params": dict(params)}
                       for label, icon, endpoint, params, admin_only in FINANCEIRO_MENU
                       if configured or not admin_only or can_manage_financeiro_settings(user)]
    menu = [settings if item["endpoint"] == "main.agro_financeiro_configuracoes" else item for item in menu]
    if not configured:
        return menu
    visible = []
    for item in menu:
        if "children" in item:
            item["children"] = [child for child in item["children"]
                                if can_access_endpoint(user, child["endpoint"], args=child["params"])]
            if not item["children"]:
                continue
        elif not can_access_endpoint(user, item["endpoint"], args=item["params"]):
            continue
        visible.append(item)
    return visible
