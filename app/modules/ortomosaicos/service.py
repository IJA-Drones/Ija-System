import hashlib
import json
import mimetypes
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import current_app, url_for
from filelock import FileLock, Timeout as FileLockTimeout
from requests.exceptions import ConnectionError, SSLError, Timeout
from sqlalchemy import and_, or_, update
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Ortomosaico
from app.shared import skybox
from .storage import TemporaryStorageError, TemporaryUpload, require_space, working_root

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ortomosaico')
_futures = {}
_lock = threading.Lock()
# This lease detects a stopped worker; it is not a processing time limit.
_LEASE_SECONDS = 300
_HEARTBEAT_SECONDS = 30


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def max_bytes():
    return max(0, current_app.config.get('ORTHOMOSAIC_MAX_UPLOAD_MB', 0)) * 1024 * 1024


def raster_command(mode, source, destination=None, interval=None, resolution=None):
    processor = "dem_processor.py" if mode in {"inspect-dem", "contours"} else "processor.py"
    args = [sys.executable, str(Path(__file__).with_name(processor)), mode, str(source)]
    if destination:
        args.append(str(destination))
    if mode == "contours":
        args.extend([str(interval), str(resolution)])
    environment = os.environ.copy()
    environment['ORTHOMOSAIC_MAX_PIXELS'] = str(max(0, int(current_app.config.get('ORTHOMOSAIC_MAX_PIXELS', 0))))
    # Keep GDAL/Python scratch files next to the job, on the configured volume.
    scratch = str(Path(source).resolve().parent)
    environment.update(TMPDIR=scratch, TMP=scratch, TEMP=scratch, CPL_TMPDIR=scratch)
    result = subprocess.run(args, capture_output=True, text=True, env=environment, timeout=None)
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        raise ValueError('O processamento do GeoTIFF foi interrompido. Tente novamente.') from None
    if result.returncode or not payload.get('ok'):
        raise ValueError(payload.get('error') or 'Não foi possível preparar o GeoTIFF.')
    return payload['metadata']


def _upload(path, remote):
    # A socket write uses Requests' connect timeout too. Large raster PUTs must
    # explicitly opt out; changing only the read timeout does not fix this.
    for attempt in range(1, 4):
        try:
            # Reopen from byte zero and PUT to the same attempt-specific path.
            # Keep the converted file and the recovery transaction across retries.
            with open(path, 'rb') as stream:
                return skybox.upload_file_to_skybox(FileStorage(
                    stream=stream, filename=Path(path).name,
                    content_type=mimetypes.guess_type(str(path))[0] or 'application/octet-stream',
                ), remote, timeout=None)
        except SSLError as exc:
            raise ValueError('Não foi possível estabelecer uma conexão segura com o Skybox. Verifique o certificado do armazenamento.') from exc
        except (ConnectionError, Timeout, skybox.SkyboxTemporaryError) as exc:
            if attempt == 3:
                raise ValueError('O envio ao Skybox não foi concluído após 3 tentativas por falha de conexão ou indisponibilidade do armazenamento. Tente novamente.') from exc
            current_app.logger.warning('Envio do levantamento ao Skybox interrompido; repetindo upload (%s/3).', attempt + 1)
            time.sleep(2 ** attempt)


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
        root = working_root()
        with tempfile.TemporaryDirectory(prefix='ija-orto-upload-', dir=root) as folder:
            reusable = isinstance(storage.stream, TemporaryUpload)
            path = storage.stream.ortho_upload_path if reusable else Path(folder) / 'original.tif'
            storage.stream.seek(0)
            digest = hashlib.sha256(); size = 0
            with nullcontext(None) if reusable else path.open('wb') as out:
                while chunk := storage.stream.read(1024*1024):
                    size += len(chunk)
                    if max_bytes() and size > max_bytes():
                        raise ValueError(f'O arquivo excede {max_bytes() // (1024*1024)} MB.')
                    digest.update(chunk)
                    if out is not None:
                        require_space(root, len(chunk))
                        out.write(chunk)
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


def _renew_claim(engine, oid, token):
    # A separate short transaction must not share the worker's session or its
    # file-recovery transaction, which can remain open during a large upload.
    with engine.begin() as connection:
        result = connection.execute(update(Ortomosaico).where(
            Ortomosaico.id == oid, Ortomosaico.status == 'processando',
            Ortomosaico.processamento_token == token,
        ).values(processamento_ate=now() + timedelta(seconds=_LEASE_SECONDS)))
        return result.rowcount == 1


