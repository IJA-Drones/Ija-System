from flask import render_template

from app.shared.solicitacao_focos import build_focus_catalog


def register_routes(bp):
    @bp.route("/portal-cidadao", methods=["GET"], endpoint="portal_cidadao")
    def portal_cidadao():
        return render_template(
            "portal_cidadao.html",
            focus_catalog=build_focus_catalog(),
        )
