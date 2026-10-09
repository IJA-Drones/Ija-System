import os

from app.extensions import db
from app.models import Solicitacao
from app.modules.gestao_ti.permissions import active_configuration, has_permission
from app.shared.access import can_access_regiao
from app.shared.uploads import get_upload_folder


ALLOWED_ATTACHMENT_VIEW_TYPES = {"dev", "diretor", "admin", "operario", "visualizar", "uvis", "regional"}
ALLOWED_ATTACHMENT_EDIT_TYPES = {"dev", "diretor", "admin", "operario"}


def can_view_attachment(user, pedido) -> bool:
    if active_configuration(user) is not None:
        from app.shared.access import apply_solicitacao_prefeitura_scope, apply_solicitacao_regiao_scope
        query = apply_solicitacao_regiao_scope(apply_solicitacao_prefeitura_scope(Solicitacao.query, user), user)
        return has_permission(user, "prefeitura.os.consultar") and query.filter(Solicitacao.id == pedido.id).first() is not None
    user_type = getattr(user, "tipo_usuario", None)
    if user_type not in ALLOWED_ATTACHMENT_VIEW_TYPES:
        return False
    if user_type == "uvis" and pedido.usuario_id != user.id:
        return False
    if user_type == "regional":
        pedido_regiao = getattr(getattr(pedido, "usuario", None), "regiao", None)
        return can_access_regiao(user, pedido_regiao)
    return True


def can_remove_attachment(user, pedido) -> bool:
    if active_configuration(user) is not None:
        return has_permission(user, "prefeitura.os.midias") and can_view_attachment(user, pedido)
    return getattr(user, "tipo_usuario", None) in ALLOWED_ATTACHMENT_EDIT_TYPES and can_view_attachment(user, pedido)


def resolve_attachment_file(pedido):
    if not pedido.anexo_path:
        raise FileNotFoundError("Anexo nao encontrado.")

    upload_folder = get_upload_folder()
    rel = (pedido.anexo_path or "").replace("\\", "/")
    if rel.startswith("upload-files/"):
        rel = rel.split("upload-files/", 1)[1]
    rel = os.path.basename(rel)

    file_path = os.path.join(upload_folder, rel)
    if not os.path.isfile(file_path):
        raise FileNotFoundError("Arquivo nao encontrado.")

    return upload_folder, rel, (pedido.anexo_nome or rel)


def remove_attachment(pedido):
    pedido.anexo_path = None
    pedido.anexo_nome = None
    db.session.commit()
