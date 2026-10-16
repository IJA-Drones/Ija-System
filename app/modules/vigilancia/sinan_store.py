"""Small, private SINAN store. Never uses the operational database connection pool.

One running import per shared store, short transactions, immutable snapshots and
bounded storage. Deployments must mount SINAN_STORAGE_PATH on persistent local
storage; this is a single-host worker, not a distributed queue.
"""

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class StoreError(ValueError):
    pass


class BusyError(StoreError):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Creation is private even before sqlite connects (also applies to backups).
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL,
                    disease TEXT NOT NULL, ibge TEXT NOT NULL, year INTEGER NOT NULL,
                    demo INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0, pages INTEGER NOT NULL DEFAULT 0,
                    cancel INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '{}', fingerprint TEXT NOT NULL DEFAULT ''
                );
                CREATE UNIQUE INDEX IF NOT EXISTS sinan_single_worker
                    ON jobs ((1)) WHERE status = 'running';
                CREATE INDEX IF NOT EXISTS sinan_owner_scope
                    ON jobs (owner, disease, ibge, year, created DESC);
                CREATE TABLE IF NOT EXISTS cases (
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    reference TEXT NOT NULL, week TEXT, classification TEXT NOT NULL,
                    latitude REAL NOT NULL, longitude REAL NOT NULL,
                    PRIMARY KEY (job_id, reference)
                );
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=2000")
            # 64 MiB database ceiling, 2 MiB page cache, no unbounded WAL file.
            db.execute("PRAGMA max_page_count=16384")
            db.execute("PRAGMA cache_size=-2048")
            with db:
                yield db
        except sqlite3.Error as exc:
            raise StoreError("Armazenamento SINAN ocupado ou no limite. Tente novamente; a consulta pública continua disponível.") from exc
        finally:
            db.close()

    @staticmethod
    def _expire(db):
        db.execute("UPDATE jobs SET status='failed', message=? WHERE status='running' AND updated < ?",
                   ("Processamento interrompido. Inicie uma nova importação.", time.time() - 90))

    def create(self, owner, *, kind, disease, ibge, year, demo=False, fingerprint=""):
        now = time.time()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._expire(db)
            if fingerprint:
                previous = db.execute("SELECT id FROM jobs WHERE owner=? AND kind=? AND disease=? AND ibge=? AND year=? AND demo=? AND fingerprint=? AND status='completed' ORDER BY created DESC LIMIT 1",
                                      (owner, kind, disease, ibge, year, int(demo), fingerprint)).fetchone()
                if previous:
                    return previous["id"], True
            if db.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone():
                raise BusyError("Já existe uma importação em andamento. Aguarde a conclusão antes de iniciar outra.")
            if db.execute("SELECT count(*) FROM jobs").fetchone()[0] >= 1000:
                raise StoreError("Limite de 1.000 lotes atingido. Solicite manutenção do armazenamento SINAN.")
            job_id = uuid.uuid4().hex
            db.execute("INSERT INTO jobs (id, owner, kind, disease, ibge, year, demo, status, created, updated, fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?)",
                       (job_id, owner, kind, disease, ibge, year, int(demo), now, now, fingerprint))
        return job_id, False

    @staticmethod
    def _public(row):
        data = dict(row)
        data.pop("owner", None)
        data.pop("fingerprint", None)
        data["summary"] = json.loads(data["summary"])
        data["demo"] = bool(data["demo"])
        data["cancel"] = bool(data["cancel"])
        return data

    def list(self, owner, *, disease, ibge, year):
        with self.connection() as db:
            self._expire(db)
            rows = db.execute("SELECT * FROM jobs WHERE owner=? AND disease=? AND ibge=? AND year=? ORDER BY created DESC LIMIT 10",
                              (owner, disease, ibge, year)).fetchall()
            # A partial/failed refresh never replaces a completed snapshot.
            current = db.execute("SELECT * FROM jobs WHERE owner=? AND disease=? AND ibge=? AND year=? AND kind='api' AND status='completed' ORDER BY created DESC LIMIT 1",
                                 (owner, disease, ibge, year)).fetchone()
            if current and not any(row["id"] == current["id"] for row in rows):
                rows = rows[:9] + [current]
        return {"jobs": [self._public(row) for row in rows], "current_id": current["id"] if current else None}

    def get(self, job_id, owner):
        with self.connection() as db:
            self._expire(db)
            row = db.execute("SELECT * FROM jobs WHERE id=? AND owner=?", (job_id, owner)).fetchone()
        return self._public(row) if row else None

    def stopped(self, job_id):
        with self.connection() as db:
            row = db.execute("SELECT status, cancel FROM jobs WHERE id=?", (job_id,)).fetchone()
        return not row or row["status"] != "running" or bool(row["cancel"])

    def cancel(self, job_id, owner):
        with self.connection() as db:
            db.execute("UPDATE jobs SET cancel=1 WHERE id=? AND owner=? AND status='running'", (job_id, owner))

    def progress(self, job_id, count, pages):
        with self.connection() as db:
            db.execute("UPDATE jobs SET count=?, pages=?, updated=? WHERE id=? AND status='running'",
                       (count, pages, time.time(), job_id))

    def finish(self, job_id, status, summary=None, message="", cases=()):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status, cancel FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["status"] != "running":
                return
            if row["cancel"]:
                status, summary, cases, message = "cancelled", None, (), "Importação cancelada. O lote anterior foi preservado."
            if cases:
                db.executemany("INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?)",
                               ((job_id, r["reference"], r["week"], r["classification"], r["latitude"], r["longitude"]) for r in cases))
            db.execute("UPDATE jobs SET status=?, summary=?, message=?, updated=?, count=CASE WHEN ? IS NULL THEN count ELSE ? END WHERE id=?",
                       (status, json.dumps(summary or {}, separators=(",", ":")), message, time.time(),
                        summary.get("total") if summary else None, summary.get("total") if summary else None, job_id))

    def cases(self, job_id, owner):
        # Ownership is checked in SQL as well as at the HTTP boundary.
        with self.connection() as db:
            rows = db.execute("SELECT c.reference, c.week, c.classification, c.latitude, c.longitude FROM cases c JOIN jobs j ON j.id=c.job_id WHERE j.id=? AND j.owner=? AND j.status='completed' ORDER BY c.reference LIMIT 500",
                              (job_id, owner)).fetchall()
        return [dict(row) for row in rows]
