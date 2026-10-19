"""Adiciona o contorno opcional do território. Sem --apply, somente leitura."""

import argparse
import importlib.util
import json
import os
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
PARENT, TARGET = "d8a31e62bc09", "e91c7b4a203d"
TABLE = "vigilancia_campo_quarteiroes"


def upgrade(engine, *, apply=False):
    with engine.connect() as conn, conn.begin():
        if not apply:
            conn.execute(sa.text("SET TRANSACTION READ ONLY"))
        conn.execute(sa.text("SET LOCAL lock_timeout = '3s'"))
        conn.execute(sa.text("SET LOCAL statement_timeout = '30s'"))
        conn.execute(sa.text("SET LOCAL search_path = public"))
        if apply:
            conn.execute(sa.select(sa.func.pg_advisory_xact_lock(1229603074, 2)))
        revisions = list(conn.scalars(sa.text("SELECT version_num FROM public.alembic_version")))
        columns = {column["name"] for column in sa.inspect(conn).get_columns(TABLE, schema="public")}
        if revisions == [TARGET] and "geometria" in columns:
            return dict(revision=TARGET, changed=False)
        if revisions != [PARENT] or "geometria" in columns:
            raise ValueError("A revisão ou a estrutura difere do plano esperado. Nenhuma migração foi aplicada.")
        if apply:
            spec = importlib.util.spec_from_file_location("geometry_upgrade", ROOT / f"migrations/versions/{TARGET}_geometria_territorio_liraa.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(conn)):
                module.upgrade()
            result = conn.execute(sa.text("UPDATE public.alembic_version SET version_num=:target WHERE version_num=:parent"), dict(target=TARGET, parent=PARENT))
            if result.rowcount != 1 or "geometria" not in {c["name"] for c in sa.inspect(conn).get_columns(TABLE, schema="public")}:
                raise ValueError("A conferência da migração falhou. A transação será desfeita.")
        return dict(revision=TARGET if apply else PARENT, target=TARGET, changed=apply, added_column="geometria")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env", interpolate=False)
    uri = os.environ.get("DATABASE_URL") or values.get("DATABASE_URL")
    if not uri:
        raise ValueError("DATABASE_URL não configurada.")
    url = make_url(uri.replace("postgres://", "postgresql://", 1))
    if url.get_backend_name() != "postgresql":
        raise ValueError("Esta atualização exige PostgreSQL.")
    engine = sa.create_engine(url, poolclass=NullPool, connect_args={"connect_timeout":10}, hide_parameters=True)
    try:
        print(json.dumps(upgrade(engine, apply=args.apply), ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, sa.exc.SQLAlchemyError) as exc:
        print(json.dumps({"status":"error", "message":str(exc) if isinstance(exc, ValueError) else "Falha na conexão ou migração; nenhuma alteração parcial foi mantida."}, ensure_ascii=False))
        raise SystemExit(1)
