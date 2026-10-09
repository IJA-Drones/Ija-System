"""Existing financial endpoints, kept stable while their navigation moves."""

FINANCEIRO_LEGACY_PREFIXES = (
    "main.agro_financeiro_", "main.agro_banco_", "main.agro_bancos_",
    "main.agro_caixa_", "main.agro_contas_receber_", "main.agro_contas_pagar_",
    "main.agro_relatorio_contas_geral",
)
FINANCEIRO_LEGACY_ENDPOINTS = {
    "main.agro_contratos_comprovantes", "main.agro_fluxo_caixa_exportar_excel",
}


def is_financeiro_legacy_endpoint(endpoint):
    endpoint = endpoint or ""
    return endpoint in FINANCEIRO_LEGACY_ENDPOINTS or endpoint.startswith(FINANCEIRO_LEGACY_PREFIXES)


def is_financeiro_endpoint(endpoint):
    return (endpoint or "").startswith("main.financeiro_") or is_financeiro_legacy_endpoint(endpoint)


def is_financeiro_settings_endpoint(endpoint):
    return (endpoint or "").startswith(("main.agro_financeiro_configuracoes", "main.agro_financeiro_categoria"))
