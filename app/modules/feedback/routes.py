from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, func

from app.extensions import db
from app.models import FeedbackComentarioAnexo, FeedbackTopico, Usuario
from app.modules.feedback.service import (
    CATEGORY_LABELS,
    FEEDBACK_ACTIVE_STATUSES,
    FEEDBACK_CATEGORY_OPTIONS,
    FEEDBACK_MAX_IMAGES_PER_COMMENT,
    FEEDBACK_MAX_ACTIVE_BUGS_PER_COORDINATION,
    FEEDBACK_NOTIFICATIONS_ENABLED,
    FEEDBACK_PRIORITY_OPTIONS,
    FEEDBACK_STATUS_OPTIONS,
    PRIORITY_LABELS,
    SUPPORT_SECTOR_LABELS,
    SUPPORT_SECTOR_OPTIONS,
    STATUS_LABELS,
    add_feedback_comment,
    apply_feedback_filters,
    build_feedback_query,
    build_support_notification_snapshot,
    build_support_responsaveis_query,
    can_access_feedback,
    can_manage_feedback_comment,
    can_view_feedback_attachment,
    can_moderate_feedback,
    can_moderate_feedback_topic,
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
from app.shared.access import get_user_regiao, is_covisa_user, is_dev_user, is_regional_user
from app.shared.skybox import SkyboxError, is_skybox_path, stream_skybox_file


FEEDBACK_PER_PAGE = 12
FEEDBACK_FEATURE_ENABLED = True
BUG_IMPACT_OPTIONS = (
    ("bloqueia", "Impede trabalhar"),
    ("contorno", "Atrapalha, mas dá para contornar"),
    ("visual", "Erro visual/texto"),
    ("duvida", "Dúvida se é bug"),
)
BUG_USER_STATUS_LABELS = {
    "aberto": "Recebido",
    "em_analise": "Em análise",
    "aguardando_info": "Aguardando informações",
    "planejado": "Planejado",
    "em_desenvolvimento": "Em correção",
    "respondido": "Atualizado",
    "concluido": "Corrigido",
    "arquivado": "Encerrado",
}


def _require_feedback_access():
    if not FEEDBACK_FEATURE_ENABLED:
        flash("Suporte está em desenvolvimento e ainda não foi liberado para uso.", "warning")
        return False
    if not can_access_feedback(current_user):
        flash("Suporte ainda não foi liberado para seu perfil.", "warning")
        return False
    return True


def _require_dev_bug_access():
    if not is_dev_user(current_user):
        flash("A área de tratamento de bugs é exclusiva para devs.", "warning")
        return False
    return True


def _require_bug_report_access():
    if not (is_regional_user(current_user) or is_covisa_user(current_user)):
        flash("O envio de bugs é exclusivo para a coordenadoria e COVISA.", "warning")
        return False
    return True


def _build_bug_counts(query):
    rows = (
        query.with_entities(FeedbackTopico.status, func.count(FeedbackTopico.id))
        .group_by(FeedbackTopico.status)
        .all()
    )
    counts = {status: total for status, total in rows}
    return {
        "total": sum(counts.values()),
        "abertos": counts.get("aberto", 0),
        "em_analise": counts.get("em_analise", 0)
        + counts.get("aguardando_info", 0)
        + counts.get("planejado", 0)
        + counts.get("em_desenvolvimento", 0)
        + counts.get("respondido", 0),
        "resolvidos": counts.get("concluido", 0) + counts.get("arquivado", 0),
    }


def _count_active_coordination_bugs(user):
    return (
        _build_coordination_bug_query(user)
        .filter(FeedbackTopico.status.in_(FEEDBACK_ACTIVE_STATUSES))
        .with_entities(func.count(FeedbackTopico.id))
        .scalar()
        or 0
    )


def _get_active_coordination_bugs(user):
    return (
        _build_coordination_bug_query(user)
        .filter(FeedbackTopico.status.in_(FEEDBACK_ACTIVE_STATUSES))
        .order_by(FeedbackTopico.atualizado_em.desc())
        .all()
    )


def _build_coordination_bug_query(user):
    regiao = get_user_regiao(user)
    if not regiao:
        return FeedbackTopico.query.filter(False)

    query = FeedbackTopico.query.filter_by(categoria="bug", setor_suporte="tecnico", regiao=regiao)
    if is_covisa_user(user):
        query = query.filter(FeedbackTopico.criado_por_id == getattr(user, "id", None))
    return query


def _get_coordination_bug_or_404(user, topico_id):
    return _build_coordination_bug_query(user).filter(FeedbackTopico.id == topico_id).first_or_404()


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def _clean_text(name, max_length=None):
    value = (request.form.get(name) or "").strip()
    if max_length:
        value = value[:max_length]
    return value


def _build_bug_description(descricao, impacto):
    parts = []
    if impacto:
        impacto_label = dict(BUG_IMPACT_OPTIONS).get(impacto, impacto)
        parts.append(f"Impacto: {impacto_label}")
    if parts:
        parts.append("")
    parts.append("Detalhes:")
    parts.append(descricao)
    return "\n".join(parts).strip()


def _split_bug_description(descricao):
    impacto = ""
    detalhes = []
    in_details = False

    for line in str(descricao or "").splitlines():
        clean_line = line.strip()
        clean_lower = clean_line.lower()
        if clean_lower.startswith("impacto:"):
            impacto = clean_line.split(":", 1)[1].strip()
            continue
        if clean_lower.startswith("página onde aconteceu:") or clean_lower.startswith("pagina onde aconteceu:"):
            continue
        if clean_lower.startswith("navegador/dispositivo:"):
            continue
        if clean_lower == "detalhes:":
            in_details = True
            continue
        if clean_line or in_details:
            detalhes.append(line)

    return {
        "impacto": impacto,
        "detalhes": "\n".join(detalhes).strip() or str(descricao or "").strip(),
    }


def _get_feedback_comment_or_404(topico, comment_id):
    comentario = next((item for item in topico.comentarios if item.id == comment_id), None)
    if comentario is None:
        abort(404)
    return comentario


def _abort_if_not_technical_bug(topico):
    if topico.categoria != "bug" or topico.setor_suporte != "tecnico":
        abort(404)


def register_routes(bp):
    @bp.route("/feedback/notificacoes/status", methods=["GET"], endpoint="feedback_notificacoes_status")
    @login_required
    def feedback_notificacoes_status():
        if not FEEDBACK_NOTIFICATIONS_ENABLED:
            return jsonify({"success": True, "count": 0, "latest_id": 0, "enabled": False})
        if not can_access_feedback(current_user):
            return jsonify({"success": False, "count": 0, "latest_id": 0}), 403
        snapshot = build_support_notification_snapshot(current_user)
        return jsonify({"success": True, **snapshot})

    @bp.route("/feedback", methods=["GET"], endpoint="feedback_listar")
    @login_required
    def feedback_listar():
        if not _require_dev_bug_access():
            return redirect(request.referrer or url_for("main.dashboard"))

        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip()
        categoria = "bug"
        prioridade = (request.args.get("prioridade") or "").strip()
        setor_suporte = "tecnico"
        uvis_id = request.args.get("uvis_id", type=int)
        page = request.args.get("page", 1, type=int)
        can_moderate = True

        bug_counts_query = apply_feedback_filters(
            build_feedback_query(current_user),
            categoria="bug",
            setor_suporte="tecnico",
        )
        query = build_feedback_query(current_user)
        query = apply_feedback_filters(
            query,
            q=q,
            status=status,
            categoria=categoria,
            prioridade=prioridade,
            setor_suporte=setor_suporte,
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
        uvis_options = (
            Usuario.query.filter(Usuario.tipo_usuario == "uvis").order_by(Usuario.nome_uvis.asc()).all()
            if can_moderate
            else get_accessible_uvis(current_user)
        )

        return render_template(
            "feedback_listar.html",
            paginacao=paginacao,
            feedbacks=paginacao.items,
            counts=_build_bug_counts(bug_counts_query),
            q=q,
            status=status,
            categoria=categoria,
            prioridade=prioridade,
            setor_suporte=setor_suporte,
            uvis_id=uvis_id,
            uvis_options=uvis_options,
            status_options=FEEDBACK_STATUS_OPTIONS,
            category_options=FEEDBACK_CATEGORY_OPTIONS,
            support_sector_options=SUPPORT_SECTOR_OPTIONS,
            priority_options=FEEDBACK_PRIORITY_OPTIONS,
            status_labels=STATUS_LABELS,
            category_labels=CATEGORY_LABELS,
            support_sector_labels=SUPPORT_SECTOR_LABELS,
            priority_labels=PRIORITY_LABELS,
            can_moderate=can_moderate,
            can_view_all=can_view_all_feedback(current_user),
            pagination_args=_query_args_without_page(),
        )

    @bp.route("/bugs", methods=["GET"], endpoint="bugs_listar")
    @login_required
    def bugs_listar():
        if not _require_bug_report_access():
            return redirect(request.referrer or url_for("main.dashboard"))

        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip()
        page = request.args.get("page", 1, type=int)

        query = apply_feedback_filters(
            _build_coordination_bug_query(current_user),
            q=q,
            status=status,
            categoria="",
            setor_suporte="",
        )
        if not status:
            query = query.filter(FeedbackTopico.status.in_(FEEDBACK_ACTIVE_STATUSES))

        counts = _build_bug_counts(_build_coordination_bug_query(current_user))
        active_bug_count = _count_active_coordination_bugs(current_user)
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
            "bugs_listar.html",
            paginacao=paginacao,
            bugs=paginacao.items,
            counts=counts,
            active_bug_count=active_bug_count,
            max_active_bug_count=FEEDBACK_MAX_ACTIVE_BUGS_PER_COORDINATION,
            q=q,
            status=status,
            status_options=FEEDBACK_STATUS_OPTIONS,
            status_labels=BUG_USER_STATUS_LABELS,
            priority_labels=PRIORITY_LABELS,
            pagination_args=_query_args_without_page(),
        )

    @bp.route("/bugs/ajuda", methods=["GET"], endpoint="bugs_ajuda")
    @login_required
    def bugs_ajuda():
        if not _require_bug_report_access():
            return redirect(request.referrer or url_for("main.dashboard"))

        return render_template(
            "bugs_ajuda.html",
            max_active_bug_count=FEEDBACK_MAX_ACTIVE_BUGS_PER_COORDINATION,
        )

    @bp.route("/feedback/novo", methods=["GET", "POST"], endpoint="feedback_novo")
    @bp.route("/bugs/novo", methods=["GET", "POST"], endpoint="bug_report_novo")
    @login_required
    def feedback_novo():
        if not _require_bug_report_access():
            return redirect(request.referrer or url_for("main.dashboard"))

        is_bug_report = request.endpoint == "main.bug_report_novo" or request.args.get("tipo") == "bug"
        if not is_bug_report:
            return redirect(url_for("main.bug_report_novo"))

        owner = current_user if is_covisa_user(current_user) else get_feedback_owner_uvis(current_user)
        uvis_options = (
            Usuario.query.filter(Usuario.tipo_usuario == "uvis").order_by(Usuario.nome_uvis.asc()).all()
            if can_moderate_feedback(current_user)
            else get_accessible_uvis(current_user)
        )
        form = {
            "uvis_id": owner.id if owner else request.form.get("uvis_id", type=int),
            "titulo": "",
            "descricao": "",
            "impacto": "contorno",
            "categoria": "bug" if is_bug_report else "duvida",
            "setor_suporte": "tecnico" if is_bug_report else "operacional",
            "prioridade": "media",
        }
        errors = {}
        active_bugs = _get_active_coordination_bugs(current_user)
        active_bug_count = len(active_bugs)

        if request.method == "POST":
            form.update(
                {
                    "uvis_id": owner.id if owner else request.form.get("uvis_id", type=int),
                    "titulo": _clean_text("titulo", 180),
                    "descricao": _clean_text("descricao"),
                    "impacto": _clean_text("impacto", 30),
                    "categoria": "bug" if is_bug_report else _clean_text("categoria", 30),
                    "setor_suporte": "tecnico" if is_bug_report else _clean_text("setor_suporte", 30),
                    "prioridade": _clean_text("prioridade", 20),
                }
            )
            imagens = request.files.getlist("imagens")

            if not form["titulo"]:
                errors["titulo"] = "Informe um título."
            if len(form["titulo"]) > 180:
                errors["titulo"] = "Use no máximo 180 caracteres."
            if not form["descricao"]:
                errors["descricao"] = "Descreva a dúvida ou problema."
            if form["categoria"] not in CATEGORY_LABELS:
                errors["categoria"] = "Categoria inválida."
            if form["setor_suporte"] not in SUPPORT_SECTOR_LABELS:
                errors["setor_suporte"] = "Selecione o tipo de suporte."
            if form["prioridade"] not in PRIORITY_LABELS:
                errors["prioridade"] = "Prioridade inválida."
            if form["impacto"] not in dict(BUG_IMPACT_OPTIONS):
                errors["impacto"] = "Selecione o impacto do bug."
            if active_bug_count >= FEEDBACK_MAX_ACTIVE_BUGS_PER_COORDINATION:
                errors["limite"] = (
                    f"Sua coordenadoria já possui {FEEDBACK_MAX_ACTIVE_BUGS_PER_COORDINATION} bugs em aberto. "
                    "Aguarde a conclusão de um deles antes de enviar outro."
                )

            uvis_usuario = None
            if form["uvis_id"]:
                if is_covisa_user(current_user) and form["uvis_id"] == getattr(current_user, "id", None):
                    uvis_usuario = current_user
                else:
                    uvis_usuario = Usuario.query.filter_by(id=form["uvis_id"], tipo_usuario="uvis").first()
            if not user_can_use_uvis(current_user, uvis_usuario):
                errors["uvis_id"] = "Selecione uma UVIS permitida para seu acesso."

            if not errors:
                topico = create_feedback_topic(
                    current_user,
                    uvis_usuario=uvis_usuario,
                    titulo=form["titulo"],
                    descricao=_build_bug_description(form["descricao"], form["impacto"]),
                    categoria=form["categoria"],
                    setor_suporte=form["setor_suporte"],
                    prioridade=form["prioridade"],
                )
                db.session.flush()
                if any(item and getattr(item, "filename", None) for item in imagens):
                    comentario = add_feedback_comment(current_user, topico, "Prints/anexos enviados na abertura do bug.")
                    db.session.flush()
                    try:
                        save_feedback_comment_attachments(comentario, imagens)
                    except ValueError as exc:
                        db.session.rollback()
                        flash(str(exc), "warning")
                        return render_template(
                            "feedback_form.html",
                            form=form,
                            errors=errors,
                            uvis_options=uvis_options,
                            owner=owner,
                            category_options=FEEDBACK_CATEGORY_OPTIONS,
                            support_sector_options=SUPPORT_SECTOR_OPTIONS,
                            priority_options=FEEDBACK_PRIORITY_OPTIONS,
                            is_bug_report=is_bug_report,
                            active_bug_count=active_bug_count,
                            max_active_bug_count=FEEDBACK_MAX_ACTIVE_BUGS_PER_COORDINATION,
                            active_bugs=active_bugs,
                            impact_options=BUG_IMPACT_OPTIONS,
                        )
                db.session.commit()
                flash(
                    "Reporte de bug enviado para a fila técnica dos devs."
                    if form["categoria"] == "bug" and form["setor_suporte"] == "tecnico"
                    else "Chamado aberto com sucesso.",
                    "success",
                )
                if is_bug_report:
                    if is_dev_user(current_user):
                        return redirect(url_for("main.feedback_listar"))
                    return redirect(url_for("main.bug_acompanhamento", topico_id=topico.id))
                return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

            flash("Revise os campos destacados.", "warning")
            if errors.get("limite"):
                flash(errors["limite"], "warning")

        return render_template(
            "feedback_form.html",
            form=form,
            errors=errors,
            uvis_options=uvis_options,
            owner=owner,
            category_options=FEEDBACK_CATEGORY_OPTIONS,
            support_sector_options=SUPPORT_SECTOR_OPTIONS,
            priority_options=FEEDBACK_PRIORITY_OPTIONS,
            is_bug_report=is_bug_report,
            active_bug_count=active_bug_count,
            max_active_bug_count=FEEDBACK_MAX_ACTIVE_BUGS_PER_COORDINATION,
            active_bugs=active_bugs,
            impact_options=BUG_IMPACT_OPTIONS,
        )

    @bp.route("/feedback/<int:topico_id>", methods=["GET"], endpoint="feedback_detalhe")
    @login_required
    def feedback_detalhe(topico_id):
        if not _require_dev_bug_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)
        _abort_if_not_technical_bug(topico)
        can_moderate_topico = can_moderate_feedback_topic(current_user, topico)

        return render_template(
            "feedback_detalhe.html",
            topico=topico,
            comentarios=get_visible_comments(topico, current_user),
            max_images_per_comment=FEEDBACK_MAX_IMAGES_PER_COMMENT,
            status_options=FEEDBACK_STATUS_OPTIONS,
            priority_options=FEEDBACK_PRIORITY_OPTIONS,
            status_labels=STATUS_LABELS,
            category_labels=CATEGORY_LABELS,
            support_sector_labels=SUPPORT_SECTOR_LABELS,
            priority_labels=PRIORITY_LABELS,
            can_moderate=can_moderate_topico,
            can_view_all=can_view_all_feedback(current_user),
            responsaveis=build_support_responsaveis_query(topico.setor_suporte).all()
            if can_moderate_topico
            else [],
            bug_report=_split_bug_description(topico.descricao),
        )

    @bp.route("/bugs/<int:topico_id>/acompanhar", methods=["GET"], endpoint="bug_acompanhamento")
    @login_required
    def bug_acompanhamento(topico_id):
        if not _require_bug_report_access():
            return redirect(request.referrer or url_for("main.dashboard"))

        topico = _get_coordination_bug_or_404(current_user, topico_id)
        _abort_if_not_technical_bug(topico)

        return render_template(
            "bug_acompanhamento.html",
            topico=topico,
            atualizacoes=get_visible_comments(topico, current_user),
            status_labels=BUG_USER_STATUS_LABELS,
            priority_labels=PRIORITY_LABELS,
            bug_report=_split_bug_description(topico.descricao),
        )

    @bp.route("/feedback/<int:topico_id>/status", methods=["GET"], endpoint="feedback_status")
    @login_required
    def feedback_status(topico_id):
        if not is_dev_user(current_user):
            return jsonify({"success": False}), 403

        topico = get_feedback_or_404(current_user, topico_id)
        _abort_if_not_technical_bug(topico)
        comentarios = get_visible_comments(topico, current_user)
        return jsonify(
            {
                "success": True,
                "topico_id": topico.id,
                "updated_at": topico.atualizado_em.isoformat() if topico.atualizado_em else "",
                "comment_count": len(comentarios) + 1,
                "status": topico.status,
            }
        )

    @bp.route("/feedback/<int:topico_id>/comentar", methods=["POST"], endpoint="feedback_comentar")
    @login_required
    def feedback_comentar(topico_id):
        if not _require_dev_bug_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)
        _abort_if_not_technical_bug(topico)
        mensagem = _clean_text("mensagem")
        interno = request.form.get("interno") == "1"
        imagens = request.files.getlist("imagens")

        if not mensagem and not any(item and getattr(item, "filename", None) for item in imagens):
            flash("Escreva um comentário ou envie ao menos uma imagem.", "warning")
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
        flash("Comentário registrado.", "success")
        return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

    @bp.route("/feedback/anexos/<int:anexo_id>", methods=["GET"], endpoint="feedback_anexo")
    @login_required
    def feedback_anexo(anexo_id):
        anexo = FeedbackComentarioAnexo.query.get_or_404(anexo_id)
        topico = getattr(getattr(anexo, "comentario", None), "topico", None)
        if topico is None:
            abort(404)
        _abort_if_not_technical_bug(topico)

        can_view_as_dev = is_dev_user(current_user) and can_view_feedback_attachment(current_user, anexo)
        can_view_as_coordination = False
        if not getattr(getattr(anexo, "comentario", None), "interno", False):
            if is_regional_user(current_user):
                can_view_as_coordination = topico.regiao == get_user_regiao(current_user)
            elif is_covisa_user(current_user):
                can_view_as_coordination = getattr(topico, "criado_por_id", None) == getattr(current_user, "id", None)
        if not can_view_as_dev and not can_view_as_coordination:
            abort(403)

        if is_skybox_path(anexo.arquivo_path):
            try:
                return stream_skybox_file(
                    anexo.arquivo_path,
                    request.headers.get("Range"),
                    as_attachment=False,
                )
            except SkyboxError as exc:
                current_app.logger.warning(
                    "Falha ao abrir anexo do Skybox do feedback %s: %s",
                    anexo.id,
                    exc,
                )
                abort(404)

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
        if not _require_dev_bug_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)
        _abort_if_not_technical_bug(topico)
        comentario = _get_feedback_comment_or_404(topico, comment_id)
        if not can_manage_feedback_comment(current_user, comentario):
            abort(403)

        mensagem = _clean_text("mensagem")
        if not mensagem and not comentario.anexos:
            flash("O comentário não pode ficar vazio.", "warning")
            return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

        update_feedback_comment(comentario, mensagem)
        db.session.commit()
        flash("Comentário atualizado.", "success")
        return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

    @bp.route("/feedback/<int:topico_id>/comentarios/<int:comment_id>/apagar", methods=["POST"], endpoint="feedback_comentario_apagar")
    @login_required
    def feedback_comentario_apagar(topico_id, comment_id):
        if not _require_dev_bug_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)
        _abort_if_not_technical_bug(topico)
        comentario = _get_feedback_comment_or_404(topico, comment_id)
        if not can_manage_feedback_comment(current_user, comentario):
            abort(403)

        delete_feedback_comment(comentario)
        db.session.commit()
        flash("Comentário apagado.", "success")
        return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

    @bp.route("/feedback/<int:topico_id>/atualizar", methods=["POST"], endpoint="feedback_atualizar")
    @login_required
    def feedback_atualizar(topico_id):
        if not _require_dev_bug_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)
        _abort_if_not_technical_bug(topico)
        if not can_moderate_feedback_topic(current_user, topico):
            abort(403)

        status = _clean_text("status", 30)
        prioridade = _clean_text("prioridade", 20)
        responsavel_id = request.form.get("responsavel_id", type=int)
        mensagem_status = _clean_text("mensagem_status")
        interno = request.form.get("mensagem_interna") == "1"

        if status not in STATUS_LABELS or prioridade not in PRIORITY_LABELS:
            flash("Status ou prioridade inválida.", "warning")
            return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

        responsavel = None
        if responsavel_id:
            responsavel = build_support_responsaveis_query(topico.setor_suporte).filter(Usuario.id == responsavel_id).first()
            if responsavel is None:
                flash("Responsável inválido para este setor de suporte.", "warning")
                return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

        update_feedback_status(
            current_user,
            topico,
            status=status,
            prioridade=prioridade,
            responsavel_id=responsavel.id if responsavel else None,
        )
        if mensagem_status:
            add_feedback_comment(current_user, topico, mensagem_status, interno=interno)

        db.session.commit()
        flash("Feedback atualizado.", "success")
        return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

    @bp.route("/feedback/<int:topico_id>/assumir", methods=["POST"], endpoint="feedback_assumir")
    @login_required
    def feedback_assumir(topico_id):
        if not _require_dev_bug_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)
        _abort_if_not_technical_bug(topico)

        update_feedback_status(
            current_user,
            topico,
            status="em_analise",
            prioridade=topico.prioridade,
            responsavel_id=current_user.id,
        )
        add_feedback_comment(current_user, topico, "Bug recebido pelo suporte técnico e em análise.")
        db.session.commit()
        flash("Bug assumido.", "success")
        return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

    @bp.route("/feedback/<int:topico_id>/corrigir", methods=["POST"], endpoint="feedback_corrigir")
    @login_required
    def feedback_corrigir(topico_id):
        if not _require_dev_bug_access():
            return redirect(request.referrer or url_for("main.dashboard"))
        topico = get_feedback_or_404(current_user, topico_id)
        _abort_if_not_technical_bug(topico)

        mensagem = _clean_text("mensagem_conclusao")
        if not mensagem:
            flash("Informe o que foi corrigido antes de encerrar o bug.", "warning")
            return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))

        update_feedback_status(
            current_user,
            topico,
            status="concluido",
            prioridade=topico.prioridade,
            responsavel_id=topico.responsavel_id or current_user.id,
        )
        add_feedback_comment(current_user, topico, mensagem)
        db.session.commit()
        flash("Bug marcado como corrigido.", "success")
        return redirect(url_for("main.feedback_detalhe", topico_id=topico.id))
