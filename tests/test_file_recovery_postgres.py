"""Real PostgreSQL compensation tests. Never reads .env or the application's DB.

IJA_FILE_RECOVERY_TEST_URL must target the disposable local database named
ija_file_recovery_test. Each test owns a separate schema and local upload root.
"""
import importlib.util
from io import BytesIO
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from flask import Flask
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import ArquivoOperacao, FinanceiroEmpresaPerfil
from app.shared import file_recovery as recovery
from app.shared import skybox


def authorized_url(raw):
    url = make_url(raw)
    if (url.drivername != 'postgresql+psycopg2' or url.host not in {'127.0.0.1', 'localhost'}
            or url.database != 'ija_file_recovery_test' or url.query):
        raise ValueError('Somente PostgreSQL local descartável.')
    return url


@pytest.mark.parametrize('raw', ['sqlite://', 'postgresql+psycopg2://prod.example/ija_file_recovery_test',
    'postgresql+psycopg2://localhost/production',
    'postgresql+psycopg2://localhost/ija_file_recovery_test?host=prod.example'])
def test_rejects_production(raw):
    with pytest.raises(ValueError):
        authorized_url(raw)


@pytest.fixture
def app(tmp_path):
    raw = os.environ.get('IJA_FILE_RECOVERY_TEST_URL')
    if not raw:
        pytest.skip('Configure o PostgreSQL local descartável para os testes de recuperação.')
    url = authorized_url(raw)
    schema = 'recovery_' + uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA {schema}'))
    app = Flask(__name__, root_path=str(tmp_path / 'app'), instance_path=str(tmp_path / 'instance'))
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI=url,
        SQLALCHEMY_ENGINE_OPTIONS={'connect_args': {'options': f'-csearch_path={schema}'}},
        SKYBOX_WEBDAV_URL='https://storage.invalid/dav', SKYBOX_USERNAME='test', SKYBOX_APP_PASSWORD='test-only')
    db.init_app(app)
    recovery.register_file_recovery(app)
    with app.app_context():
        db.create_all()
    try:
        yield app
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        with admin.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def upload(app, name='new.jpg'):
    path = Path(app.root_path).parent / 'upload-files' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    recovery.save_file(FileStorage(stream=BytesIO(b'new-image'), filename=name), path)
    return path


def due():
    with db.engine.begin() as conn:
        conn.execute(ArquivoOperacao.__table__.update().values(proxima_tentativa=sa.text("TIMESTAMP '2000-01-01'")))


def run_other(app):
    def run():
        with app.app_context():
            return recovery.recover_batch()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run).result(timeout=10)


def test_rollback_reclaims_file_and_business_row(app):
    with app.app_context():
        db.session.add(FinanceiroEmpresaPerfil(empresa_slug='rollback'))
        db.session.flush()  # intent is independently durable after a business write
        path = upload(app)
        db.session.rollback()
        due()
        assert recovery.recover_batch()['removidos'] == 1
        assert not path.exists()
        assert db.session.get(FinanceiroEmpresaPerfil, 'rollback') is None


def test_committed_reference_preserved_even_after_session_lost(app):
    with app.app_context():
        path = upload(app)
        db.session.add(FinanceiroEmpresaPerfil(empresa_slug='ok', logo_path='upload-files/new.jpg'))
        db.session.commit()
        db.session.remove()  # response could have been lost after COMMIT
        due()
        assert recovery.recover_batch()['preservados'] == 1
        assert path.read_bytes() == b'new-image'


def test_long_running_upload_is_not_collected(app):
    with app.app_context():
        path = upload(app)
        due()
        assert run_other(app)['removidos'] == 0
        assert path.exists()
        db.session.remove()  # process/session crash releases locks
        assert recovery.recover_batch()['removidos'] == 1


