import hashlib
import json
import mimetypes
import os
import subprocess
import sys
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import current_app, url_for
from sqlalchemy import and_, or_, update
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Ortomosaico
from app.shared import skybox

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ortomosaico')
_futures = {}
_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def max_bytes():
    return max(0, current_app.config.get('ORTHOMOSAIC_MAX_UPLOAD_MB', 0)) * 1024 * 1024


def process_timeout():
    return max(60, int(current_app.config.get('ORTHOMOSAIC_PROCESS_TIMEOUT_SECONDS', 3600)))


def raster_command(mode, source, destination=None, interval=None, resolution=None):
    processor = "dem_processor.py" if mode in {"inspect-dem", "contours"} else "processor.py"
    args = [sys.executable, str(Path(__file__).with_name(processor)), mode, str(source)]
    if destination:
        args.append(str(destination))
    if mode == "contours":
        args.extend([str(interval), str(resolution)])
    environment = os.environ.copy()
    environment['ORTHOMOSAIC_MAX_PIXELS'] = str(max(0, int(current_app.config.get('ORTHOMOSAIC_MAX_PIXELS', 0))))
    result = subprocess.run(args, capture_output=True, text=True, env=environment,
                            timeout=60 if mode.startswith('inspect') else process_timeout())
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        raise ValueError('O processamento do GeoTIFF foi interrompido. Tente novamente.') from None
    if result.returncode or not payload.get('ok'):
        raise ValueError(payload.get('error') or 'Não foi possível preparar o GeoTIFF.')
    return payload['metadata']


def _upload(path, remote):
    with open(path, 'rb') as stream:
        return skybox.upload_file_to_skybox(FileStorage(stream=stream, filename=Path(path).name, content_type=mimetypes.guess_type(str(path))[0] or 'application/octet-stream'), remote)


def create_upload(storage, name, prefeitura_id, user_id, tipo="rgb", interval=None, resolution=None):
    if tipo not in {"rgb", "dem"}:
        raise ValueError("Tipo de levantamento inválido.")
    if tipo == "dem":
        from .dem_processor import parameters
        interval, resolution = parameters(interval, resolution)
    else:
        interval = resolution = None
    filename = secure_filename(storage.filename or '')
    if not filename.lower().endswith(('.tif', '.tiff')):
        raise ValueError('Selecione um arquivo .tif ou .tiff.')
    name = (name or '').strip()
    if not name or len(name) > 120:
        raise ValueError('Informe um nome com até 120 caracteres.')
    if not skybox.skybox_enabled():
        raise ValueError('Configure o Skybox antes de enviar um ortomosaico.')
    marker = None
    try:
        with tempfile.TemporaryDirectory(prefix='ija-orto-upload-') as folder:
            path = Path(folder) / 'original.tif'
            digest = hashlib.sha256(); size = 0
            with path.open('wb') as out:
                while chunk := storage.stream.read(1024*1024):
                    size += len(chunk)
                    if max_bytes() and size > max_bytes():
                        raise ValueError(f'O arquivo excede {max_bytes() // (1024*1024)} MB.')
                    digest.update(chunk); out.write(chunk)
            if not size:
                raise ValueError('O arquivo está vazio.')
            metadata = raster_command('inspect-dem' if tipo == 'dem' else 'inspect', path)
            url = db.engine.url
            namespace = hashlib.sha256(f'{url.host}|{url.database}|{url.username}'.encode()).hexdigest()[:16]
            base = current_app.config.get('SKYBOX_BASE_DIR') or 'dados ordens de serviço'
            remote = f'{base}/ortomosaicos/{namespace}/prefeitura-{prefeitura_id}/{uuid.uuid4().hex}/original.tif'
            marker = _upload(path, remote)
            row = Ortomosaico(nome=name, prefeitura_id=prefeitura_id, usuario_id=user_id,
                arquivo_nome=filename[:255], original_path=marker, tamanho_bytes=size,
                sha256=digest.hexdigest(), metadados=metadata, status='pendente',
                tipo=tipo, intervalo_m=interval, resolucao_m=resolution)
            db.session.add(row); db.session.commit()
            return row
    except Exception:
        db.session.rollback()
        if marker:
            try:
                skybox.delete_skybox_file(marker)
            except Exception:
                current_app.logger.exception('Falha ao limpar upload de ortomosaico não registrado.')
        raise


def eligible():
    return or_(Ortomosaico.status == 'pendente', and_(Ortomosaico.status == 'processando', Ortomosaico.processamento_ate < now()))


def _download(row, destination):
    digest = hashlib.sha256(); size = 0
    with skybox._request('GET', skybox.remote_path_from_marker(row.original_path), stream=True) as response:
        if response.status_code != 200:
            raise ValueError('Não foi possível recuperar o TIF original do Skybox.')
        with open(destination, 'wb') as output:
            for chunk in response.iter_content(1024*1024):
                size += len(chunk)
                if size > row.tamanho_bytes:
                    raise ValueError('O arquivo armazenado tem tamanho diferente do original.')
                output.write(chunk); digest.update(chunk)
    if size != row.tamanho_bytes or digest.hexdigest() != row.sha256:
        raise ValueError('A integridade do TIF armazenado não confere. Envie o arquivo novamente.')


