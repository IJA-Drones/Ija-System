from flask import abort, render_template, request
from flask_login import current_user, login_required

from app.modules.admin_checklists.service import (
    build_admin_checklist_detail,
    build_admin_checklists_totals,
    build_admin_checklists_weekly_groups,
)


def _admin_only():
    if getattr(current_user, "tipo_usuario", None) != "admin":
        abort(403)


def register_routes(bp):
    @bp.route("/admin/checklists/semanais", methods=["GET"], endpoint="admin_checklists_semanais")
    @login_required
    def admin_checklists_semanais():
        _admin_only()

        q = (request.args.get("q") or "").strip()
        data_inicio = (request.args.get("data_inicio") or "").strip()
        data_fim = (request.args.get("data_fim") or "").strip()

        grupos = build_admin_checklists_weekly_groups(
            q=q,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        totais = build_admin_checklists_totals(grupos)

        return render_template(
            "admin_checklists_semanais.html",
            grupos=grupos,
            totais=totais,
            filters={
                "q": q,
                "data_inicio": data_inicio,
                "data_fim": data_fim,
            },
        )

    @bp.route(
        "/admin/checklists/semanais/<int:piloto_id>/<string:semana_inicio>",
        methods=["GET"],
        endpoint="admin_checklist_semanal_detalhe",
    )
    @login_required
    def admin_checklist_semanal_detalhe(piloto_id, semana_inicio):
        _admin_only()

        try:
            detail = build_admin_checklist_detail(piloto_id=piloto_id, semana_inicio=semana_inicio)
        except ValueError:
            abort(404)

        if not detail:
            abort(404)

        return render_template(
            "admin_checklist_semanal_detalhe.html",
            piloto_id=detail["piloto_id"],
            piloto_nome=detail["piloto_nome"],
            semana_inicio=detail["semana_inicio"],
            semana_fim=detail["semana_fim"],
            ultima_movimentacao=detail["ultima_movimentacao"],
            veiculos=detail["veiculos"],
            drones=detail["drones"],
            totais=detail["totais"],
        )
