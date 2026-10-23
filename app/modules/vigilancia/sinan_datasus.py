"""Fonte oficial alternativa: arquivos DBC do SINAN no FTP do DATASUS.

Usada quando a API de dados abertos está indisponível. Baixa o arquivo nacional
do ano (preliminar ou final), converte para DBF e filtra o município em
streaming, sem carregar o arquivo inteiro em memória. Só agregados públicos
(semana, classificação, residência) são publicados; nenhum dado pessoal é salvo.
"""

import ftplib
import os
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone

from . import sinan

FTP_HOST = "ftp.datasus.gov.br"
FTP_DIRS = ("/dissemin/publicos/SINAN/DADOS/PRELIM", "/dissemin/publicos/SINAN/DADOS/FINAIS")
PREFIX = {"dengue": "DENG", "chikungunya": "CHIK", "zika": "ZIKA"}
CACHE_SECONDS = 6 * 3600
CACHE_DIR = os.path.join(tempfile.gettempdir(), "ija-sinan-datasus")


def file_name(disease, year):
    return f"{PREFIX[disease]}BR{year % 100:02d}.dbc"


def source_url(disease, year):
    return f"ftp://{FTP_HOST}{FTP_DIRS[0]}/{file_name(disease, year)}"


def _fresh(path):
    return os.path.exists(path) and os.path.getsize(path) > 0 and time.time() - os.path.getmtime(path) < CACHE_SECONDS


def download(disease, year, progress=None):
    """Devolve o caminho local do DBC, reaproveitando o cache por algumas horas."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    name = file_name(disease, year)
    target = os.path.join(CACHE_DIR, name)
    if _fresh(target):
        return target
    ftp = ftplib.FTP(FTP_HOST, timeout=60)
    try:
        ftp.login()
        ftp.set_pasv(True)
        last_error = None
        for directory in FTP_DIRS:
            try:
                ftp.cwd(directory)
                size = ftp.size(name)
            except ftplib.all_errors as exc:
                last_error = exc
                continue
            done = 0
            partial = target + ".part"
            with open(partial, "wb") as handle:
                def write(chunk):
                    nonlocal done
                    handle.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress("download", done, size)
                ftp.retrbinary(f"RETR {name}", write, blocksize=256 * 1024)
            os.replace(partial, target)
            return target
        raise sinan.SinanError(f"O DATASUS não publicou o arquivo {name} para este ano ({last_error}).")
    except ftplib.all_errors as exc:
        raise sinan.SinanError(f"Não foi possível baixar o arquivo do DATASUS ({exc}).") from exc
    finally:
        try:
            ftp.quit()
        except ftplib.all_errors:
            pass


def to_dbf(dbc_path):
    dbf_path = dbc_path[:-4] + ".dbf"
    if not (_fresh(dbf_path) and os.path.getmtime(dbf_path) >= os.path.getmtime(dbc_path)):
        from pyreaddbc import dbc2dbf
        dbc2dbf(dbc_path, dbf_path)
    return dbf_path


def _code(value):
    return sinan._code(value)


def iter_rows(dbf_path, *, ibge, year, tick=None):
    """Linhas do município de notificação, só com campos públicos agregáveis.

    tick() é chamado a cada 20 mil linhas lidas (mesmo sem encontrar o município), para o lote
    mostrar que está vivo e não ser marcado como interrompido em arquivos grandes.
    """
    from dbfread import DBF
    code = ibge[:6]
    scanned = 0
    for row in DBF(dbf_path, encoding="latin-1", load=False, ignore_missing_memofile=True):
        scanned += 1
        if tick and scanned % 20000 == 0:
            tick()
        if _code(row.get("ID_MUNICIP")) != code:
            continue
        notified = row.get("DT_NOTIFIC")
        row_year = _code(row.get("NU_ANO")) or (str(notified.year) if hasattr(notified, "year") else "")
        if row_year != str(year):
            continue
        week = _code(row.get("SEM_NOT"))
        if not (len(week) == 6 and abs(int(week[:4]) - year) <= 1 and 1 <= int(week[4:]) <= 53):
            week = None
        resident = _code(row.get("ID_MN_RESI"))
        yield {
            "week": week,
            "classification": _code(row.get("CLASSI_FIN")) or "unknown",
            "residence": "unknown" if len(resident) != 6 else "local" if resident == code else "other",
        }


def run(store, job_id, scope, *, max_seconds=900):
    """Mesmo contrato de sinan_import.run_api: publica só o resumo agregado."""
    disease, ibge, year = scope["disease"], scope["ibge"], scope["year"]
    started = time.monotonic()
    groups = Counter()

    def snapshot():
        return {**_summary(groups), "source_url": source_url(disease, year), "geographic_filter": "municipio_notificacao",
                "source": "datasus", "retrieved_at": datetime.now(timezone.utc).isoformat()}

    def progress(stage, done, total):
        if store.stopped(job_id):
            raise _Cancelled()
        store.progress(job_id, 0, 1 if stage == "download" else 2)

    try:
        if store.stopped(job_id):
            store.finish(job_id, "cancelled")
            return
        dbc_path = download(disease, year, progress)
        dbf_path = to_dbf(dbc_path)
        store.progress(job_id, 0, 2)
        count = 0
        def tick():
            if store.stopped(job_id):
                raise _Cancelled()
            store.progress(job_id, count, 3)

        for row in iter_rows(dbf_path, ibge=ibge, year=year, tick=tick):
            groups[(row["week"], row["classification"], row["residence"])] += 1
            count += 1
            if count % 500 == 0:
                if store.stopped(job_id):
                    store.finish(job_id, "cancelled")
                    return
                store.progress(job_id, count, 3)
            if time.monotonic() - started > max_seconds:
                store.finish(job_id, "partial", snapshot(), "Tempo máximo de leitura atingido. O lote é parcial.")
                return
        store.finish(job_id, "completed", snapshot(),
                     f"Leitura concluída do arquivo oficial {file_name(disease, year)} do DATASUS (município de notificação).")
    except _Cancelled:
        store.finish(job_id, "cancelled")
    except Exception as exc:
        message = str(exc) if isinstance(exc, (sinan.SinanError, ValueError)) else "Não foi possível concluir a leitura do DATASUS. O lote anterior foi preservado."
        store.finish(job_id, "failed", message=message)


class _Cancelled(Exception):
    pass


def _summary(groups):
    from .sinan_import import _summary as summary
    return summary(groups)
