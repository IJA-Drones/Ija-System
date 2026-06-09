from flask import abort, render_template, request
from flask_login import current_user, login_required

from app.modules.admin_checklists.service import (
    build_admin_checklist_detail,
    build_admin_checklists_totals,
    build_admin_checklists_weekly_groups,
)
from app.shared.access import is_admin_global_user


def _admin_only():
    if not is_admin_global_user(current_user):
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
        return _render_admin_checklist_detail("piloto", piloto_id, semana_inicio)

    @bp.route(
        "/admin/checklists/semanais/<string:actor_type>/<int:actor_id>/<string:semana_inicio>",
        methods=["GET"],
        endpoint="admin_checklist_semanal_detalhe_actor",
    )
    @login_required
    def admin_checklist_semanal_detalhe_actor(actor_type, actor_id, semana_inicio):
        return _render_admin_checklist_detail(actor_type, actor_id, semana_inicio)


def _render_admin_checklist_detail(actor_type, actor_id, semana_inicio):
    _admin_only()

    if actor_type not in {"piloto", "equipe"}:
        abort(404)

    try:
        detail = build_admin_checklist_detail(
            actor_type=actor_type,
            actor_id=actor_id,
            semana_inicio=semana_inicio,
        )
    except ValueError:
        abort(404)

    if not detail:
        abort(404)

    return render_template(
        "admin_checklist_semanal_detalhe.html",
        piloto_id=detail["piloto_id"],
        equipe_id=detail["equipe_id"],
        actor_id=detail["actor_id"],
        actor_type=detail["actor_type"],
        piloto_nome=detail["piloto_nome"],
        semana_inicio=detail["semana_inicio"],
        semana_fim=detail["semana_fim"],
        ultima_movimentacao=detail["ultima_movimentacao"],
        veiculos=detail["veiculos"],
        drones=detail["drones"],
        totais=detail["totais"],
    )
