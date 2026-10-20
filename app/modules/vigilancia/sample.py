"""Amostra ficcional do layout provisório; não representa um levantamento oficial."""

import csv
from io import StringIO

from .domain import CSV_COLUMNS, DEPOSIT_COLUMNS, MAX_PREFEITURA_ID


def build_sample_csv(prefeitura_id: int) -> bytes:
    """Produz cinco linhas sintéticas para a prévia do município selecionado."""
    if isinstance(prefeitura_id, bool) or not isinstance(prefeitura_id, int) or not 1 <= prefeitura_id <= MAX_PREFEITURA_ID:
        raise ValueError("O município deve possuir um identificador inteiro positivo.")

    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(CSV_COLUMNS)
    shared = [str(prefeitura_id), "LIRAA"]
    territory = ["Bairro Sintético — Exemplo", "AREA-SINTETICA-001", "LEV-SINTETICO-001", "ESTRATO-SINTETICO-001"]
    rows = [
        shared + ["IMOVEL-SINTETICO-001", "INSP-SINTETICA-001", "2026-01-10"] + territory + ["INSPECIONADO", "SIM", "-23.5501", "-46.6331"],
        shared + ["IMOVEL-SINTETICO-002", "INSP-SINTETICA-002", "2026-01-10"] + territory + ["INSPECIONADO", "NAO", "-23.5502", "-46.6332"],
        shared + ["IMOVEL-SINTETICO-003", "INSP-SINTETICA-003", "2026-01-10"] + territory + ["INSPECIONADO", "NAO", "", ""],
        shared + ["IMOVEL-SINTETICO-004", "INSP-SINTETICA-004", "2026-01-10"] + territory + ["FECHADO", "", "", ""],
        [str(prefeitura_id), "FOCAL", "IMOVEL-SINTETICO-005", "INSP-SINTETICA-005", "2026-01-10", territory[0], territory[1], "", "", "INSPECIONADO", "SIM", "-23.5505", "-46.6335"],
    ]
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def build_geolocated_sample_csv(prefeitura_id, ibge, base_date):
    """Dados fictícios para o importador normal, dentro de um limite real IBGE."""
    import random
    from shapely.geometry import Point, shape
    from .territory import municipality_feature

    if isinstance(prefeitura_id, bool) or not isinstance(prefeitura_id, int) or not 1 <= prefeitura_id <= MAX_PREFEITURA_ID:
        raise ValueError("Informe uma prefeitura válida para a demonstração.")
    feature = municipality_feature(ibge)
    if feature is None:
        raise ValueError("Configure o vínculo IBGE da prefeitura. A amostra geolocalizada está disponível para os municípios de Pernambuco.")
    geometry = shape(feature['geometry'])
    rng = random.Random(int(ibge))
    west, south, east, north = geometry.bounds
    points = []
    for _ in range(10000):
        longitude, latitude = round(rng.uniform(west, east), 6), round(rng.uniform(south, north), 6)
        if geometry.covers(Point(longitude, latitude)):
            points.append((latitude, longitude))
        if len(points) == 20:
            break
    if len(points) != 20:
        raise ValueError("Não foi possível preparar posições de demonstração nesta malha.")
    prefix = f"DEMO-MAPA-{ibge}-{base_date:%Y%m%d}"
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=(*CSV_COLUMNS, *DEPOSIT_COLUMNS), delimiter=";")
    writer.writeheader()
    positives = [1, 5, 9, 13]
    for n, (latitude, longitude) in enumerate(points, 1):
        inspected, positive = n <= 16, n in positives
        row = dict(municipio_id=prefeitura_id, origem="LIRAA", imovel_codigo=f"{prefix}-IM-{n:03}",
            inspecao_codigo=f"{prefix}-VIS-{n:03}", data_inspecao=base_date.isoformat(),
            bairro="Área fictícia de demonstração", area_codigo=f"DEMO-AREA-{ibge}",
            levantamento_codigo=prefix, estrato_codigo="DEMO-ESTRATO-01",
            situacao="INSPECIONADO" if inspected else "RECUSADO" if n == 20 else "FECHADO",
            positivo_aedes=("SIM" if positive else "NAO") if inspected else "",
            latitude=latitude, longitude=longitude)
        if inspected:
            row.update({name: 0 for name in DEPOSIT_COLUMNS})
            if positive:
                row[DEPOSIT_COLUMNS[positives.index(n)]] = 2
        writer.writerow(row)
    return stream.getvalue().encode("utf-8-sig")
