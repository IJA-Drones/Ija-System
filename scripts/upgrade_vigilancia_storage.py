"""Instala apenas a revisão de vigilância e copia o SQLite com backup.

Sem --apply, confere o plano em transação somente de leitura. Não inicia Flask,
agendadores ou importadores. Reinicie os processos da aplicação após a operação.
"""

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.modules.vigilancia.sinan_transfer import backup, snapshot, transfer
from app.modules.vigilancia.sinan_store import StoreError

PARENT, TARGET = "b6e9d2a4f017", "c7f2a9d810e4"
TABLES = {"vigilancia_campo_os", "vigilancia_sinan_lotes", "vigilancia_sinan_casos"}


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
        present = TABLES & set(sa.inspect(conn).get_table_names(schema="public"))
        if revisions == [TARGET] and present == TABLES:
            return {"database_revision": TARGET, "target_revision": TARGET, "schema_changed": False}
        if revisions != [PARENT] or present:
            raise StoreError("A versão ou a estrutura do banco difere do plano esperado. Nenhuma migração foi aplicada.")
        if apply:
            spec = importlib.util.spec_from_file_location("vigilancia_storage_upgrade", ROOT / f"migrations/versions/{TARGET}_vigilancia_os_sinan_postgres.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(conn)):
                module.upgrade()
            result = conn.execute(sa.text("UPDATE public.alembic_version SET version_num=:target WHERE version_num=:parent"),
                                  {"target": TARGET, "parent": PARENT})
            if result.rowcount != 1 or not TABLES <= set(sa.inspect(conn).get_table_names(schema="public")):
                raise StoreError("A verificação da migração falhou; a transação será desfeita.")
        return {"database_revision": TARGET if apply else PARENT, "target_revision": TARGET, "schema_changed": apply}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sqlite-source", type=Path)
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env", interpolate=False)
    uri = os.environ.get("DATABASE_URL") or values.get("DATABASE_URL")
    if not uri:
        raise StoreError("DATABASE_URL não configurada.")
    url = make_url(uri.replace("postgres://", "postgresql://", 1))
    if url.get_backend_name() != "postgresql":
        raise StoreError("Esta atualização exige a conexão PostgreSQL configurada para o projeto.")
    source = args.sqlite_source or Path(os.environ.get("SINAN_STORAGE_PATH") or values.get("SINAN_STORAGE_PATH") or ROOT / "instance/sinan/sinan.sqlite")
    jobs, cases = snapshot(source)
    engine = sa.create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 10}, hide_parameters=True)
    try:
        result = upgrade(engine, apply=args.apply)
        result.update(source_jobs=len(jobs), source_cases=len(cases), applied=args.apply)
        if args.apply and source.is_file():
            destination = ROOT / "instance/sinan/backups" / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}.sqlite"
            saved = backup(source, destination)
            result.update(transfer(saved, engine), backup=str(saved.relative_to(ROOT)))
            if snapshot(source) != snapshot(saved):
                raise StoreError("A origem mudou durante a transferência. Preserve o backup e repita a sincronização antes de reiniciar a aplicação.")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except (StoreError, sa.exc.SQLAlchemyError, OSError) as exc:
        message = str(exc) if isinstance(exc, StoreError) else "Não foi possível concluir a atualização. Confira a conexão e os backups; nenhum dado da origem foi removido."
        print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))
        raise SystemExit(1)
