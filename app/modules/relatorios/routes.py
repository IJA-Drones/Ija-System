from flask import flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.modules.relatorios.exporters import (
    build_relatorio_excel_export,
    build_relatorio_os_excel_export,
    build_relatorio_os_pdf_export,
    build_relatorio_pdf_export,
)
from app.modules.relatorios.service import (
    build_relatorios_os_context,
    build_relatorios_solicitacoes_context,
    can_access_relatorios_menu,
)


def register_routes(bp):
    @bp.route("/relatorios/solicitacoes", methods=["GET"], endpoint="relatorios_solicitacoes")
    def relatorios_solicitacoes():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))

        try:
            context = build_relatorios_solicitacoes_context(current_user, request.args)
            return render_template("relatorios.html", **context)
        except Exception as exc:
            db.session.rollback()
            print(f"ERRO NOS RELATORIOS: {exc}")
            return render_template(
                "erro.html",
                codigo=500,
                titulo="Erro nos Relatorios",
                mensagem="Houve um erro tecnico ao processar os dados.",
            )

    @bp.route("/relatorios", methods=["GET"], endpoint="relatorios")
    @login_required
    def relatorios_menu():
        if not can_access_relatorios_menu(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))
        return render_template("relatorios_menu.html")

    @bp.route("/relatorios-os", methods=["GET"], endpoint="relatorios_os")
    @login_required
    def relatorios_os():
        try:
            context = build_relatorios_os_context(current_user, request.args)
            return render_template("relatorios_os.html", **context)
        except Exception as exc:
            db.session.rollback()
            print(f"ERRO NOS RELATORIOS DE OS: {exc}")
            return render_template(
                "erro.html",
                codigo=500,
                titulo="Erro nos Relatorios de OS",
                mensagem="Houve um erro tecnico ao processar os dados das ordens de servico.",
            )

    @bp.route("/admin/exportar_relatorio_pdf", endpoint="exportar_relatorio_pdf")
    @login_required
    def exportar_relatorio_pdf():
        caminho_pdf, download_name = build_relatorio_pdf_export(current_user, request.args)
        return send_file(
            caminho_pdf,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )

    @bp.route("/admin/exportar_relatorio_excel", endpoint="exportar_relatorio_excel")
    @login_required
    def exportar_relatorio_excel():
        output, download_name = build_relatorio_excel_export(current_user, request.args)
        return send_file(
            output,
            download_name=download_name,
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @bp.route("/relatorios-os/export/excel", methods=["GET"], endpoint="relatorios_os_export_excel")
    @login_required
    def relatorios_os_export_excel():
        output, download_name = build_relatorio_os_excel_export(current_user, request.args)
        return send_file(
            output,
            download_name=download_name,
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @bp.route("/relatorios-os/export/pdf", methods=["GET"], endpoint="relatorios_os_export_pdf")
    @login_required
    def relatorios_os_export_pdf():
        caminho_pdf, download_name = build_relatorio_os_pdf_export(current_user, request.args)
        return send_file(
            caminho_pdf,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )
