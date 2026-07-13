import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Usuario
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
from app.shared.query_filters import query_args_without_page


def _env_int(name, default, minimum=0):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


PDF_EXPORT_MAX_CONCURRENT = _env_int("PDF_EXPORT_MAX_CONCURRENT", 1)
PDF_EXPORT_SEMAPHORE = (
    threading.BoundedSemaphore(PDF_EXPORT_MAX_CONCURRENT)
    if PDF_EXPORT_MAX_CONCURRENT > 0
    else None
)
COLETA_IMAGENS_PDF_ASYNC_WORKERS = _env_int("RELATORIO_COLETA_IMAGENS_PDF_ASYNC_WORKERS", 1, minimum=1)
COLETA_IMAGENS_PDF_JOBS = {}
COLETA_IMAGENS_PDF_JOBS_LOCK = threading.Lock()
COLETA_IMAGENS_PDF_EXECUTOR = ThreadPoolExecutor(max_workers=COLETA_IMAGENS_PDF_ASYNC_WORKERS)


def _build_pdf_export_with_memory_guard(builder, user, args):
    if PDF_EXPORT_SEMAPHORE is None:
        return builder(user, args)
    if not PDF_EXPORT_SEMAPHORE.acquire(blocking=False):
        return None
    try:
        return builder(user, args)
    finally:
        PDF_EXPORT_SEMAPHORE.release()


def _coleta_pdf_jobs_dir():
    path = os.path.join(current_app.instance_path, "relatorio_coleta_imagens_jobs")
    os.makedirs(path, exist_ok=True)
    return path


def _coleta_pdf_job_meta_path(job_id):
    return os.path.join(_coleta_pdf_jobs_dir(), f"{job_id}.json")


def _write_json_file(path, payload):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True)
    os.replace(temp_path, path)


