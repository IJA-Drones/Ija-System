"""Bounded, resumable transfers on the private shared working volume.

The browser never waits for raster inspection or the Skybox PUT. File locks
coordinate Gunicorn processes; atomic manifests allow status reads during I/O.
"""
import errno
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import click

from filelock import FileLock, Timeout
from flask import abort, current_app, jsonify, request, url_for
from flask_login import current_user
from flask.logging import default_handler
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Ortomosaico, Prefeitura
from app.shared import skybox
from app.shared.access import can_access_prefeitura
from . import service
from .storage import TemporaryStorageError, require_space, working_root

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(default_handler)
logger.propagate = False

CHUNK_BYTES = 8 * 1024 * 1024
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ortho-receive')
_pending = set()
_pending_lock = threading.Lock()


def folder_for(token):
    if not re.fullmatch(r'[a-f0-9]{32}', token):
        abort(404)
    folder = working_root() / ('receive-' + token)
    if not folder.is_dir():
        abort(404, description='Envio não encontrado. Selecione o arquivo para iniciar novamente.')
    return folder


def read(folder):
    return json.loads((folder / 'state.json').read_text())


def write(folder, state):
    state['updated'] = time.time()
    temporary = folder / 'state.new'
    with temporary.open('w') as stream:
        json.dump(state, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(folder / 'state.json')


def authorized(folder):
    state = read(folder)
    if state['user_id'] != current_user.id or not can_access_prefeitura(current_user, state['prefeitura_id']):
        abort(404)
    return state


def payload(state):
    result = {key: state[key] for key in ('id', 'size', 'offset', 'status')}
    result.update(chunk_bytes=CHUNK_BYTES, url=url_for('main.ortomosaico_transfer', token=state['id']))
    if state.get('error'):
        result['error'] = state['error']
    if state.get('item_id'):
        row = db.session.get(Ortomosaico, state['item_id'])
        if row:
            result['item'] = service.serialize(row)
    return result


def finalize(token):
    folder = folder_for(token)
    try:
        with FileLock(str(folder / 'finalize.lock'), timeout=0):
            state = read(folder)
            if state['status'] != 'finalizing':
                return
            try:
                # Recovery if a worker committed the row but died before updating
                # the manifest. The finalization lock prevents duplicate commits.
                row = Ortomosaico.query.filter(Ortomosaico.metadados['_upload_id'].as_string() == token).first()
                if row is None:
                    with (folder / 'original.tif').open('rb') as stream:
                        row = service.create_upload(FileStorage(stream=stream, filename=state['filename']),
                            state['nome'], state['prefeitura_id'], state['user_id'], tipo=state['tipo'],
                            interval=state.get('intervalo_m'), resolution=state.get('resolucao_m'),
                            received_path=folder / 'original.tif', upload_id=token)
                state.update(status='complete', item_id=row.id)
                write(folder, state)
                (folder / 'original.tif').unlink(missing_ok=True)
                logger.info('ortho_upload complete id=%s item=%s bytes=%s', token, row.id, state['size'])
                service.dispatch(row.id)
            except Exception as exc:
                db.session.rollback()
                logger.exception('ortho_upload finalization_failed id=%s', token)
                state.update(status='failed', error=str(exc) if isinstance(exc, (ValueError, TemporaryStorageError)) else
                    'Não foi possível armazenar o levantamento. O arquivo recebido foi preservado; tente novamente.')
                write(folder, state)
    except Timeout:
        pass  # Another Gunicorn process is finalizing this exact upload.


def dispatch(token):
    if not current_app.config.get('ORTHOMOSAIC_BACKGROUND_ENABLED', True):
        return
    app = current_app._get_current_object()
    key = (app.instance_path, token)
    with _pending_lock:
        if key in _pending or len(_pending) >= 2:
            return  # The next status poll will dispatch queued work.
        _pending.add(key)
    def run():
        try:
            with app.app_context():
                try:
                    finalize(token)
                finally:
                    db.session.remove()
        finally:
            with _pending_lock:
                _pending.discard(key)
    _executor.submit(run)


def register_routes(bp, restricted):
    @bp.post('/api/ortomosaicos/uploads', endpoint='ortomosaico_transfer_start')
    @restricted
    def start():
        if request.content_length is None or request.content_length > 16384:
            abort(413)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='Dados de envio inválidos.'), 400
        try:
            size = int(data.get('size', 0))
            pid = int(data.get('prefeitura_id', 0))
            nome = str(data.get('nome', '')).strip()
            filename = secure_filename(str(data.get('filename', '')))
            tipo = data.get('tipo', 'rgb')
            prefeitura = db.session.get(Prefeitura, pid)
            if not prefeitura or not prefeitura.ativa or not can_access_prefeitura(current_user, pid):
                raise ValueError('Selecione uma prefeitura válida.')
            if not nome or len(nome) > 120 or not filename.lower().endswith(('.tif', '.tiff')):
                raise ValueError('Informe um nome e um arquivo GeoTIFF válido.')
            if size <= 0 or size > 2**53-1 or (service.max_bytes() and size > service.max_bytes()):
                raise ValueError('Tamanho de arquivo inválido ou acima do limite configurado.')
            if tipo not in ('rgb', 'dem'):
                raise ValueError('Tipo de levantamento inválido.')
            if tipo == 'dem':
                from .dem_processor import parameters
                if data.get('elevacoes_metros') != '1':
                    raise ValueError('Confirme que as elevações do DEM estão em metros.')
                parameters(data.get('intervalo_m'), data.get('resolucao_m'))
            if not skybox.skybox_enabled():
                raise ValueError('Configure o Skybox antes de enviar um ortomosaico.')
        except (ValueError, TypeError) as exc:
            return jsonify(error=str(exc)), 400
        root = working_root()
        require_space(root, size)
        token = uuid.uuid4().hex
        folder = root / ('receive-' + token)
        folder.mkdir(mode=0o700)
        (folder / 'original.tif').touch(mode=0o600)
        state = dict(id=token, size=size, offset=0, status='receiving', user_id=current_user.id,
            prefeitura_id=pid, nome=nome, filename=filename, tipo=tipo,
            intervalo_m=data.get('intervalo_m'), resolucao_m=data.get('resolucao_m'))
        write(folder, state)
        logger.info('ortho_upload started id=%s user=%s bytes=%s', token, current_user.id, size)
        return jsonify(payload(state)), 201

    @bp.route('/api/ortomosaicos/uploads/<token>', methods=['GET', 'PUT', 'POST'], endpoint='ortomosaico_transfer')
    @restricted
    def transfer(token):
        folder = folder_for(token)
        state = authorized(folder)
        if request.method == 'GET':
            if state['status'] == 'finalizing':
                dispatch(token)
            response = jsonify(payload(state))
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        try:
            with FileLock(str(folder / 'receive.lock'), timeout=0):
                state = authorized(folder)
                if request.method == 'POST':
                    if state['offset'] != state['size']:
                        return jsonify(error='O arquivo ainda não foi recebido por completo.'), 409
                    if state['status'] in ('receiving', 'failed'):
                        state.update(status='finalizing', error=None)
                        write(folder, state)
                        logger.info('ortho_upload received id=%s bytes=%s', token, state['size'])
                    if state['status'] == 'finalizing':
                        dispatch(token)
                    return jsonify(payload(state)), 202
                try:
                    offset = int(request.headers.get('Upload-Offset', '-1'))
                except ValueError:
                    return jsonify(error='Posição de envio inválida.'), 400
                if state['status'] != 'receiving' or offset != state['offset']:
                    return jsonify(payload(state)), 409
                length = request.content_length
                if not length or length > CHUNK_BYTES or offset + length > state['size']:
                    return jsonify(error='Parte do arquivo com tamanho inválido.'), 413
                require_space(folder, length)
                # Roll back unacknowledged bytes after a disconnected request or
                # process crash. Only the atomic manifest advances the offset.
                with (folder / 'original.tif').open('r+b') as stream:
                    stream.truncate(offset)
                    stream.seek(offset)
                    remaining = length
                    while remaining:
                        chunk = request.stream.read(min(1024*1024, remaining))
                        if not chunk:
                            abort(400)
                        stream.write(chunk)
                        remaining -= len(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
                state['offset'] += length
                write(folder, state)
                logger.info('ortho_upload progress id=%s bytes=%s total=%s', token, state['offset'], state['size'])
                return jsonify(payload(state))
        except Timeout:
            return jsonify(error='Outra parte está sendo recebida. Aguarde e tente novamente.'), 409
        except OSError as exc:
            if exc.errno in (errno.ENOSPC, errno.EDQUOT):
                raise TemporaryStorageError('Espaço insuficiente no disco de trabalho. Libere espaço e retome o envio.') from exc
            raise

    @bp.cli.command('limpar-envios-ortomosaicos')
    @click.option('--dias', default=7, type=click.IntRange(min=1), show_default=True)
    def cleanup(dias):
        """Remove transfers without activity for DIAS days; skips held locks."""
        removed = 0
        for folder in working_root().glob('receive-*'):
            try:
                with FileLock(str(folder / 'receive.lock'), timeout=0), FileLock(str(folder / 'finalize.lock'), timeout=0):
                    if read(folder)['updated'] >= time.time() - dias * 86400:
                        continue
                    shutil.rmtree(folder)
                    removed += 1
            except (Timeout, FileNotFoundError):
                continue
        click.echo(f'{removed} envios antigos removidos.')
