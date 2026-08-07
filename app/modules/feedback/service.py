from datetime import datetime
import os
import uuid

from sqlalchemy import false, func, or_
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import FeedbackComentario, FeedbackComentarioAnexo, FeedbackTopico, Usuario
from app.shared.access import (
    apply_prefeitura_scope,
    get_user_regiao,
    is_admin_global_user,
    is_regional_user,
    normalize_regiao,
    normalize_role,
)
from app.shared.uploads import get_upload_folder


FEEDBACK_STATUS_OPTIONS = (
    ("aberto", "Aberto"),
    ("em_analise", "Em analise"),
    ("aguardando_info", "Aguardando informacoes"),
    ("planejado", "Planejado"),
    ("em_desenvolvimento", "Em desenvolvimento"),
    ("respondido", "Respondido"),
    ("concluido", "Concluido"),
    ("arquivado", "Arquivado"),
)

FEEDBACK_CATEGORY_OPTIONS = (
    ("sugestao", "Sugestao"),
    ("melhoria", "Melhoria"),
    ("bug", "Erro no sistema"),
    ("processo", "Processo operacional"),
    ("duvida", "Duvida"),
    ("outro", "Outro"),
)

SUPPORT_SECTOR_OPTIONS = (
    ("operacional", "Duvidas operacionais"),
    ("tecnico", "Problemas no sistema"),
)

FEEDBACK_PRIORITY_OPTIONS = (
    ("baixa", "Baixa"),
    ("media", "Media"),
    ("alta", "Alta"),
    ("urgente", "Urgente"),
)

FEEDBACK_FINAL_STATUSES = {"concluido", "arquivado"}
FEEDBACK_ACTIVE_STATUSES = tuple(status for status, _label in FEEDBACK_STATUS_OPTIONS if status not in FEEDBACK_FINAL_STATUSES)
FEEDBACK_ACCESS_TYPES = {"dev", "diretor", "admin"}
FEEDBACK_MODERATOR_TYPES = {"dev", "diretor", "admin"}
FEEDBACK_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
FEEDBACK_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg"}
FEEDBACK_MAX_IMAGES_PER_COMMENT = 6
FEEDBACK_NOTIFICATIONS_ENABLED = False


STATUS_LABELS = dict(FEEDBACK_STATUS_OPTIONS)
CATEGORY_LABELS = dict(FEEDBACK_CATEGORY_OPTIONS)
SUPPORT_SECTOR_LABELS = dict(SUPPORT_SECTOR_OPTIONS)
PRIORITY_LABELS = dict(FEEDBACK_PRIORITY_OPTIONS)


def user_role(user) -> str:
    return normalize_role(getattr(user, "tipo_usuario", None))


def get_user_support_sectors(user) -> tuple[str, ...]:
    setores = []
    if getattr(user, "suporte_operacional", False):
        setores.append("operacional")
    if getattr(user, "suporte_tecnico", False):
        setores.append("tecnico")
    return tuple(setores)


def can_attend_support(user) -> bool:
    return bool(get_user_support_sectors(user))


def can_open_support_ticket(user) -> bool:
    return is_admin_global_user(user) or is_regional_user(user) or get_feedback_owner_uvis(user) is not None


def can_access_feedback(user) -> bool:
    return is_admin_global_user(user) or can_attend_support(user) or can_open_support_ticket(user)


def can_moderate_feedback(user) -> bool:
    return is_admin_global_user(user) or can_attend_support(user)


def can_moderate_feedback_topic(user, topico) -> bool:
    support_sectors = get_user_support_sectors(user)
    if support_sectors:
        return getattr(topico, "setor_suporte", None) in support_sectors
    return is_admin_global_user(user)


def can_view_all_feedback(user) -> bool:
    return is_admin_global_user(user)


def get_feedback_owner_uvis(user):
    role = user_role(user)
    if role == "uvis":
        return user

    if role == "equipe_uvis":
        owner = getattr(user, "equipe_uvis_dona", None)
        if owner:
            return owner
        owner_id = getattr(user, "equipe_uvis_uvis_usuario_id", None)
        if owner_id:
            return Usuario.query.get(owner_id)

    return None


