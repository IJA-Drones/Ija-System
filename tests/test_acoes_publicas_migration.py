"""Migração aditiva em SQLite descartável e compilação SQL PostgreSQL offline."""
import importlib.util
import io
from pathlib import Path

import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from app.extensions import db
from app.models import AcaoPublica, AcaoPublicaMidia, AcaoPublicaEvento

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('actions_migration',ROOT/'migrations/versions/a73e5c9b204f_acoes_publicas.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
TABLES = [AcaoPublica.__table__, AcaoPublicaMidia.__table__, AcaoPublicaEvento.__table__]


def test_upgrade_matches_models_and_downgrade_preserves_existing_tables(tmp_path):
    engine = sa.create_engine('sqlite:///'+str(tmp_path/'migration.sqlite'))
    base_tables = [t for t in db.metadata.sorted_tables if t not in TABLES]
    db.metadata.create_all(engine,tables=base_tables)
    with engine.begin() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            migration.upgrade()
        assert compare_metadata(ctx,db.metadata) == []
        with Operations.context(ctx):
            migration.downgrade()
        assert set(sa.inspect(connection).get_table_names()) == {t.name for t in base_tables}
    engine.dispose()


def test_postgres_ddl_and_single_revision_chain():
    output = io.StringIO()
    ctx = MigrationContext.configure(dialect_name='postgresql',opts={'as_sql':True,'output_buffer':output})
    with Operations.context(ctx):
        migration.upgrade()
    sql = output.getvalue()
    assert sql.count('CREATE TABLE ') == 3
    assert 'FOREIGN KEY(acao_id, prefeitura_id)' in sql
    assert 'JSON' in sql and 'ON DELETE SET NULL' in sql
    assert 'ALTER TABLE' not in sql and 'DROP TABLE' not in sql
    config = Config()
    config.set_main_option('script_location',str(ROOT/'migrations'))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == [migration.revision]
    assert scripts.get_revision(migration.revision).down_revision == 'f2a6d9c1074e'
