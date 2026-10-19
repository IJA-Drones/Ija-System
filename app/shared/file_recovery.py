"""Recover external file side effects without changing upload transports.

An independent durable intent survives a business rollback. Transaction advisory
locks fence recovery while the caller is writing; committed references are the
source of truth, including after an ambiguous COMMIT or a process crash.
"""
import hashlib
import os
from pathlib import Path
import socket
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.parse import quote

import click
import requests
from flask import current_app, has_app_context
from sqlalchemy import event, func, or_, and_, select, text, union_all, literal
from sqlalchemy.orm import Session

from app.extensions import db


class FileRecoveryError(RuntimeError):
    pass


def _table():
    from app.models import ArquivoOperacao
    return ArquivoOperacao.__table__


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enabled():
    return has_app_context() and current_app.extensions.get('file_recovery', False)


def _remote_config(backend):
    def setting(*keys):
        return next((current_app.config.get(k) or os.getenv(k) for k in keys
                     if current_app.config.get(k) or os.getenv(k)), '')
    if backend == 'webdav':
        return (setting('WEBDAV_URL', 'SKYBOX_WEBDAV_URL').rstrip('/'),
                setting('WEBDAV_USER', 'SKYBOX_USERNAME'), setting('WEBDAV_PASS', 'SKYBOX_APP_PASSWORD'))
    return (setting('SKYBOX_WEBDAV_URL').rstrip('/'), setting('SKYBOX_USERNAME'), setting('SKYBOX_APP_PASSWORD'))


def _identity(backend):
    if backend == 'local':
        return str(current_app.config.get('FILE_RECOVERY_LOCAL_NODE_ID') or socket.gethostname())
    if backend == 'dropbox':
        from app.modules.agro.talent_bank_service import _resolve_config_value
        return hashlib.sha256((_resolve_config_value('DROPBOX_APP_KEY') + '\n' +
            _resolve_config_value('DROPBOX_REFRESH_TOKEN')).encode()).hexdigest()
    url, user, _ = _remote_config(backend)
    return hashlib.sha256(f'{url}\n{user}'.encode()).hexdigest()


def _local_roots():
    return [Path(current_app.root_path).parent / 'upload-files',
            Path(current_app.root_path) / 'static' / 'uploads',
            Path(current_app.instance_path) / 'documentos_marca_dagua']


def _local_target(path):
    # Reject symlinks as well as traversal. Never scan directories for orphans.
    target = Path(os.path.abspath(path))
    resolved = target.resolve()
    if resolved != target or not any(resolved.is_relative_to(root.resolve()) for root in _local_roots()):
        raise FileRecoveryError('Arquivo fora das pastas de armazenamento permitidas.')
    if target.is_dir():
        raise FileRecoveryError('A recuperação não remove diretórios.')
    return str(target)


def _aliases(backend, target, extra):
    values = set(extra)
    if backend == 'local':
        for root in _local_roots():
            if Path(target).is_relative_to(root.resolve()):
                relative = Path(target).relative_to(root.resolve()).as_posix()
                values.update((relative, f'{root.name}/{relative}'))
        # static/uploads/... is persisted relative to static, not uploads.
        static = Path(current_app.root_path) / 'static'
        if Path(target).is_relative_to(static.resolve()):
            values.add(Path(target).relative_to(static.resolve()).as_posix())
    elif backend == 'dropbox':
        values.add(target.lower())
    else:
        values.update((f'skybox://{target}', f'webdav://{target}'))
    return sorted(values)


def _key(identity, target):
    return int.from_bytes(hashlib.sha256(f'{identity}\n{target}'.encode()).digest()[:8], 'big', signed=True)


def _lock(conn, key, *, wait=True):
    fn = 'pg_advisory_xact_lock' if wait else 'pg_try_advisory_xact_lock'
    return conn.execute(text(f'SELECT {fn}(:key)'), {'key': key}).scalar()


