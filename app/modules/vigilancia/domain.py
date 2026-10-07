"""Tipos da prévia local de vigilância; não representam tabelas do banco."""

from dataclasses import dataclass
from datetime import date


LAYOUT_VERSION = "ija-vigilancia-preview-v1"
MAX_PREFEITURA_ID = 2147483647
CSV_COLUMNS = (
    "municipio_id",
    "origem",
    "imovel_codigo",
    "inspecao_codigo",
    "data_inspecao",
    "bairro",
    "area_codigo",
    "levantamento_codigo",
    "estrato_codigo",
    "situacao",
    "positivo_aedes",
    "latitude",
    "longitude",
)


@dataclass(frozen=True)
class ImovelVigilancia:
    prefeitura_id: int
    imovel_codigo: str
    bairro: str
    area_codigo: str
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class InspecaoCampo:
    prefeitura_id: int
    origem: str
    imovel_codigo: str
    inspecao_codigo: str
    data_inspecao: date
    situacao: str
    positivo_aedes: bool | None
    levantamento_codigo: str = ""
    estrato_codigo: str = ""
