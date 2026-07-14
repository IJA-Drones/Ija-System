from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.modules.equipe_uvis_dashboard.service import (
    EquipeUvisDashboardError,
    build_dashboard_equipe_uvis_context,
    build_equipe_uvis_os_historico_context,
    build_equipe_uvis_os_unificado_context,
    concluir_os_equipe_uvis,
    salvar_equipe_uvis_complemento_form,
)


def _can_access_equipe_uvis_panel(user):
    return getattr(user, "tipo_usuario", None) in {"equipe_uvis", "uvis"}


def register_routes(bp):
    @bp.route("/equipe-uvis", methods=["GET"], endpoint="dashboard_equipe_uvis")
    @login_required
    def dashboard_equipe_uvis():
        if not _can_access_equipe_uvis_panel(current_user):
            return redirect(url_for("main.dashboard"))

        google_maps_key = current_app.config.get("KEY_API_GOOGLE_MAPS")

        try:
            context = build_dashboard_equipe_uvis_context(
                current_user,
                request.args,
                google_maps_key,
            )
        except EquipeUvisDashboardError as exc:
            flash(exc.message, exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        context["pagination_args"] = {k: v for k, v in request.args.items() if k != "page"}
        return render_template("dashboard_equipe_uvis.html", **context)

    @bp.route("/equipe-uvis/os/<int:os_id>/formulario", methods=["GET", "POST"], endpoint="equipe_uvis_os_formulario_view")
    @login_required
    def equipe_uvis_os_formulario_view(os_id):
        if not _can_access_equipe_uvis_panel(current_user):
            return redirect(url_for("main.dashboard"))

        try:
            context = build_equipe_uvis_os_unificado_context(current_user, os_id)
        except EquipeUvisDashboardError as exc:
            flash(exc.message, exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        if request.method == "POST":
            try:
                flash(salvar_equipe_uvis_complemento_form(current_user, os_id, request.form), "success")
                redirect_args = {"os_id": os_id, "aba": "uvis"}
                if (request.args.get("voltar") or "").strip().lower() == "historico":
                    redirect_args["voltar"] = "historico"
                return redirect(url_for("main.equipe_uvis_os_formulario_view", **redirect_args))
            except EquipeUvisDashboardError as exc:
                db.session.rollback()
                flash(exc.message, exc.category)
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao salvar OS da equipe UVIS %s", os_id)
                flash("Erro ao salvar o formulario da equipe UVIS.", "danger")

            context = build_equipe_uvis_os_unificado_context(current_user, os_id)

        url_voltar = url_for("main.dashboard_equipe_uvis")
        form_action_args = {"os_id": os_id}
        if (request.args.get("voltar") or "").strip().lower() == "historico":
            url_voltar = url_for("main.equipe_uvis_os_historico")
            form_action_args["voltar"] = "historico"

        return render_template(
            "piloto_os_formulario.html",
            **context,
            form_action=url_for("main.equipe_uvis_os_formulario_view", **form_action_args),
            url_voltar=url_voltar,
        )

    @bp.route("/equipe-uvis/os/historico", methods=["GET"], endpoint="equipe_uvis_os_historico")
    @login_required
    def equipe_uvis_os_historico():
        if not _can_access_equipe_uvis_panel(current_user):
            return redirect(url_for("main.dashboard"))

        try:
            context = build_equipe_uvis_os_historico_context(current_user, request.args)
        except EquipeUvisDashboardError as exc:
            flash(exc.message, exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        context["pagination_args"] = {k: v for k, v in request.args.items() if k != "page"}
        return render_template("equipe_uvis_os_historico.html", **context)

    @bp.route("/equipe-uvis/os/<int:os_id>/concluir", methods=["POST"], endpoint="equipe_uvis_concluir_os")
    @login_required
    def equipe_uvis_concluir_os(os_id):
        if not _can_access_equipe_uvis_panel(current_user):
            return redirect(url_for("main.dashboard"))

        try:
            flash(concluir_os_equipe_uvis(current_user, os_id), "success")
        except EquipeUvisDashboardError as exc:
            db.session.rollback()
            flash(exc.message, exc.category)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao concluir OS da equipe UVIS %s", os_id)
            flash("Erro ao concluir a OS da equipe UVIS.", "danger")

        return redirect(url_for("main.dashboard_equipe_uvis"))
