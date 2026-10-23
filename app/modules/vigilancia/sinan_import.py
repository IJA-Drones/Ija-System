"""Bounded background ingestion; only small normalized snapshots are published."""

import csv
import hashlib
import io
import math
import re
import threading
import time
from collections import Counter

from . import sinan

MAX_BYTES = 1024 * 1024
MAX_CASES = 100
MAX_RECORDS = 100
MAX_SECONDS = 120
COLUMNS = ("referencia", "doenca", "municipio_ibge", "ano", "semana", "classificacao", "latitude", "longitude")
CASE_CLASSES = {"suspeito": "Suspeito", "confirmado": "Confirmado", "descartado": "Descartado", "ignorado": "Não informado"}


def validate_scope(values):
    disease, ibge = values.get("disease"), values.get("ibge")
    raw_year = values.get("year")
    if isinstance(raw_year, bool) or not re.fullmatch(r"[0-9]{4}", str(raw_year or "")):
        raise ValueError("Informe um ano válido.")
    year = int(raw_year)
    from datetime import datetime
    if disease not in sinan.DISEASES or ibge not in sinan.MUNICIPALITIES_BY_IBGE or not 2015 <= year <= datetime.now().year:
        raise ValueError("Selecione doença, município e ano válidos.")
    return {"disease": disease, "ibge": ibge, "year": year}


def parse_cases(content, scope, demo):
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Envie um CSV de até 1 MiB.")
    try:
        stream = io.StringIO(content.decode("utf-8-sig"), newline="")
        first_line = stream.readline()
        stream.seek(0)
        reader = csv.DictReader(stream, delimiter=";" if ";" in first_line else ",", strict=True)
        if reader.fieldnames != list(COLUMNS):
            raise ValueError("Use as colunas e a ordem do modelo CSV. Não inclua nomes, documentos ou endereços.")
        rows, references = [], set()
        for number, row in enumerate(reader, 2):
            if len(rows) >= MAX_CASES:
                raise ValueError(f"O limite é de {MAX_CASES} casos por arquivo. Divida o arquivo antes de importar.")
            if None in row or any(value is None or len(value) > 80 for value in row.values()):
                raise ValueError(f"Linha {number}: quantidade ou tamanho de campos inválido.")
            row = {key: value.strip() for key, value in row.items()}
            reference = row["referencia"]
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", reference) or reference in references:
                raise ValueError(f"Linha {number}: referência inválida ou repetida.")
            if reference.startswith("DEMO-") and not demo:
                raise ValueError("O arquivo de demonstração deve ser importado como dados fictícios.")
            if row["doenca"] != scope["disease"] or row["municipio_ibge"] != scope["ibge"] or row["ano"] != str(scope["year"]):
                raise ValueError(f"Linha {number}: doença, município ou ano diferente dos filtros selecionados.")
            week = row["semana"]
            if week and (not re.fullmatch(r"[0-9]{6}", week) or abs(int(week[:4]) - scope["year"]) > 1 or not 1 <= int(week[4:]) <= 53):
                raise ValueError(f"Linha {number}: semana deve estar no formato AAAASS.")
            if row["classificacao"] not in CASE_CLASSES:
                raise ValueError(f"Linha {number}: classificação inválida. Use suspeito, confirmado, descartado ou ignorado.")
            try:
                lat, lng = float(row["latitude"]), float(row["longitude"])
            except ValueError:
                raise ValueError(f"Linha {number}: coordenadas inválidas. Use ponto decimal.") from None
            if not math.isfinite(lat) or not math.isfinite(lng) or not (-34 <= lat <= 6 and -74 <= lng <= -28):
                raise ValueError(f"Linha {number}: coordenadas fora dos limites do Brasil.")
            references.add(reference)
            rows.append({"reference": reference, "week": week or None, "classification": row["classificacao"], "latitude": lat, "longitude": lng})
        if not rows:
            raise ValueError("O arquivo não contém casos.")
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("CSV inválido. Use UTF-8 e o modelo disponibilizado.") from exc


def _summary(groups):
    classes, weeks, residences = Counter(), Counter(), Counter()
    for (week, classification, residence), count in groups.items():
        classes[classification] += count
        if week:
            weeks[week] += count
        residences[residence] += count
    return {"total": sum(groups.values()), "classifications": dict(classes), "weeks": dict(weeks),
            "residence": dict(residences), "unknown_week": sum(n for (w, _, _), n in groups.items() if not w),
            "groups": [{"week": w, "classification": c, "residence": r, "count": n} for (w, c, r), n in sorted(groups.items(), key=lambda item: str(item[0]))]}


