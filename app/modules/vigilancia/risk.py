"""Estratificação exploratória Gi* e recorrência (MS 2025, apêndice E).

Somente contagens agregadas de casos prováveis de dengue; não usa OS como casos.
A normalização afim positiva preserva Z de Gi* e a ordem das permutações.
"""
import csv
import hashlib
import io
import json
import math
import re
from datetime import date

import numpy as np
from shapely.geometry import shape, mapping
from shapely.errors import GEOSException

MAX_BYTES = 1_048_576
MAX_AREAS = 200
PERMUTATIONS = 999
SEED = 20261019
VERSION = "gi-star-queen-binary-v1"
SOURCE = "https://bvsms.saude.gov.br/bvs/publicacoes/diretrizes_nacionais_arboviroses_urbanas.pdf"
LABELS = {"hotspot": "Hotspot", "coldspot": "Coldspot", "nao_significativo": "Não significativo", "nao_avaliado": "Não avaliado"}
COLORS = {"hotspot": "#dc2626", "coldspot": "#2563eb", "nao_significativo": "#e2e8f0", "nao_avaliado": "#64748b"}
CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")


class RiskError(ValueError):
    pass


def _text(value, name, maximum=120):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum or any(ord(c) < 32 for c in value):
        raise RiskError(f"{name}: informe um texto de até {maximum} caracteres.")
    return value.strip()


def _code(value):
    if not isinstance(value, str) or not CODE.fullmatch(value):
        raise RiskError("Código territorial inválido. Use até 80 letras, números, ponto, hífen ou sublinhado.")
    return value


def territories(content):
    try:
        if not content or len(content) > MAX_BYTES:
            raise RiskError("O GeoJSON deve ter até 1 MiB.")
        obj = json.loads(content.decode("utf-8-sig"))
        if obj.get("type") != "FeatureCollection" or "crs" in obj:
            raise RiskError("Envie uma FeatureCollection GeoJSON em WGS84, sem CRS alternativo.")
        features = obj.get("features")
        if not isinstance(features, list) or not 1 <= len(features) <= MAX_AREAS:
            raise RiskError(f"Informe de 1 a {MAX_AREAS} áreas no território.")
        cleaned, polygons, seen, vertices = [], [], set(), 0
        for feature in features:
            if feature.get("type") != "Feature":
                raise RiskError("Cada área deve ser uma Feature GeoJSON.")
            props = feature["properties"]
            code = _code(props.get("codigo"))
            name = _text(props.get("nome"), "Nome da área")
            if code in seen:
                raise RiskError(f"Código territorial repetido: {code}.")
            seen.add(code)
            geometry = feature["geometry"]
            if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
                raise RiskError("Use somente Polygon ou MultiPolygon para delimitar as áreas.")
            # Verifica os dados antes do GEOS; não corrige nem arredonda limites.
            parts = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
            for polygon in parts:
                if not polygon:
                    raise RiskError("Polígono vazio.")
                for ring in polygon:
                    if len(ring) < 4 or ring[0] != ring[-1]:
                        raise RiskError("Os anéis precisam ser fechados e ter ao menos quatro posições.")
                    for point in ring:
                        vertices += 1
                        if vertices > 25000:
                            raise RiskError("Simplifique o território para até 25.000 posições.")
                        if len(point) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point):
                            raise RiskError("Coordenadas devem ser pares finitos [longitude, latitude].")
                        if not -74 <= point[0] <= -34 or not -34 <= point[1] <= 6:
                            raise RiskError("Coordenadas fora do Brasil. Confira a projeção WGS84 do arquivo.")
            polygon = shape(geometry)
            if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
                raise RiskError(f"Geometria inválida na área {code}; revise o limite na origem.")
            polygons.append((code, polygon))
            cleaned.append({"type": "Feature", "properties": {"codigo": code, "nome": name}, "geometry": mapping(polygon)})
        polygons.sort(key=lambda pair: pair[0])
        neighbors = {code: [] for code, _ in polygons}
        for i, (code, polygon) in enumerate(polygons):
            for other, candidate in polygons[i+1:]:
                if polygon.intersection(candidate).area > 0:
                    raise RiskError(f"Áreas sobrepostas: {code} e {other}. Revise a malha territorial.")
                if polygon.touches(candidate):
                    neighbors[code].append(other)
                    neighbors[other].append(code)
        return {"type": "FeatureCollection", "features": sorted(cleaned, key=lambda f: f["properties"]["codigo"])}, neighbors
    except RiskError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, GEOSException) as exc:
        raise RiskError("Não foi possível ler os polígonos do GeoJSON. Confira o modelo de território.") from exc