def process_one(oid):
    token = str(uuid.uuid4())
    result = db.session.execute(update(Ortomosaico).where(Ortomosaico.id == oid, eligible()).values(
        status='processando', processamento_token=token,
        processamento_ate=now()+timedelta(seconds=process_timeout()+1800),
        atualizado_em=now(), erro=None).execution_options(synchronize_session=False))
    db.session.commit()
    if result.rowcount != 1:
        return False
    row = db.session.get(Ortomosaico, oid)
    markers = []
    try:
        with tempfile.TemporaryDirectory(prefix='ija-orto-process-') as folder:
            source, cog = Path(folder)/'original.tif', Path(folder)/'mapa.tif'
            _download(row, source)
            remote_base = skybox.remote_path_from_marker(row.original_path).rsplit('/', 1)[0]
            outputs = {}
            if row.tipo == 'dem':
                destination = Path(folder)/'curvas'
                metadata = raster_command('contours', source, destination, row.intervalo_m, row.resolucao_m)
                for field, filename in (('curvas_path', 'curvas.geojson'), ('jpeg_path', 'curvas.jpg')):
                    marker = _upload(destination/filename, f'{remote_base}/{token}-{filename}')
                    markers.append(marker); outputs[field] = marker
            else:
                metadata = raster_command('convert', source, cog)
                remote = f'{remote_base}/mapa-{token}.tif'
                marker = _upload(cog, remote)
                markers.append(marker); outputs['cog_path'] = marker
                # RGB navigation needs real range support from storage.
                with skybox._request('GET', remote, headers={'Range':'bytes=0-15'}, stream=True) as response:
                    if response.status_code != 206 or not response.headers.get('Content-Range', '').startswith('bytes 0-15/'):
                        raise ValueError('O armazenamento não oferece leitura parcial do TIF. Solicite a configuração ao suporte.')
            updated = db.session.execute(update(Ortomosaico).where(Ortomosaico.id == oid,
                Ortomosaico.processamento_token == token).values(status='pronto', metadados=metadata,
                **outputs, erro=None, processamento_ate=None, atualizado_em=now()).execution_options(synchronize_session=False))
            db.session.commit()
            if updated.rowcount != 1:
                for marker in markers:
                    skybox.delete_skybox_file(marker)
                return False
        return True
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Falha ao processar ortomosaico %s', oid)
        message = str(exc) if isinstance(exc, ValueError) else 'O processamento foi interrompido. Tente processar novamente.'
        db.session.execute(update(Ortomosaico).where(Ortomosaico.id == oid, Ortomosaico.processamento_token == token).values(
            status='falha', erro=message[:500], processamento_ate=None, atualizado_em=now()))
        db.session.commit()
        for marker in markers:
            try:
                skybox.delete_skybox_file(marker)
            except Exception:
                current_app.logger.exception('Falha ao limpar cópia incompleta do levantamento %s', oid)
        return False


def dispatch(oid):
    if not current_app.config.get('ORTHOMOSAIC_BACKGROUND_ENABLED', True):
        return
    app = current_app._get_current_object()
    key = (app.config['SQLALCHEMY_DATABASE_URI'], oid)
    with _lock:
        for previous in list(_futures):
            if _futures[previous].done():
                del _futures[previous]
        if key in _futures or len(_futures) >= 2:
            return
        def run():
            with app.app_context():
                try:
                    process_one(oid)
                finally:
                    db.session.remove()
        _futures[key] = _executor.submit(run)


def serialize(row):
    return dict(id=row.id, nome=row.nome, prefeitura=row.prefeitura.nome, prefeitura_id=row.prefeitura_id,
        tipo=row.tipo, intervalo_m=row.intervalo_m, resolucao_m=row.resolucao_m,
        curvas_url=url_for('main.ortomosaico_curvas', oid=row.id) if row.status == 'pronto' and row.curvas_path else None,
        jpeg_url=url_for('main.ortomosaico_jpeg', oid=row.id) if row.status == 'pronto' and row.jpeg_path else None,
        status=row.status, erro=row.erro, tamanho_bytes=row.tamanho_bytes, arquivo_nome=row.arquivo_nome,
        metadados=row.metadados or {}, criado_em=row.criado_em.isoformat()+'Z',
        status_url=url_for('main.ortomosaico_status', oid=row.id),
        retry_url=url_for('main.ortomosaico_retry', oid=row.id),
        arquivo_url=url_for('main.ortomosaico_arquivo', oid=row.id) if row.status == 'pronto' and row.tipo == 'rgb' else None)
