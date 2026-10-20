"""Derivados sem metadados pessoais; armazenamento privado e entrega por publicação."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import warnings
from uuid import uuid4

from flask import abort, current_app, request, send_file
from flask_login import current_user
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.shared import skybox
from .models import AcaoPublicaMidia, now
from .service import ActionError, event, text, version

MAX_FILE = 50 * 1024 * 1024
MAX_IMAGE = 10 * 1024 * 1024
MAX_SELECTED = 5
MAX_RETAINED = 20


def sanitize(upload):
    data = upload.stream.read(MAX_FILE + 1)
    if not data or len(data) > MAX_FILE:
        raise ActionError('Envie uma imagem de até 10 MiB ou um vídeo MP4 de até 50 MiB.')
    if len(data) >= 12 and data[4:8] == b'ftyp':
        executable = current_app.config.get('FFMPEG_PATH') or os.getenv('FFMPEG_PATH') or shutil.which('ffmpeg')
        if not executable or not Path(executable).is_file():
            raise ActionError('O processamento de vídeos precisa do FFmpeg configurado no servidor. As imagens continuam disponíveis.')
        with tempfile.TemporaryDirectory(prefix='ija-public-video-') as directory:
            source, target = Path(directory)/'source.mp4', Path(directory)/'public.mp4'
            source.write_bytes(data)
            try:
                subprocess.run([executable, '-nostdin', '-v', 'error', '-y', '-protocol_whitelist', 'file,pipe',
                    '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?', '-map_metadata', '-1',
                    '-map_metadata:s', '-1', '-map_chapters', '-1', '-sn', '-dn', '-c', 'copy',
                    '-movflags', '+faststart', str(target)], check=True, capture_output=True, timeout=25)
                result = target.read_bytes()
            except (OSError, subprocess.SubprocessError) as exc:
                raise ActionError('Não foi possível preparar o MP4. Confira o formato e tente novamente.') from exc
        if not result or len(result) > MAX_FILE:
            raise ActionError('O vídeo preparado ultrapassou 50 MiB.')
        return result, 'video/mp4', 'mp4'
    if len(data) > MAX_IMAGE:
        raise ActionError('As imagens precisam ter até 10 MiB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {'PNG', 'JPEG', 'WEBP'} or source.width * source.height > 20_000_000:
                    raise ActionError('Use PNG, JPG ou WebP com até 20 megapixels.')
                source.load()
                image = ImageOps.exif_transpose(source).convert('RGB')
                image.thumbnail((1920, 1920))
                # New image, no source EXIF, GPS, filenames, comments or ICC data.
                clean = Image.new('RGB', image.size)
                clean.paste(image)
                output = io.BytesIO()
                clean.save(output, format='JPEG', quality=88, optimize=True)
                return output.getvalue(), 'image/jpeg', 'jpg'
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ActionError('Não foi possível ler a imagem. Use um PNG, JPG ou WebP válido.') from exc


def local_path(marker):
    root = Path(current_app.config.get('ACOES_PUBLICAS_UPLOAD_DIR') or Path(current_app.root_path).parent/'upload-files'/'acoes-publicas').resolve()
    candidate = (root / marker).resolve()
    if not candidate.is_relative_to(root) or candidate == root or '..' in Path(marker).parts:
        raise ActionError('Arquivo indisponível.')
    return candidate


def store(data, municipality, identifier, extension):
    relative = f'{municipality}/{identifier}.{extension}'
    if skybox.skybox_enabled():
        namespace = hashlib.sha256(str(db.engine.url).encode()).hexdigest()[:16]
        try:
            return skybox.upload_file_to_skybox(FileStorage(stream=io.BytesIO(data), filename=f'{identifier}.{extension}'),
                f'acoes-publicas/{namespace}/{relative}')
        except skybox.SkyboxError as exc:
            raise ActionError('O armazenamento está indisponível. Tente adicionar a mídia novamente.') from exc
    target = local_path(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    from app.shared.file_recovery import save_file
    try:
        save_file(FileStorage(stream=io.BytesIO(data)), target)
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise ActionError('Não foi possível armazenar a mídia. Tente novamente.') from exc
    # Absolute paths allow the existing recovery tracker to find this reference.
    return str(target)


def cleanup(marker):
    try:
        if skybox.is_skybox_path(marker):
            skybox.delete_skybox_file(marker)
        else:
            from app.shared.file_recovery import remove_file
            remove_file(local_path(marker))
    except Exception:
        current_app.logger.warning('Ações públicas: cópia não vinculada aguarda recuperação de arquivos.')


def add(row, upload, form):
    version(row, form.get('versao'))
    if row.status == 'EM_REVISAO':
        raise ActionError('Devolva a ação ao rascunho antes de alterar mídias.')
    if sum(item.selecionada for item in row.midias) >= MAX_SELECTED or len(row.midias) >= MAX_RETAINED:
        raise ActionError('Cada publicação aceita até cinco mídias; o histórico desta ação conserva até vinte arquivos.')
    caption = text(form.get('legenda'), 'a legenda pública', 240)
    identifier, expected_version = row.id, row.versao
    municipality, actor = row.prefeitura_id, current_user.id
    # Finish the read transaction before processing/uploading a potentially large file.
    db.session.commit()
    data, mime, extension = sanitize(upload)
    media_id, stored = uuid4().hex, None
    try:
        stored = store(data, municipality, media_id, extension)
        from .service import scoped_action
        row = scoped_action(identifier)
        db.session.refresh(row)
        version(row, str(expected_version))
        if row.status == 'EM_REVISAO' or sum(item.selecionada for item in row.midias) >= MAX_SELECTED or len(row.midias) >= MAX_RETAINED:
            raise ActionError('A ação mudou durante o envio. Recarregue antes de adicionar o arquivo.')
        row.midias.append(AcaoPublicaMidia(id=media_id, acao_id=row.id, prefeitura_id=municipality,
            stored_path=stored, mime=mime, legenda=caption, sha256=hashlib.sha256(data).hexdigest(),
            tamanho=len(data), criado_por_id=actor))
        row.status, row.atualizado_em = 'RASCUNHO', now()
        event(row, 'MIDIA_ADICIONADA')
        db.session.commit()
    except Exception:
        db.session.rollback()
        if stored:
            cleanup(stored)
        raise


def remove(row, media_id, form):
    version(row, form.get('versao'))
    if row.status == 'EM_REVISAO':
        raise ActionError('Devolva a ação ao rascunho antes de alterar mídias.')
    item = next((item for item in row.midias if item.id == media_id and item.selecionada), None)
    if item is None:
        abort(404)
    item.selecionada = False
    row.status, row.atualizado_em = 'RASCUNHO', now()
    event(row, 'MIDIA_REMOVIDA_RASCUNHO')
    db.session.commit()


def serve(item):
    if skybox.is_skybox_path(item.stored_path):
        try:
            response = skybox.stream_skybox_file(item.stored_path, request.headers.get('Range'))
        except skybox.SkyboxError:
            abort(503, description='A mídia está temporariamente indisponível.')
    else:
        try:
            response = send_file(local_path(item.stored_path), mimetype=item.mime, conditional=True, etag=False)
        except (FileNotFoundError, ActionError):
            abort(404)
    response.headers['Content-Type'] = item.mime
    response.headers['Content-Disposition'] = 'inline'
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response
