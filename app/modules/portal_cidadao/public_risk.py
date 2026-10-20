"""Projeção pública dos mesmos registros de vigilância, somente por leitura.

Nunca serializa visitas, coordenadas individuais, referências SINAN ou autores.
Demo consulta registros demo persistidos; não gera uma análise paralela.
"""

import json
import re
import sqlite3
from pathlib import Path

import sqlalchemy as sa
from flask import current_app
from werkzeug.exceptions import BadRequest

from app.extensions import db
from app.models import Prefeitura, Usuario
from app.shared.access import GLOBAL_ADMIN_USER_TYPES
from app.modules.vigilancia.field_capture import FieldInputError
from app.modules.vigilancia.field_store import FieldStoreError
from app.modules.vigilancia.results import ResultsStore, filters_from, sinan_filters
from app.modules.vigilancia.service import PreviewValidationError
from app.modules.vigilancia.sinan import DISEASES
from app.modules.vigilancia.sinan_import import CASE_CLASSES
from app.modules.vigilancia.sinan_models import SinanJob
from app.modules.vigilancia.territory import municipality_feature, pernambuco_context


INDEX_FIELDS = ("levantamento_codigo", "estrato_codigo", "area_codigo", "imoveis_inspecionados",
                "imoveis_positivos", "imoveis_pendentes", "iip", "ib")


def _selection(args):
    for name in ("demo", "levantamento", "inicio", "fim", "doenca", "ano_sinan"):
        if len(args.getlist(name)) > 1:
            raise BadRequest("Informe um único valor por filtro do mapa.")
    if args.get("demo", "false") not in {"true", "false"}:
        raise BadRequest("Selecione dados de demonstração ou dados da vigilância.")
    try:
        field = filters_from({name: args.get(name, "") for name in ("levantamento", "inicio", "fim")})
        source = sinan_filters(args)
    except FieldInputError as exc:
        raise BadRequest(str(exc)) from None
    return args.get("demo") == "true", field, source


def _municipality_id(config, ibge, engine):
    mapping = config.get("VIGILANCIA_MUNICIPIOS_IBGE", {})
    try:
        mapping = json.loads(mapping) if isinstance(mapping, str) else mapping
    except (TypeError, ValueError):
        return None
    if not isinstance(mapping, dict):
        return None
    candidates = {int(key) for key, code in mapping.items()
                  if code == ibge and re.fullmatch(r"[1-9][0-9]{0,9}", str(key)) and int(key) <= 2147483647}
    if not candidates:
        return None
    table = Prefeitura.__table__
    with engine.connect() as conn:
        active = list(conn.scalars(sa.select(table.c.id).where(table.c.id.in_(candidates), table.c.ativa.is_(True))))
    # Não adivinhar nem somar bases se o mesmo IBGE estiver ligado a duas prefeituras.
    return active[0] if len(active) == 1 else None


def _field_summary(engine, prefeitura, demo, filters):
    store = ResultsStore(engine)
    records = store.records(prefeitura, demo=demo)
    dates = {}
    for row in records:
        if row["origem"] == "LIRAA":
            code = row["levantamento_codigo"]
            dates[code] = max(dates.get(code, ""), row["data_inspecao"])
    surveys = sorted(dates, key=lambda code: (dates[code], code), reverse=True)
    filters = {**filters, "levantamento": filters["levantamento"] or (surveys[0] if surveys else "")}
    if filters["levantamento"] and filters["levantamento"] not in surveys:
        raise BadRequest("Selecione um levantamento disponível neste município e modo de dados.")
    report = store.report(prefeitura, demo, filters)
    indices = [{name: item[name] for name in INDEX_FIELDS} for item in report["indicadores"]]
    geography = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": item["geometry"], "properties": {
            **{name: item["properties"][name] for name in INDEX_FIELDS}, "cor": item["properties"]["cor"]}}
        for item in report["geografia"]["features"]]}
    rows = report["registros"]
    liraa = [row for row in rows if row["origem"] == "LIRAA"]
    focal = [row for row in rows if row["origem"] == "FOCAL"]

    def period(values):
        dates = [row["data_inspecao"] for row in values]
        return {"inicio": min(dates) if dates else None, "fim": max(dates) if dates else None}

    return dict(levantamentos=surveys, filtros=filters, geografia=geography, avisos=report["avisos"],
        liraa=dict(disponivel=bool(liraa), visitas=len(liraa), indicadores=indices, **period(liraa)),
        focal=dict(disponivel=bool(focal), visitas=len(focal),
                   inspecionados=sum(row["situacao"] == "INSPECIONADO" for row in focal), **period(focal)))