def test_reusing_transaction_after_rollback_cannot_commit_removed_file(app):
    with app.app_context():
        upload(app)
        db.session.rollback()
        due()
        assert recovery.recover_batch()['removidos'] == 1
        db.session.add(FinanceiroEmpresaPerfil(empresa_slug='stale', logo_path='new.jpg'))
        with pytest.raises(recovery.FileRecoveryError, match='Reenvie'):
            db.session.commit()
        db.session.rollback()
        assert db.session.get(FinanceiroEmpresaPerfil, 'stale') is None


@pytest.mark.parametrize('commit', [False, True])
def test_old_file_deleted_only_after_reference_removed(app, commit):
    with app.app_context():
        path = Path(app.root_path).parent / 'upload-files' / 'old.jpg'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'original')
        row = FinanceiroEmpresaPerfil(empresa_slug='old', logo_path='old.jpg')
        db.session.add(row); db.session.commit()
        recovery.remove_file(path)
        row.logo_path = None
        due()
        assert run_other(app)['removidos'] == 0
        assert path.exists()
        if commit:
            db.session.commit()
        else:
            db.session.rollback()
        result = recovery.recover_batch()
        assert path.exists() is not commit
        assert result['removidos' if commit else 'preservados'] == 1


def test_cleanup_retry_survives_storage_failure_and_restart(app, monkeypatch):
    with app.app_context():
        path = upload(app); db.session.remove(); due()
        original = recovery._delete
        def fail(row): raise OSError('secret URL must not be stored')
        monkeypatch.setattr(recovery, '_delete', fail)
        assert recovery.recover_batch()['pendentes'] == 1
        row = db.session.query(ArquivoOperacao).one()
        assert row.ultimo_erro == 'OSError' and row.tentativas == 1
        assert path.exists()
        db.session.remove(); monkeypatch.setattr(recovery, '_delete', original); due()
        assert recovery.recover_batch()['removidos'] == 1
        assert recovery.recover_batch()['removidos'] == 0


def test_reference_check_failure_never_deletes(app, monkeypatch):
    with app.app_context():
        path = upload(app); db.session.remove(); due()
        def broken(conn, aliases): conn.execute(sa.text('SELECT nonexistent_column FROM arquivo_operacoes'))
        monkeypatch.setattr(recovery, '_referenced', broken)
        assert recovery.recover_batch()['pendentes'] == 1
        assert path.exists()


@pytest.mark.parametrize('backend', ['skybox', 'webdav'])
def test_remote_upload_timeout_is_recoverable(app, monkeypatch, backend):
    with app.app_context():
        deletes = []
        class Response:
            status_code = 204
            def __enter__(self): return self
            def __exit__(self, *args): pass
        monkeypatch.setattr(recovery.requests, 'delete', lambda url, **kwargs: deletes.append(url) or Response())
        if backend == 'skybox':
            monkeypatch.setattr(skybox, '_ensure_parent_collections', lambda path: None)
            def timeout(*args, **kwargs): raise skybox.requests.Timeout('PUT may have completed')
            monkeypatch.setattr(skybox, '_request', timeout)
            with pytest.raises(skybox.requests.Timeout):
                skybox.upload_file_to_skybox(FileStorage(stream=BytesIO(b'x'), filename='a.jpg'), 'denuncias/1/a.jpg')
        else:
            recovery.track('webdav', 'denuncias/1/a.jpg')
        db.session.remove(); due()
        assert recovery.recover_batch()['removidos'] == 1
        assert len(deletes) == 1 and deletes[0].endswith('/denuncias/1/a.jpg')


def test_storage_destination_change_keeps_pending(app, monkeypatch):
    with app.app_context():
        recovery.track('skybox', 'denuncias/1/a.jpg'); db.session.remove(); due()
        app.config['SKYBOX_WEBDAV_URL'] = 'https://other.invalid/dav'
        monkeypatch.setattr(recovery.requests, 'delete', lambda *a, **k: pytest.fail('wrong storage'))
        assert recovery.recover_batch()['pendentes'] == 1


