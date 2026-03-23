import os

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.modules.piloto_os.exporters import build_admin_os_excel_v2_export, build_admin_os_pdf_v2_export
from app.modules.piloto_os.service import (
    PilotoOsError,
    build_admin_os_form_context,
    build_piloto_os_form_context,
    build_piloto_os_context,
    build_piloto_os_historico_context,
    concluir_os_piloto,
    get_piloto_drone_payload,
    salvar_piloto_os_form,
)


def _require_piloto():
    if getattr(current_user, "tipo_usuario", None) != "piloto":
        abort(403)


def _require_admin_os_view():
    if getattr(current_user, "tipo_usuario", None) not in ["admin", "operario", "visualizar"]:
        abort(403)


def _require_admin_only():
    if getattr(current_user, "tipo_usuario", None) not in ["admin", "visualizar"]:
        abort(403)


def register_routes(bp):
    @bp.route("/piloto/os", methods=["GET"], endpoint="piloto_os")
    @login_required
    def piloto_os():
        _require_piloto()

        google_maps_key = (
            os.getenv("KEY_API_GOOGLE_MAPS")
            or current_app.config.get("GOOGLE_MAPS_API_KEY", "")
        )

        try:
            context = build_piloto_os_context(current_user, request.args, google_maps_key)
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        if context["sem_equipe_ativa"]:
            flash("Voce ainda nao esta vinculado a nenhuma equipe ativa.", "warning")

        return render_template(
            "piloto_os.html",
            pedidos=context["pedidos"],
            paginacao=context["paginacao"],
            status_ok=context["status_ok"],
            pilot_team_nome=context["pilot_team_nome"],
            pilot_team_regiao=context["pilot_team_regiao"],
            pilot_team_papel=context["pilot_team_papel"],
            google_maps_key=context["google_maps_key"],
            drones_equipe=context["drones_equipe"],
            baterias_equipe=context["baterias_equipe"],
            veiculos_equipe=context["veiculos_equipe"],
        )

    @bp.route("/piloto/os/historico", methods=["GET"], endpoint="piloto_os_historico")
    @login_required
    def piloto_os_historico():
        _require_piloto()

        try:
            context = build_piloto_os_historico_context(current_user, request.args)
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        return render_template(
            "piloto_os_historico.html",
            pedidos=context["pedidos"],
            paginacao=context["paginacao"],
        )

    @bp.route("/piloto/os/<int:os_id>/concluir", methods=["POST"], endpoint="piloto_concluir_os")
    @login_required
    def piloto_concluir_os(os_id):
        _require_piloto()

        try:
            flash(concluir_os_piloto(current_user, os_id), "success")
        except PilotoOsError as exc:
            flash(str(exc), exc.category)

        return redirect(url_for("main.piloto_os"))

    @bp.route("/piloto/os/formulario", methods=["GET"], endpoint="piloto_os_formulario_redirect")
    @login_required
    def piloto_os_formulario_redirect():
        _require_piloto()

        os_id = request.args.get("os_id", type=int) or request.args.get("solicitacao_id", type=int)
        if not os_id:
            flash("Selecione uma OS para preencher o formulario.", "info")
            return redirect(url_for("main.piloto_os"))

        return redirect(url_for("main.piloto_os_formulario_view", os_id=os_id))

    @bp.route("/piloto/os/<int:os_id>/formulario", methods=["GET", "POST"], endpoint="piloto_os_formulario_view")
    @login_required
    def piloto_os_formulario_view(os_id):
        _require_piloto()

        try:
            context = build_piloto_os_form_context(current_user, os_id)
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        if request.method == "POST":
            if context["modo_visualizacao"]:
                flash("Esta OS ja foi concluida e nao pode mais ser editada pelo piloto.", "warning")
                return redirect(url_for("main.piloto_os_formulario_view", os_id=os_id))

            try:
                flash(salvar_piloto_os_form(current_user, os_id, request.form), "success")
                return redirect(url_for("main.piloto_os"))
            except PilotoOsError as exc:
                flash(str(exc), exc.category)
                if exc.redirect_endpoint == "main.piloto_os_formulario_view":
                    return redirect(url_for(exc.redirect_endpoint, os_id=os_id))
                return redirect(url_for(exc.redirect_endpoint))
            except Exception:
                from app.extensions import db

                db.session.rollback()
                current_app.logger.exception("Erro ao salvar formulario da OS %s", os_id)
                flash("Erro ao salvar o formulario. Verifique os campos e tente novamente.", "danger")

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
            url_voltar=url_for("main.piloto_os"),
            form_action=url_for("main.piloto_os_formulario_view", os_id=os_id),
        )

    @bp.route("/piloto/api/drone/<int:drone_id>", methods=["GET"], endpoint="piloto_api_drone")
    @login_required
    def piloto_api_drone(drone_id):
        _require_piloto()

        try:
            return jsonify(get_piloto_drone_payload(current_user, drone_id))
        except PilotoOsError as exc:
            return jsonify({"error": str(exc)}), 403

    @bp.route("/admin/os/<int:os_id>/formulario", methods=["GET"], endpoint="admin_os_formulario_view")
    @login_required
    def admin_os_formulario_view(os_id):
        _require_admin_os_view()

        try:
            context = build_admin_os_form_context(current_user, os_id)
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return redirect(url_for(exc.redirect_endpoint))

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
            url_voltar=url_for("main.admin_dashboard"),
            form_action="#",
        )

    @bp.route("/admin/os/<int:os_id>/export/pdf/v2", methods=["GET"], endpoint="admin_export_os_pdf_v2")
    @login_required
    def admin_export_os_pdf_v2(os_id):
        _require_admin_only()

        caminho_pdf, download_name = build_admin_os_pdf_v2_export(os_id, request.args)
        return send_file(
            caminho_pdf,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )

    @bp.route("/admin/os/<int:os_id>/export/excel/v2", methods=["GET"], endpoint="admin_export_os_excel_v2")
    @login_required
    def admin_export_os_excel_v2(os_id):
        _require_admin_only()

        output, download_name = build_admin_os_excel_v2_export(os_id, request.args)
        return send_file(
            output,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
