from io import BytesIO
from pathlib import Path

from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import CurriculoAgro
from app.modules.agro.service import can_edit_agro_panel
from app.modules.agro.talent_bank_service import (
    PROFILE_LIST_FIELDS,
    PROFILE_TEXT_FIELDS,
    analyze_resume_with_gemini,
    build_dropbox_resume_path,
    delete_resume_from_dropbox,
    download_resume_from_dropbox,
    upload_resume_to_dropbox,
    validate_resume_pdf,
)
from app.shared.access import ADMIN_PANEL_VIEW_TYPES, apply_prefeitura_scope, normalize_role
from app.shared.query_filters import id_search_clause


def _require_access():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) not in ADMIN_PANEL_VIEW_TYPES:
        abort(403)


def _require_edit():
    if not can_edit_agro_panel(current_user):
        abort(403)


def _get_resume_or_404(resume_id):
    query = apply_prefeitura_scope(CurriculoAgro.query, current_user, CurriculoAgro.prefeitura_id)
    return query.filter(CurriculoAgro.id == resume_id).first_or_404()


def _duplicate_resume_query(sha256):
    prefeitura_id = getattr(current_user, "prefeitura_id", None)
    query = CurriculoAgro.query.filter(CurriculoAgro.arquivo_sha256 == sha256)
    if prefeitura_id is None:
        return query.filter(CurriculoAgro.prefeitura_id.is_(None))
    return query.filter(CurriculoAgro.prefeitura_id == prefeitura_id)


def _fallback_candidate_name(filename):
    return (Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "Candidato")[:180]


def _apply_profile(resume, profile, model):
    for field in PROFILE_TEXT_FIELDS:
        value = profile.get(field)
        if field == "nome" and not value:
            continue
        setattr(resume, field, value)
    for field in PROFILE_LIST_FIELDS:
        setattr(resume, field, profile.get(field) or [])
    resume.gemini_modelo = model
    resume.analise_status = CurriculoAgro.ANALISE_CONCLUIDA
    resume.analise_erro = None
    resume.analisado_em = db.func.now()


def _process_resume_analysis(resume, file_bytes):
    resume_id = resume.id
    try:
        profile, model = analyze_resume_with_gemini(file_bytes)
        _apply_profile(resume, profile, model)
        db.session.commit()
        return True, None
    except Exception as exc:
        db.session.rollback()
        resume = db.session.get(CurriculoAgro, resume_id)
        resume.analise_status = CurriculoAgro.ANALISE_ERRO
        resume.analise_erro = str(exc)[:4000]
        db.session.commit()
        return False, str(exc)


