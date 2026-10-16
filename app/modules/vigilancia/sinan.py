"""Consulta pública de arboviroses: uma página por chamada, sem persistência de casos."""

import json
import re
from collections import Counter
from datetime import datetime, timezone

import requests


REGION_URL = "https://www.condomar.pe.gov.br/municipios"
CATALOG_CHECKED_AT = "2026-10-16"
PAGE_SIZE = 10  # A fonte falhou com 100/1000; lote de 10 validado em consulta real.
MAX_RECORDS = 1_000_000  # Limite por município; atingir o limite nunca significa conclusão.
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
FIELDS = "nu_ano,id_municip,id_mn_resi,classi_fin,sem_not"

# Relação institucional do CONDOMAR, conferida com a API de localidades do IBGE.
# São Caitano é a grafia do IBGE; o consórcio usa São Caetano.
MUNICIPALITIES = (
    {"ibge": "2600609", "name": "Alagoinha", "uf": "PE", "region": "condomar"},
    {"ibge": "2601201", "name": "Arcoverde", "uf": "PE", "region": "condomar"},
    {"ibge": "2601706", "name": "Belo Jardim", "uf": "PE", "region": "condomar"},
    {"ibge": "2602605", "name": "Brejo da Madre de Deus", "uf": "PE", "region": "condomar"},
    {"ibge": "2602803", "name": "Buíque", "uf": "PE", "region": "condomar"},
    {"ibge": "2608008", "name": "Jataúba", "uf": "PE", "region": "condomar"},
    {"ibge": "2610806", "name": "Pedra", "uf": "PE", "region": "condomar"},
    {"ibge": "2610905", "name": "Pesqueira", "uf": "PE", "region": "condomar"},
    {"ibge": "2611200", "name": "Poção", "uf": "PE", "region": "condomar"},
    {"ibge": "2612406", "name": "Sanharó", "uf": "PE", "region": "condomar"},
    {"ibge": "2613107", "name": "São Caitano (São Caetano)", "uf": "PE", "region": "condomar"},
    {"ibge": "2614105", "name": "Sertânia", "uf": "PE", "region": "condomar"},
    {"ibge": "2614857", "name": "Tamandaré", "uf": "PE", "region": "condomar"},
    {"ibge": "2615805", "name": "Tupanatinga", "uf": "PE", "region": "condomar"},
    {"ibge": "2616001", "name": "Venturosa", "uf": "PE", "region": "condomar"},
    {"ibge": "3550308", "name": "São Paulo — capital", "uf": "SP", "region": "sao_paulo"},
)
MUNICIPALITIES_BY_IBGE = {item["ibge"]: item for item in MUNICIPALITIES}

# Dicionário do catálogo (dic_dados_dengue.pdf, p. 12) e layout SINAN Online
# 2015 (5/10/11/12/13), ainda observado na API. Exibir o código junto do rótulo:
# a fonte usa classificações de layouts distintos. Não inferir confirmação lab.
CLASSIFICATIONS = {
    "0": "Ignorado",
    "1": "Confirmado",
    "2": "Descartado",
    "5": "Descartado",
    "8": "Inconclusivo",
    "9": "Ignorado",
    "10": "Dengue",
    "11": "Dengue com sinais de alarme",
    "12": "Dengue grave",
    "13": "Chikungunya",
    "unknown": "Não informada",
}

# Endpoints e envelopes fixos: o parâmetro da requisição nunca vira uma URL.
# Dengue/chikungunya compartilham o layout Online; zika usa o SINAN Net.
DISEASES = {
    "dengue": {
        "label": "Dengue",
        "api_url": "https://apidadosabertos.saude.gov.br/arboviroses/dengue",
        "response_key": "dengue",
        "source_url": "https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue",
        "dictionary_url": "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/dic_dados_dengue.pdf",
        "classifications": CLASSIFICATIONS,
        "legacy_layout": True,
    },
    "zika": {
        "label": "Zika",
        "api_url": "https://apidadosabertos.saude.gov.br/arboviroses/zikavirus",
        "response_key": "zikavirus",
        "source_url": "https://dadosabertos.saude.gov.br/dataset/arboviroses-zika-virus",
        "dictionary_url": "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Zikavirus/dic_dados_zika.pdf",
        "classifications": {"1": "Confirmado", "2": "Descartado", "9": "Ignorado", "unknown": "Não informada"},
        "legacy_layout": False,
    },
    "chikungunya": {
        "label": "Chikungunya",
        "api_url": "https://apidadosabertos.saude.gov.br/arboviroses/chikungunya",
        "response_key": "chikungunya",
        "source_url": "https://dadosabertos.saude.gov.br/dataset/arboviroses-febre-de-chikungunya",
        "dictionary_url": "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Chikungunya/dic_dados_chikungunya.pdf",
        "classifications": CLASSIFICATIONS,
        "legacy_layout": True,
    },
}


class SinanError(ValueError):
    """Erro público e seguro para apresentação na consulta."""


def _code(value):
    if value is None or isinstance(value, bool):
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text if re.fullmatch(r"[0-9]{1,7}", text) else ""


def summarize(records, *, year, municipality_code):
    classes, weeks, residence = Counter(), Counter(), Counter()
    unknown_week = 0
    for row in records:
        # Não publicar totais de uma resposta que ignorou o filtro solicitado.
        if not isinstance(row, dict) or _code(row.get("nu_ano")) != str(year) or _code(row.get("id_municip")) != municipality_code:
            raise SinanError("A fonte retornou registros fora do município ou ano solicitado. Esta página não foi contabilizada.")
        classes[_code(row.get("classi_fin")) or "unknown"] += 1
        week = _code(row.get("sem_not"))
        # O ano epidemiológico pode divergir do ano civil na virada do ano.
        if len(week) == 6 and abs(int(week[:4]) - year) <= 1 and 1 <= int(week[4:]) <= 53:
            weeks[week] += 1
        else:
            unknown_week += 1
        resident_code = _code(row.get("id_mn_resi"))
        residence["unknown" if len(resident_code) != 6 else "local" if resident_code == municipality_code else "other"] += 1
    return {
        "total": len(records), "classifications": dict(classes), "weeks": dict(weeks),
        "unknown_week": unknown_week, "residence": dict(residence),
    }


def fetch_page(*, ibge, year, offset=0, disease="dengue"):
    """Devolve uma página com campos públicos mínimos, sem identificadores pessoais."""
    if disease not in DISEASES:
        raise SinanError("Doença inválida para esta consulta.")
    source = DISEASES[disease]
    if ibge not in MUNICIPALITIES_BY_IBGE or not isinstance(year, int) or isinstance(year, bool) or not 2015 <= year <= datetime.now().year:
        raise SinanError("Município ou ano inválido para esta consulta.")
    if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset < MAX_RECORDS or offset % PAGE_SIZE:
        raise SinanError("Posição de consulta inválida.")
    params = {"id_municip": ibge[:6], "nu_ano": year, "limit": PAGE_SIZE, "offset": offset, "campos": FIELDS}
    try:
        with requests.get(source["api_url"], params=params, timeout=(5, 45), stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                raise SinanError(f"A API do Ministério da Saúde respondeu com erro HTTP {response.status_code}. Tente carregar novamente mais tarde.")
            content = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise SinanError("A resposta da fonte excedeu o limite de leitura. Esta página não foi contabilizada.")
            payload = json.loads(content)
    except requests.Timeout as exc:
        raise SinanError("A API do Ministério da Saúde excedeu o tempo de espera (45 segundos). Tente carregar novamente; isso não indica ausência de registros.") from exc
    except requests.ConnectionError as exc:
        raise SinanError("Não foi possível conectar à API do Ministério da Saúde. Confira a conexão e tente novamente.") from exc
    except (requests.RequestException, UnicodeError, ValueError) as exc:
        if isinstance(exc, SinanError):
            raise
        raise SinanError("Não foi possível ler a fonte SINAN. Tente novamente mais tarde.") from exc
    records = payload.get(source["response_key"]) if isinstance(payload, dict) else None
    if not isinstance(records, list) or len(records) > PAGE_SIZE:
        raise SinanError("A fonte retornou um formato inesperado. Esta página não foi contabilizada.")
    summary = summarize(records, year=year, municipality_code=ibge[:6])
    public_records = []
    for row in records:
        week = _code(row.get("sem_not"))
        resident_code = _code(row.get("id_mn_resi"))
        public_records.append({
            "year": year,
            "week": week if week in summary["weeks"] else None,
            "classification": _code(row.get("classi_fin")) or "unknown",
            "residence": "unknown" if len(resident_code) != 6 else "local" if resident_code == ibge[:6] else "other",
        })
    next_offset = offset + len(records)
    # Em teste real (16/10/2026), offset é deslocamento de REGISTROS, embora
    # o Swagger o descreva como número da página. Incrementar 1 duplica dados.
    finished = len(records) < PAGE_SIZE
    return {
        "municipality": MUNICIPALITIES_BY_IBGE[ibge], "year": year, "disease": disease,
        "offset": offset, "next_offset": None if finished or next_offset >= MAX_RECORDS else next_offset,
        "finished": finished, "limit_reached": not finished and next_offset >= MAX_RECORDS,
        "records": public_records, "summary": summary, "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": source["source_url"], "geographic_filter": "municipio_notificacao", "persisted": False,
    }
