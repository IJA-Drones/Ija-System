from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.modules.admin_checklists.service import (
    build_admin_checklist_detail,
    build_admin_checklist_edit_context,
    build_admin_checklists_totals,
    build_admin_checklists_weekly_groups,
    update_admin_checklist,
)
from app.shared.access import VEICULOS_SUPERVISOR_USER_TYPES, is_admin_global_user, normalize_role


def _admin_only():
    if not is_admin_global_user(current_user) and normalize_role(getattr(current_user, "tipo_usuario", None)) not in VEICULOS_SUPERVISOR_USER_TYPES:
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
            user=current_user,
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

    @bp.route(
        "/admin/checklists/<string:tipo>/<int:checklist_id>/editar",
        methods=["GET", "POST"], endpoint="editar_checklist_semanal",
    )
    @login_required
    def editar_checklist_semanal(tipo, checklist_id):
        _admin_only()
        try:
            context = build_admin_checklist_edit_context(current_user, tipo, checklist_id)
        except PermissionError:
            abort(403)
        except LookupError:
            abort(404)

        voltar_url = url_for(
            "main.admin_checklist_semanal_detalhe_actor",
            actor_type=context["actor_type"], actor_id=context["actor_id"],
            semana_inicio=context["semana_inicio"].isoformat(),
        ) if context["actor_id"] else url_for("main.admin_checklists_semanais")
        status = 200
        if request.method == "POST":
            try:
                update_admin_checklist(current_user, tipo, checklist_id, request.form)
            except PermissionError:
                abort(403)
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "warning")
                status = 400
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao corrigir checklist semanal %s/%s", tipo, checklist_id)
                flash("Não foi possível salvar a correção. Tente novamente.", "danger")
                status = 500
            else:
                flash("Checklist corrigido com sucesso.", "success")
                return redirect(voltar_url)

        return render_template(
            "admin_checklist_editar.html", **context, voltar_url=voltar_url,
            form_data=request.form if request.method == "POST" else {},
        ), status


def _render_admin_checklist_detail(actor_type, actor_id, semana_inicio):
    _admin_only()

    if actor_type not in {"piloto", "equipe"}:
        abort(404)

    try:
        detail = build_admin_checklist_detail(
            actor_type=actor_type,
            actor_id=actor_id,
            semana_inicio=semana_inicio,
            user=current_user,
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
