"""Prepare only the Central TI tables in the explicitly authorized Neon test DB.

Default mode is read-only. --apply installs the pending migration directly,
without running other migrations or changing the general alembic_version.
--seed-profiles adds missing profile configurations, with no permissions selected.
No login account is created or changed. Never call the application factory here.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "migrations/pending/c1a0f8b6d2e4_add_central_ti_configurations.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("central_ti_pending", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def target_url():
    # Read only DATABASE_URL from this checkout's .env; don't load other settings.
    uri = dotenv_values(ROOT / ".env").get("DATABASE_URL")
    if not uri:
        raise ValueError("DATABASE_URL não configurada.")
    url = make_url(uri.replace("postgres://", "postgresql://", 1))
    if url.get_backend_name() != "postgresql" or not (url.host or "").lower().endswith(".neon.tech"):
        raise ValueError("Este comando aceita somente o Neon de testes autorizado.")
    if url.query.get("sslmode") != "require":
        raise ValueError("A conexão Neon deve exigir SSL.")
    identifier = "|".join((url.host or "", url.database or "", url.username or ""))
    return url, hashlib.sha256(identifier.encode()).hexdigest()[:16]


def inspect_state(connection, migration):
    if connection.execute(sa.text("SELECT current_schema()")).scalar_one() != "public":
        raise ValueError("Schema inesperado; esperado public.")
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    if "usuarios" not in tables:
        raise ValueError("A tabela usuarios deve existir antes de preparar a central.")
    revisions = connection.execute(sa.text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars().all() if "alembic_version" in tables else []
    users_count = connection.execute(sa.text("SELECT count(*) FROM usuarios")).scalar_one()
    central_tables = sorted(tables & set(migration.EXPECTED_COLUMNS))
    if central_tables and len(central_tables) != len(migration.EXPECTED_COLUMNS):
        raise ValueError("Estrutura parcial da central; nenhuma alteração será aplicada.")
    profiles = []
    if central_tables:
        migration.validate_existing_schema(connection)
        profiles = connection.execute(sa.text("SELECT perfil_codigo FROM central_ti_perfis_configuracoes ORDER BY perfil_codigo")).scalars().all()
    return {"alembic_revisions": revisions, "users_count": users_count,
            "central_tables": central_tables, "profiles": profiles}


def seed_profiles(connection, profiles):
    batch = str(uuid4())
    added = []
    audit_insert = sa.text("""
        INSERT INTO central_ti_auditoria
            (lote, perfil_codigo, usuario_id, usuario_login, versao_anterior, versao_nova, antes, depois)
        VALUES (:batch, :profile, NULL, 'inicializacao_neon', 0, 1, :before, :after)
    """).bindparams(sa.bindparam("before", type_=sa.JSON), sa.bindparam("after", type_=sa.JSON))
    for profile in profiles:
        inserted = connection.execute(sa.text("""
            INSERT INTO central_ti_perfis_configuracoes (perfil_codigo, versao)
            VALUES (:profile, 1) ON CONFLICT (perfil_codigo) DO NOTHING
            RETURNING perfil_codigo
        """), {"profile": profile["id"]}).scalar_one_or_none()
        if inserted:
            connection.execute(audit_insert, {"batch": batch, "profile": inserted,
                               "before": {"areas": [], "permissions": []},
                               "after": {"areas": [], "permissions": []}})
            added.append(inserted)
    return added


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--seed-profiles", action="store_true")
    parser.add_argument("--expected-target", help="Fingerprint obtained in read-only mode")
    args = parser.parse_args()
    engine = None
    try:
        url, fingerprint = target_url()
        if args.apply and args.expected_target != fingerprint:
            raise ValueError("Confirme o mesmo destino inspecionado com --expected-target.")
        if args.seed_profiles and not args.apply:
            raise ValueError("A população exige --apply.")
        migration = load_migration()
        profiles = json.loads((ROOT / "app/modules/gestao_ti/catalog.json").read_text())["profiles"]
        engine = sa.create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 10}, hide_parameters=True)
        with engine.begin() as connection:
            if not args.apply:
                connection.execute(sa.text("SET TRANSACTION READ ONLY"))
            connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(sa.text("SET LOCAL statement_timeout = '60s'"))
            if args.apply:
                connection.execute(sa.text("SELECT pg_advisory_xact_lock(481725910063)"))
            before = inspect_state(connection, migration)
            added = []
            if args.apply:
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
                if args.seed_profiles:
                    added = seed_profiles(connection, profiles)
            after = inspect_state(connection, migration)
            if (before["alembic_revisions"], before["users_count"]) != (after["alembic_revisions"], after["users_count"]):
                raise ValueError("O histórico geral ou as contas mudaram; transação cancelada.")
        # Only report success after the transaction commits.
        print(json.dumps({"applied": args.apply, "target_fingerprint": fingerprint,
                          "tables_created": sorted(set(after["central_tables"]) - set(before["central_tables"])),
                          "profiles_added": added, **after}, ensure_ascii=False))
    except Exception as exc:
        # Driver errors can contain credentials or personal data; never print them.
        message = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else "Falha de conexão ou SQL; transação não confirmada."
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "message": message}, ensure_ascii=False))
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
