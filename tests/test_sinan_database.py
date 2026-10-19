"""Contrato do armazenamento compartilhado, migração e isolamento por proprietário."""

import importlib.util
import io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.modules.vigilancia.sinan_database import DatabaseStore
from app.modules.vigilancia.sinan_models import SINAN_TABLES, SinanJob
from app.modules.vigilancia.field_models import FIELD_OS_TABLES
from app.modules.vigilancia.sinan_transfer import backup, snapshot, transfer
from app.modules.vigilancia.sinan_store import BusyError, Store, StoreError
from tests import test_sinan_import as contract


@pytest.fixture
def store(tmp_path):
    engine = sa.create_engine('sqlite:///' + str(tmp_path / 'sinan-db.sqlite'), connect_args={'timeout': 3})
    for table in SINAN_TABLES:
        table.create(engine)
    yield DatabaseStore(engine)
    engine.dispose()


@pytest.mark.parametrize('check', [
    contract.test_api_complete_aggregates_all_pages_and_reimport_is_not_summed,
    contract.test_failure_and_partial_refresh_preserve_previous_completed_snapshot,
    contract.test_cancel_during_fetch_discards_late_page_and_releases_worker,
    contract.test_default_import_stops_at_100_without_fetching_an_eleventh_page,
    contract.test_csv_accepts_100_and_rejects_101_atomically,
    contract.test_time_budget_and_empty_read_are_distinguished,
    contract.test_export_is_bounded_saved_data_with_provenance_and_no_network,
])
def test_existing_import_contract_on_database(store, check):
    check(store)


@pytest.mark.parametrize('bad', [{'latitude': 'nan'}, {'classificacao': ''}, {'referencia': '=CMD'}, {'ano': '2025'}])
def test_invalid_files_are_atomic(store, bad):
    contract.test_invalid_csv_is_atomic_and_does_not_publish_earlier_valid_rows(store, bad)


def test_single_worker_and_owner_scope_across_store_instances(store):
    def create(owner):
        try:
            return contract.new_job(DatabaseStore(store.engine), owner)
        except BusyError:
            return None
    with ThreadPoolExecutor(max_workers=4) as executor:
        jobs = list(executor.map(create, ['a', 'b', 'c', 'd']))
    assert sum(value is not None for value in jobs) == 1
    job = next(value for value in jobs if value)
    owner = next(name for name in ('a', 'b', 'c', 'd') if store.get(job, name))
    assert store.get(job, 'stranger') is None
    store.cancel(job, 'stranger')
    store.finish(job, 'completed', {'total': 0})
    assert store.get(job, owner)['status'] == 'completed'


def test_restart_fences_late_result_and_csv_reuse_survives_reopen(store):
    old = contract.new_job(store)
    with store.engine.begin() as conn:
        conn.execute(SinanJob.__table__.update().where(SinanJob.id == old).values(updated=0))
    new = contract.new_job(store)
    store.finish(old, 'completed', {'total': 99})
    assert store.get(old, 'admin')['status'] == 'failed'
    store.finish(new, 'completed', {'total': 0})
    content = contract.csv_bytes()
    import hashlib
    job, reused = store.create('admin', kind='csv', **contract.SCOPE, demo=True, fingerprint=hashlib.sha256(content).hexdigest())
    contract.sinan_import.run_cases(store, job, contract.SCOPE, content, True)
    assert DatabaseStore(store.engine).create('admin', kind='csv', **contract.SCOPE, demo=True,
        fingerprint=hashlib.sha256(content).hexdigest()) == (job, True)
    assert len(store.cases(job, 'admin')) == 2
    assert store.cases(job, 'stranger') == []


def test_transfer_preserves_backup_ids_owners_and_cases_and_can_be_repeated(store, tmp_path):
    source = tmp_path / 'legacy.sqlite'
    legacy = Store(source)
    job = contract.new_job(legacy, owner='7:1', kind='csv', demo=True)
    contract.sinan_import.run_cases(legacy, job, contract.SCOPE, contract.csv_bytes(), True)
    original = source.read_bytes()
    saved = backup(source, tmp_path / 'private' / 'backup.sqlite')
    assert saved.stat().st_mode & 0o777 == 0o600
    result = transfer(saved, store.engine)
    assert result['inserted_jobs'] == 1 and result['inserted_cases'] == 2
    assert store.get(job, '7:1')['demo'] is True
    assert store.cases(job, '7:1') == legacy.cases(job, '7:1')
    assert store.get(job, '8:1') is None
    assert source.read_bytes() == original
    assert transfer(source, store.engine)['inserted_jobs'] == 0
    with pytest.raises(FileExistsError):
        backup(source, saved)


def test_transfer_rejects_active_worker_and_conflict_without_overwriting(store, tmp_path):
    source = tmp_path / 'legacy.sqlite'
    legacy = Store(source)
    job = contract.new_job(legacy)
    with pytest.raises(StoreError, match='ativa'):
        transfer(source, store.engine)
    legacy.finish(job, 'completed', {'total': 0})
    transfer(source, store.engine)
    with legacy.connection() as conn:
        conn.execute('UPDATE jobs SET message=? WHERE id=?', ('changed', job))
    with pytest.raises(StoreError, match='divergente'):
        transfer(source, store.engine)
    assert store.get(job, 'admin')['message'] == ''


def test_missing_tables_fail_without_creating_them(tmp_path):
    engine = sa.create_engine('sqlite:///' + str(tmp_path / 'empty.sqlite'))
    try:
        with pytest.raises(StoreError, match='migração'):
            DatabaseStore(engine).list('admin', **contract.SCOPE)
        assert sa.inspect(engine).get_table_names() == []
    finally:
        engine.dispose()


def test_additive_migration_matches_models_and_generates_postgres_sql(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'migrations/versions/c7f2a9d810e4_vigilancia_os_sinan_postgres.py'
    spec = importlib.util.spec_from_file_location('vigilancia_storage_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine('sqlite:///' + str(tmp_path / 'migration.sqlite'))
    metadata = sa.MetaData()
    sa.Table('solicitacoes', metadata, sa.Column('id', sa.Integer, primary_key=True))
    sa.Table('vigilancia_campo_lotes', metadata, sa.Column('id', sa.String(32), primary_key=True))
    metadata.create_all(engine)
    for table in (*SINAN_TABLES, *FIELD_OS_TABLES):
        table.to_metadata(metadata)
    try:
        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                migration.upgrade()
            assert compare_metadata(ctx, metadata) == []
            with Operations.context(ctx):
                migration.downgrade()
            assert set(sa.inspect(conn).get_table_names()) == {'solicitacoes', 'vigilancia_campo_lotes'}
        output = io.StringIO()
        with Operations.context(MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': output})):
            migration.upgrade()
        sql = output.getvalue()
        assert sql.count('CREATE TABLE') == 3
        assert "WHERE status = 'running'" in sql
        assert 'ALTER TABLE solicitacoes' not in sql and 'DROP TABLE' not in sql
    finally:
        engine.dispose()
