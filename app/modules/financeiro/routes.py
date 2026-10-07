from flask import abort, current_app, g, render_template, request, url_for
from flask_login import current_user, login_required

from app.modules.financeiro.service import build_financeiro_empresas, build_financeiro_menu
from app.shared.access import can_access_financeiro_panel, can_manage_financeiro_settings, is_agro_finance_user
from app.shared.financeiro_navigation import is_financeiro_endpoint, is_financeiro_legacy_endpoint, is_financeiro_settings_endpoint


COMPANY_CONSULTATION_ENDPOINTS = {
    "relacionamentos": "main.agro_clientes_menu",
    "clientes": "main.agro_clientes_listar",
    "fornecedores": "main.agro_fornecedores_listar",
    "orcamentos": "main.agro_orcamentos_listar",
    "mapeamentos": "main.agro_orcamentos_template_mapeamento",
    "contratos": "main.agro_contratos_listar",
}
SHARED_FINANCE_ENDPOINTS = {
    "main.agro_contrato_comprovante_pagamento",
    "main.agro_contrato_comprovante_pagamento_upload",
    "main.agro_contrato_comprovante_pagamento_remover",
    "main.agro_contrato_pdf", "main.agro_orcamento_pdf", "main.agro_orcamento_anexo",
    "main.agro_fornecedores_listar", "main.agro_fornecedor_novo",
    "main.agro_fornecedor_editar", "main.agro_fornecedor_deletar",
}
PREFEITURA_MAP_ENDPOINTS = {
    "main.mapa_relatorio", "main.heatmap_data", "main.consultar_endereco_geolocalizacao",
}


def _require_financeiro_access():
    if not can_access_financeiro_panel(current_user):
        abort(403)


def _resolve_empresa(empresa_slug, *, existing_data=False):
    _require_financeiro_access()
    empresa = next((item for item in build_financeiro_empresas(current_user)
                    if item["slug"] == empresa_slug), None)
    if empresa is None:
        abort(404)
    if not empresa["disponivel"] or (existing_data and empresa["slug"] != "ija"):
        abort(403)
    return empresa


def _consulta_url(endpoint, **values):
    empresa = getattr(g, "financeiro_empresa", None)
    if empresa is None:
        return url_for(endpoint, **values)
    if endpoint == "main.admin_agro":
        return url_for("main.financeiro_empresa", empresa_slug=empresa["slug"])
    tipo = next((tipo for tipo, original in COMPANY_CONSULTATION_ENDPOINTS.items() if original == endpoint), None)
    if tipo is None:
        return url_for(endpoint, **values)
    params = {**values, "empresa_slug": empresa["slug"]}
    if tipo in {"relacionamentos", "clientes", "fornecedores"}:
        params.pop("aba", None)
        return url_for("main.financeiro_empresa_" + tipo, **params)
    params["aba"] = tipo
    return url_for("main.financeiro_empresa_comercial", **params)


def register_routes(bp):
    @bp.before_request
    def restrict_financial_users_to_finance():
        if not current_user.is_authenticated or not is_agro_finance_user(current_user):
            return None
        endpoint = request.endpoint or ""
        if endpoint in SHARED_FINANCE_ENDPOINTS:
            # Shared files/suppliers are needed by the existing finance screens.
            g.financeiro_empresa = _resolve_empresa("ija", existing_data=True)
            return None
        if endpoint in PREFEITURA_MAP_ENDPOINTS or (endpoint.startswith("main.agro_") and not is_financeiro_legacy_endpoint(endpoint)):
            abort(403)

    @bp.before_request
    def authorize_existing_financial_views():
        if not is_financeiro_legacy_endpoint(request.endpoint):
            return None
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        _require_financeiro_access()
        empresa = next((item for item in build_financeiro_empresas(current_user) if item["slug"] == "ija"), None)
        if empresa is None or not empresa["disponivel"]:
            abort(403)
        if is_financeiro_settings_endpoint(request.endpoint) and not can_manage_financeiro_settings(current_user):
            abort(403)
        g.financeiro_empresa = empresa

    @bp.app_context_processor
    def inject_financeiro_access():
        return {
            "can_access_financeiro_panel": can_access_financeiro_panel,
            "can_manage_financeiro_settings": can_manage_financeiro_settings,
            "is_financeiro_endpoint": lambda endpoint: is_financeiro_endpoint(endpoint) or getattr(g, "financeiro_empresa", None) is not None or is_agro_finance_user(current_user),
            "financeiro_empresa_atual": getattr(g, "financeiro_empresa", None),
            "build_financeiro_menu": build_financeiro_menu,
            "financeiro_consulta_url": _consulta_url,
        }

    @bp.after_request
    def prevent_financeiro_cache(response):
        if is_financeiro_endpoint(request.endpoint) or getattr(g, "financeiro_empresa", None) is not None:
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.route("/financeiro", methods=["GET"], endpoint="financeiro_central")
    @login_required
    def financeiro_central():
        _require_financeiro_access()
        empresas = build_financeiro_empresas(current_user)
        return render_template(
            "financeiro_central.html",
            empresas=empresas,
            total_empresas_disponiveis=sum(empresa["disponivel"] for empresa in empresas),
        )

    @bp.route("/financeiro/empresas/<empresa_slug>", methods=["GET"], endpoint="financeiro_empresa")
    @login_required
    def financeiro_empresa(empresa_slug):
        empresa = _resolve_empresa(empresa_slug)
        # The company is resolved on every request from the URL and permissions.
        # No shared selected-company cookie can change another tab's context.
        return render_template("financeiro_empresa.html", empresa=empresa)

    def render_company_consulta(empresa_slug, tipo):
        empresa = _resolve_empresa(empresa_slug, existing_data=True)
        g.financeiro_empresa = empresa
        # Reuse the original controllers/templates; only company navigation changes.
        return current_app.view_functions[COMPANY_CONSULTATION_ENDPOINTS[tipo]]()

    @bp.route("/financeiro/empresas/<empresa_slug>/clientes", methods=["GET"], endpoint="financeiro_empresa_clientes")
    @login_required
    def financeiro_empresa_clientes(empresa_slug):
        return render_company_consulta(empresa_slug, "clientes")

    @bp.route("/financeiro/empresas/<empresa_slug>/relacionamentos", methods=["GET"], endpoint="financeiro_empresa_relacionamentos")
    @login_required
    def financeiro_empresa_relacionamentos(empresa_slug):
        return render_company_consulta(empresa_slug, "relacionamentos")

    @bp.route("/financeiro/empresas/<empresa_slug>/fornecedores", methods=["GET"], endpoint="financeiro_empresa_fornecedores")
    @login_required
    def financeiro_empresa_fornecedores(empresa_slug):
        return render_company_consulta(empresa_slug, "fornecedores")

    @bp.route("/financeiro/empresas/<empresa_slug>/comercial", methods=["GET"], endpoint="financeiro_empresa_comercial")
    @login_required
    def financeiro_empresa_comercial(empresa_slug):
        tipo = request.args.get("aba", "orcamentos")
        if tipo not in {"orcamentos", "mapeamentos", "contratos"}:
            abort(404)
        return render_company_consulta(empresa_slug, tipo)