def track(backend, target, *, action='create', aliases=()):
    """Call BEFORE writing or deleting a persistent file. False = legacy test app."""
    if not enabled():
        return False
    if db.engine.dialect.name != 'postgresql':
        raise FileRecoveryError('A recuperação de arquivos exige PostgreSQL.')
    if backend not in {'local', 'skybox', 'webdav', 'dropbox'} or action not in {'create', 'delete'}:
        raise FileRecoveryError('Operação de arquivo inválida.')
    if backend == 'local':
        target = _local_target(target)
    elif backend == 'dropbox':
        target = str(target).lower()
        if not target.startswith('/agro/banco-de-talentos/') or any(p in {'.', '..', ''} for p in target[1:].split('/')):
            raise FileRecoveryError('Caminho do currículo inválido.')
    else:
        target = str(target).removeprefix('skybox://').removeprefix('webdav://')
        if not target or target.startswith('/') or any(p in {'', '.', '..'} for p in target.replace('\\', '/').split('/')):
            raise FileRecoveryError('Caminho remoto inválido.')
    table, identity = _table(), _identity(backend)
    key, op_id = _key(identity, target), str(uuid4())
    refs = _aliases(backend, target, aliases)
    with db.session.no_autoflush:
        conn = db.session.connection()
        _lock(conn, key)
        # Do not overwrite a committed asset (unique names are required).
        if action == 'create' and _referenced(conn, refs):
            raise FileRecoveryError('O arquivo já possui vínculo. Use um novo nome para substituí-lo.')
        with db.engine.begin() as journal:
            journal.execute(table.insert().values(id=op_id, backend=backend, destino=target,
                identidade=identity, lock_key=key, aliases=refs, acao=action, estado='pendente',
                criado_em=_now(), proxima_tentativa=_now() + timedelta(seconds=300), tentativas=0))
        db.session.info.setdefault('file_recovery_ops', {})[op_id] = (key, action)
    return True


def save_file(storage, path):
    track('local', path)
    storage.save(path)


def remove_file(path):
    if not track('local', path, action='delete'):
        Path(path).unlink(missing_ok=True)


def _referenced(conn, aliases):
    # All persisted file paths currently use these columns. JSON lists are
    # conservatively matched as quoted strings; no arbitrary audit text counts.
    queries = []
    for table in db.metadata.sorted_tables:
        if table.name.startswith(('auditoria_', 'arquivo_operacoes')):
            continue
        cols = [c for c in table.c if c.name.endswith('_path') or
                c.name in {'imagem_principal', 'video', 'outras_imagens', 'stored_path'}]
        for col in cols:
            if col.name == 'outras_imagens':
                import json
                conditions = [col.contains(json.dumps(a, ensure_ascii=False), autoescape=True) for a in aliases]
                conditions += [col.contains(json.dumps(a, ensure_ascii=True), autoescape=True) for a in aliases]
            else:
                conditions = [(func.lower(col) if col.name == 'dropbox_path' else col).in_(aliases)]
            queries.append(select(literal(1)).select_from(table).where(or_(*conditions)))
    return bool(queries and conn.execute(union_all(*queries).limit(1)).first())


@event.listens_for(Session, 'before_commit')
def _fence_commit(session):
    if not enabled() or not session.info.get('file_recovery_ops'):
        return
    with session.no_autoflush:
        conn, table = session.connection(), _table()
        for op_id, (key, action) in sorted(session.info['file_recovery_ops'].items(), key=lambda item: item[1][0]):
            _lock(conn, key)
            state = conn.execute(select(table.c.estado).where(table.c.id == op_id)).scalar_one()
            if action == 'create' and state == 'removido':
                raise FileRecoveryError('A operação foi recuperada após uma interrupção. Reenvie o arquivo.')


def _delete(row):
    if row['identidade'] != _identity(row['backend']):
        raise FileRecoveryError('Destino de armazenamento diferente; mantenha pendente para revisão.')
    if row['backend'] == 'local':
        Path(_local_target(row['destino'])).unlink(missing_ok=True)
        return
    if row['backend'] == 'dropbox':
        from app.modules.agro.talent_bank_service import _dropbox_client
        import dropbox
        try:
            _dropbox_client().files_delete_v2(row['destino'])
        except dropbox.exceptions.ApiError as exc:
            if not exc.error.is_path_lookup() or not exc.error.get_path_lookup().is_not_found():
                raise
        return
    base, user, password = _remote_config(row['backend'])
    if not all((base, user, password)):
        raise FileRecoveryError('Armazenamento não configurado.')
    url = base + '/' + '/'.join(quote(p, safe='') for p in row['destino'].split('/'))
    with requests.delete(url, auth=(user, password), timeout=(5, 20)) as response:
        # 202 is only acceptance, not confirmation. Retry until confirmed.
        if response.status_code not in (200, 204, 404):
            raise FileRecoveryError(f'Remoção não confirmada: HTTP {response.status_code}.')