def history_csv(content, codes, *, last_year=None):
    last_year = last_year if last_year is not None else date.today().year - 1
    try:
        if not content or len(content) > MAX_BYTES:
            raise RiskError("O CSV deve ter até 1 MiB.")
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), delimiter=";")
        if reader.fieldnames != ["codigo", "ano", "casos_provaveis"]:
            raise RiskError("Cabeçalho esperado: codigo;ano;casos_provaveis. Use o modelo disponível.")
        rows, seen, years = [], set(), set()
        for row in reader:
            if len(rows) >= MAX_AREAS * 20 or None in row or None in row.values():
                raise RiskError("CSV com colunas inválidas ou mais de 4.000 registros.")
            code = _code(row["codigo"])
            if code not in codes:
                raise RiskError(f"Área {code} não encontrada no território; use o mesmo código nos dois arquivos.")
            if not re.fullmatch(r"[0-9]{4}", row["ano"]) or not re.fullmatch(r"[0-9]{1,8}", row["casos_provaveis"]):
                raise RiskError("Ano e casos devem ser inteiros não negativos, sem separador de milhar.")
            year, cases = int(row["ano"]), int(row["casos_provaveis"])
            if not 2000 <= year <= last_year:
                raise RiskError(f"Use anos encerrados, entre 2000 e {last_year}.")
            if (code, year) in seen:
                raise RiskError(f"Área e ano repetidos: {code}, {year}.")
            seen.add((code, year)); years.add(year)
            rows.append({"codigo": code, "ano": year, "casos_provaveis": cases})
        if not rows or len(years) > 20:
            raise RiskError("Informe de 1 a 20 anos no histórico.")
        return sorted(rows, key=lambda r: (r["ano"], r["codigo"]))
    except (UnicodeError, csv.Error) as exc:
        raise RiskError("Não foi possível ler o CSV em UTF-8 separado por ponto e vírgula.") from exc


