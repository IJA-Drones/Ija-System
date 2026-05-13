from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.modules.dashboard.service import (
    DashboardError,
    build_dashboard_context,
    build_uvis_equipe_os_form_context,
    build_uvis_historico_os_context,
    build_uvis_os_form_context,
)
from app.shared.access import ADMIN_PANEL_VIEW_TYPES, is_agro_finance_user


def register_routes(bp):
    @bp.route("/", endpoint="dashboard")
    @login_required
    def dashboard():
        google_maps_key = current_app.config.get("KEY_API_GOOGLE_MAPS")

        if current_user.tipo_usuario == "piloto":
            return redirect(url_for("main.piloto_os"))

        if current_user.tipo_usuario == "piloto_agro":
            return redirect(url_for("main.agro_piloto_dashboard"))

        if current_user.tipo_usuario == "equipe_uvis":
            return redirect(url_for("main.dashboard_equipe_uvis"))

        if is_agro_finance_user(current_user):
            return redirect(url_for("main.admin_agro"))

        if current_user.tipo_usuario in ADMIN_PANEL_VIEW_TYPES:
            return redirect(url_for("main.admin_dashboard"))

        context = build_dashboard_context(current_user, request.args, google_maps_key)
        context["pagination_args"] = {k: v for k, v in request.args.items() if k != "page"}
        return render_template("dashboard.html", **context)

    @bp.route("/uvis/historico-os", methods=["GET"], endpoint="uvis_historico_os")
    @login_required
    def uvis_historico_os():
        try:
            context = build_uvis_historico_os_context(current_user, request.args)
        except DashboardError as exc:
            flash(exc.message, exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        context["pagination_args"] = {k: v for k, v in request.args.items() if k != "page"}
        return render_template("uvis_os_historico.html", **context)

    @bp.route("/uvis/os/<int:os_id>/formulario", methods=["GET"], endpoint="uvis_os_formulario_view")
    @login_required
    def uvis_os_formulario_view(os_id):
        try:
            context = build_uvis_os_form_context(current_user, os_id)
        except DashboardError as exc:
            flash(exc.message, exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        filtro_tipo_os = (request.args.get("tipo_os") or "").strip()
        url_voltar = url_for("main.uvis_historico_os", tipo_os=filtro_tipo_os) if filtro_tipo_os else url_for("main.uvis_historico_os")

        return render_template(
            "piloto_os_formulario.html",
            solicitacao=context["solicitacao"],
            equipe=context["equipe"],
            ordem=context["ordem"],
            modo_visualizacao=context["modo_visualizacao"],
            uvis_nome=context["uvis_nome"],
            endereco_os=context["endereco_os"],
            piloto_padrao=context["piloto_padrao"],
            auxiliar_padrao=context["auxiliar_padrao"],
            respondido_por_padrao=context["respondido_por_padrao"],
            respondido_em_value=context["respondido_em_value"],
            drones_equipe=context["drones_equipe"],
            calculo_dosagem_planejado=context.get("calculo_dosagem_planejado", {}),
            url_voltar=url_voltar,
            form_action="#",
        )

    @bp.route("/uvis/os/<int:os_id>/equipe-formulario", methods=["GET"], endpoint="uvis_equipe_os_formulario_view")
    @login_required
    def uvis_equipe_os_formulario_view(os_id):
        try:
            context = build_uvis_equipe_os_form_context(current_user, os_id)
        except DashboardError as exc:
            flash(exc.message, exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        url_voltar = url_for("main.dashboard")
        if (request.args.get("voltar") or "").strip().lower() == "historico":
            filtro_tipo_os = (request.args.get("tipo_os") or "").strip()
            url_voltar = url_for("main.uvis_historico_os", tipo_os=filtro_tipo_os) if filtro_tipo_os else url_for("main.uvis_historico_os")

        return render_template(
            "equipe_uvis_os_formulario.html",
            **context,
            url_voltar=url_voltar,
            form_action="#",
        )
