"""Company catalog for the finance hub, initially with one demo entry.

The hub and workspace consume a list of companies. Registration and persisted
company permissions will be added after the finance area is validated.
"""

from app.modules.agro.service import can_access_agro_finance_panel
from app.shared.access import can_access_financeiro_panel, can_manage_financeiro_settings
from app.shared.formatters import format_documento


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
    return [{
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


def build_financeiro_menu(user, empresa):
    # Existing Agro records are available only through IJA until company storage
    # and data scopes have been modeled; another card must not expose these data.
    if not empresa or empresa["slug"] != "ija" or not empresa["disponivel"] or not can_access_financeiro_panel(user):
        return []
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
    return consultas + [{"label": label, "icon": icon, "endpoint": "main." + endpoint, "params": dict(params)}
                       for label, icon, endpoint, params, admin_only in FINANCEIRO_MENU
                       if not admin_only or can_manage_financeiro_settings(user)]
