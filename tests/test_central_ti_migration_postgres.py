"""Opt-in PostgreSQL checks; never read application configuration or .env.

The user-authorized Neon homologation database is accepted only by its pinned
host/database/user fingerprint and required TLS. Production and other remote
databases are rejected before connecting. No Docker dependency is required.

Example (a disposable local PostgreSQL database only)::

    IJA_CENTRAL_TI_TEST_POSTGRES_URL=postgresql+psycopg2://test:test@127.0.0.1:55432/ija_central_ti_test_migration \
        .venv/bin/python -m pytest tests/test_central_ti_migration_postgres.py -q

Each integration test creates its own schema inside an outer transaction. The
transaction is always rolled back, including all schema objects and test data.
"""

import hashlib
import os
from pathlib import Path
import re
from unittest.mock import patch
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url


REVISION = "c1a0f8b6d2e4"
PREVIOUS_REVISION = "a71d9c4e203b"
ENVIRONMENT_VARIABLE = "IJA_CENTRAL_TI_TEST_POSTGRES_URL"
NEON_TEST_FINGERPRINT = "b90eb571d84c0287"
MIGRATIONS_PATH = Path(__file__).resolve().parents[1] / "migrations"
CENTRAL_TABLES = {
    "central_ti_perfis_configuracoes",
    "central_ti_selecoes",
    "central_ti_auditoria",
}


def authorized_postgres_url(value):
    """Validate the complete destination before opening any connection."""
    try:
        url = make_url(value)
    except (TypeError, ValueError, sa.exc.ArgumentError):
        raise ValueError("Informe uma URL PostgreSQL de teste autorizada.") from None
    if url.drivername in {"postgresql", "postgresql+psycopg2", "postgresql+psycopg"}:
        if (
            url.host in {"localhost", "127.0.0.1", "::1"}
            and re.fullmatch(r"ija_central_ti_test_[a-z0-9_]+", url.database or "")
            and not url.query
        ):
            return url
        fingerprint = hashlib.sha256(
            f"{url.host}|{url.database}|{url.username}".encode("utf-8")
        ).hexdigest()[:16]
        if (
            (url.host or "").endswith(".neon.tech")
            and url.port in {None, 5432}
            and fingerprint == NEON_TEST_FINGERPRINT
            and set(url.query) <= {"sslmode", "channel_binding"}
            and url.query.get("sslmode") in {"require", "verify-full"}
            and url.query.get("channel_binding", "prefer") in {"require", "prefer", "disable"}
        ):
            return url
    raise ValueError(
        "Teste permitido somente em PostgreSQL local descartável ou no Neon de "
        "homologação autorizado, com TLS e sem parâmetros de redirecionamento."
    )


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://test:test@production.example/ija_central_ti_test_migration",
        "postgresql://test:test@ep-example.neon.tech/ija_central_ti_test_migration",
        "postgresql://test:test@ep-example.neon.tech/neondb?sslmode=require",
        "postgresql://test:test@127.0.0.1/production",
        "postgresql://test:test@127.0.0.1/ija_central_ti_test_migration?host=production.example",
        "postgresql://test:test@localhost/ija_central_ti_test_migration?service=production",
        "sqlite:///:memory:",
    ],
)
def test_postgres_fixture_rejects_unsafe_destinations(value):
    with pytest.raises(ValueError):
        authorized_postgres_url(value)


def test_postgres_fixture_accepts_explicit_local_disposable_database():
    url = authorized_postgres_url(
        "postgresql+psycopg2://test:test@127.0.0.1:55432/ija_central_ti_test_migration"
    )
    assert url.host == "127.0.0.1"
    assert url.database == "ija_central_ti_test_migration"


@pytest.mark.parametrize("sslmode", ["require", "verify-full"])
def test_postgres_fixture_accepts_pinned_neon_with_tls(monkeypatch, sslmode):
    # Synthetic endpoint only; the real authorized fingerprint stays pinned.
    value = f"postgresql+psycopg2://test:test@ep-unit-test.neon.tech/neondb?sslmode={sslmode}&channel_binding=require"
    synthetic_fingerprint = hashlib.sha256(
        b"ep-unit-test.neon.tech|neondb|test"
    ).hexdigest()[:16]
    monkeypatch.setitem(globals(), "NEON_TEST_FINGERPRINT", synthetic_fingerprint)
    assert authorized_postgres_url(value).host == "ep-unit-test.neon.tech"


@pytest.mark.parametrize(
    "query",
    [
        "sslmode=disable",
        "sslmode=prefer",
        "sslmode=require&host=production.example",
        "sslmode=require&service=production",
        "sslmode=require&options=-csearch_path=public",
        "sslmode=require&channel_binding=invalid",
    ],
)
def test_postgres_fixture_rejects_unsafe_neon_options_even_with_matching_fingerprint(monkeypatch, query):
    monkeypatch.setitem(
        globals(), "NEON_TEST_FINGERPRINT",
        hashlib.sha256(b"ep-unit-test.neon.tech|neondb|test").hexdigest()[:16],
    )
    with pytest.raises(ValueError):
        authorized_postgres_url(f"postgresql://test:test@ep-unit-test.neon.tech/neondb?{query}")