def test_cannot_escape_local_storage_or_delete_directory(app, tmp_path):
    with app.app_context():
        with pytest.raises(recovery.FileRecoveryError): recovery.remove_file(tmp_path / 'secret')
        path = upload(app); db.session.rollback()
        with pytest.raises(recovery.FileRecoveryError): recovery.remove_file(path.parent)
        link = path.parent / 'link.jpg'; link.symlink_to(tmp_path / 'secret')
        with pytest.raises(recovery.FileRecoveryError): recovery.remove_file(link)


def test_upload_rejects_overwrite_of_referenced_asset(app):
    with app.app_context():
        db.session.add(FinanceiroEmpresaPerfil(empresa_slug='old', logo_path='new.jpg')); db.session.commit()
        with pytest.raises(recovery.FileRecoveryError): upload(app)


def test_multiple_files_failure_removes_all_new_files(app):
    from app.modules.portal_cidadao import service
    with app.app_context():
        app.config['SKYBOX_WEBDAV_URL'] = ''
        # Use the real complaint storage boundary, including persisted aliases.
        a = service._save_denuncia_media(SimpleNamespace(id=7), FileStorage(stream=BytesIO(b'a'), filename='a.jpg', content_type='image/jpeg'))
        class Broken(BytesIO):
            def read(self, *args): raise OSError('disk read interrupted')
        with pytest.raises(OSError):
            service._save_denuncia_media(SimpleNamespace(id=7), FileStorage(stream=Broken(b'b'), filename='b.jpg', content_type='image/jpeg'))
        db.session.remove(); due()
        assert recovery.recover_batch()['removidos'] == 2
        assert not (Path(app.root_path).parent / 'upload-files' / a.arquivo_path).exists()


