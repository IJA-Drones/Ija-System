"""Transferência idempotente do SQLite legado, sem alterar a origem."""

import json
import os
import sqlite3
import time
from pathlib import Path

import sqlalchemy as sa

from .sinan_database import DatabaseStore
from .sinan_models import SinanCase, SinanJob
from .sinan_store import StoreError


def snapshot(path):
    path = Path(path).resolve()
    if not path.is_file():
        return [], []
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as source:
            source.row_factory = sqlite3.Row
            source.execute("PRAGMA query_only=ON")
            source.execute("BEGIN")
            names = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"jobs", "cases"} <= names:
                raise StoreError("O arquivo informado não contém o armazenamento SINAN esperado.")
            jobs = [dict(row) for row in source.execute("SELECT * FROM jobs ORDER BY id LIMIT 1001")]
            cases = [dict(row) for row in source.execute('SELECT * FROM cases ORDER BY job_id, reference LIMIT 100001')]
    except sqlite3.Error as exc:
        raise StoreError("Não foi possível ler o SQLite SINAN de origem.") from exc
    if len(jobs) > 1000 or len(cases) > 100000:
        raise StoreError("A origem excede os limites previstos. A transferência precisa de revisão.")
    for row in jobs:
        if row["status"] == "running":
            if row["updated"] >= time.time() - 90:
                raise StoreError("Existe uma importação SINAN ativa na origem. Aguarde sua conclusão antes de transferir.")
            row.update(status="failed", message="Processamento interrompido antes da transferência de armazenamento.")
        try:
            row["summary"] = json.loads(row["summary"])
        except (TypeError, ValueError) as exc:
            raise StoreError("Há um resumo SINAN inválido na origem. Nenhum dado foi transferido.") from exc
        if not isinstance(row["summary"], dict):
            raise StoreError("Há um resumo SINAN inválido na origem.")
        row.update(demo=bool(row["demo"]), cancel=bool(row["cancel"]), pages=row.get("pages", 0))
        if set(row) != set(SinanJob.__table__.c.keys()):
            raise StoreError("O formato do SQLite SINAN precisa de revisão antes da transferência.")
    return jobs, cases


def backup(path, destination):
    """Backup consistente, inclusive quando a origem possui journal/WAL."""
    path, destination = Path(path).resolve(), Path(destination).resolve()
    if path == destination:
        raise StoreError("O backup deve usar outro arquivo.")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as source:
            with sqlite3.connect(destination) as target:
                source.backup(target)
        snapshot(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def transfer(path, engine):
    jobs, cases = snapshot(path)
    if not jobs:
        if cases:
            raise StoreError("Existem casos sem lotes na origem. Revise antes de transferir.")
        return {"source_jobs": 0, "source_cases": 0, "inserted_jobs": 0, "inserted_cases": 0}
    job_ids = [row["id"] for row in jobs]
    if any(row["job_id"] not in job_ids for row in cases):
        raise StoreError("Existem casos sem lotes na origem. Revise antes de transferir.")
    job_table, case_table = SinanJob.__table__, SinanCase.__table__
    with DatabaseStore(engine).connection(write=True) as conn:
        if conn.scalar(sa.select(sa.func.count()).select_from(job_table).where(job_table.c.status == "running")):
            raise StoreError("Existe uma importação SINAN ativa no destino. Aguarde sua conclusão.")
        existing_jobs = {row["id"]: dict(row) for row in conn.execute(sa.select(job_table).where(job_table.c.id.in_(job_ids))).mappings()}
        existing_cases = {(row["job_id"], row["reference"]): dict(row) for row in conn.execute(
            sa.select(case_table).where(case_table.c.job_id.in_(job_ids))).mappings()}
        expected_cases = {(row["job_id"], row["reference"]): row for row in cases}
        if any(key not in expected_cases for key in existing_cases):
            raise StoreError("Um lote no destino contém casos diferentes da origem. Nenhum dado foi sobrescrito.")
        if any(row != existing_jobs[row["id"]] for row in jobs if row["id"] in existing_jobs):
            raise StoreError("Existe um lote divergente no destino. Nenhum dado foi sobrescrito.")
        if any(row != existing_cases[key] for key, row in expected_cases.items() if key in existing_cases):
            raise StoreError("Existe um caso divergente no destino. Nenhum dado foi sobrescrito.")
        new_jobs = [row for row in jobs if row["id"] not in existing_jobs]
        new_cases = [row for key, row in expected_cases.items() if key not in existing_cases]
        if conn.scalar(sa.select(sa.func.count()).select_from(job_table)) + len(new_jobs) > 1000:
            raise StoreError("A transferência ultrapassaria o limite de lotes SINAN no destino.")
        if new_jobs:
            conn.execute(job_table.insert(), new_jobs)
        if new_cases:
            conn.execute(case_table.insert(), new_cases)
        saved_jobs = {row["id"]: dict(row) for row in conn.execute(sa.select(job_table).where(job_table.c.id.in_(job_ids))).mappings()}
        saved_cases = {(row["job_id"], row["reference"]): dict(row) for row in conn.execute(
            sa.select(case_table).where(case_table.c.job_id.in_(job_ids))).mappings()}
        if saved_jobs != {row["id"]: row for row in jobs} or saved_cases != expected_cases:
            raise StoreError("A verificação da cópia falhou. A transferência foi desfeita.")
    return {"source_jobs": len(jobs), "source_cases": len(cases),
            "inserted_jobs": len(new_jobs), "inserted_cases": len(new_cases)}
