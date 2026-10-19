"""Migração isolada e SQL PostgreSQL, sem conectar ao Render."""

import importlib.util
import io
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from app.models import Prefeitura
from app.modules.vigilancia.field_models import FIELD_TABLES
from app.modules.vigilancia.field_store import FieldStore, FieldStoreError

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('field_migration',ROOT/'migrations/versions/a41c9e7f26b0_vigilancia_campo.py')
migration=importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def test_migration_upgrade_matches_models_and_downgrade_preserves_operational_data(tmp_path):
    engine=sa.create_engine('sqlite:///' + str(tmp_path/'migration.sqlite'))
    @sa.event.listens_for(engine,'connect')
    def foreign_keys(connection,_):
        connection.execute('PRAGMA foreign_keys=ON')
    Prefeitura.__table__.create(engine)
    with engine.begin() as conn:
        conn.execute(Prefeitura.__table__.insert().values(id=7,nome='Preservada',slug='preservada'))
        ctx=MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.upgrade()
        metadata=sa.MetaData()
        Prefeitura.__table__.to_metadata(metadata)
        for table in FIELD_TABLES:
            table.to_metadata(metadata)
        assert compare_metadata(ctx,metadata)==[]
        with Operations.context(ctx):
            migration.downgrade()
        assert conn.scalar(sa.select(Prefeitura.nome))=='Preservada'
        assert sa.inspect(conn).get_table_names()==['prefeituras']
    engine.dispose()


def test_postgresql_sql_creates_only_field_tables_with_bytea_and_json():
    output=io.StringIO()
    ctx=MigrationContext.configure(dialect_name='postgresql',opts={'as_sql':True,'output_buffer':output})
    with Operations.context(ctx):
        migration.upgrade()
    sql=output.getvalue()
    assert 'BYTEA' in sql and 'JSON' in sql
    assert sql.count('CREATE TABLE ')==5
    assert 'ALTER TABLE prefeituras' not in sql
    assert 'DROP TABLE' not in sql
    assert 'REFERENCES prefeituras' in sql
    config=Config()
    config.set_main_option('script_location',str(ROOT/'migrations'))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ['b6e9d2a4f017']
    assert set(scripts.get_revision('b6e9d2a4f017').down_revision) == {'a41c9e7f26b0', 'd82b46fa910c'}


def test_missing_migration_returns_controlled_error_without_creating_tables(tmp_path):
    engine=sa.create_engine('sqlite:///' + str(tmp_path/'empty.sqlite'))
    with pytest.raises(FieldStoreError,match='migração'):
        FieldStore(engine).history(7)
    assert sa.inspect(engine).get_table_names()==[]
    engine.dispose()