def test_migration_roundtrip_and_pending_downgrade_guard(app):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / 'migrations/versions/f2a91d0c6b38_file_recovery.py'
    spec = importlib.util.spec_from_file_location('file_recovery_migration', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with app.app_context():
        ArquivoOperacao.__table__.drop(db.engine)
        with db.engine.begin() as conn:
            module.op = Operations(MigrationContext.configure(conn)); module.upgrade()
        upload(app); db.session.rollback()
        with pytest.raises(RuntimeError, match='pendentes'):
            with db.engine.begin() as conn:
                module.op = Operations(MigrationContext.configure(conn)); module.downgrade()
        due(); recovery.recover_batch()
        with db.engine.begin() as conn:
            module.op = Operations(MigrationContext.configure(conn)); module.downgrade(); module.upgrade()
        assert sa.inspect(db.engine).has_table('arquivo_operacoes')


def test_local_os_mirror_kept_on_rollback(app, monkeypatch):
    from app.modules.piloto_os import service
    with app.app_context():
        monkeypatch.setattr(skybox, '_ensure_parent_collections', lambda path: None)
        monkeypatch.setattr(skybox, '_request', lambda *a, **k: SimpleNamespace(status_code=201))
        path = service._salvar_upload_os_imagem(FileStorage(stream=BytesIO(b'image'), filename='a.jpg'),
            app.root_path, 7, 'principal', copiar_skybox=True)
        db.session.add(FinanceiroEmpresaPerfil(empresa_slug='mirror', logo_path=path)); db.session.commit()
        service._remover_upload_os_arquivo(app.root_path, path)
        db.session.rollback(); due()
        monkeypatch.setattr(recovery, '_delete', lambda row: pytest.fail('valid mirror must stay'))
        assert recovery.recover_batch()['preservados'] == 4  # local+mirror create and delete


def test_dropbox_rollback_and_committed_reference(app, monkeypatch):
    from app.modules.agro import talent_bank_service as service
    with app.app_context():
        deleted = []
        monkeypatch.setattr(service, '_resolve_config_value', lambda key: 'isolated-test')
        monkeypatch.setattr(service, '_dropbox_client', lambda: SimpleNamespace(
            files_upload=lambda data, path, **kw: SimpleNamespace(path_display=path, rev='1'),
            files_delete_v2=lambda path: deleted.append(path)))
        service.upload_resume_to_dropbox(b'pdf', '/agro/banco-de-talentos/test/one.pdf')
        db.session.remove(); due()
        assert recovery.recover_batch()['removidos'] == 1
        assert deleted == ['/agro/banco-de-talentos/test/one.pdf']
        service.upload_resume_to_dropbox(b'pdf', '/agro/banco-de-talentos/test/two.pdf')
        db.session.add(FinanceiroEmpresaPerfil(empresa_slug='dropbox', logo_path='/agro/banco-de-talentos/test/two.pdf'))
        db.session.commit(); due()
        assert recovery.recover_batch()['preservados'] == 1


def test_json_image_reference_is_kept(app):
    with app.app_context():
        # Exercise real JSON/text reference matching without unrelated required OS fields.
        from unittest.mock import patch
        table = sa.Table('recovery_json_images', sa.MetaData(),
            sa.Column('id', sa.Integer, primary_key=True), sa.Column('outras_imagens', sa.Text))
        table.create(db.engine)
        with db.engine.begin() as conn:
            conn.execute(table.insert().values(id=1, outras_imagens='["skybox://imagens/a.jpg"]'))
            fake_meta = SimpleNamespace(sorted_tables=[table])
            with patch.object(db, 'metadatas', {None: fake_meta}):
                assert recovery._referenced(conn, ['skybox://imagens/a.jpg'])
                assert not recovery._referenced(conn, ['skybox://imagens/a.jp'])


def test_two_recovery_workers_delete_once(app, monkeypatch):
    import threading
    with app.app_context():
        path = upload(app); db.session.remove(); due()
    started, release = threading.Event(), threading.Event()
    calls = []
    original = recovery._delete
    def slow(row):
        calls.append(row['id']); started.set()
        assert release.wait(10)
        original(row)
    monkeypatch.setattr(recovery, '_delete', slow)
    def work():
        with app.app_context(): return recovery.recover_batch()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(work)
        assert started.wait(5)
        try:
            assert pool.submit(work).result(timeout=5)['removidos'] == 0
        finally:
            release.set()
        assert first.result(timeout=5)['removidos'] == 1
    assert len(calls) == 1 and not path.exists()


def test_commit_constraint_failure_keeps_old_and_recovers_new(app):
    with app.app_context():
        old = Path(app.root_path).parent / 'upload-files' / 'old.jpg'
        old.parent.mkdir(parents=True); old.write_bytes(b'old')
        db.session.add(FinanceiroEmpresaPerfil(empresa_slug='original', logo_path='old.jpg', cnpj='same'))
        db.session.commit()
        new = upload(app)
        recovery.remove_file(old)
        db.session.get(FinanceiroEmpresaPerfil, 'original').logo_path = 'new.jpg'
        db.session.add(FinanceiroEmpresaPerfil(empresa_slug='duplicate', cnpj='same'))
        with pytest.raises(sa.exc.IntegrityError): db.session.commit()
        db.session.rollback(); due()
        result = recovery.recover_batch()
        assert result['removidos'] == result['preservados'] == 1
        assert old.read_bytes() == b'old' and not new.exists()
        assert db.session.get(FinanceiroEmpresaPerfil, 'original').logo_path == 'old.jpg'


def test_pending_intent_failure_prevents_upload(app, monkeypatch):
    with app.app_context():
        ArquivoOperacao.__table__.drop(db.engine)
        monkeypatch.setattr(skybox, '_request', lambda *a, **k: pytest.fail('no file without durable intent'))
        with pytest.raises(sa.exc.ProgrammingError):
            skybox.upload_file_to_skybox(FileStorage(stream=BytesIO(b'a'), filename='a.jpg'), 'a.jpg')


def test_late_remote_put_after_process_crash_is_reconciled_again(app, monkeypatch):
    with app.app_context():
        remote = {'exists': True}
        recovery.track('skybox', 'test/crashed.jpg'); db.session.remove(); due()
        def delete(row): remote['exists'] = False
        monkeypatch.setattr(recovery, '_delete', delete)
        assert recovery.recover_batch()['removidos'] == 1
        remote['exists'] = True  # remote server finishes an interrupted PUT later
        due()
        assert recovery.recover_batch()['removidos'] == 1
        assert remote['exists'] is False


def test_full_complaint_failure_rolls_back_rows(app, monkeypatch):
    from app.modules.portal_cidadao import service
    from app.models import Prefeitura, Denuncia, DenunciaAnexo
    from werkzeug.datastructures import MultiDict
    with app.app_context():
        app.config['SKYBOX_WEBDAV_URL'] = ''
        prefeitura = Prefeitura(nome='Teste', slug='teste', ativa=True)
        db.session.add(prefeitura); db.session.commit()
        monkeypatch.setattr(service, '_enrich_address_from_location', lambda data: None)
        monkeypatch.setattr(service, '_try_geocode_address', lambda data: None)
        original = service._save_denuncia_media
        counter = []
        def fail_second(*args):
            counter.append(1)
            if len(counter) == 2: raise OSError('second media failed')
            return original(*args)
        monkeypatch.setattr(service, '_save_denuncia_media', fail_second)
        form = MultiDict(dict(prefeitura_id=str(prefeitura.id), tipo_visita='Culex', foco='Corrego',
            logradouro='Rua Teste', numero='1', bairro='Centro', cidade='Sao Paulo',
            nome='Cidadao Teste', cpf='52998224725', telefone='11987654321', consentimento='1'))
        files = MultiDict([('midias', FileStorage(stream=BytesIO(b'a'), filename='a.jpg', content_type='image/jpeg')),
                          ('midias', FileStorage(stream=BytesIO(b'b'), filename='b.jpg', content_type='image/jpeg'))])
        with pytest.raises(OSError): service.criar_denuncia(form, files)
        assert db.session.query(Denuncia).count() == db.session.query(DenunciaAnexo).count() == 0
        due()
        assert recovery.recover_batch()['removidos'] == 1


@pytest.mark.parametrize('prefix, filename, content_type', [
    ('principal', 'foto.jpg', 'image/jpeg'), ('video', 'voo.mp4', 'video/mp4')])
def test_os_direct_stream_keeps_transport_and_compensates_failed_commit(app, monkeypatch, prefix, filename, content_type):
    from app.modules.piloto_os import routes
    payload = b'original bytes unchanged' * 100
    with app.test_request_context('/upload', method='POST', data=payload,
        headers={'X-File-Name': filename, 'Content-Type': content_type}):
        monkeypatch.setattr(routes.requests, 'request', lambda *args, **kwargs: SimpleNamespace(status_code=201))
        received = []
        def put(url, **kwargs):
            received.append(b''.join(kwargs['data']))
            assert kwargs['headers']['Content-Length'] == str(len(payload))
            return SimpleNamespace(status_code=201)
        monkeypatch.setattr(routes.requests, 'put', put)
        name, url, error, status = routes._upload_request_stream_to_webdav(7, prefix)
        assert error is status is None and name.endswith(Path(filename).suffix)
        assert received == [payload]
        db.session.rollback(); due()
        removed = []
        monkeypatch.setattr(recovery, '_delete', lambda row: removed.append(row['destino']))
        assert recovery.recover_batch()['removidos'] == 1
        assert removed[0].endswith('/7/' + name)


def test_remote_accepted_delete_is_retried_not_reported_complete(app, monkeypatch):
    with app.app_context():
        recovery.track('skybox', 'test/a.jpg'); db.session.remove(); due()
        class Accepted:
            status_code = 202
            def __enter__(self): return self
            def __exit__(self, *args): pass
        monkeypatch.setattr(recovery.requests, 'delete', lambda *a, **k: Accepted())
        assert recovery.recover_batch()['pendentes'] == 1
        assert db.session.query(ArquivoOperacao).one().estado == 'pendente'
