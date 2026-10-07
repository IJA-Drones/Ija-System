"""Validação em memória de CSV provisório, sem Flask, banco ou rede.

Esta prévia não homologa um levantamento LIRAa. O percentual só é exibido
para um lote sem erros e conta imóveis únicos no grupo territorial informado.
"""

import csv
import hashlib
import io
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .domain import CSV_COLUMNS, LAYOUT_VERSION, MAX_PREFEITURA_ID, ImovelVigilancia, InspecaoCampo


MAX_FILE_BYTES = 1024 * 1024
MAX_ROWS = 5000
CODE_COLUMNS = (
    "imovel_codigo",
    "inspecao_codigo",
    "area_codigo",
    "levantamento_codigo",
    "estrato_codigo",
)
REQUIRED_VALUES = (
    "municipio_id",
    "origem",
    "imovel_codigo",
    "inspecao_codigo",
    "data_inspecao",
    "bairro",
    "area_codigo",
    "situacao",
)


class PreviewValidationError(ValueError):
    """Arquivo cuja estrutura impede uma prévia íntegra."""

    def __init__(self, mensagem, *, codigo="ESTRUTURA_INVALIDA", linha=None):
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.linha = linha


@dataclass
class _Row:
    linha: int
    data: dict
    signature: tuple
    errors: list = field(default_factory=list)
    duplicate: bool = False
    imovel: ImovelVigilancia | None = None
    inspecao: InspecaoCampo | None = None

    def add_error(self, campo, codigo, mensagem):
        if any(error["campo"] == campo and error["codigo"] == codigo for error in self.errors):
            return
        self.errors.append({
            "linha": self.linha,
            "campo": campo,
            "codigo": codigo,
            "mensagem": mensagem,
        })


def preview_csv(content: bytes, *, prefeitura_id: int) -> dict:
    """Valida todo o arquivo antes de produzir registros e indicadores.

    Códigos são texto e preservam zeros. Espaços externos são removidos e
    enums são normalizados para maiúsculas. Coordenadas ausentes permanecem
    ``None``. Linhas vazias são ignoradas; demais linhas são contabilizadas.
    """
    if (
        isinstance(prefeitura_id, bool)
        or not isinstance(prefeitura_id, int)
        or not 1 <= prefeitura_id <= MAX_PREFEITURA_ID
    ):
        raise PreviewValidationError("Informe uma prefeitura válida para a prévia.", codigo="PREFEITURA_INVALIDA")
    if not isinstance(content, bytes):
        raise PreviewValidationError("O conteúdo do arquivo deve ser enviado em bytes.", codigo="CONTEUDO_INVALIDO")
    if len(content) > MAX_FILE_BYTES:
        raise PreviewValidationError("O arquivo excede o limite de 1 MiB.", codigo="ARQUIVO_MUITO_GRANDE")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PreviewValidationError("Use um CSV codificado em UTF-8.", codigo="ENCODING_INVALIDO") from exc

    rows = _read_rows(text, prefeitura_id)
    _validate_inspection_identities(rows, prefeitura_id)
    _validate_property_identities(rows)
    _validate_liraa_results(rows)

    # Classificar duplicadas somente após todas as quarentenas evita aceitar
    # uma cópia de identidade cuja outra ocorrência exige revisão.
    inspections = defaultdict(list)
    for row in rows:
        if not row.errors:
            inspections[(row.data["origem"], row.data["inspecao_codigo"])].append(row)
    for group in inspections.values():
        for row in group[1:]:
            row.duplicate = True

    accepted = [row for row in rows if not row.errors and not row.duplicate]
    errors = [error for row in rows for error in row.errors]
    records = [{**row.data, "linha": row.linha} for row in accepted]
    indicators = _build_indicators(accepted, has_errors=bool(errors))
    points = [
        {
            "latitude": row.data["latitude"],
            "longitude": row.data["longitude"],
            "imovel_codigo": row.data["imovel_codigo"],
            "origem": row.data["origem"],
            "positivo_aedes": row.data["positivo_aedes"],
        }
        for row in accepted if row.data["latitude"] is not None
    ]
    return {
        "layout": LAYOUT_VERSION,
        "provisorio": True,
        "persistido": False,
        "prefeitura_id": prefeitura_id,
        "arquivo_sha256": hashlib.sha256(content).hexdigest(),
        "status": "COM_PENDENCIAS" if errors else "VALIDADO",
        "resumo": {
            "linhas": len(rows),
            "aceitas": len(accepted),
            "duplicadas": sum(row.duplicate for row in rows),
            "rejeitadas": sum(bool(row.errors) for row in rows),
            "imoveis": len({row.data["imovel_codigo"] for row in accepted}),
            "inspecoes": len(accepted),
            "sem_coordenadas": sum(row.data["latitude"] is None for row in accepted),
        },
        "erros": errors,
        "registros": records,
        "indicadores": indicators,
        "pontos": points,
    }


