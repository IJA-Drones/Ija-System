"""Durable JSONL batches, leased delivery and verified private Skybox copies."""
import hashlib
import json
import re
import threading
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

import click
from flask import current_app
from sqlalchemy import func, or_, select, update
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import AuditoriaArquivo, AuditoriaInstalacao, AuditoriaUsuario
from app.shared.skybox import download_skybox_bytes, skybox_enabled, upload_file_to_skybox


MAX_BATCH_BYTES = 4 * 1024 * 1024


def _now():
    from app.modules.auditoria.recorder import utcnow
    return utcnow()


def _encode(row):
    # Legacy URL/referrer/query strings were unsanitized: do not archive them.
    fields = ('evento_id', 'requisicao_id', 'criado_em', 'usuario_id', 'usuario_nome',
              'usuario_login', 'tipo_usuario', 'prefeitura_id', 'prefeitura_usuario_id',
              'tipo_evento', 'resultado', 'objeto_tipo', 'objeto_id', 'detalhes',
              'metodo', 'endpoint', 'status_code', 'ip')
    payload = {key: row[key] for key in fields}
    payload['evento_id'] = payload['evento_id'] or f'legado-{row["id"]}'
    payload['versao_formato'] = 1
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      default=lambda value: value.isoformat(), separators=(',', ':')) + '\n'


def prepare_batch():
    events, archives = AuditoriaUsuario.__table__, AuditoriaArquivo.__table__
    now = _now()
    with db.engine.begin() as conn:
        installation = conn.execute(select(AuditoriaInstalacao.identificador).where(AuditoriaInstalacao.id == 1)).scalar_one()
        first = conn.execute(select(events.c.id, events.c.prefeitura_id).where(events.c.arquivo_id.is_(None))
                             .order_by(events.c.id).limit(1).with_for_update(skip_locked=True)).first()
        if first is None:
            return None
        rows = conn.execute(select(events).where(events.c.arquivo_id.is_(None),
                            events.c.prefeitura_id == first.prefeitura_id)
                            .order_by(events.c.id).limit(200).with_for_update(skip_locked=True)).mappings().all()
        lines, ids, size = [], [], 0
        for row in rows:
            line = _encode(row)
            length = len(line.encode('utf-8'))
            if lines and size + length > MAX_BATCH_BYTES:
                break
            lines.append(line)
            ids.append(row['id'])
            size += length
        if not ids:
            return None
        batch_id = str(uuid4())
        namespace = current_app.config.get('AUDIT_SKYBOX_NAMESPACE', '').strip()
        if namespace and not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', namespace):
            raise ValueError('AUDIT_SKYBOX_NAMESPACE inválido.')
        folder = f'{namespace}-{installation}' if namespace else installation
        tenant = f'prefeitura-{first.prefeitura_id}' if first.prefeitura_id is not None else 'sistema'
        path = f'auditoria_sistema/{folder}/{tenant}/{now:%Y/%m/%d}/{batch_id}.jsonl'
        content = ''.join(lines)
        conn.execute(archives.insert().values(id=batch_id, caminho=path, conteudo=content,
            sha256=hashlib.sha256(content.encode('utf-8')).hexdigest(), quantidade=len(ids),
            prefeitura_id=first.prefeitura_id, criado_em=now, tentativas=0, proxima_tentativa=now))
        changed = conn.execute(update(events).where(events.c.id.in_(ids), events.c.arquivo_id.is_(None))
                               .values(arquivo_id=batch_id))
        if changed.rowcount != len(ids):
            raise RuntimeError('Lote concorrente; a seleção será repetida.')
        return batch_id