def recover_batch(limit=10):
    if db.engine.dialect.name != 'postgresql':
        raise FileRecoveryError('A recuperação de arquivos exige PostgreSQL.')
    table, counts = _table(), {'preservados': 0, 'removidos': 0, 'pendentes': 0}
    # Different workers skip rows/targets currently being written or recovered.
    eligible = or_(table.c.estado == 'pendente', and_(
        table.c.estado == 'removido', table.c.acao == 'create', table.c.backend != 'local',
        table.c.criado_em >= _now() - timedelta(days=7)))
    with db.engine.connect() as listing:
        ids = listing.execute(select(table.c.id).where(eligible,
            table.c.proxima_tentativa <= _now()).order_by(table.c.proxima_tentativa).limit(limit)).scalars().all()
    for op_id in ids:
        with db.engine.begin() as conn:
            row = conn.execute(select(table).where(table.c.id == op_id, eligible)
                               .with_for_update(skip_locked=True)).mappings().first()
            if not row or not _lock(conn, row['lock_key'], wait=False):
                continue
            try:
                with conn.begin_nested():
                    referenced = _referenced(conn, row['aliases'])
                if referenced:
                    state = 'preservado'
                    counts['preservados'] += 1
                else:
                    _delete(row)
                    state = 'removido'
                    counts['removidos'] += 1
                conn.execute(table.update().where(table.c.id == op_id).values(
                    estado=state, concluido_em=row['concluido_em'] or _now(), ultimo_erro=None,
                    proxima_tentativa=_now() + timedelta(hours=1)))
            except Exception as exc:
                # Do not store URLs/credentials/response bodies in recovery logs.
                attempts = row['tentativas'] + 1
                conn.execute(table.update().where(table.c.id == op_id).values(tentativas=attempts,
                    ultimo_erro=type(exc).__name__, proxima_tentativa=_now() + timedelta(
                        seconds=min(3600, 30 * 2 ** min(attempts, 7)))))
                counts['pendentes'] += 1
    return counts


def register_file_recovery(app):
    app.extensions['file_recovery'] = True
    start_lock = threading.Lock()

    def loop(stop):
        while not stop.wait(60):
            with app.app_context():
                try:
                    result = recover_batch()
                    if result['pendentes']:
                        app.logger.warning('Recuperação de arquivos: %s operações aguardam nova tentativa.', result['pendentes'])
                except Exception:
                    app.logger.warning('Recuperação de arquivos pendente: confira a migração e o banco.')

    @app.before_request
    def start_worker():
        if app.testing:
            return
        with start_lock:
            if 'file_recovery_stop' not in app.extensions:
                stop = threading.Event()
                app.extensions['file_recovery_stop'] = stop
                threading.Thread(target=loop, args=(stop,), name='file-recovery', daemon=True).start()

    @app.cli.command('arquivos-recuperar')
    @click.option('--limite', default=10, type=click.IntRange(1, 100))
    def recover_command(limite):
        """Recover due operations; also usable by a periodic external worker."""
        click.echo(recover_batch(limite))

    @app.cli.command('arquivos-recuperacao-status')
    def status_command():
        table = _table()
        with db.engine.connect() as conn:
            for state, count in conn.execute(select(table.c.estado, func.count()).group_by(table.c.estado)):
                click.echo(f'{state}: {count}')
            failed = conn.execute(select(func.count()).select_from(table).where(
                table.c.estado == 'pendente', table.c.ultimo_erro.isnot(None))).scalar()
            click.echo(f'Pendentes com falha: {failed}')