@pytest.fixture
def postgres_connection():
    value = os.environ.get(ENVIRONMENT_VARIABLE)
    if not value:
        pytest.skip(f"Configure {ENVIRONMENT_VARIABLE} com PostgreSQL de teste autorizado.")
    url = authorized_postgres_url(value)
    engine = sa.create_engine(url, connect_args={"connect_timeout": 5})
    schema_name = "central_ti_test_" + uuid4().hex
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                connection.execute(sa.text(f'CREATE SCHEMA "{schema_name}"'))
                # Only this random schema is visible; no application tables are used.
                connection.execute(sa.text(f'SET LOCAL search_path TO "{schema_name}"'))
                connection.execute(sa.text("SET LOCAL lock_timeout = '3s'"))
                connection.execute(sa.text("SET LOCAL statement_timeout = '15s'"))
                connection.execute(sa.text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, login VARCHAR(50) NOT NULL)"))
                connection.execute(sa.text("INSERT INTO usuarios VALUES (17, 'usuario-preservado')"))
                connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
                connection.execute(sa.text("INSERT INTO alembic_version VALUES (:revision)"), {"revision": PREVIOUS_REVISION})
                try:
                    yield connection
                finally:
                    transaction.rollback()
    finally:
        engine.dispose()


def migration_script():
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_PATH))
    return ScriptDirectory.from_config(config)


def upgrade_from_previous(connection):
    """Use Alembic's revision scheduler and real version-table update."""
    scripts = migration_script()
    assert scripts.get_heads() == [REVISION]
    assert scripts.get_revision(REVISION).down_revision == PREVIOUS_REVISION
    context = MigrationContext.configure(
        connection,
        opts={"fn": lambda heads, _context: scripts._upgrade_revs(REVISION, heads)},
    )
    with Operations.context(context):
        context.run_migrations()


def assert_preserved_user_and_revision(connection, revision):
    assert connection.execute(sa.text("SELECT id, login FROM usuarios")).all() == [
        (17, "usuario-preservado")
    ]
    assert connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalars().all() == [revision]


def test_postgres_creates_isolated_tables_and_advances_revision(postgres_connection):
    connection = postgres_connection
    upgrade_from_previous(connection)
    assert CENTRAL_TABLES <= set(sa.inspect(connection).get_table_names())
    migration_script().get_revision(REVISION).module.validate_existing_schema(connection)
    for table in CENTRAL_TABLES:
        assert connection.execute(sa.text(f'SELECT count(*) FROM "{table}"')).scalar_one() == 0
    assert_preserved_user_and_revision(connection, REVISION)


def test_postgres_adopts_existing_tables_without_changing_rows(postgres_connection):
    connection = postgres_connection
    migration = migration_script().get_revision(REVISION).module
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
    connection.execute(sa.text("INSERT INTO central_ti_perfis_configuracoes (perfil_codigo, versao, atualizado_por_id) VALUES ('admin', 3, 17)"))
    connection.execute(sa.text("INSERT INTO central_ti_selecoes VALUES ('admin', 'area:prefeitura'), ('admin', 'prefeitura.mapas.consultar')"))
    connection.execute(
        sa.text("INSERT INTO central_ti_auditoria (lote, perfil_codigo, usuario_id, usuario_login, versao_anterior, versao_nova, antes, depois) VALUES (:lote, 'admin', 17, 'usuario-preservado', 2, 3, :antes, :depois)").bindparams(
            sa.bindparam("antes", type_=sa.JSON()),
            sa.bindparam("depois", type_=sa.JSON()),
        ),
        {"lote": str(uuid4()), "antes": ["area:prefeitura"], "depois": ["area:prefeitura", "prefeitura.mapas.consultar"]},
    )
    rows_before = {
        table: connection.execute(sa.text(f'SELECT * FROM "{table}" ORDER BY 1, 2')).all()
        for table in CENTRAL_TABLES
    }
    oids_before = {
        table: connection.execute(sa.text("SELECT CAST(:table AS regclass)::oid"), {"table": table}).scalar_one()
        for table in CENTRAL_TABLES
    }
    upgrade_from_previous(connection)
    for table in CENTRAL_TABLES:
        assert connection.execute(sa.text(f'SELECT * FROM "{table}" ORDER BY 1, 2')).all() == rows_before[table]
        assert connection.execute(sa.text("SELECT CAST(:table AS regclass)::oid"), {"table": table}).scalar_one() == oids_before[table]
    assert_preserved_user_and_revision(connection, REVISION)


def test_postgres_rejects_partial_installation_without_stamping(postgres_connection):
    connection = postgres_connection
    connection.execute(sa.text("CREATE TABLE central_ti_perfis_configuracoes (perfil_codigo VARCHAR(20) PRIMARY KEY)"))
    with pytest.raises(RuntimeError):
        with connection.begin_nested():
            upgrade_from_previous(connection)
    assert set(sa.inspect(connection).get_table_names()) & CENTRAL_TABLES == {
        "central_ti_perfis_configuracoes"
    }
    assert_preserved_user_and_revision(connection, PREVIOUS_REVISION)


def test_postgres_rolls_back_new_ddl_on_failure(postgres_connection):
    connection = postgres_connection
    migration = migration_script().get_revision(REVISION).module
    with patch.object(migration.op, "create_index", side_effect=RuntimeError("falha simulada")):
        with pytest.raises(RuntimeError, match="falha simulada"):
            with connection.begin_nested():
                upgrade_from_previous(connection)
    assert not set(sa.inspect(connection).get_table_names()) & CENTRAL_TABLES
    assert_preserved_user_and_revision(connection, PREVIOUS_REVISION)