def _reader(text, delimiter):
    return csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)


def _read_rows(text, prefeitura_id):
    if not text.strip():
        raise PreviewValidationError("O arquivo CSV está vazio.", codigo="ARQUIVO_VAZIO")
    candidates = []
    for delimiter in (",", ";"):
        reader = _reader(text, delimiter)
        try:
            header = next(reader)
        except (csv.Error, StopIteration):
            continue
        candidates.append((len(header), delimiter, header, reader))
    if not candidates:
        raise PreviewValidationError("Não foi possível ler o cabeçalho CSV.", codigo="CABECALHO_INVALIDO", linha=1)
    _, _, header, reader = max(candidates, key=lambda item: item[0])
    header = [value.strip() for value in header]
    if len(set(header)) != len(header):
        raise PreviewValidationError("O cabeçalho contém colunas repetidas.", codigo="COLUNA_REPETIDA", linha=1)
    missing = [name for name in CSV_COLUMNS if name not in header]
    extra = [name for name in header if name not in CSV_COLUMNS]
    if missing or extra:
        # Nomes desconhecidos do arquivo não são reproduzidos na mensagem.
        details = []
        if missing:
            details.append("Colunas obrigatórias ausentes: " + ", ".join(missing) + ".")
        if extra:
            details.append("Há colunas não previstas no layout provisório.")
        raise PreviewValidationError(" ".join(details), codigo="CABECALHO_INVALIDO", linha=1)
    if reader.line_num != 1:
        raise PreviewValidationError("O cabeçalho deve ocupar uma única linha.", codigo="CABECALHO_INVALIDO", linha=1)

    rows = []
    while True:
        start_line = reader.line_num + 1
        try:
            values = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            raise PreviewValidationError(
                f"A linha {start_line} do CSV está malformada; revise aspas e separadores.",
                codigo="LINHA_MALFORMADA", linha=start_line,
            ) from exc
        if not values or all(not value.strip() for value in values):
            continue
        if len(rows) >= MAX_ROWS:
            raise PreviewValidationError("O arquivo excede o limite de 5.000 registros.", codigo="MUITAS_LINHAS")
        if len(values) != len(header):
            raise PreviewValidationError(
                f"A linha {start_line} deve conter exatamente 13 valores, conforme o cabeçalho.",
                codigo="QUANTIDADE_COLUNAS_INVALIDA", linha=start_line,
            )
        data = {name: value.strip() for name, value in zip(header, values)}
        row = _normalize_and_validate(data, start_line, prefeitura_id)
        rows.append(row)
    if not rows:
        raise PreviewValidationError("O arquivo não contém registros para validar.", codigo="SEM_REGISTROS")
    return rows


def _normalize_and_validate(data, linha, prefeitura_id):
    for name in ("origem", "situacao", "positivo_aedes"):
        data[name] = data[name].upper()
    row = _Row(linha, data, ())

    # Um município diferente é isolado antes de tratar qualquer outro dado.
    municipio = data["municipio_id"]
    municipio_sem_zeros = municipio.lstrip("0")
    if (
        not re.fullmatch(r"[0-9]+", municipio)
        or not municipio_sem_zeros
        or len(municipio_sem_zeros) > 10
        or (len(municipio_sem_zeros) == 10 and municipio_sem_zeros > str(MAX_PREFEITURA_ID))
    ):
        row.add_error("municipio_id", "MUNICIPIO_INVALIDO", "Informe um municipio_id inteiro entre 1 e 2147483647.")
        row.signature = tuple(data[name] for name in CSV_COLUMNS)
        return row
    # Comparar texto antes de converter também protege contra números que
    # excedam o limite de dígitos de int() em uma entrada não confiável.
    if municipio_sem_zeros != str(prefeitura_id):
        row.add_error("municipio_id", "MUNICIPIO_FORA_ESCOPO", "O registro pertence a outro município e foi rejeitado.")
        row.signature = tuple(data[name] for name in CSV_COLUMNS)
        return row
    data["municipio_id"] = prefeitura_id

    for name in REQUIRED_VALUES:
        if not data[name]:
            row.add_error(name, "CAMPO_OBRIGATORIO", "Preencha o campo obrigatório.")
    for name in CODE_COLUMNS:
        if len(data[name]) > 80:
            row.add_error(name, "CODIGO_MUITO_LONGO", "O código deve ter no máximo 80 caracteres.")
    if len(data["bairro"]) > 120:
        row.add_error("bairro", "BAIRRO_MUITO_LONGO", "O bairro deve ter no máximo 120 caracteres.")
    for name, value in data.items():
        if isinstance(value, str) and any(ord(char) < 32 or ord(char) == 127 for char in value):
            row.add_error(name, "CARACTERE_INVALIDO", "O valor contém caracteres de controle.")

    if data["origem"] not in {"FOCAL", "LIRAA"}:
        row.add_error("origem", "ORIGEM_INVALIDA", "Use FOCAL ou LIRAA.")
    elif data["origem"] == "LIRAA":
        for name in ("levantamento_codigo", "estrato_codigo"):
            if not data[name]:
                row.add_error(name, "CAMPO_OBRIGATORIO_LIRAA", "Informe levantamento e estrato para registros LIRAA.")
    else:
        for name in ("levantamento_codigo", "estrato_codigo"):
            if data[name]:
                row.add_error(name, "CAMPO_INCOMPATIVEL_FOCAL", "O campo deve ficar vazio para registros FOCAL.")

    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", data["data_inspecao"]):
            raise ValueError
        date.fromisoformat(data["data_inspecao"])
    except ValueError:
        row.add_error("data_inspecao", "DATA_INVALIDA", "Informe uma data válida no formato AAAA-MM-DD.")

    if data["situacao"] not in {"INSPECIONADO", "FECHADO", "RECUSADO"}:
        row.add_error("situacao", "SITUACAO_INVALIDA", "Use INSPECIONADO, FECHADO ou RECUSADO.")
    elif data["situacao"] == "INSPECIONADO":
        if data["positivo_aedes"] not in {"SIM", "NAO"}:
            row.add_error("positivo_aedes", "POSITIVIDADE_OBRIGATORIA", "Use SIM ou NAO para um imóvel inspecionado.")
    elif data["positivo_aedes"]:
        row.add_error("positivo_aedes", "POSITIVIDADE_INCOMPATIVEL", "Deixe a positividade vazia em imóveis fechados ou recusados.")

    latitude, longitude = data["latitude"], data["longitude"]
    if bool(latitude) != bool(longitude):
        row.add_error("coordenadas", "COORDENADAS_INCOMPLETAS", "Informe latitude e longitude juntas, ou deixe ambas vazias.")
    for name, limit in (("latitude", 90), ("longitude", 180)):
        if not data[name]:
            data[name] = None
            continue
        try:
            number = float(data[name])
            if not math.isfinite(number) or not -limit <= number <= limit:
                raise ValueError
        except ValueError:
            row.add_error(name, "COORDENADA_INVALIDA", "Informe uma coordenada finita dentro do intervalo geográfico válido.")
        else:
            data[name] = number
    row.signature = tuple(data[name] for name in CSV_COLUMNS)
    if not row.errors:
        row.imovel = ImovelVigilancia(
            prefeitura_id=prefeitura_id,
            imovel_codigo=data["imovel_codigo"],
            bairro=data["bairro"],
            area_codigo=data["area_codigo"],
            latitude=data["latitude"],
            longitude=data["longitude"],
        )
        row.inspecao = InspecaoCampo(
            prefeitura_id=prefeitura_id,
            origem=data["origem"],
            imovel_codigo=data["imovel_codigo"],
            inspecao_codigo=data["inspecao_codigo"],
            data_inspecao=date.fromisoformat(data["data_inspecao"]),
            situacao=data["situacao"],
            positivo_aedes=(data["positivo_aedes"] == "SIM") if data["situacao"] == "INSPECIONADO" else None,
            levantamento_codigo=data["levantamento_codigo"],
            estrato_codigo=data["estrato_codigo"],
        )
    return row