def build_accessible_uvis_query(user):
    role = user_role(user)

    if is_admin_global_user(user):
        return Usuario.query.filter(Usuario.tipo_usuario == "uvis").order_by(Usuario.nome_uvis.asc())

    if is_regional_user(user):
        regiao = get_user_regiao(user)
        if not regiao:
            return Usuario.query.filter(false())

        query = Usuario.query.filter(
            Usuario.tipo_usuario == "uvis",
            func.upper(func.coalesce(Usuario.regiao, "")) == regiao,
        )
        query = apply_prefeitura_scope(query, user, Usuario.prefeitura_id)
        return query.order_by(Usuario.nome_uvis.asc())

    owner = get_feedback_owner_uvis(user)
    if owner:
        return Usuario.query.filter(Usuario.id == owner.id)

    return Usuario.query.filter(false())


def get_accessible_uvis(user):
    return build_accessible_uvis_query(user).all()


def user_can_use_uvis(user, uvis_usuario) -> bool:
    if not uvis_usuario:
        return False

    if is_admin_global_user(user):
        return True

    if can_moderate_feedback(user):
        return True

    if is_regional_user(user):
        return (
            build_accessible_uvis_query(user)
            .filter(Usuario.id == uvis_usuario.id)
            .first()
            is not None
        )

    owner = get_feedback_owner_uvis(user)
    return bool(owner and owner.id == uvis_usuario.id)


def build_feedback_query(user):
    query = FeedbackTopico.query.options(
        joinedload(FeedbackTopico.uvis_usuario),
        joinedload(FeedbackTopico.criado_por),
        joinedload(FeedbackTopico.responsavel),
    )

    support_sectors = get_user_support_sectors(user)
    if support_sectors:
        return query.filter(FeedbackTopico.setor_suporte.in_(support_sectors))

    if is_admin_global_user(user):
        return query

    visibility_rules = [FeedbackTopico.criado_por_id == getattr(user, "id", None)]

    owner = get_feedback_owner_uvis(user)
    if owner:
        visibility_rules.append(FeedbackTopico.uvis_usuario_id == owner.id)

    if len(visibility_rules) == 1 and getattr(user, "id", None) is None:
        return query.filter(false())

    return query.filter(or_(*visibility_rules))


def apply_feedback_filters(query, *, q="", status="", categoria="", prioridade="", setor_suporte="", uvis_id=None):
    termo = (q or "").strip()
    if termo:
        like = f"%{termo}%"
        query = query.filter(
            or_(
                FeedbackTopico.titulo.ilike(like),
                FeedbackTopico.descricao.ilike(like),
                FeedbackTopico.uvis_nome.ilike(like),
                FeedbackTopico.regiao.ilike(like),
            )
        )

    if status in STATUS_LABELS:
        query = query.filter(FeedbackTopico.status == status)

    if categoria in CATEGORY_LABELS:
        query = query.filter(FeedbackTopico.categoria == categoria)

    if prioridade in PRIORITY_LABELS:
        query = query.filter(FeedbackTopico.prioridade == prioridade)

    if setor_suporte in SUPPORT_SECTOR_LABELS:
        query = query.filter(FeedbackTopico.setor_suporte == setor_suporte)

    if uvis_id:
        query = query.filter(FeedbackTopico.uvis_usuario_id == uvis_id)

    return query


def build_feedback_counts(user):
    query = build_feedback_query(user)
    rows = (
        query.with_entities(FeedbackTopico.status, func.count(FeedbackTopico.id))
        .group_by(FeedbackTopico.status)
        .all()
    )
    counts = {status: total for status, total in rows}
    return {
        "total": sum(counts.values()),
        "abertos": counts.get("aberto", 0),
        "em_analise": counts.get("em_analise", 0) + counts.get("aguardando_info", 0),
        "resolvidos": counts.get("concluido", 0),
    }