def gi_star(values, neighbor_indices, *, seed=SEED, permutations=PERMUTATIONS):
    """Queen binária com self=1; inferência condicional, cauda direcional.

    Fixa x_i e sorteia k vizinhos sem reposição entre as n-1 outras áreas.
    Pseudo-p=(1+contagem de valores tão extremos ou mais)/(R+1), incluindo empates.
    O Z analítico é diagnóstico; a classificação usa a permutação, não a normal.
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 3 or not np.all(np.isfinite(values)) or np.any(values < 0):
        raise RiskError("Gi* exige ao menos três valores finitos não negativos.")
    mean, std = float(values.mean()), float(values.std())
    if std <= 0:
        return [{"classe": "nao_avaliado", "motivo": "Sem variação entre as áreas neste ano", "z": None, "p": None, "gi": None, "valor_normalizado": None} for _ in values]
    standardized = (values - mean) / std
    normalized = standardized - standardized.min() + 1.0
    total, norm_mean, norm_std = float(normalized.sum()), float(normalized.mean()), float(normalized.std())
    result = []
    for i, neighbors in enumerate(neighbor_indices):
        k = len(neighbors)
        count = k + 1
        if k == 0 or count >= n:
            result.append({"classe": "nao_avaliado", "motivo": "Sem vizinhos" if k == 0 else "A vizinhança abrange todo o território", "z": None, "p": None, "gi": None, "valor_normalizado": float(normalized[i])})
            continue
        local = float(normalized[i] + normalized[neighbors].sum())
        denominator = norm_std * math.sqrt((n * count - count * count) / (n - 1))
        z = (local - norm_mean * count) / denominator
        candidates = np.delete(normalized, i)
        rng = np.random.default_rng(np.random.SeedSequence([seed, i]))
        samples = np.array([rng.choice(n-1, k, replace=False) for _ in range(permutations)])
        simulated = normalized[i] + candidates[samples].sum(axis=1)
        tolerance = max(1.0, abs(local)) * 1e-12
        extreme = np.count_nonzero(simulated >= local - tolerance) if z > 0 else np.count_nonzero(simulated <= local + tolerance)
        p = (int(extreme) + 1) / (permutations + 1)
        category = "hotspot" if z > 0 and p <= .05 else "coldspot" if z < 0 and p <= .05 else "nao_significativo"
        result.append({"classe": category, "motivo": "", "z": float(z), "p": p, "gi": local / total, "valor_normalizado": float(normalized[i])})
    return result


def analyze(geo_content, csv_content, *, last_year=None):
    if len(geo_content) + len(csv_content) > MAX_BYTES:
        raise RiskError("Os dois arquivos juntos devem ter até 1 MiB.")
    geography, neighbors = territories(geo_content)
    codes = list(neighbors)
    rows = history_csv(csv_content, set(codes), last_year=last_year)
    years = sorted({r["ano"] for r in rows})
    by_key = {(r["codigo"], r["ano"]): r["casos_provaveis"] for r in rows}
    missing = [(code, year) for year in years for code in codes if (code, year) not in by_key]
    warnings = []
    ready = len(years) >= 5 and years == list(range(years[0], years[-1]+1)) and not missing and len(codes) >= 3
    if len(years) < 5:
        warnings.append("São necessários pelo menos cinco anos encerrados para a recorrência histórica.")
    if years != list(range(years[0], years[-1]+1)):
        warnings.append("O histórico precisa conter anos consecutivos.")
    if missing:
        warnings.append(f"Faltam {len(missing)} combinações de área e ano. Ausência não é zero: complete o histórico explicitamente.")
    if len(codes) < 3:
        warnings.append("É necessário um território com pelo menos três áreas.")
    if any(not neighbors[code] for code in codes):
        warnings.append("Há áreas sem vizinhos Queen; elas permanecem não avaliadas. Revise a malha com a equipe técnica.")
    if any(0 < len(neighbors[code]) < 4 for code in codes):
        warnings.append("Há áreas com menos de quatro vizinhos. Avalie a sensibilidade da matriz com a vigilância municipal.")
    if len(codes) < 20:
        warnings.append("Poucas áreas limitam o poder do teste por permutação; interprete os resultados com cautela.")
    annual = []
    indices = [[codes.index(other) for other in neighbors[code]] for code in codes]
    if ready:
        for year in years:
            values = [by_key[code, year] for code in codes]
            calculated = gi_star(values, indices)
            for code, value, item in zip(codes, values, calculated):
                annual.append({"codigo": code, "ano": year, "casos_provaveis": value, **item})
    recurrence = []
    for code in codes:
        items = [item for item in annual if item["codigo"] == code]
        evaluated = sum(item["classe"] != "nao_avaliado" for item in items)
        recurrence.append({"codigo": code, "anos_avaliados": evaluated, "anos_hotspot": sum(item["classe"] == "hotspot" for item in items) if evaluated == len(years) else None})
    if ready and any(item["anos_hotspot"] is None for item in recurrence):
        warnings.append("A recorrência é exibida somente onde todos os anos puderam ser avaliados. Cinza escuro não significa baixo risco.")
    metadata = {"versao": VERSION, "fonte_metodo": SOURCE, "doenca": "dengue", "casos": "provaveis", "vizinhos": "Queen de primeira ordem, pesos binários, incluindo a própria área", "normalizacao": "Z anual populacional, deslocado por -min(Z)+1; transformação afim positiva", "inferencia": "Permutação condicional; cauda direcional com empates conservadores", "permutacoes": PERMUTATIONS, "semente": SEED, "p_limite": .05, "multiplicidade": "Exploratória; sem ajuste para testes múltiplos", "territorio_sha256": hashlib.sha256(geo_content).hexdigest(), "historico_sha256": hashlib.sha256(csv_content).hexdigest()}
    return {"status": "CALCULADO" if ready else "INSUFICIENTE", "geografia": geography, "vizinhos": neighbors, "historico": rows, "anos": years, "anual": annual, "recorrencia": recurrence, "avisos": warnings, "faltantes": len(missing), "metodo": metadata}


def example_files():
    """Grade artificial: não é o limite de nenhum município ou bairro real."""
    features, rows = [], []
    last = date.today().year - 1
    for y in range(5):
        for x in range(5):
            code = f"DEMO-{y*5+x+1:02d}"
            left, bottom = -37.0+x*.01, -8.5+y*.01
            # A mesma fórmula em ambas as bordas evita fendas de ponto flutuante.
            right, top = -37.0+(x+1)*.01, -8.5+(y+1)*.01
            ring = [[left,bottom],[right,bottom],[right,top],[left,top],[left,bottom]]
            features.append({"type":"Feature", "properties":{"codigo":code,"nome":f"Área fictícia {y*5+x+1:02d}"}, "geometry":{"type":"Polygon","coordinates":[ring]}})
            for year in range(last-4,last+1):
                cases = 200+(year%5)*15+x+y if x >= 3 and y >= 3 else 1+(x+y+year)%6
                rows.append([code,year,cases])
    stream=io.StringIO(newline=""); writer=csv.writer(stream,delimiter=";")
    writer.writerow(["codigo","ano","casos_provaveis"]); writer.writerows(rows)
    return json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False).encode(), stream.getvalue().encode("utf-8")


def csv_export(report):
    stream=io.StringIO(newline=""); writer=csv.writer(stream,delimiter=";")
    names={f["properties"]["codigo"]:f["properties"]["nome"] for f in report["geografia"]["features"]}
    recurrence={r["codigo"]:r for r in report["recorrencia"]}
    writer.writerow(["codigo","nome","ano","casos_provaveis","classe","z_gi_estrela","pseudo_p","anos_hotspot","anos_avaliados"])
    # Evita fórmulas ao abrir nomes fornecidos no Excel.
    safe=lambda v: "'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@")) else v
    for item in report["anual"]:
        rec=recurrence[item["codigo"]]
        writer.writerow([safe(item["codigo"]),safe(names[item["codigo"]]),item["ano"],item["casos_provaveis"],item["classe"],item["z"],item["p"],rec["anos_hotspot"],rec["anos_avaliados"]])
    return stream.getvalue().encode("utf-8-sig")
