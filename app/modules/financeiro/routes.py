from flask import abort, render_template, request
from flask_login import current_user, login_required

from app.modules.financeiro.service import build_financeiro_empresas
from app.shared.access import can_access_financeiro_panel, is_financeiro_admin_user


def _require_financeiro_access():
    if not can_access_financeiro_panel(current_user):
        abort(403)


def register_routes(bp):
    @bp.app_context_processor
    def inject_financeiro_access():
        return {
            "can_access_financeiro_panel": can_access_financeiro_panel,
            "is_financeiro_admin_user": is_financeiro_admin_user,
        }

    @bp.after_request
    def prevent_financeiro_cache(response):
        if (request.endpoint or "").startswith("main.financeiro_"):
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
        _require_financeiro_access()
        empresa = next((item for item in build_financeiro_empresas(current_user)
                        if item["slug"] == empresa_slug), None)
        if empresa is None:
            abort(404)
        if not empresa["disponivel"]:
            abort(403)
        # The company is resolved on every request from the URL and permissions.
        # No shared selected-company cookie can change another tab's context.
        return render_template("financeiro_empresa.html", empresa=empresa)
