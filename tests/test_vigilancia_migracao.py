"""Migração de dados legados (TR 4.7): mapeamento, limpeza e carga LIRAa."""

import csv
import io

import pytest
import sqlalchemy as sa

from app.models import Prefeitura
from app.modules.vigilancia import migracao as mig
from app.modules.vigilancia.field_models import FIELD_TABLES, CampoInspecao
from app.modules.vigilancia.migracao_models import Migracao
from app.modules.vigilancia.planning_models import PLANNING_TABLES

OPTIONS = {"fonte": "SISPNCD", "origem": "LIRAA", "levantamento": "", "estrato": "", "geocodificar": False}


def legacy(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(["COD_IMOVEL", "DT_VISITA", "CICLO", "ESTRATO", "BAIRRO", "ZONA", "SITUACAO", "FOCO", "LATITUDE", "LONGITUDE"])
    writer.writerows(rows)
    return stream.getvalue().encode("cp1252")


ROWS = [
    ["0101", "05/10/2026", "LIRAA 10/2026", "E1", "Centro", "Z-01", "T", "S", "-8,3561", "-36,6981"],
    ["0101", "05/10/2026", "LIRAA 10/2026", "E1", "Centro", "Z-01", "T", "S", "-8,3561", "-36,6981"],
    ["0102", "31/02/2026", "LIRAA 10/2026", "E1", "Centro", "Z-01", "T", "N", "", ""],
    ["", "06/10/2026", "LIRAA 10/2026", "E1", "Centro", "Z-01", "T", "N", "", ""],
    ["0104", "7/10/26", "LIRAA 10/2026", "E1", "centro ", "z-01", "F", "N", "", ""],
]


@pytest.fixture
def store(tmp_path):
    engine = sa.create_engine("sqlite:///" + str(tmp_path / "migracao.sqlite"))
    Prefeitura.__table__.create(engine)
    for table in (*FIELD_TABLES, *PLANNING_TABLES, Migracao.__table__):
        table.create(engine)
    with engine.begin() as conn:
        conn.execute(Prefeitura.__table__.insert().values(id=7, nome="Sete", slug="sete"))
    yield mig.MigracaoStore(engine)
    engine.dispose()


def run(store, content=None):
    identifier = store.create(prefeitura=7, demo=True, actor="1", destino="visitas", fonte="SISPNCD",
                              filename="visitas.csv", content=content or legacy(ROWS))
    item = store.get(identifier, 7)
    header, _ = mig.read_extracted(item["extraido"])
    mapping = mig.parse_mapping("visitas", header, {f"map_{k}": v for k, v in item["mapeamento"]["colunas"].items()})
    ctx = {**store.context("visitas", 7, True), "prefeitura": 7, "ibge": "2610905", "demo": True}
    report, adequado = mig.validate("visitas", item["extraido"], mapping, OPTIONS, ctx)
    store.save(identifier, 7, etapa="VALIDADO", relatorio=report, adequado=adequado)
    return identifier, mapping, report


def test_mapping_suggested_from_legacy_names():
    mapping = mig.suggest_mapping("visitas", ["COD_IMOVEL", "DT_VISITA", "BAIRRO", "ZONA", "CICLO", "Situação", "FOCO"])
    assert mapping["imovel_codigo"] == "COD_IMOVEL" and mapping["data_inspecao"] == "DT_VISITA"
    assert mapping["area_codigo"] == "ZONA" and mapping["levantamento_codigo"] == "CICLO"
    assert mapping["situacao"] == "Situação" and mapping["positivo_aedes"] == "FOCO"
    with pytest.raises(mig.MigracaoError, match="obrigatória"):
        mig.parse_mapping("visitas", ["COD_IMOVEL"], {"map_imovel_codigo": "COD_IMOVEL"})


def test_duplicates_invalid_date_and_missing_property(store):
    _, _, report = run(store)
    assert (report["lidos"], report["validos"], report["duplicados"], report["rejeitados"]) == (5, 2, 1, 2)
    by_line = {(o["linha"], o["tipo"], o["campo"]): o for o in report["ocorrencias"]}
    assert (3, "DUPLICADO", "registro") in by_line
    assert by_line[(4, "REJEITADO", "data_inspecao")]["original"] == "31/02/2026"
    assert (5, "REJEITADO", "imovel_codigo") in by_line
    assert by_line[(6, "CORRIGIDO", "positivo_aedes")]["final"] == ""
    assert by_line[(6, "PADRONIZADO", "data_inspecao")]["final"] == "2026-10-07"
    assert report["amostra"][0][5:8] == ["CENTRO", "Z-01", "LIRAA-10-2026"]


def test_liraa_load_through_field_store_is_idempotent(store):
    identifier, _, report = run(store)
    result = mig.load(store.get(identifier, 7), actor="1", engine=store.engine)
    assert (result["inseridos"], result["reaproveitados"]) == (2, 0)
    with store.engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(CampoInspecao)) == 2
    second, _, again = run(store)
    assert again["ja_carregados"] == 2
    assert mig.load(store.get(second, 7), actor="1", engine=store.engine)["reaproveitados"] == 2