def build_support_notification_snapshot(user):
    if not FEEDBACK_NOTIFICATIONS_ENABLED:
        return {
            "count": 0,
            "latest_id": 0,
        }

    query = build_feedback_query(user).filter(FeedbackTopico.status.in_(FEEDBACK_ACTIVE_STATUSES))
    count = query.with_entities(func.count(FeedbackTopico.id)).scalar() or 0
    latest_id = query.with_entities(func.max(FeedbackTopico.id)).scalar() or 0
    return {
        "count": int(count),
        "latest_id": int(latest_id or 0),
    }


def get_feedback_or_404(user, topico_id):
    return build_feedback_query(user).filter(FeedbackTopico.id == topico_id).first_or_404()


def get_visible_comments(topico, user):
    comments = list(topico.comentarios)
    if can_moderate_feedback_topic(user, topico):
        return comments
    return [comment for comment in comments if not comment.interno]


def can_view_feedback_comment(comment, user) -> bool:
    if comment.interno and not can_moderate_feedback_topic(user, getattr(comment, "topico", None)):
        return False

    query = build_feedback_query(user).filter(FeedbackTopico.id == comment.topico_id)
    return query.first() is not None


def can_view_feedback_attachment(user, anexo) -> bool:
    comentario = getattr(anexo, "comentario", None)
    if comentario is None:
        return False
    return can_view_feedback_comment(comentario, user)


def can_manage_feedback_comment(user, comment) -> bool:
    if not can_view_feedback_comment(comment, user):
        return False
    return can_moderate_feedback_topic(user, getattr(comment, "topico", None)) or getattr(comment, "usuario_id", None) == getattr(user, "id", None)


def user_display_name(user) -> str:
    return (
        getattr(user, "nome_uvis", None)
        or getattr(user, "login", None)
        or f"Usuario #{getattr(user, 'id', '')}"
    )


def create_feedback_topic(user, *, uvis_usuario, titulo, descricao, categoria, prioridade, setor_suporte):
    now = datetime.now()
    topico = FeedbackTopico(
        prefeitura_id=getattr(uvis_usuario, "prefeitura_id", None),
        uvis_usuario_id=uvis_usuario.id,
        uvis_nome=uvis_usuario.nome_uvis,
        regiao=normalize_regiao(getattr(uvis_usuario, "regiao", None)) or None,
        criado_por_id=user.id,
        criado_por_nome=user_display_name(user),
        criado_por_tipo=user_role(user),
        titulo=titulo,
        descricao=descricao,
        categoria=categoria if categoria in CATEGORY_LABELS else "sugestao",
        setor_suporte=setor_suporte if setor_suporte in SUPPORT_SECTOR_LABELS else "operacional",
        prioridade=prioridade if prioridade in PRIORITY_LABELS else "media",
        status="aberto",
        criado_em=now,
        atualizado_em=now,
    )
    db.session.add(topico)
    return topico


def add_feedback_comment(user, topico, mensagem, interno=False):
    comment = FeedbackComentario(
        topico_id=topico.id,
        usuario_id=user.id,
        usuario_nome=user_display_name(user),
        usuario_tipo=user_role(user),
        mensagem=mensagem or "",
        interno=bool(interno and can_moderate_feedback_topic(user, topico)),
        criado_em=datetime.now(),
    )
    topico.atualizado_em = datetime.now()
    db.session.add(comment)
    return comment


def _feedback_attachment_directory():
    base_dir = get_upload_folder()
    relative_dir = os.path.join("feedback", "comentarios")
    absolute_dir = os.path.join(base_dir, relative_dir)
    os.makedirs(absolute_dir, exist_ok=True)
    return base_dir, absolute_dir


def _validate_feedback_image(uploaded_file):
    filename = secure_filename((getattr(uploaded_file, "filename", "") or "").strip())
    if not filename:
        raise ValueError("Selecione uma imagem valida.")

    if "." not in filename:
        raise ValueError("A imagem precisa ter extensao valida.")

    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in FEEDBACK_IMAGE_EXTENSIONS:
        raise ValueError("Use somente imagens PNG ou JPG.")

    content_type = (getattr(uploaded_file, "mimetype", None) or "").lower()
    if content_type and content_type not in FEEDBACK_IMAGE_CONTENT_TYPES:
        raise ValueError("Formato de imagem nao permitido.")

    return filename, extension, content_type or None


