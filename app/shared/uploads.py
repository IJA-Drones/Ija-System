import os

from flask import current_app


ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"}


def get_upload_folder():
    """Resolve e cria a pasta padrao de uploads do projeto."""
    folder = os.path.join(current_app.root_path, "..", "upload-files")
    os.makedirs(folder, exist_ok=True)
    return os.path.abspath(folder)


def allowed_file(filename: str) -> bool:
    """Valida se a extensao do arquivo esta liberada para upload."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_UPLOAD_EXTENSIONS
