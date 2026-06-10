import os

from app.extensions import db
from app.shared.access import can_access_regiao
from app.shared.uploads import get_upload_folder


ALLOWED_ATTACHMENT_VIEW_TYPES = {"dev", "admin", "operario", "visualizar", "uvis", "regional"}
ALLOWED_ATTACHMENT_EDIT_TYPES = {"dev", "admin", "operario"}


def can_view_attachment(user, pedido) -> bool:
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