def save_feedback_comment_attachments(comment, uploaded_files):
    files = [item for item in (uploaded_files or []) if item and getattr(item, "filename", None)]
    if not files:
        return []

    if len(files) > FEEDBACK_MAX_IMAGES_PER_COMMENT:
        raise ValueError(f"Envie no maximo {FEEDBACK_MAX_IMAGES_PER_COMMENT} imagens por comentario.")

    upload_root, upload_dir = _feedback_attachment_directory()
    saved_items = []

    for uploaded_file in files:
        original_name, extension, content_type = _validate_feedback_image(uploaded_file)
        unique_name = secure_filename(f"feedback_comment_{comment.id}_{uuid.uuid4().hex}.{extension}")
        absolute_path = os.path.join(upload_dir, unique_name)
        uploaded_file.save(absolute_path)

        tamanho_bytes = None
        try:
            tamanho_bytes = os.path.getsize(absolute_path)
        except OSError:
            tamanho_bytes = None

        anexo = FeedbackComentarioAnexo(
            comentario_id=comment.id,
            arquivo_path=os.path.join("feedback", "comentarios", unique_name).replace("\\", "/"),
            arquivo_nome=original_name,
            mime_type=content_type,
            tamanho_bytes=tamanho_bytes,
            criado_em=datetime.now(),
        )
        db.session.add(anexo)
        saved_items.append(anexo)

    return saved_items


def resolve_feedback_attachment_file(anexo):
    relative_path = (getattr(anexo, "arquivo_path", None) or "").replace("\\", "/").strip("/")
    if not relative_path:
        raise FileNotFoundError("Arquivo nao encontrado.")

    upload_root = os.path.abspath(get_upload_folder())
    absolute_path = os.path.abspath(os.path.join(upload_root, relative_path))
    if os.path.commonpath([upload_root, absolute_path]) != upload_root:
        raise FileNotFoundError("Arquivo invalido.")
    if not os.path.isfile(absolute_path):
        raise FileNotFoundError("Arquivo nao encontrado.")

    return upload_root, relative_path, (anexo.arquivo_nome or os.path.basename(relative_path))


def remove_feedback_attachment_file(anexo):
    try:
        upload_root, relative_path, _ = resolve_feedback_attachment_file(anexo)
    except FileNotFoundError:
        return

    absolute_path = os.path.abspath(os.path.join(upload_root, relative_path))
    try:
        os.remove(absolute_path)
    except FileNotFoundError:
        return


def update_feedback_comment(comment, mensagem):
    comment.mensagem = mensagem or ""
    topico = getattr(comment, "topico", None)
    if topico is not None:
        topico.atualizado_em = datetime.now()
    return comment


def delete_feedback_comment(comment):
    topico = getattr(comment, "topico", None)
    for anexo in list(getattr(comment, "anexos", []) or []):
        remove_feedback_attachment_file(anexo)

    db.session.delete(comment)
    if topico is not None:
        topico.atualizado_em = datetime.now()


def update_feedback_status(user, topico, *, status, prioridade, responsavel_id=None):
    if status in STATUS_LABELS:
        topico.status = status
        topico.resolvido_em = datetime.now() if status in FEEDBACK_FINAL_STATUSES else None

    if prioridade in PRIORITY_LABELS:
        topico.prioridade = prioridade

    if can_moderate_feedback_topic(user, topico):
        topico.responsavel_id = responsavel_id or None

    topico.atualizado_em = datetime.now()
    return topico


def build_support_responsaveis_query(setor_suporte):
    query = Usuario.query
    if setor_suporte == "operacional":
        query = query.filter(Usuario.suporte_operacional.is_(True))
    elif setor_suporte == "tecnico":
        query = query.filter(Usuario.suporte_tecnico.is_(True))
    else:
        query = query.filter(false())
    return query.order_by(Usuario.nome_uvis.asc())