def register_routes(bp):
    @bp.route("/agro/banco-de-talentos", methods=["GET"], endpoint="agro_talentos_listar")
    @login_required
    def agro_talentos_listar():
        _require_access()
        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip().upper()
        analysis_status = (request.args.get("analise_status") or "").strip().upper()

        query = apply_prefeitura_scope(CurriculoAgro.query, current_user, CurriculoAgro.prefeitura_id)
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    id_search_clause(CurriculoAgro.id, q),
                    CurriculoAgro.nome.ilike(like),
                    CurriculoAgro.email.ilike(like),
                    CurriculoAgro.telefone.ilike(like),
                    CurriculoAgro.titulo_profissional.ilike(like),
                    CurriculoAgro.area_principal.ilike(like),
                    CurriculoAgro.resumo_perfil.ilike(like),
                    db.cast(CurriculoAgro.habilidades_tecnicas, db.String).ilike(like),
                    db.cast(CurriculoAgro.areas_atuacao, db.String).ilike(like),
                    db.cast(CurriculoAgro.areas_desenvolvimento, db.String).ilike(like),
                )
            )
        if status in CurriculoAgro.STATUS_OPTIONS:
            query = query.filter(CurriculoAgro.status == status)
        else:
            status = ""
        if analysis_status in {
            CurriculoAgro.ANALISE_PROCESSANDO,
            CurriculoAgro.ANALISE_CONCLUIDA,
            CurriculoAgro.ANALISE_ERRO,
        }:
            query = query.filter(CurriculoAgro.analise_status == analysis_status)
        else:
            analysis_status = ""

        resumes = query.order_by(CurriculoAgro.criado_em.desc(), CurriculoAgro.id.desc()).all()
        return render_template(
            "agro_talentos_listar.html",
            curriculos=resumes,
            status_options=CurriculoAgro.STATUS_OPTIONS,
            filters={
                "q": q,
                "status": status,
                "analise_status": analysis_status,
                "total": len(resumes),
            },
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/banco-de-talentos/novo", methods=["GET", "POST"], endpoint="agro_talento_novo")
    @login_required
    def agro_talento_novo():
        _require_edit()
        if request.method == "GET":
            return render_template("agro_talento_upload.html")

        try:
            upload = validate_resume_pdf(request.files.get("curriculo"))
        except ValueError as exc:
            flash(str(exc), "warning")
            return render_template("agro_talento_upload.html"), 400

        duplicate = _duplicate_resume_query(upload["sha256"]).first()
        if duplicate is not None:
            flash("Este PDF ja esta cadastrado no Banco de Talentos.", "warning")
            return redirect(url_for("main.agro_talento_detalhe", curriculo_id=duplicate.id))

        prefeitura_id = getattr(current_user, "prefeitura_id", None)
        dropbox_path = build_dropbox_resume_path(upload["original_name"], prefeitura_id)
        try:
            cloud_file = upload_resume_to_dropbox(upload["bytes"], dropbox_path)
        except Exception as exc:
            current_app.logger.exception("Falha ao enviar curriculo ao Dropbox.")
            flash(f"Nao foi possivel armazenar o PDF no Dropbox: {exc}", "danger")
            return render_template("agro_talento_upload.html"), 502

        resume = CurriculoAgro(
            prefeitura_id=prefeitura_id,
            criado_por_usuario_id=getattr(current_user, "id", None),
            nome=_fallback_candidate_name(upload["original_name"]),
            arquivo_nome_original=upload["original_name"],
            arquivo_mime_type="application/pdf",
            arquivo_tamanho=upload["size"],
            arquivo_sha256=upload["sha256"],
            dropbox_path=cloud_file["path"],
            dropbox_rev=cloud_file["rev"],
            analise_status=CurriculoAgro.ANALISE_PROCESSANDO,
        )
        try:
            db.session.add(resume)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            try:
                delete_resume_from_dropbox(cloud_file["path"])
            except Exception:
                current_app.logger.exception("Falha ao remover curriculo orfao do Dropbox.")
            raise

        success, error = _process_resume_analysis(resume, upload["bytes"])
        if success:
            flash("Curriculo armazenado e perfil criado pelo Gemini com sucesso.", "success")
        else:
            flash(
                "O PDF foi salvo no Dropbox, mas a analise da IA falhou. "
                "Voce pode tentar novamente na tela do candidato.",
                "warning",
            )
            current_app.logger.warning("Falha ao analisar curriculo %s: %s", resume.id, error)
        return redirect(url_for("main.agro_talento_detalhe", curriculo_id=resume.id))

    @bp.route(
        "/agro/banco-de-talentos/<int:curriculo_id>",
        methods=["GET", "POST"],
        endpoint="agro_talento_detalhe",
    )
    @login_required
    def agro_talento_detalhe(curriculo_id):
        _require_access()
        resume = _get_resume_or_404(curriculo_id)
        if request.method == "POST":
            _require_edit()
            status = (request.form.get("status") or "").strip().upper()
            if status not in CurriculoAgro.STATUS_OPTIONS:
                flash("Status do candidato invalido.", "warning")
            else:
                resume.status = status
                resume.observacoes = (request.form.get("observacoes") or "").strip() or None
                db.session.commit()
                flash("Acompanhamento do candidato atualizado.", "success")
            return redirect(url_for("main.agro_talento_detalhe", curriculo_id=resume.id))

        return render_template(
            "agro_talento_detalhe.html",
            curriculo=resume,
            status_options=CurriculoAgro.STATUS_OPTIONS,
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route(
        "/agro/banco-de-talentos/<int:curriculo_id>/pdf",
        methods=["GET"],
        endpoint="agro_talento_pdf",
    )
    @login_required
    def agro_talento_pdf(curriculo_id):
        _require_access()
        resume = _get_resume_or_404(curriculo_id)
        try:
            _metadata, file_bytes = download_resume_from_dropbox(resume.dropbox_path)
        except Exception:
            current_app.logger.exception("Falha ao baixar curriculo %s do Dropbox.", resume.id)
            abort(502, description="Nao foi possivel recuperar o PDF no Dropbox.")
        return send_file(
            BytesIO(file_bytes),
            mimetype="application/pdf",
            as_attachment=False,
            download_name=resume.arquivo_nome_original,
        )

    @bp.route(
        "/agro/banco-de-talentos/<int:curriculo_id>/reprocessar",
        methods=["POST"],
        endpoint="agro_talento_reprocessar",
    )
    @login_required
    def agro_talento_reprocessar(curriculo_id):
        _require_edit()
        resume = _get_resume_or_404(curriculo_id)
        resume.analise_status = CurriculoAgro.ANALISE_PROCESSANDO
        resume.analise_erro = None
        db.session.commit()

        try:
            _metadata, file_bytes = download_resume_from_dropbox(resume.dropbox_path)
        except Exception as exc:
            resume.analise_status = CurriculoAgro.ANALISE_ERRO
            resume.analise_erro = f"Falha ao recuperar PDF no Dropbox: {exc}"[:4000]
            db.session.commit()
            flash("Nao foi possivel recuperar o PDF no Dropbox.", "danger")
            return redirect(url_for("main.agro_talento_detalhe", curriculo_id=resume.id))

        success, error = _process_resume_analysis(resume, file_bytes)
        if success:
            flash("Perfil reprocessado pelo Gemini com sucesso.", "success")
        else:
            flash(f"A analise do Gemini falhou novamente: {error}", "warning")
        return redirect(url_for("main.agro_talento_detalhe", curriculo_id=resume.id))

    @bp.route(
        "/agro/banco-de-talentos/<int:curriculo_id>/deletar",
        methods=["POST"],
        endpoint="agro_talento_deletar",
    )
    @login_required
    def agro_talento_deletar(curriculo_id):
        _require_edit()
        resume = _get_resume_or_404(curriculo_id)
        try:
            delete_resume_from_dropbox(resume.dropbox_path)
        except Exception as exc:
            current_app.logger.exception("Falha ao excluir curriculo %s do Dropbox.", resume.id)
            flash(f"Nao foi possivel excluir o PDF do Dropbox: {exc}", "danger")
            return redirect(url_for("main.agro_talento_detalhe", curriculo_id=resume.id))

        db.session.delete(resume)
        db.session.commit()
        flash("Candidato e curriculo removidos do Banco de Talentos.", "success")
        return redirect(url_for("main.agro_talentos_listar"))
