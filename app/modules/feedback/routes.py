from flask import abort, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy import case

from app.extensions import db
from app.models import FeedbackComentarioAnexo, FeedbackTopico, Usuario
from app.modules.feedback.service import (
    CATEGORY_LABELS,
    FEEDBACK_CATEGORY_OPTIONS,
    FEEDBACK_MAX_IMAGES_PER_COMMENT,
    FEEDBACK_PRIORITY_OPTIONS,
    FEEDBACK_STATUS_OPTIONS,
    PRIORITY_LABELS,
    STATUS_LABELS,
    add_feedback_comment,
    apply_feedback_filters,
    build_accessible_uvis_query,
    build_feedback_counts,
    build_feedback_query,
    can_access_feedback,
    can_manage_feedback_comment,
    can_view_feedback_attachment,
    can_moderate_feedback,
    can_view_all_feedback,
    create_feedback_topic,
    delete_feedback_comment,
    get_accessible_uvis,
    get_feedback_or_404,
    get_feedback_owner_uvis,
    get_visible_comments,
    resolve_feedback_attachment_file,
    save_feedback_comment_attachments,
    update_feedback_comment,
    update_feedback_status,
    user_can_use_uvis,
)


FEEDBACK_PER_PAGE = 12
FEEDBACK_FEATURE_ENABLED = True


def _require_feedback_access():
    if not FEEDBACK_FEATURE_ENABLED:
        flash("Feedback esta em desenvolvimento e ainda nao foi liberado para uso.", "warning")
        return False
    if not can_access_feedback(current_user):
        flash("Feedback esta em desenvolvimento e ainda nao foi liberado para seu perfil.", "warning")
        return False
    return True


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def _clean_text(name, max_length=None):
    value = (request.form.get(name) or "").strip()
    if max_length:
        value = value[:max_length]
    return value


def _get_feedback_comment_or_404(topico, comment_id):
    comentario = next((item for item in topico.comentarios if item.id == comment_id), None)
    if comentario is None:
        abort(404)
    return comentario


