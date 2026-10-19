"""Relatórios de registros confirmados; geografia do plano e fontes separadas."""

import csv
import io
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime

import sqlalchemy as sa

from .domain import DEPOSIT_TYPES
from .field_capture import FieldInputError, consolidate, parse_filters
from .field_store import FieldStore
from .planning_models import CampoPlanoQuarteirao, CampoPlano
from . import sinan


def filters_from(values):
    filters = parse_filters(values)
    for name, limit in (("area", 80), ("bairro", 120)):
        value = values.get(name, "").strip()
        if len(value) > limit or any(ord(char) < 32 for char in value):
            raise FieldInputError("Revise os filtros de área e bairro.")
        filters[name] = value
    return filters


def municipality_ibge(config, prefeitura):
    """IDs internos e códigos IBGE só se relacionam por configuração explícita."""
    try:
        mapping = json.loads(config) if isinstance(config, str) else config
        code = mapping.get(str(prefeitura)) if isinstance(mapping, dict) else None
        return code if code in sinan.MUNICIPALITIES_BY_IBGE else None
    except (TypeError, ValueError):
        return None


def iip_color(value):
    # Escala numérica contínua, sem afirmar risco de epidemia por cor.
    if value is None:
        return "#94a3b8"
    value = max(0, min(100, value)) / 100
    return "#%02x%02x%02x" % tuple(round(low + (high - low) * value) for low, high in ((219, 30), (234, 64), (254, 175)))


class ResultsStore(FieldStore):
    def boundaries(self, prefeitura, demo, filters):
        blocks, plans = CampoPlanoQuarteirao.__table__, CampoPlano.__table__
        query = sa.select(blocks.c.plano, blocks.c.estrato, blocks.c.quarteirao, blocks.c.territorio).join(
            plans, sa.and_(plans.c.prefeitura == blocks.c.prefeitura, plans.c.demo == blocks.c.demo,
                           plans.c.code == blocks.c.plano)).where(
            blocks.c.prefeitura == prefeitura, blocks.c.demo == demo, plans.c.status.in_(("LIBERADO", "ENCERRADO")))
        if filters["levantamento"]:
            query = query.where(blocks.c.plano == filters["levantamento"])
        if filters["estrato"]:
            query = query.where(blocks.c.estrato == filters["estrato"])
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(query).mappings()]

    def report(self, prefeitura, demo, filters):
        all_records = self.records(prefeitura, demo=demo)
        chosen = [row for row in all_records if
                  (not filters["area"] or row["area_codigo"] == filters["area"]) and
                  (not filters["bairro"] or row["bairro"] == filters["bairro"]) and
                  (row["origem"] == "FOCAL" or (
                      (not filters["levantamento"] or row["levantamento_codigo"] == filters["levantamento"]) and
                      (not filters["estrato"] or row["estrato_codigo"] == filters["estrato"])))]
        # Focal não tem levantamento/estrato: o recorte comum é território e data.
        report = consolidate(chosen, prefeitura=prefeitura, filters={**filters, "levantamento": "", "estrato": ""})
        report["levantamentos"] = sorted({row["levantamento_codigo"] for row in all_records if row["origem"] == "LIRAA"})
        report["bairros"] = sorted({row["bairro"] for row in all_records})
        report["areas"] = sorted({row["area_codigo"] for row in all_records})
        report["atividades"] = dict(Counter(row["origem"] for row in report["registros"]))
        report["situacoes"] = dict(Counter(row["situacao"] for row in report["registros"]))
        geometry = {"type": "FeatureCollection", "features": []}
        warnings = []
        if report["indicadores"] and not filters["levantamento"]:
            warnings.append("Selecione um levantamento para exibir o IIP no mapa sem sobrepor campanhas diferentes.")
        elif report["indicadores"]:
            grouped = defaultdict(list)
            for block in self.boundaries(prefeitura, demo, filters):
                territory = block["territorio"]
                if filters["bairro"] and territory["bairro"] != filters["bairro"]:
                    continue
                grouped[(block["plano"], block["estrato"], territory["area"])].append(block)
            for indicator in report["indicadores"]:
                key = tuple(indicator[name] for name in ("levantamento_codigo", "estrato_codigo", "area_codigo"))
                all_blocks = grouped.get(key, [])
                blocks = [block for block in all_blocks if block["territorio"].get("geometria")]
                if not blocks:
                    warnings.append(f"Estrato {key[1]} / área {key[2]}: sem contorno preservado no plano. O índice permanece disponível na tabela.")
                    continue
                if len(blocks) != len(all_blocks):
                    warnings.append(f"Estrato {key[1]} / área {key[2]}: {len(blocks)} de {len(all_blocks)} quarteirões possuem contorno. O mapa mostra somente a parte disponível.")
                geometry["features"].append({"type": "Feature", "geometry": {
                    "type": "MultiPolygon", "coordinates": [block["territorio"]["geometria"]["coordinates"] for block in blocks]},
                    "properties": {**indicator, "quarteiroes": [block["quarteirao"] for block in blocks], "quarteiroes_total": len(all_blocks), "cor": iip_color(indicator["iip"])}})
        report["geografia"] = geometry
        report["avisos"] = warnings
        report["pontos"] = [{"latitude": row["latitude"], "longitude": row["longitude"],
            "origem": row["origem"], "situacao": row["situacao"], "positivo_aedes": row["positivo_aedes"],
            "data_inspecao": row["data_inspecao"], "bairro": row["bairro"],
            "levantamento": row["levantamento_codigo"], "estrato": row["estrato_codigo"]}
            for row in report["registros"] if row["latitude"] is not None]
        return report