def _sinan_job(config, engine, prefeitura, ibge, demo, selection):
    """Um snapshot municipal, sem somar reimportações nem expirar jobs via GET."""
    backend = config.get("SINAN_STORAGE_BACKEND", "database")
    # Administradores globais também importam para o município pelo IBGE,
    # inclusive quando sua própria conta não tem uma prefeitura associada.
    users = Usuario.__table__
    with engine.connect() as conn:
        global_owners = [f"{row.prefeitura_id}:{row.id}" for row in conn.execute(
            sa.select(users.c.id, users.c.prefeitura_id).where(users.c.tipo_usuario.in_(GLOBAL_ADMIN_USER_TYPES)))]
    if backend == "sqlite" or (backend == "auto" and "sqlalchemy" not in current_app.extensions):
        path = Path(config.get("SINAN_STORAGE_PATH") or Path(current_app.instance_path) / "sinan" / "sinan.sqlite")
        if not path.is_file():
            return None
        # Não instancia Store: seu construtor cria tabelas e arquivos.
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        conn.row_factory = sqlite3.Row
        try:
            owners = "owner LIKE ?" + (" OR owner IN (" + ",".join("?" for _ in global_owners) + ")" if global_owners else "")
            row = conn.execute(f"""SELECT kind, status, count, summary, updated FROM jobs
                WHERE ({owners}) AND ibge=? AND demo=? AND disease=? AND year=?
                AND status IN ('completed','partial')
                ORDER BY CASE WHEN status='completed' THEN 0 ELSE 1 END, created DESC, id DESC LIMIT 1""",
                (f"{prefeitura}:%", *global_owners, ibge, int(demo), selection["disease"], selection["year"])).fetchone()
            return {**dict(row), "summary": json.loads(row["summary"])} if row else None
        finally:
            conn.close()
    if backend not in {"auto", "database"}:
        raise ValueError("Armazenamento SINAN indisponível.")
    table = SinanJob.__table__
    with engine.connect() as conn:
        row = conn.execute(sa.select(table.c.kind, table.c.status, table.c.count, table.c.summary, table.c.updated).where(
            sa.or_(table.c.owner.startswith(f"{prefeitura}:"), table.c.owner.in_(global_owners)),
            table.c.ibge == ibge, table.c.demo == demo,
            table.c.disease == selection["disease"], table.c.year == selection["year"],
            table.c.status.in_(("completed", "partial")))
            .order_by(sa.case((table.c.status == "completed", 0), else_=1), table.c.created.desc(), table.c.id.desc())
            .limit(1)).mappings().first()
    return dict(row) if row else None


def _sinan_summary(job, selection):
    if not job:
        return None
    labels = CASE_CLASSES if job["kind"] == "csv" else DISEASES[selection["disease"]]["classifications"]
    summary = job["summary"]
    if not isinstance(summary, dict):
        raise ValueError("Resumo SINAN inválido.")
    total = job["count"]
    classes = summary.get("classifications", {})
    if not isinstance(total, int) or isinstance(total, bool) or total < 0 or not isinstance(classes, dict):
        raise ValueError("Resumo SINAN inválido.")
    if any(not isinstance(count, int) or isinstance(count, bool) or count < 0
           for count in classes.values()) or sum(classes.values()) != total:
        raise ValueError("Classificações SINAN inconsistentes.")
    grouped = {}
    for code, count in classes.items():
        label = labels.get(code, "Não informada")
        grouped[label] = grouped.get(label, 0) + count
    return dict(disponivel=True, total=total, parcial=job["status"] == "partial", ano=selection["year"],
                doenca=DISEASES[selection["disease"]]["label"], atualizado=job["updated"],
                origem="Arquivo importado" if job["kind"] == "csv" else "API pública · município de notificação",
                classificacoes=[{"rotulo": label, "total": count} for label, count in sorted(grouped.items())])


def get_public_risk_report(config, municipality, args, *, engine=None, logger=None):
    demo, field_filters, selection = _selection(args)
    report = dict(demo=demo, municipio={name: municipality[name] for name in ("ibge", "name", "uf")},
        contexto=pernambuco_context(municipality["ibge"]) if municipality["uf"] == "PE" else None,
        limite=municipality_feature(municipality["ibge"]),
        filtros={**field_filters, "doenca": selection["disease"], "ano_sinan": selection["year"]},
        levantamentos=[], geografia={"type": "FeatureCollection", "features": []},
        liraa={"disponivel": False}, focal={"disponivel": False}, sinan=None, avisos=[])
    field_enabled = config.get("VIGILANCIA_IMPORT_ENABLED", False)
    sinan_enabled = config.get("SINAN_ENABLED", True) and config.get("SINAN_IMPORT_ENABLED", True)
    if not field_enabled and not sinan_enabled:
        report["avisos"].append("As fontes de vigilância estão desabilitadas neste ambiente.")
        return report
    if engine is None and "sqlalchemy" not in current_app.extensions:
        report["avisos"].append("O armazenamento municipal ainda não está disponível neste ambiente.")
        return report
    try:
        engine = engine if engine is not None else db.engine
        prefeitura = _municipality_id(config, municipality["ibge"], engine)
    except sa.exc.SQLAlchemyError:
        prefeitura = None
    if prefeitura is None:
        report["avisos"].append("O vínculo único entre a prefeitura e o código IBGE ainda não está disponível. Nenhum dado municipal foi publicado neste mapa.")
        return report
    if field_enabled:
        try:
            field = _field_summary(engine, prefeitura, demo, field_filters)
            report.update(field)
            report["filtros"].update(doenca=selection["disease"], ano_sinan=selection["year"])
        except (FieldStoreError, FieldInputError, PreviewValidationError):
            report["avisos"].append("Os dados de campo estão temporariamente indisponíveis.")
            if logger:
                logger.warning("Portal: resumo público de campo indisponível.")
    if sinan_enabled:
        try:
            report["sinan"] = _sinan_summary(_sinan_job(config, engine, prefeitura, municipality["ibge"], demo, selection), selection)
        except (sa.exc.SQLAlchemyError, sqlite3.Error, OSError, ValueError, TypeError):
            report["avisos"].append("Os totais do SINAN estão temporariamente indisponíveis.")
            if logger:
                logger.warning("Portal: resumo público SINAN indisponível.")
    return report