def _read_json_file(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _now_epoch():
    return time.time()


def _set_coleta_pdf_job(job_id, **updates):
    with COLETA_IMAGENS_PDF_JOBS_LOCK:
        job = COLETA_IMAGENS_PDF_JOBS.get(job_id) or _read_json_file(_coleta_pdf_job_meta_path(job_id))
        if not job:
            return None
        job.update(updates)
        job["updated_at"] = _now_epoch()
        COLETA_IMAGENS_PDF_JOBS[job_id] = job
        _write_json_file(_coleta_pdf_job_meta_path(job_id), job)
        return dict(job)


def _get_coleta_pdf_job(job_id):
    with COLETA_IMAGENS_PDF_JOBS_LOCK:
        job = _read_json_file(_coleta_pdf_job_meta_path(job_id)) or COLETA_IMAGENS_PDF_JOBS.get(job_id)
        if job:
            COLETA_IMAGENS_PDF_JOBS[job_id] = job
        return dict(job) if job else None


def _coleta_pdf_job_json(job):
    payload = {
        "success": job.get("status") != "error",
        "job_id": job.get("id"),
        "status": job.get("status"),
        "progress": int(job.get("progress") or 0),
        "message": job.get("message") or "",
        "error": job.get("error"),
        "download_name": job.get("download_name"),
    }
    if job.get("status") == "success":
        payload["download_url"] = url_for("main.relatorios_coleta_imagens_pdf_job_download", job_id=job["id"])
    return payload


def _create_coleta_pdf_job(user, args):
    job_id = uuid.uuid4().hex
    now = _now_epoch()
    args_payload = {
        key: value
        for key, value in query_args_without_page(args).items()
        if key not in {"page", "relatorio_pdf_job_id"}
    }
    job = {
        "id": job_id,
        "user_id": int(user.id),
        "args": args_payload,
        "status": "queued",
        "progress": 0,
        "message": "Relatorio recebido. Aguardando geracao do PDF.",
        "error": None,
        "path": None,
        "download_name": None,
        "created_at": now,
        "updated_at": now,
    }
    with COLETA_IMAGENS_PDF_JOBS_LOCK:
        COLETA_IMAGENS_PDF_JOBS[job_id] = job
        _write_json_file(_coleta_pdf_job_meta_path(job_id), job)
    return job_id


def _run_coleta_pdf_job(app, job_id):
    with app.app_context():
        acquired = False
        try:
            job = _get_coleta_pdf_job(job_id)
            if not job:
                return

            _set_coleta_pdf_job(
                job_id,
                status="running",
                progress=5,
                message="Preparando dados do relatorio de imagens.",
                error=None,
            )
            user = Usuario.query.get(job["user_id"])
            if not user:
                raise RuntimeError("Usuario do relatorio nao foi encontrado.")

            if PDF_EXPORT_SEMAPHORE is not None:
                _set_coleta_pdf_job(
                    job_id,
                    progress=10,
                    message="Aguardando a vez na fila de exportacao PDF.",
                )
                PDF_EXPORT_SEMAPHORE.acquire()
                acquired = True

            _set_coleta_pdf_job(
                job_id,
                progress=20,
                message="Gerando PDF do relatorio de imagens.",
            )
            caminho_pdf, download_name = build_relatorio_coleta_imagens_pdf_export(
                user,
                MultiDict(job.get("args") or {}),
            )
            _set_coleta_pdf_job(
                job_id,
                status="success",
                progress=100,
                message="PDF pronto para download.",
                path=caminho_pdf,
                download_name=download_name,
            )
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception("Erro ao gerar PDF assincrono do relatorio de coleta de imagens.")
            message = str(exc).strip()[:500] or "Nao foi possivel gerar o PDF do relatorio de imagens."
            _set_coleta_pdf_job(
                job_id,
                status="error",
                message=message,
                error=message,
            )
        finally:
            if acquired and PDF_EXPORT_SEMAPHORE is not None:
                PDF_EXPORT_SEMAPHORE.release()
            db.session.remove()


def _redirect_to_coleta_imagens_with_job(job_id):
    params = {
        key: value
        for key, value in query_args_without_page(request.args).items()
        if key not in {"page", "relatorio_pdf_job_id"}
    }
    params["relatorio_pdf_job_id"] = job_id
    return redirect(url_for("main.relatorios_coleta_imagens", **params))


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

        job_id = _create_coleta_pdf_job(current_user, request.args)
        COLETA_IMAGENS_PDF_EXECUTOR.submit(
            _run_coleta_pdf_job,
            current_app._get_current_object(),
            job_id,
        )
        flash("O PDF esta sendo gerado em segundo plano. Voce pode continuar usando o sistema.", "info")
        return _redirect_to_coleta_imagens_with_job(job_id)

    @bp.route(
        "/relatorios-coleta-imagens/export/pdf/jobs/<job_id>",
        methods=["GET"],
        endpoint="relatorios_coleta_imagens_pdf_job_status",
    )
    @login_required
    def relatorios_coleta_imagens_pdf_job_status(job_id):
        if not can_access_relatorio_coleta_imagens(current_user):
            return jsonify({"success": False, "error": "Acesso restrito."}), 403

        job = _get_coleta_pdf_job(job_id)
        if not job or int(job.get("user_id") or 0) != int(current_user.id):
            return jsonify({"success": False, "error": "Exportacao nao encontrada."}), 404

        return jsonify(_coleta_pdf_job_json(job))

    @bp.route(
        "/relatorios-coleta-imagens/export/pdf/jobs/<job_id>/download",
        methods=["GET"],
        endpoint="relatorios_coleta_imagens_pdf_job_download",
    )
    @login_required
    def relatorios_coleta_imagens_pdf_job_download(job_id):
        if not can_access_relatorio_coleta_imagens(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        job = _get_coleta_pdf_job(job_id)
        if not job or int(job.get("user_id") or 0) != int(current_user.id):
            flash("Exportacao nao encontrada.", "warning")
            return redirect(url_for("main.relatorios_coleta_imagens"))

        if job.get("status") != "success" or not job.get("path") or not os.path.isfile(job["path"]):
            flash("O PDF ainda nao esta pronto para download.", "warning")
            return _redirect_to_coleta_imagens_with_job(job_id)

        return send_file(
            job["path"],
            as_attachment=True,
            download_name=job.get("download_name") or "relatorio_coleta_imagens.pdf",
            mimetype="application/pdf",
        )