@contextmanager
def _keep_claim_alive(oid, token):
    engine = db.engine
    logger = current_app.logger
    stopped = threading.Event()

    def heartbeat():
        while not stopped.wait(_HEARTBEAT_SECONDS):
            try:
                if not _renew_claim(engine, oid, token):
                    return
            except Exception:
                # A temporary database outage is not a raster-processing error.
                # Retry; publication is still conditional on the claim token.
                logger.exception('Falha ao renovar reserva do ortomosaico %s', oid)

    thread = threading.Thread(target=heartbeat, name=f'ortomosaico-reserva-{oid}', daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=5)


def _download(row, destination):
    digest = hashlib.sha256(); size = 0
    with skybox._request('GET', skybox.remote_path_from_marker(row.original_path), stream=True) as response:
        if response.status_code != 200:
            raise ValueError('Não foi possível recuperar o TIF original do Skybox.')
        with open(destination, 'wb') as output:
            for chunk in response.iter_content(1024*1024):
                require_space(Path(destination).parent, len(chunk))
                size += len(chunk)
                if size > row.tamanho_bytes:
                    raise ValueError('O arquivo armazenado tem tamanho diferente do original.')
                output.write(chunk); digest.update(chunk)
    if size != row.tamanho_bytes or digest.hexdigest() != row.sha256:
        raise ValueError('A integridade do TIF armazenado não confere. Envie o arquivo novamente.')


def process_one(oid):
    # Gunicorn has multiple processes; one executor per process is insufficient
    # to prevent simultaneous multi-GB conversions on the same volume.
    lock = FileLock(str(working_root() / '.processing.lock'))
    try:
        lock.acquire(timeout=0)
    except FileLockTimeout:
        return False  # Leave the task queued for the next status/CLI dispatch.
    try:
        return _claim_and_process(oid)
    finally:
        lock.release()


def _claim_and_process(oid):
    token = str(uuid.uuid4())
    result = db.session.execute(update(Ortomosaico).where(Ortomosaico.id == oid, eligible()).values(
        status='processando', processamento_token=token,
        processamento_ate=now()+timedelta(seconds=_LEASE_SECONDS),
        atualizado_em=now(), erro=None).execution_options(synchronize_session=False))
    db.session.commit()
    if result.rowcount != 1:
        return False
    with _keep_claim_alive(oid, token):
        return _process_claimed(oid, token)


def _process_claimed(oid, token):
    db.session.expire_all()
    row = db.session.get(Ortomosaico, oid)
    if row is None or row.processamento_token != token:
        db.session.rollback()
        return False
    # Snapshot the input and release the read transaction before lengthy I/O.
    db.session.expunge(row)
    db.session.commit()
    markers = []
    try:
        root = working_root()
        require_space(root, row.tamanho_bytes)
        with tempfile.TemporaryDirectory(prefix='ija-orto-process-', dir=root) as folder:
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
        message = str(exc) if isinstance(exc, (ValueError, TemporaryStorageError)) else 'O processamento foi interrompido. Tente processar novamente.'
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
        agua_url=url_for('main.ortomosaico_agua', oid=row.id),
        tipo=row.tipo, intervalo_m=row.intervalo_m, resolucao_m=row.resolucao_m,
        curvas_url=url_for('main.ortomosaico_curvas', oid=row.id) if row.status == 'pronto' and row.curvas_path else None,
        jpeg_url=url_for('main.ortomosaico_jpeg', oid=row.id) if row.status == 'pronto' and row.jpeg_path else None,
        status=row.status, erro=row.erro, tamanho_bytes=row.tamanho_bytes, arquivo_nome=row.arquivo_nome,
        metadados=row.metadados or {}, criado_em=row.criado_em.isoformat()+'Z',
        status_url=url_for('main.ortomosaico_status', oid=row.id),
        retry_url=url_for('main.ortomosaico_retry', oid=row.id),
        original_url=url_for('main.ortomosaico_original', oid=row.id),
        exportar={f'{layer}_{fmt}': url_for('main.ortomosaico_exportar', oid=row.id, camada=layer, formato=fmt)
                  for layer in ('curvas', 'medicoes') for fmt in ('geojson', 'zip')} if row.status == 'pronto' else {},
        arquivo_url=url_for('main.ortomosaico_arquivo', oid=row.id,
            v=hashlib.sha256((row.cog_path or '').encode()).hexdigest()[:16])
            if row.status == 'pronto' and row.tipo == 'rgb' else None)
