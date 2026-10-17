"""Configuração municipal isolada dos exportadores PDF."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings

from flask import abort, current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from requests import RequestException
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Prefeitura, PrefeituraDocumentoConfig, PrefeituraDocumentoHistorico, Usuario
from app.modules.gestao_ti.permissions import has_permission
from app.shared.access import is_covisa_user, is_dev_user
from app.shared.skybox import SkyboxError, delete_skybox_file, is_skybox_path, skybox_enabled, upload_file_to_skybox


MAX_IMAGE_BYTES = 5 * 1024 * 1024
DEFAULTS = dict(ativo=False, imagem_nome=None, opacidade=12, largura_percentual=55, identificar_usuario=False)


class ConfigValidationError(ValueError):
    pass


class ConfigConflictError(ValueError):
    pass


def require_access(user, *, write=False):
    permission = "prefeitura.documentos.configurar" if write else "prefeitura.documentos.consultar"
    if not has_permission(user, permission, legacy=is_dev_user(user) or is_covisa_user(user)):
        abort(403)


def prefeituras_permitidas(user):
    require_access(user)
    query = Prefeitura.query
    if not is_dev_user(user):
        # Use the persisted account association, never a posted municipality.
        query = query.join(Usuario, Usuario.prefeitura_id == Prefeitura.id).filter(Usuario.id == user.id)
    return query.order_by(Prefeitura.nome, Prefeitura.id)


def prefeitura_permitida(user, prefeitura_id):
    prefeitura = prefeituras_permitidas(user).filter(Prefeitura.id == prefeitura_id).first()
    if prefeitura is None:
        abort(404)
    return prefeitura


def snapshot(config):
    return {key: getattr(config, key) for key in DEFAULTS} if config else dict(DEFAULTS)


def _integer(form, field, minimum, maximum, label):
    try:
        value = int(form.get(field, ""))
    except (ValueError, TypeError):
        raise ConfigValidationError(f"Informe {label} entre {minimum} e {maximum}.")
    if not minimum <= value <= maximum:
        raise ConfigValidationError(f"Informe {label} entre {minimum} e {maximum}.")
    return value


def normalize_image(upload):
    name = secure_filename(upload.filename or "")
    if Path(name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ConfigValidationError("Envie uma imagem PNG, JPG ou WebP.")
    raw = upload.stream.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise ConfigValidationError("A imagem deve ter no máximo 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"} or getattr(image, "n_frames", 1) != 1:
                    raise ConfigValidationError("Use uma imagem estática PNG, JPG ou WebP.")
                if max(image.size) > 4096 or image.width * image.height > 16_000_000:
                    raise ConfigValidationError("Use uma imagem de até 4096 pixels por lado e 16 megapixels.")
                image.load()
                normalized = ImageOps.exif_transpose(image).convert("RGBA")
                normalized.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                # Copy pixels into a fresh image to strip embedded metadata.
                clean = Image.new("RGBA", normalized.size)
                clean.paste(normalized)
                out = BytesIO()
                clean.save(out, format="PNG")
                return out.getvalue(), name[:180]
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        if isinstance(exc, ConfigValidationError):
            raise
        raise ConfigValidationError("Não foi possível ler a imagem. Envie um PNG, JPG ou WebP válido.") from exc


def local_image_path(path):
    root = Path(current_app.instance_path) / "documentos_marca_dagua"
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ConfigValidationError("Caminho de imagem inválido.")
    return target


def store_image(prefeitura_id, data):
    if not skybox_enabled():
        raise SkyboxError("Configure o Skybox para salvar a imagem da prefeitura.")
    path = f"prefeituras_logo/{prefeitura_id}/{uuid4().hex}.png"
    upload = FileStorage(stream=BytesIO(data), filename="marca-dagua.png", content_type="image/png")
    return upload_file_to_skybox(upload, path)


def cleanup_image(path):
    if not path:
        return
    try:
        if is_skybox_path(path):
            delete_skybox_file(path)
        else:
            from app.shared.file_recovery import remove_file
            remove_file(local_image_path(path))
    except (SkyboxError, RequestException, OSError, ConfigValidationError):
        current_app.logger.exception("Não foi possível remover imagem de configuração substituída.")


def save_config(user, prefeitura_id, form, upload):
    require_access(user, write=True)
    prefeitura_permitida(user, prefeitura_id)
    config = db.session.get(PrefeituraDocumentoConfig, prefeitura_id)
    version = _integer(form, "versao", 0, 2147483647, "uma versão válida")
    if version != (config.versao if config else 0):
        raise ConfigConflictError("Outra pessoa alterou esta configuração. Recarregue a página antes de salvar.")
    values = {
        "ativo": form.get("ativo") == "1",
        "identificar_usuario": form.get("identificar_usuario") == "1",
        "opacidade": _integer(form, "opacidade", 5, 30, "a intensidade"),
        "largura_percentual": _integer(form, "largura_percentual", 25, 80, "o tamanho"),
    }
    remove = form.get("remover_imagem") == "1"
    has_upload = bool(upload and upload.filename)
    if remove and has_upload:
        raise ConfigValidationError("Escolha entre substituir a imagem ou removê-la.")
    old_path = config.imagem_path if config else None
    if values["ativo"] and not (values["identificar_usuario"] or has_upload or (old_path and not remove)):
        raise ConfigValidationError("Para ativar, envie uma imagem ou habilite a identificação do usuário.")
    image = normalize_image(upload) if has_upload else None
    before = snapshot(config)
    new_path = None
    try:
        if image:
            new_path = store_image(prefeitura_id, image[0])
        if config is None:
            config = PrefeituraDocumentoConfig(prefeitura_id=prefeitura_id)
            db.session.add(config)
        for key, value in values.items():
            setattr(config, key, value)
        if image or remove:
            config.imagem_path = new_path
            config.imagem_nome = image[1] if image else None
        config.atualizado_em = datetime.now()
        after = snapshot(config)
        # Record replacement even when the uploaded filename is unchanged.
        after["imagem_alterada"] = bool(image or (remove and old_path))
        db.session.add(PrefeituraDocumentoHistorico(
            prefeitura_id=prefeitura_id, usuario_id=user.id,
            usuario_nome=(user.nome_uvis or user.login)[:100], antes=before, depois=after,
        ))
        db.session.commit()
    except (SQLAlchemyError, SkyboxError, RequestException, OSError):
        db.session.rollback()
        cleanup_image(new_path)
        raise
    if (image or remove) and old_path:
        cleanup_image(old_path)
    return config
