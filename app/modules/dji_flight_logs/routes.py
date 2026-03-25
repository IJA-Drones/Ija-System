from flask import current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.modules.dji_flight_logs.service import (
    build_dji_logs_context,
    build_dji_logs_excel_export,
    can_access_dji_logs,
    can_import_dji_logs,
    import_dji_log_excel,
)


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
            flash("Apenas administradores e operadores podem importar logs DJI.", "danger")
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
