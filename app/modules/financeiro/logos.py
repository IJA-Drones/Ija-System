"""Company logos use the same authenticated Skybox storage as other media."""
from io import BytesIO
from uuid import uuid4

from flask import current_app
from requests import RequestException
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.shared.skybox import SkyboxError, delete_skybox_file, upload_file_to_skybox


def upload_company_logo(empresa_slug, data):
    path = f"financeiro/empresas/{secure_filename(empresa_slug)}/logos/{uuid4().hex}.png"
    storage = FileStorage(stream=BytesIO(data), filename="logo.png", content_type="image/png")
    try:
        return upload_file_to_skybox(storage, path)
    except (SkyboxError, RequestException) as exc:
        raise SkyboxError("Não foi possível enviar a logo ao Skybox. Tente novamente.") from exc


def cleanup_company_logo(path):
    if not path:
        return
    try:
        delete_skybox_file(path)
    except (SkyboxError, RequestException):
        current_app.logger.exception("Falha ao limpar logo antiga no Skybox: %s", path)