def sinan_filters(values):
    year = values.get("ano_sinan", str(datetime.now().year))
    disease = values.get("doenca", "dengue")
    if not re.fullmatch(r"[0-9]{4}", year) or not 2015 <= int(year) <= datetime.now().year or disease not in sinan.DISEASES:
        raise FieldInputError("Selecione doença e ano válidos para o SINAN.")
    result = dict(year=int(year), disease=disease)
    for name in ("semana_inicio", "semana_fim"):
        value = values.get(name, "")
        if value and (not re.fullmatch(r"[0-9]{6}", value) or abs(int(value[:4]) - int(year)) > 1 or not 1 <= int(value[4:]) <= 53):
            raise FieldInputError("Informe a semana SINAN no formato AAAASS, de 01 a 53.")
        result[name] = value
    if result["semana_inicio"] and result["semana_fim"] and result["semana_inicio"] > result["semana_fim"]:
        raise FieldInputError("A semana inicial deve ser anterior ou igual à semana final.")
    return result


def sinan_snapshot(store, owner, job, filters):
    """Apenas um snapshot; nunca somar lotes que podem conter os mesmos casos."""
    def selected(week):
        if not filters["semana_inicio"] and not filters["semana_fim"]:
            return True
        return bool(week and (not filters["semana_inicio"] or week >= filters["semana_inicio"]) and
                    (not filters["semana_fim"] or week <= filters["semana_fim"]))
    if job["kind"] == "csv":
        cases = [row for row in store.cases(job["id"], owner) if selected(row["week"])]
        classes = dict(Counter(row["classification"] for row in cases))
        total = len(cases)
        # Referências individuais não são necessárias para a comparação territorial.
        points = [{key: row[key] for key in ("week", "classification", "latitude", "longitude")} for row in cases]
    else:
        groups = [group for group in job["summary"].get("groups", []) if selected(group["week"])]
        classes = Counter()
        for group in groups:
            classes[group["classification"]] += group["count"]
        classes, total, points = dict(classes), sum(group["count"] for group in groups), []
    from .sinan_import import CASE_CLASSES
    labels = CASE_CLASSES if job["kind"] == "csv" else sinan.DISEASES[job["disease"]]["classifications"]
    return dict(id=job["id"], kind=job["kind"], status=job["status"], total=total, classification_labels=labels,
                classifications=classes, points=points, year=job["year"], disease=job["disease"],
                ibge=job["ibge"], updated=job["updated"], demo=job["demo"])


def indicators_csv(report):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", quoting=csv.QUOTE_ALL)
    columns = ("levantamento_codigo", "estrato_codigo", "area_codigo", "imoveis_inspecionados", "imoveis_positivos", "imoveis_pendentes", "iip", "ib", "depositos_positivos")
    writer.writerow((*columns, *(f"positivos_{code}" for code, _ in DEPOSIT_TYPES), *(f"itr_{code}" for code, _ in DEPOSIT_TYPES)))
    for item in report["indicadores"]:
        values = [item[name] for name in columns] + [row["positivos"] for row in item["recipientes"]] + [row["itr"] for row in item["recipientes"]]
        writer.writerow("" if value is None else "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value for value in values)
    return stream.getvalue().encode("utf-8-sig")


def schematic(geography):
    """Contornos para impressão, projetados localmente; sem imagem de terceiros."""
    features = geography["features"]
    rings = [polygon[0] for item in features for polygon in item["geometry"]["coordinates"]]
    if not rings:
        return []
    coords = [pair for ring in rings for pair in ring]
    latitude = sum(pair[1] for pair in coords) / len(coords)
    correction = max(.01, math.cos(math.radians(latitude)))
    points = [(pair[0] * correction, pair[1]) for pair in coords]
    west, east = min(p[0] for p in points), max(p[0] for p in points)
    south, north = min(p[1] for p in points), max(p[1] for p in points)
    scale = min(920 / max(east-west, .000001), 360 / max(north-south, .000001))
    paths = []
    for item in features:
        name = f"{item['properties']['estrato_codigo']} / {item['properties']['area_codigo']}"
        for polygon in item["geometry"]["coordinates"]:
            xy = [(40 + (p[0] * correction-west)*scale, 400 - (p[1]-south)*scale) for p in polygon[0]]
            paths.append(dict(points=" ".join(f"{x:.2f},{y:.2f}" for x, y in xy), label=name,
                color=item["properties"]["cor"], x=sum(p[0] for p in xy[:-1])/len(xy[:-1]),
                y=sum(p[1] for p in xy[:-1])/len(xy[:-1])))
    return paths
