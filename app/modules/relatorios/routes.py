import os
import threading

from flask import flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.modules.relatorios.exporters import (
    build_relatorio_coleta_imagens_pdf_export,
    build_relatorio_excel_export,
    build_relatorio_os_excel_export,
    build_relatorio_os_pdf_export,
    build_relatorio_pdf_export,
)
from app.modules.relatorios.service import (
    build_relatorios_coleta_imagens_context,
    build_relatorios_os_context,
    build_relatorios_solicitacoes_context,
    can_access_relatorio_coleta_imagens,
    can_access_relatorios_menu,
)


def _env_int(name, default, minimum=0):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


PDF_EXPORT_MAX_CONCURRENT = _env_int("PDF_EXPORT_MAX_CONCURRENT", 0)
PDF_EXPORT_SEMAPHORE = (
    threading.BoundedSemaphore(PDF_EXPORT_MAX_CONCURRENT)
    if PDF_EXPORT_MAX_CONCURRENT > 0
    else None
)


def _build_pdf_export_with_memory_guard(builder, user, args):
    if PDF_EXPORT_SEMAPHORE is None:
        return builder(user, args)
    if not PDF_EXPORT_SEMAPHORE.acquire(blocking=False):
        return None
    try:
        return builder(user, args)
    finally:
        PDF_EXPORT_SEMAPHORE.release()


def register_routes(bp):
    @bp.route("/relatorios/solicitacoes", methods=["GET"], endpoint="relatorios_solicitacoes")
    @login_required
    def relatorios_solicitacoes():
        if not can_access_relatorios_menu(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

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
        if not can_access_relatorios_menu(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

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

    @bp.route("/relatorios-coleta-imagens", methods=["GET"], endpoint="relatorios_coleta_imagens")
    @login_required
    def relatorios_coleta_imagens():
        if not can_access_relatorio_coleta_imagens(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        try:
            context = build_relatorios_coleta_imagens_context(current_user, request.args)
            return render_template("relatorios_coleta_imagens.html", **context)
        except Exception as exc:
            db.session.rollback()
            print(f"ERRO NOS RELATORIOS DE COLETA DE IMAGENS: {exc}")
            return render_template(
                "erro.html",
                codigo=500,
                titulo="Erro no Relatorio de Coleta de Imagens",
                mensagem="Houve um erro tecnico ao processar os dados do levantamento de midias.",
            )

    @bp.route("/admin/exportar_relatorio_pdf", endpoint="exportar_relatorio_pdf")
    @login_required
    def exportar_relatorio_pdf():
        if not can_access_relatorios_menu(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        result = _build_pdf_export_with_memory_guard(build_relatorio_pdf_export, current_user, request.args)
        if result is None:
            flash("Ja existe uma exportacao PDF em andamento. Aguarde alguns instantes e tente novamente.", "warning")
            return redirect(request.referrer or url_for("main.relatorios"))
        caminho_pdf, download_name = result
        return send_file(
            caminho_pdf,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )

    @bp.route("/admin/exportar_relatorio_excel", endpoint="exportar_relatorio_excel")
    @login_required
    def exportar_relatorio_excel():
        if not can_access_relatorios_menu(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

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
        if not can_access_relatorios_menu(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

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
        if not can_access_relatorios_menu(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        result = _build_pdf_export_with_memory_guard(build_relatorio_os_pdf_export, current_user, request.args)
        if result is None:
            flash("Ja existe uma exportacao PDF em andamento. Aguarde alguns instantes e tente novamente.", "warning")
            return redirect(request.referrer or url_for("main.relatorios_os"))
        caminho_pdf, download_name = result
        return send_file(
            caminho_pdf,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )

    @bp.route("/relatorios-coleta-imagens/export/pdf", methods=["GET"], endpoint="relatorios_coleta_imagens_export_pdf")
    @login_required
    def relatorios_coleta_imagens_export_pdf():
        if not can_access_relatorio_coleta_imagens(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        result = _build_pdf_export_with_memory_guard(build_relatorio_coleta_imagens_pdf_export, current_user, request.args)
        if result is None:
            flash("Ja existe uma exportacao PDF em andamento. Aguarde alguns instantes e tente novamente.", "warning")
            return redirect(request.referrer or url_for("main.relatorios_coleta_imagens"))
        caminho_pdf, download_name = result
        return send_file(
            caminho_pdf,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )
