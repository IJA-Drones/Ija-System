"""Amostra ficcional do layout provisório; não representa um levantamento oficial."""

import csv
from io import StringIO

from .domain import CSV_COLUMNS, MAX_PREFEITURA_ID


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