def register_routes(bp):
    @bp.route("/feedback", methods=["GET"], endpoint="feedback_listar")
    @login_required
    def feedback_listar():
        if not _require_feedback_access():
            return redirect(request.referrer or url_for("main.dashboard"))

        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip()
        categoria = (request.args.get("categoria") or "").strip()
        prioridade = (request.args.get("prioridade") or "").strip()
        uvis_id = request.args.get("uvis_id", type=int)
        page = request.args.get("page", 1, type=int)

        if uvis_id and not build_accessible_uvis_query(current_user).filter(Usuario.id == uvis_id).first():
            uvis_id = None

        query = build_feedback_query(current_user)
        query = apply_feedback_filters(
            query,
            q=q,
            status=status,
            categoria=categoria,
            prioridade=prioridade,
            uvis_id=uvis_id,
        )
        paginacao = query.order_by(
            case(
                {
                    "aberto": 1,
                    "aguardando_info": 2,
                    "em_analise": 3,
                    "planejado": 4,
                    "em_desenvolvimento": 5,
                    "respondido": 6,
                    "concluido": 7,
                    "arquivado": 8,
                },
                value=FeedbackTopico.status,
                else_=99,
            ),
            FeedbackTopico.atualizado_em.desc(),
        ).paginate(page=page, per_page=FEEDBACK_PER_PAGE, error_out=False)

        return render_template(
            "feedback_listar.html",
            paginacao=paginacao,
            feedbacks=paginacao.items,
            counts=build_feedback_counts(current_user),
            q=q,
            status=status,
            categoria=categoria,
            prioridade=prioridade,
            uvis_id=uvis_id,
            uvis_options=get_accessible_uvis(current_user),
            status_options=FEEDBACK_STATUS_OPTIONS,
            category_options=FEEDBACK_CATEGORY_OPTIONS,
            priority_options=FEEDBACK_PRIORITY_OPTIONS,
            status_labels=STATUS_LABELS,
            category_labels=CATEGORY_LABELS,
            priority_labels=PRIORITY_LABELS,
            can_moderate=can_moderate_feedback(current_user),
            can_view_all=can_view_all_feedback(current_user),
            pagination_args=_query_args_without_page(),
        )

    @bp.route("/feedback/novo", methods=["GET", "POST"], endpoint="feedback_novo")
    @login_required
    def feedback_novo():
        if not _require_feedback_access():
            return redirect(request.referrer or url_for("main.dashboard"))

        owner = get_feedback_owner_uvis(current_user)
        uvis_options = get_accessible_uvis(current_user)
        form = {
            "uvis_id": owner.id if owner else request.form.get("uvis_id", type=int),
            "titulo": "",
            "descricao": "",
            "categoria": "sugestao",
            "prioridade": "media",
        }
        errors = {}

        if request.method == "POST":
            form.update(
                {
                    "uvis_id": owner.id if owner else request.form.get("uvis_id", type=int),
                    "titulo": _clean_text("titulo", 180),
                    "descricao": _clean_text("descricao"),
                    "categoria": _clean_text("categoria", 30),
                    "prioridade": _clean_text("prioridade", 20),
                }
            )

            if not form["titulo"]:
                errors["titulo"] = "Informe um titulo."
            if len(form["titulo"]) > 180:
                errors["titulo"] = "Use no maximo 180 caracteres."
            if not form["descricao"]:
                errors["descricao"] = "Descreva a sugestao ou feedback."
            if form["categoria"] not in CATEGORY_LABELS:
                errors["categoria"] = "Categoria invalida."
            if form["prioridade"] not in PRIORITY_LABELS:
                errors["prioridade"] = "Prioridade invalida."

            uvis_usuario = None
            if form["uvis_id"]:
                uvis_usuario = Usuario.query.filter_by(id=form["uvis_id"], tipo_usuario="uvis").first()
            if not user_can_use_uvis(current_user, uvis_usuario):
                errors["uvis_id"] = "Selecione uma UVIS permitida para seu acesso."

            if not errors:
                create_feedback_topic(
                    current_user,
                    uvis_usuario=uvis_usuario,
                    titulo=form["titulo"],
                    descricao=form["descricao"],
                    categoria=form["categoria"],
                    prioridade=form["prioridade"],
                )
                db.session.commit()
                flash("Feedback enviado com sucesso.", "success")
                return redirect(url_for("main.feedback_listar"))

            flash("Revise os campos destacados.", "warning")

        return render_template(
            "feedback_form.html",
            form=form,
            errors=errors,
            uvis_options=uvis_options,
            owner=owner,
            category_options=FEEDBACK_CATEGORY_OPTIONS,
            priority_options=FEEDBACK_PRIORITY_OPTIONS,
        )

    @bp.route("/feedback/<int:topico_id>", methods=["GET"], endpoint="feedback_detalhe")
    @login_required
    def feedback_detalhe(topico_id):
        if not _require_feedback_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)

        return render_template(
            "feedback_detalhe.html",
            topico=topico,
            comentarios=get_visible_comments(topico, current_user),
            max_images_per_comment=FEEDBACK_MAX_IMAGES_PER_COMMENT,
            status_options=FEEDBACK_STATUS_OPTIONS,
            priority_options=FEEDBACK_PRIORITY_OPTIONS,
            status_labels=STATUS_LABELS,
            category_labels=CATEGORY_LABELS,
            priority_labels=PRIORITY_LABELS,
            can_moderate=can_moderate_feedback(current_user),
            can_view_all=can_view_all_feedback(current_user),
            responsaveis=Usuario.query.filter(Usuario.tipo_usuario.in_(["dev", "admin"])).order_by(Usuario.nome_uvis.asc()).all()
            if can_view_all_feedback(current_user)
            else [],
        )

    @bp.route("/feedback/<int:topico_id>/comentar", methods=["POST"], endpoint="feedback_comentar")
    @login_required
    def feedback_comentar(topico_id):
        if not _require_feedback_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)
        mensagem = _clean_text("mensagem")
        interno = request.form.get("interno") == "1"
        imagens = request.files.getlist("imagens")

        if not mensagem and not any(item and getattr(item, "filename", None) for item in imagens):
            flash("Escreva um comentario ou envie ao menos uma imagem.", "warning")
            return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

        comentario = add_feedback_comment(current_user, topico, mensagem, interno=interno)
        db.session.flush()
        try:
            save_feedback_comment_attachments(comentario, imagens)
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "warning")
            return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))
        db.session.commit()
        flash("Comentario registrado.", "success")
        return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

    @bp.route("/feedback/anexos/<int:anexo_id>", methods=["GET"], endpoint="feedback_anexo")
    @login_required
    def feedback_anexo(anexo_id):
        if not _require_feedback_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        anexo = FeedbackComentarioAnexo.query.get_or_404(anexo_id)
        if not can_view_feedback_attachment(current_user, anexo):
            abort(403)

        try:
            upload_root, relative_path, download_name = resolve_feedback_attachment_file(anexo)
        except FileNotFoundError:
            abort(404)

        return send_from_directory(
            upload_root,
            relative_path,
            as_attachment=False,
            download_name=download_name,
        )

    @bp.route("/feedback/<int:topico_id>/comentarios/<int:comment_id>/editar", methods=["POST"], endpoint="feedback_comentario_editar")
    @login_required
    def feedback_comentario_editar(topico_id, comment_id):
        if not _require_feedback_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)
        comentario = _get_feedback_comment_or_404(topico, comment_id)
        if not can_manage_feedback_comment(current_user, comentario):
            abort(403)

        mensagem = _clean_text("mensagem")
        if not mensagem and not comentario.anexos:
            flash("O comentario nao pode ficar vazio.", "warning")
            return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

        update_feedback_comment(comentario, mensagem)
        db.session.commit()
        flash("Comentario atualizado.", "success")
        return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

    @bp.route("/feedback/<int:topico_id>/comentarios/<int:comment_id>/apagar", methods=["POST"], endpoint="feedback_comentario_apagar")
    @login_required
    def feedback_comentario_apagar(topico_id, comment_id):
        if not _require_feedback_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)
        comentario = _get_feedback_comment_or_404(topico, comment_id)
        if not can_manage_feedback_comment(current_user, comentario):
            abort(403)

        delete_feedback_comment(comentario)
        db.session.commit()
        flash("Comentario apagado.", "success")
        return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

    @bp.route("/feedback/<int:topico_id>/atualizar", methods=["POST"], endpoint="feedback_atualizar")
    @login_required
    def feedback_atualizar(topico_id):
        if not _require_feedback_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        if not can_moderate_feedback(current_user):
            abort(403)

        topico = get_feedback_or_404(current_user, topico_id)
        status = _clean_text("status", 30)
        prioridade = _clean_text("prioridade", 20)
        responsavel_id = request.form.get("responsavel_id", type=int)
        mensagem_status = _clean_text("mensagem_status")
        interno = request.form.get("mensagem_interna") == "1"

        if status not in STATUS_LABELS or prioridade not in PRIORITY_LABELS:
            flash("Status ou prioridade invalida.", "warning")
            return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

        update_feedback_status(
            current_user,
            topico,
            status=status,
            prioridade=prioridade,
            responsavel_id=responsavel_id,
        )
        if mensagem_status:
            add_feedback_comment(current_user, topico, mensagem_status, interno=interno)

        db.session.commit()
        flash("Feedback atualizado.", "success")
        return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))
