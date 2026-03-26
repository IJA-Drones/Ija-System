import os

from flask import current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import DjiFlightKmlRoute
from app.modules.dji_flight_logs.service import (
    build_dji_logs_context,
    build_dji_logs_excel_export,
    can_access_dji_logs,
    can_import_dji_logs,
    get_dji_route_payload,
    import_dji_log_excel,
    import_dji_kml_files,
)
from app.shared.uploads import get_upload_folder


def register_routes(bp):
    @bp.route("/relatorios/dji-logs", methods=["GET"], endpoint="relatorios_dji_logs")
    @login_required
    def relatorios_dji_logs():
        if not can_access_dji_logs(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        try:
            context = build_dji_logs_context(request.args)
            return render_template(
                "relatorios_dji_logs.html",
                can_import=can_import_dji_logs(current_user),
                **context,
            )
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao montar relatorio de logs DJI.")
            return render_template(
                "erro.html",
                codigo=500,
                titulo="Erro nos logs de voo",
                mensagem="Nao foi possivel carregar o relatorio de logs DJI.",
            ), 500

    @bp.route("/relatorios/dji-logs/exportar", methods=["GET"], endpoint="exportar_dji_logs_excel")
    @login_required
    def exportar_dji_logs_excel():
        if not can_access_dji_logs(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        output, nome = build_dji_logs_excel_export(request.args)
        return send_file(
            output,
            download_name=nome,
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @bp.route("/relatorios/dji-logs/importar", methods=["POST"], endpoint="importar_dji_logs")
    @login_required
    def importar_dji_logs():
        if not can_import_dji_logs(current_user):
            flash("Apenas administradores podem importar logs DJI.", "danger")
            return redirect(url_for("main.relatorios_dji_logs"))

        uploaded_file = request.files.get("arquivo")
        try:
            import_batch = import_dji_log_excel(uploaded_file, current_user)
            flash(
                (
                    "Importacao concluida: "
                    f"{import_batch.total_rows} linhas lidas, "
                    f"{import_batch.imported_rows} novas e "
                    f"{import_batch.skipped_rows} repetidas."
                ),
                "success",
            )
        except ValueError as exc:
            flash(str(exc), "warning")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao importar logs DJI.")
            flash("Erro interno ao importar o Excel da DJI.", "danger")

        return redirect(url_for("main.relatorios_dji_logs"))

    @bp.route("/relatorios/dji-logs/importar-kml", methods=["POST"], endpoint="importar_dji_kml")
    @login_required
    def importar_dji_kml():
        if not can_import_dji_logs(current_user):
            flash("Apenas administradores podem importar rotas KML.", "danger")
            return redirect(url_for("main.relatorios_dji_logs"))

        uploaded_files = request.files.getlist("arquivos")
        try:
            result = import_dji_kml_files(uploaded_files, current_user)
            flash(
                (
                    "Importacao de KML concluida: "
                    f"{result['imported']} novas, "
                    f"{result['linked']} vinculadas a voos, "
                    f"{result['unlinked']} sem voo correspondente e "
                    f"{result['skipped']} ignoradas."
                ),
                "success",
            )
        except ValueError as exc:
            flash(str(exc), "warning")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao importar arquivos KML.")
            flash("Erro interno ao importar os arquivos KML.", "danger")

        return redirect(url_for("main.relatorios_dji_logs"))

    @bp.route("/api/dji-kml-route/<int:route_id>", methods=["GET"], endpoint="api_dji_kml_route")
    @login_required
    def api_dji_kml_route(route_id):
        if not can_access_dji_logs(current_user):
            return jsonify({"ok": False, "message": "Acesso restrito."}), 403
        payload = get_dji_route_payload(route_id)
        return jsonify({"ok": True, "route": payload}), 200

    @bp.route("/relatorios/dji-logs/rota/<int:route_id>", methods=["GET"], endpoint="visualizar_dji_kml_route")
    @login_required
    def visualizar_dji_kml_route(route_id):
        if not can_access_dji_logs(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        route = get_dji_route_payload(route_id)
        return render_template("dji_kml_route_map.html", route=route)

    @bp.route("/relatorios/dji-logs/rota/<int:route_id>/kml", methods=["GET"], endpoint="baixar_dji_kml_route")
    @login_required
    def baixar_dji_kml_route(route_id):
        if not can_access_dji_logs(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        route = DjiFlightKmlRoute.query.get_or_404(route_id)
        absolute_path = os.path.join(get_upload_folder(), route.stored_path)
        if not os.path.exists(absolute_path):
            flash("Arquivo KML nao encontrado no servidor.", "warning")
            return redirect(url_for("main.relatorios_dji_logs"))

        return send_file(
            absolute_path,
            as_attachment=True,
            download_name=route.original_filename,
            mimetype="application/vnd.google-earth.kml+xml",
        )