def deliver_batch():
    """Network I/O happens outside DB transactions; retries reuse identical bytes/path."""
    archives, events = AuditoriaArquivo.__table__, AuditoriaUsuario.__table__
    now, token = _now(), str(uuid4())
    available = (archives.c.enviado_em.is_(None), archives.c.proxima_tentativa <= now,
                 or_(archives.c.lease_ate.is_(None), archives.c.lease_ate < now))
    with db.engine.begin() as conn:
        row = conn.execute(select(archives).where(*available).order_by(archives.c.proxima_tentativa)
                           .limit(1).with_for_update(skip_locked=True)).mappings().first()
        if row is None:
            return None
        claimed = conn.execute(update(archives).where(archives.c.id == row['id'], *available).values(
            lease_token=token, lease_ate=now + timedelta(minutes=15), tentativas=archives.c.tentativas + 1))
        if claimed.rowcount != 1:
            return None
    try:
        content = row['conteudo'].encode('utf-8')
        if hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError('Checksum local inválido.')
        marker = upload_file_to_skybox(FileStorage(stream=BytesIO(content), filename=row['id'] + '.jsonl',
                                                   content_type='application/x-ndjson'), row['caminho'])
        remote = download_skybox_bytes(marker, max_bytes=max(MAX_BATCH_BYTES, len(content)))
        if hashlib.sha256(remote).hexdigest() != row['sha256']:
            raise ValueError('Checksum remoto divergente.')
    except Exception:
        # Do not persist provider response bodies or credential-bearing exception URLs.
        with db.engine.begin() as conn:
            conn.execute(update(archives).where(archives.c.id == row['id'], archives.c.lease_token == token).values(
                lease_token=None, lease_ate=None,
                proxima_tentativa=_now() + timedelta(seconds=min(3600, 30 * 2 ** min(row['tentativas'], 7))),
                ultimo_erro='Falha no envio ou na verificação. Nova tentativa automática agendada.'))
        current_app.logger.warning('Auditoria: lote %s permanece pendente no Skybox.', row['id'])
        return False
    with db.engine.begin() as conn:
        sent = _now()
        changed = conn.execute(update(archives).where(archives.c.id == row['id'], archives.c.lease_token == token)
            .values(enviado_em=sent, conteudo=None, lease_token=None, lease_ate=None, ultimo_erro=None))
        if changed.rowcount != 1:
            return False
        conn.execute(update(events).where(events.c.arquivo_id == row['id']).values(arquivado_em=sent))
        from app.modules.auditoria.service import trim_auditoria_usuarios
        trim_auditoria_usuarios(conn, current_app.config.get('AUDIT_RETENTION_MAX_RECORDS', 15000))
    return True


def process_archive(max_batches=5):
    if not current_app.config.get('AUDIT_SKYBOX_ENABLED', True) or not skybox_enabled():
        return {'enviados': 0, 'disponivel': False}
    sent = 0
    for _ in range(max_batches):
        outcome = deliver_batch()
        if outcome is None:
            if prepare_batch() is None:
                break
            outcome = deliver_batch()
        if outcome is False:
            break
        if outcome:
            sent += 1
    return {'enviados': sent, 'disponivel': True}


def archive_status():
    return dict(
        configurado=skybox_enabled() and current_app.config.get('AUDIT_SKYBOX_ENABLED', True),
        pendentes=db.session.query(func.count(AuditoriaUsuario.id)).filter(AuditoriaUsuario.arquivado_em.is_(None)).scalar(),
        ultimo_envio=db.session.query(func.max(AuditoriaArquivo.enviado_em)).scalar(),
        falhas=db.session.query(func.count(AuditoriaArquivo.id)).filter(
            AuditoriaArquivo.enviado_em.is_(None), AuditoriaArquivo.ultimo_erro.isnot(None)).scalar(),
        arquivos=db.session.query(func.count(AuditoriaArquivo.id)).filter(AuditoriaArquivo.enviado_em.isnot(None)).scalar(),
    )


def register_archive_worker(app):
    lock = threading.Lock()

    def loop():
        interval = max(10, int(app.config.get('AUDIT_SKYBOX_INTERVAL_SECONDS', 60)))
        stop = app.extensions['audit_archive_stop']
        while not stop.wait(interval):
            with app.app_context():
                try:
                    process_archive()
                except Exception:
                    app.logger.warning('Auditoria: arquivamento pendente; confira a migração e a conexão do banco.')

    @app.before_request
    def start_worker():
        if app.testing or not app.config.get('AUDIT_SKYBOX_ENABLED', True) or not skybox_enabled():
            return
        with lock:
            if 'audit_archive_stop' not in app.extensions:
                app.extensions['audit_archive_stop'] = threading.Event()
                threading.Thread(target=loop, name='audit-skybox', daemon=True).start()

    @app.cli.command('auditoria-enviar')
    @click.option('--max-lotes', default=5, type=click.IntRange(1, 100))
    def send_archive(max_lotes):
        """Send pending audit batches to Skybox (also usable by an external scheduler)."""
        result = process_archive(max_lotes)
        click.echo(f'Lotes enviados: {result["enviados"]}. Skybox configurado: {result["disponivel"]}.')
