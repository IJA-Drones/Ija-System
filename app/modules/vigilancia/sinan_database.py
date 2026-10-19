"""Store SINAN transacional. O engine também funciona fora do contexto HTTP."""

import copy
import time
import uuid
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError

from .sinan_models import SinanCase, SinanJob
from .sinan_store import BusyError, StoreError


class DatabaseStore:
    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def connection(self, *, write=False):
        try:
            with self.engine.connect() as conn, conn.begin():
                if write:
                    if self.engine.dialect.name == "postgresql":
                        conn.execute(sa.text("SET LOCAL lock_timeout = '3s'"))
                        conn.execute(sa.select(sa.func.pg_advisory_xact_lock(1229603074, 1)))
                    elif self.engine.dialect.name == "sqlite":
                        conn.exec_driver_sql("BEGIN IMMEDIATE")
                    else:
                        raise StoreError("O banco configurado não suporta o armazenamento SINAN.")
                yield conn
        except SQLAlchemyError as exc:
            raise StoreError("Não foi possível acessar o SINAN no banco. Confira a migração e a conexão; os dados anteriores foram preservados.") from exc

    @staticmethod
    def _public(row):
        if row is None:
            return None
        result = copy.deepcopy(dict(row))
        result.pop("owner", None)
        result.pop("fingerprint", None)
        return result

    @staticmethod
    def _expire(conn):
        table = SinanJob.__table__
        conn.execute(table.update().where(table.c.status == "running", table.c.updated < time.time() - 90).values(
            status="failed", message="Processamento interrompido. Inicie uma nova importação."))

    def create(self, owner, *, kind, disease, ibge, year, demo=False, fingerprint=""):
        table = SinanJob.__table__
        with self.connection(write=True) as conn:
            self._expire(conn)
            if fingerprint:
                previous = conn.scalar(sa.select(table.c.id).where(
                    table.c.owner == owner, table.c.kind == kind, table.c.disease == disease,
                    table.c.ibge == ibge, table.c.year == year, table.c.demo == bool(demo),
                    table.c.fingerprint == fingerprint, table.c.status == "completed"
                ).order_by(table.c.created.desc()).limit(1))
                if previous:
                    return previous, True
            if conn.scalar(sa.select(sa.func.count()).select_from(table).where(table.c.status == "running")):
                raise BusyError("Já existe uma importação em andamento. Aguarde a conclusão antes de iniciar outra.")
            if conn.scalar(sa.select(sa.func.count()).select_from(table)) >= 1000:
                raise StoreError("Limite de 1.000 lotes atingido. Solicite manutenção do armazenamento SINAN.")
            job_id, now = uuid.uuid4().hex, time.time()
            conn.execute(table.insert().values(id=job_id, owner=owner, kind=kind, disease=disease,
                         ibge=ibge, year=year, demo=bool(demo), status="running", created=now,
                         updated=now, count=0, pages=0, cancel=False, message="", summary={}, fingerprint=fingerprint))
        return job_id, False

    def list(self, owner, *, disease, ibge, year):
        table = SinanJob.__table__
        scope = (table.c.owner == owner, table.c.disease == disease, table.c.ibge == ibge, table.c.year == year)
        with self.connection(write=True) as conn:
            self._expire(conn)
            rows = list(conn.execute(sa.select(table).where(*scope).order_by(table.c.created.desc(), table.c.id.desc()).limit(10)).mappings())
            current = conn.execute(sa.select(table).where(*scope, table.c.kind == "api", table.c.status == "completed")
                                   .order_by(table.c.created.desc(), table.c.id.desc()).limit(1)).mappings().first()
            if current and not any(row["id"] == current["id"] for row in rows):
                rows = rows[:9] + [current]
        return {"jobs": [self._public(row) for row in rows], "current_id": current["id"] if current else None}

    def get(self, job_id, owner):
        table = SinanJob.__table__
        with self.connection() as conn:
            return self._public(conn.execute(sa.select(table).where(table.c.id == job_id, table.c.owner == owner)).mappings().first())

    def published(self, owner, *, ibge, year, disease, demo):
        """Leitura de snapshots para o painel; não expira nem inicia importações."""
        table = SinanJob.__table__
        with self.connection() as conn:
            rows = conn.execute(sa.select(table).where(
                table.c.owner == owner, table.c.ibge == ibge, table.c.year == year,
                table.c.disease == disease, table.c.demo == demo,
                table.c.status.in_(("completed", "partial")))
                .order_by(table.c.created.desc(), table.c.id.desc()).limit(20)).mappings()
            return [self._public(row) for row in rows]

    def stopped(self, job_id):
        table = SinanJob.__table__
        with self.connection() as conn:
            row = conn.execute(sa.select(table.c.status, table.c.cancel).where(table.c.id == job_id)).first()
        return not row or row.status != "running" or bool(row.cancel)

    def cancel(self, job_id, owner):
        table = SinanJob.__table__
        with self.connection(write=True) as conn:
            conn.execute(table.update().where(table.c.id == job_id, table.c.owner == owner, table.c.status == "running").values(cancel=True))

    def progress(self, job_id, count, pages):
        table = SinanJob.__table__
        with self.connection(write=True) as conn:
            conn.execute(table.update().where(table.c.id == job_id, table.c.status == "running").values(
                count=count, pages=pages, updated=time.time()))

    def finish(self, job_id, status, summary=None, message="", cases=()):
        table = SinanJob.__table__
        with self.connection(write=True) as conn:
            row = conn.execute(sa.select(table.c.status, table.c.cancel).where(table.c.id == job_id)).first()
            if not row or row.status != "running":
                return
            if row.cancel:
                status, summary, cases, message = "cancelled", None, (), "Importação cancelada. O lote anterior foi preservado."
            if cases:
                conn.execute(SinanCase.__table__.insert(), [dict(job_id=job_id, **record) for record in cases])
            values = dict(status=status, summary=summary or {}, message=message, updated=time.time())
            if summary is not None and summary.get("total") is not None:
                values["count"] = summary["total"]
            conn.execute(table.update().where(table.c.id == job_id).values(**values))

    def cases(self, job_id, owner):
        jobs, cases = SinanJob.__table__, SinanCase.__table__
        with self.connection() as conn:
            rows = conn.execute(sa.select(cases.c.reference, cases.c.week, cases.c.classification,
                                        cases.c.latitude, cases.c.longitude).join(jobs, jobs.c.id == cases.c.job_id)
                                .where(jobs.c.id == job_id, jobs.c.owner == owner, jobs.c.status == "completed")
                                .order_by(cases.c.reference).limit(500)).mappings()
            return [dict(row) for row in rows]