def run_api(store, job_id, scope, *, fetch_page=None, max_records=MAX_RECORDS, max_seconds=MAX_SECONDS, delay=1):
    fetch_page = fetch_page or sinan.fetch_page
    groups, offset, pages = Counter(), 0, 0
    started = time.monotonic()
    def snapshot():
        return {**_summary(groups), "source_url": sinan.DISEASES[scope["disease"]]["api_url"], "geographic_filter": "municipio_notificacao"}
    try:
        while True:
            if store.stopped(job_id):
                store.finish(job_id, "cancelled")
                return
            if offset >= max_records or time.monotonic() - started >= max_seconds:
                store.finish(job_id, "partial", snapshot(), "Limite de 100 registros ou 2 minutos atingido. Este lote é parcial; nenhuma nova carga será iniciada automaticamente.")
                return
            page = fetch_page(**scope, offset=offset)
            if store.stopped(job_id):
                store.finish(job_id, "cancelled")
                return
            for row in page["records"]:
                groups[(row["week"], row["classification"], row["residence"])] += 1
            pages += 1
            offset += len(page["records"])
            store.progress(job_id, offset, pages)
            if page["finished"]:
                store.finish(job_id, "completed", snapshot(), "Leitura concluída para o filtro de município de notificação.")
                return
            if page["next_offset"] != offset or not page["records"]:
                raise ValueError("A fonte retornou uma sequência de páginas inconsistente.")
            time.sleep(delay)
    except Exception as exc:
        message = str(exc) if isinstance(exc, (sinan.SinanError, ValueError)) else "Não foi possível concluir a importação. O lote anterior foi preservado."
        store.finish(job_id, "failed", message=message)


def run_cases(store, job_id, scope, content, demo):
    try:
        if store.stopped(job_id):
            store.finish(job_id, "cancelled")
            return
        rows = parse_cases(content, scope, demo)
        groups = Counter((r["week"], r["classification"], "unknown") for r in rows)
        store.finish(job_id, "completed", _summary(groups), "Arquivo validado e importado. Coordenadas conforme o arquivo fornecido.", cases=rows)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Não foi possível importar o arquivo. Nenhum caso foi publicado."
        store.finish(job_id, "failed", message=message)


def start(store, owner, scope, *, content=None, demo=False, source="api"):
    from . import sinan_datasus
    kind = "csv" if content is not None else ("datasus" if source == "datasus" else "api")
    fingerprint = hashlib.sha256(content).hexdigest() if content is not None else ""
    job_id, existing = store.create(owner, kind=kind, **scope, demo=demo, fingerprint=fingerprint)
    if not existing:
        target = {"csv": run_cases, "api": run_api, "datasus": sinan_datasus.run}[kind]
        args = (store, job_id, scope, content, demo) if kind == "csv" else (store, job_id, scope)
        try:
            threading.Thread(target=target, args=args, name="sinan-import", daemon=True).start()
        except Exception:
            store.finish(job_id, "failed", message="Não foi possível iniciar o processamento.")
            raise
    return job_id, existing


def sample_csv(scope):
    # Fictional coordinates in a small demonstration area, never real SINAN cases.
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(COLUMNS)
    centers = {"3550308": (-23.5505, -46.6333), "2610905": (-8.3558, -36.6978)}
    center = centers.get(scope["ibge"])
    if center is None:
        return "\ufeff" + stream.getvalue()
    for index, classification in enumerate(("suspeito", "confirmado"), 1):
        writer.writerow((f"DEMO-{index:03}", scope["disease"], scope["ibge"], scope["year"], f"{scope['year']}01", classification, center[0] + index * .002, center[1] + index * .002))
    return "\ufeff" + stream.getvalue()


def export_rows(job, cases=()):
    """CSV generated in small chunks, from the saved snapshot, never the network."""
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";")

    def line(values):
        stream.seek(0)
        stream.truncate(0)
        writer.writerow([("'" + v) if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v for v in values])
        return stream.getvalue()

    yield "\ufeff"
    prefix = ["lote", "origem", "situacao", "demonstracao", "doenca", "municipio_ibge", "ano", "importado_em_utc", "fonte"]
    from datetime import datetime, timezone
    meta = [job["id"], {"api": "SINAN_API_municipio_notificacao", "datasus": "SINAN_DATASUS_DBC_municipio_notificacao"}.get(job["kind"], "CSV_usuario_coordenadas"), job["status"], "sim" if job["demo"] else "nao", job["disease"], job["ibge"], job["year"], datetime.fromtimestamp(job["updated"], timezone.utc).isoformat(), job["summary"].get("source_url", "arquivo_fornecido_pelo_usuario")]
    if job["kind"] != "csv":
        yield line(prefix + ["semana", "classificacao_original", "residencia", "quantidade"])
        for row in job["summary"].get("groups", []):
            yield line(meta + [row["week"], row["classification"], row["residence"], row["count"]])
    else:
        yield line(prefix + ["referencia", "semana", "classificacao", "latitude", "longitude"])
        for row in cases:
            yield line(meta + [row["reference"], row["week"], row["classification"], row["latitude"], row["longitude"]])
