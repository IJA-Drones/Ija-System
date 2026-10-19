"""Registro básico e consolidação de visitas já confirmadas, sem acesso externo."""

import csv
import io
from datetime import date

from .domain import CSV_COLUMNS, DEPOSIT_COLUMNS
from .field_store import _csv
from .service import preview_csv


class FieldInputError(ValueError):
    pass


def _value(values, name):
    if hasattr(values, "getlist") and len(values.getlist(name)) > 1:
        raise FieldInputError("Informe um único valor por campo.")
    value = str(values.get(name, "")).strip()
    if len(value) > 120 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise FieldInputError("Há um campo muito longo ou com caracteres inválidos.")
    return value


def capture_csv(values, *, prefeitura):
    record = {name: _value(values, name) for name in (*CSV_COLUMNS, *DEPOSIT_COLUMNS)
              if name != "municipio_id"}
    record["municipio_id"] = str(prefeitura)
    columns = (*CSV_COLUMNS, *DEPOSIT_COLUMNS)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, delimiter=";")
    writer.writeheader()
    writer.writerow(record)
    content = stream.getvalue().encode("utf-8")
    report = preview_csv(content, prefeitura_id=prefeitura)
    if report["erros"]:
        raise FieldInputError(" ".join(dict.fromkeys(item["mensagem"] for item in report["erros"])))
    return content


def parse_filters(values):
    result = {name: _value(values, name) for name in ("origem", "levantamento", "estrato", "inicio", "fim")}
    if result["origem"] not in {"", "LIRAA", "FOCAL"}:
        raise FieldInputError("Selecione Focal, LIRAa ou todas as origens.")
    if any(len(result[name]) > 80 for name in ("levantamento", "estrato")):
        raise FieldInputError("Os códigos devem ter até 80 caracteres.")
    for name in ("inicio", "fim"):
        if result[name]:
            try:
                parsed = date.fromisoformat(result[name])
                if parsed.isoformat() != result[name]:
                    raise ValueError
            except ValueError:
                raise FieldInputError("Informe datas válidas no formato AAAA-MM-DD.") from None
    if result["inicio"] and result["fim"] and result["inicio"] > result["fim"]:
        raise FieldInputError("A data inicial deve ser anterior ou igual à data final.")
    return result


def consolidate(records, *, prefeitura, filters):
    selected = [record for record in records
                if (not filters["origem"] or record["origem"] == filters["origem"])
                and (not filters["levantamento"] or record["levantamento_codigo"] == filters["levantamento"])
                and (not filters["estrato"] or record["estrato_codigo"] == filters["estrato"])
                and (not filters["inicio"] or record["data_inspecao"] >= filters["inicio"])
                and (not filters["fim"] or record["data_inspecao"] <= filters["fim"])]
    selected.sort(key=lambda record: (record["data_inspecao"], record["inspecao_codigo"]), reverse=True)
    if not selected:
        return {"registros": [], "indicadores": [], "resumo": {"inspecoes": 0, "imoveis": 0, "sem_coordenadas": 0}}
    report = preview_csv(_csv(selected), prefeitura_id=prefeitura)
    if report["erros"]:
        raise FieldInputError("Os dados salvos possuem inconsistências; revise a base antes de consolidar.")
    return report


def export_csv(records):
    """CSV para consulta em planilha: códigos com prefixo de fórmula são protegidos."""
    columns = (*CSV_COLUMNS, *DEPOSIT_COLUMNS) if any(name in record for record in records for name in DEPOSIT_COLUMNS) else CSV_COLUMNS
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", quoting=csv.QUOTE_ALL)
    writer.writerow(columns)
    for record in records:
        cells = []
        for name in columns:
            value = record.get(name)
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            cells.append("" if value is None else value)
        writer.writerow(cells)
    return stream.getvalue().encode("utf-8-sig")
