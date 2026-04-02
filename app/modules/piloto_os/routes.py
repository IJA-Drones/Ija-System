import os

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Solicitacao
from app.modules.piloto_os.dosagem import build_piloto_dosagem_context, salvar_piloto_dosagem_planejada
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
from app.shared.access import ADMIN_PANEL_VIEW_TYPES, can_access_regiao


def _require_piloto():
    if getattr(current_user, "tipo_usuario", None) != "piloto":
        abort(403)


def _require_admin_os_view():
    if getattr(current_user, "tipo_usuario", None) not in ADMIN_PANEL_VIEW_TYPES:
        abort(403)


def _require_admin_os_export():
    if getattr(current_user, "tipo_usuario", None) not in ADMIN_PANEL_VIEW_TYPES:
        abort(403)


def _ensure_os_region_access(os_id):
    solicitacao = (
        Solicitacao.query
        .options(
            db.selectinload(Solicitacao.usuario),
        )
        .get_or_404(os_id)
    )
    pedido_regiao = getattr(getattr(solicitacao, "usuario", None), "regiao", None)
    if not can_access_regiao(current_user, pedido_regiao):
        abort(403)


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def _redirect_from_piloto_os_error(exc, *, os_id=None):
    if exc.redirect_endpoint in {"main.piloto_os_formulario_view", "main.piloto_os_dosagem"} and os_id is not None:
        return redirect(url_for(exc.redirect_endpoint, os_id=os_id))
    return redirect(url_for(exc.redirect_endpoint))


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
            pagination_args={k: v for k, v in request.args.items() if k != "page"},
        )

    @bp.route("/piloto/dosagem", methods=["GET"], endpoint="piloto_dosagem")
    @login_required
    def piloto_dosagem():
        _require_piloto()
        return render_template("piloto_dosagem.html", **build_piloto_dosagem_context(current_user))

    @bp.route("/piloto/os/<int:os_id>/dosagem", methods=["GET", "POST"], endpoint="piloto_os_dosagem")
    @login_required
    def piloto_os_dosagem(os_id):
        _require_piloto()

        if request.method == "POST":
            try:
                flash(
                    salvar_piloto_dosagem_planejada(
                        current_user,
                        os_id,
                        request.form.get("calculo_dosagem_planejado"),
                    ),
                    "success",
                )
                return redirect(url_for("main.piloto_os_dosagem", os_id=os_id))
            except PilotoOsError as exc:
                flash(str(exc), exc.category)
                return _redirect_from_piloto_os_error(exc, os_id=os_id)

        try:
            return render_template(
                "piloto_dosagem.html",
                **build_piloto_dosagem_context(current_user, os_id=os_id),
            )
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return _redirect_from_piloto_os_error(exc, os_id=os_id)

    @bp.route("/piloto/os/historico", methods=["GET"], endpoint="piloto_os_historico")
    @login_required
    def piloto_os_historico():
        _require_piloto()

        try:
            context = build_piloto_os_historico_context(current_user, request.args)
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return _redirect_from_piloto_os_error(exc)

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
            return _redirect_from_piloto_os_error(exc, os_id=os_id)

        if request.method == "POST":
            if context["modo_visualizacao"]:
                flash("Esta OS ja foi concluida e nao pode mais ser editada pelo piloto.", "warning")
                return redirect(url_for("main.piloto_os_formulario_view", os_id=os_id))

            try:
                flash(
                    salvar_piloto_os_form(
                        current_user,
                        os_id,
                        request.form,
                        request.files,
                        current_app.root_path,
                    ),
                    "success",
                )
                return redirect(url_for("main.piloto_os"))
            except PilotoOsError as exc:
                flash(str(exc), exc.category)
                return _redirect_from_piloto_os_error(exc, os_id=os_id)
            except Exception:
                from app.extensions import db

                db.session.rollback()
                current_app.logger.exception("Erro ao salvar formulario da OS %s", os_id)
                flash("Erro ao salvar o formulario. Verifique os campos e tente novamente.", "danger")

        return render_template(
            "piloto_os_formulario.html",
            **context,
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
            **context,
            url_voltar=url_for("main.admin_dashboard"),
            form_action="#",
        )

    @bp.route("/admin/os/<int:os_id>/export/pdf/v2", methods=["GET"], endpoint="admin_export_os_pdf_v2")
    @login_required
    def admin_export_os_pdf_v2(os_id):
        _require_admin_os_export()
        _ensure_os_region_access(os_id)

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
        _require_admin_os_export()
        _ensure_os_region_access(os_id)

        output, download_name = build_admin_os_excel_v2_export(os_id, request.args)
        return send_file(
            output,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