def _validate_inspection_identities(rows, prefeitura_id):
    groups = defaultdict(list)
    for row in rows:
        data = row.data
        if (
            data.get("municipio_id") == prefeitura_id
            and data.get("origem") in {"FOCAL", "LIRAA"}
            and data.get("inspecao_codigo")
        ):
            groups[(data["origem"], data["inspecao_codigo"])].append(row)
    for group in groups.values():
        if len({row.signature for row in group}) > 1:
            for row in group:
                row.add_error("inspecao_codigo", "INSPECAO_CONFLITANTE", "A mesma identidade de inspeção tem dados diferentes; revise todas as ocorrências.")


def _validate_property_identities(rows):
    groups = defaultdict(list)
    for row in rows:
        if not row.errors:
            groups[row.data["imovel_codigo"]].append(row)
    for group in groups.values():
        locations = {(row.imovel.bairro, row.imovel.area_codigo) for row in group}
        coordinates = {
            (row.imovel.latitude, row.imovel.longitude)
            for row in group if row.imovel.latitude is not None
        }
        if len(locations) > 1 or len(coordinates) > 1:
            for row in group:
                row.add_error("imovel_codigo", "IMOVEL_INCONSISTENTE", "O mesmo imóvel tem bairro, área ou coordenadas divergentes; revise todas as ocorrências.")


def _validate_liraa_results(rows):
    groups = defaultdict(list)
    for row in rows:
        if not row.errors and row.data["origem"] == "LIRAA":
            data = row.data
            groups[(data["imovel_codigo"], data["levantamento_codigo"])].append(row)
    for group in groups.values():
        if len({row.data["estrato_codigo"] for row in group}) > 1:
            for row in group:
                row.add_error("estrato_codigo", "ESTRATO_LIRAA_CONFLITANTE", "O mesmo imóvel pertence a estratos diferentes no mesmo levantamento; revise todas as ocorrências.")
            continue
        results = {row.data["positivo_aedes"] for row in group if row.data["situacao"] == "INSPECIONADO"}
        if len(results) > 1:
            for row in group:
                row.add_error("positivo_aedes", "RESULTADO_LIRAA_CONFLITANTE", "Há resultados contraditórios para o mesmo imóvel e levantamento/estrato; a vigilância deve revisar as ocorrências.")


def _build_indicators(rows, *, has_errors):
    groups = defaultdict(list)
    for row in rows:
        inspection = row.inspecao
        if inspection.origem == "LIRAA":
            groups[(inspection.levantamento_codigo, inspection.estrato_codigo, row.imovel.area_codigo)].append(inspection)
    indicators = []
    for key, group in sorted(groups.items()):
        inspected = {item.imovel_codigo for item in group if item.situacao == "INSPECIONADO"}
        positive = {item.imovel_codigo for item in group if item.situacao == "INSPECIONADO" and item.positivo_aedes}
        last_inspected, last_pending = {}, {}
        for item in group:
            dates = last_inspected if item.situacao == "INSPECIONADO" else last_pending
            dates[item.imovel_codigo] = max(dates.get(item.imovel_codigo, date.min), item.data_inspecao)
        # Somente uma inspeção concluída na mesma data ou posteriormente
        # resolve uma pendência. Visitas repetidas nunca inflacionam o IIP.
        pending = {
            code for code, pending_date in last_pending.items()
            if last_inspected.get(code, date.min) < pending_date
        }
        unavailable = has_errors or not inspected
        if has_errors:
            reason = "Há erros no arquivo; revise todo o lote antes de calcular o IIP."
        elif not inspected:
            reason = "Não há imóveis inspecionados neste grupo; o IIP está indisponível."
        else:
            reason = "Percentual preliminar do lote; depende da validação do levantamento e da amostragem pela vigilância."
        indicators.append({
            "levantamento_codigo": key[0],
            "estrato_codigo": key[1],
            "area_codigo": key[2],
            "imoveis_inspecionados": len(inspected),
            "imoveis_positivos": len(positive),
            "imoveis_pendentes": len(pending),
            "iip": None if unavailable else round(100 * len(positive) / len(inspected), 2),
            "status": "INDISPONIVEL" if unavailable else "PREVIA",
            "motivo": reason,
        })
    return indicators
