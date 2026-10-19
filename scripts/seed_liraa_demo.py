"""Amostra fictícia de LIRAa/Focal, apenas em demo=True e prefeitura de teste.

Sem --apply, confere e mostra o plano. Não cria tabelas, usuários nem OS.
A aplicação exige IJA_ALLOW_TEST_SEED=1 e é uma única transação repetível.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models import Prefeitura  # noqa: E402
from app.modules.vigilancia.domain import DEPOSIT_COLUMNS  # noqa: E402
from app.modules.vigilancia.field_models import CampoInspecao, CampoLevantamento, CampoLote, CampoImovel  # noqa: E402
from app.modules.vigilancia.field_store import FieldConflict, _csv  # noqa: E402
from app.modules.vigilancia.planning import PlanningStore  # noqa: E402
from app.modules.vigilancia.planning_models import CampoPlano, CampoQuarteirao  # noqa: E402
from app.modules.vigilancia.results import ResultsStore, filters_from  # noqa: E402

ACTOR = "demo:liraa-v1"
SOURCE = "DEMONSTRACAO IJA v1 - dados ficticios para visualizar o painel"


def fixture(prefeitura: int, base: date):
    prefix = "DEMO-VIG-" + base.strftime("%Y%m%d")
    survey = "DEMO-LIRAA-" + base.strftime("%Y%m%d")
    blocks, records, focal = [], {}, []
    groups = [("NORTE", -8.342, -36.695, 1), ("CENTRO", -8.352, -36.700, 4), ("SUL", -8.362, -36.705, 8)]
    for group, (name, lat, lng, positives) in enumerate(groups, 1):
        stratum, area, neighborhood = f"DEMO-E{group:02}", f"DEMO-A{group:02}", f"Bairro fictício {name.title()}"
        for half in range(2):
            code = f"{prefix}-Q{group}{half+1}"
            center_lng = lng + (half * 2 - 1) * .0014
            ring = [[round(center_lng+x, 6), round(lat+y, 6)] for x, y in [(-.001,-.001),(.001,-.001),(.001,.001),(-.001,.001),(-.001,-.001)]]
            blocks.append(dict(quarteirao=code, bairro=neighborhood, area=area, imoveis="100", referencia=SOURCE,
                geometria_acao="substituir", geometria_confirmada="sim", geometria=json.dumps({"type":"Polygon", "coordinates":[ring]}),
                estrato=stratum))
            visits = []
            for index in range(11):
                code_visit = f"{prefix}-L{group}{half+1}-{index+1:02}"
                positive = index < 10 and half * 10 + index < positives
                situation = "INSPECIONADO" if index < 10 else ["FECHADO", "RECUSADO", "NAO_INSPECIONADO"][(group+half-1) % 3]
                row = dict(municipio_id=prefeitura, origem="LIRAA", imovel_codigo=code_visit, inspecao_codigo=code_visit,
                    data_inspecao=(base-timedelta(days=2-half)).isoformat(), bairro=neighborhood, area_codigo=area,
                    levantamento_codigo=survey, estrato_codigo=stratum, situacao=situation,
                    positivo_aedes=("SIM" if positive else "NAO") if index < 10 else "",
                    latitude=round(lat + (-.00055 if index < 5 else .00055), 6),
                    longitude=round(center_lng-.0006+(index % 5)*.0003, 6))
                if index < 10:
                    row.update({name:0 for name in DEPOSIT_COLUMNS})
                    if positive:
                        category = ["depositos_a2", "depositos_d1", "depositos_d2"][group-1]
                        row[category] = 2
                        row["depositos_b"] = 1
                visits.append(row)
            records[code] = visits
        for index in range(4):
            code = f"{prefix}-F{group}-{index+1:02}"
            row = dict(municipio_id=prefeitura, origem="FOCAL", imovel_codigo=code, inspecao_codigo=code,
                data_inspecao=base.isoformat(), bairro=neighborhood, area_codigo=area,
                levantamento_codigo="", estrato_codigo="", situacao="INSPECIONADO", positivo_aedes="SIM" if index % 2 == 0 else "NAO",
                latitude=round(lat+.0003*index, 6), longitude=round(lng+.0002*index, 6))
            focal.append(row)
    return dict(prefix=prefix, survey=survey, blocks=blocks, records=records, focal=focal, base=base)


class TransactionStore(PlanningStore):
    """Usa as regras dos serviços mantendo toda a fixture na mesma transação."""
    def __init__(self, connection):
        super().__init__(connection.engine)
        self.bound_connection = connection

    @contextmanager
    def connection(self, *, write_prefeitura=None):
        yield self.bound_connection


def _existing(conn, prefeitura, data):
    table = CampoPlano.__table__
    previous = conn.execute(sa.select(table).where(table.c.prefeitura == prefeitura,
        table.c.demo.is_(True), table.c.code == data["survey"])).mappings().first()
    if previous:
        if previous["fonte"] != SOURCE:
            raise FieldConflict("O código da amostra já é usado por outro cadastro; nada foi sobrescrito.")
        actual = list(conn.scalars(sa.select(CampoInspecao.payload).where(CampoInspecao.prefeitura == prefeitura,
            CampoInspecao.demo.is_(True), CampoInspecao.code.startswith(data["prefix"]))))
        # Normalização é a mesma do importador, inclusive campos opcionais.
        from app.modules.vigilancia.service import preview_csv
        expected = preview_csv(_csv([row for rows in data["records"].values() for row in rows] + data["focal"]), prefeitura_id=prefeitura)["registros"]
        normalize = lambda rows: {(row["origem"], row["inspecao_codigo"]): {key:value for key,value in row.items() if key != "linha"} for row in rows}
        if normalize(actual) != normalize(expected):
            raise FieldConflict("A amostra existente foi alterada ou está incompleta; nenhuma linha será sobrescrita.")
        return True
    for model in (CampoInspecao, CampoImovel, CampoLevantamento, CampoQuarteirao):
        if conn.scalar(sa.select(sa.func.count()).select_from(model).where(model.prefeitura == prefeitura,
            model.demo.is_(True), model.code.startswith(data["prefix"] if model is not CampoLevantamento else data["survey"]))):
            raise FieldConflict("Há códigos demonstrativos conflitantes; nenhum cadastro será sobrescrito.")
    return False


def seed_connection(conn, prefeitura: int, base: date, *, apply=False):
    registered = conn.execute(sa.select(Prefeitura.id, Prefeitura.nome, Prefeitura.ativa).where(Prefeitura.id == prefeitura)).mappings().first()
    if not registered or not registered["ativa"] or not any(word in registered["nome"].lower() for word in ("teste", "test", "demo")):
        raise FieldConflict("Escolha uma prefeitura ativa identificada como teste ou demonstração.")
    data = fixture(prefeitura, base)
    exists = _existing(conn, prefeitura, data)
    result = dict(prefeitura_id=prefeitura, prefeitura=registered["nome"], demonstracao=True,
        levantamento=data["survey"], quarteiroes=6, estratos=3, visitas_liraa=66, acoes_focais=12,
        imoveis_inspecionados=60, imoveis_positivos=13, pendencias=6,
        iip_por_estrato={"DEMO-E01":5.0,"DEMO-E02":20.0,"DEMO-E03":40.0}, changed=False, existing=exists)
    if not apply or exists:
        return result
    store = TransactionStore(conn)
    for block in data["blocks"]:
        store.mutate(prefeitura, True, ACTOR, "territorio", block)
    store.mutate(prefeitura, True, ACTOR, "criar", dict(plano=data["survey"], titulo="DEMONSTRAÇÃO · LIRAa fictício",
        inicio=(base-timedelta(days=6)).isoformat(), fim=base.isoformat(), responsavel="Coordenação fictícia de demonstração", fonte=SOURCE))

    def change(action, **values):
        version = conn.scalar(sa.select(CampoPlano.versao).where(CampoPlano.prefeitura == prefeitura,
            CampoPlano.demo.is_(True), CampoPlano.code == data["survey"]))
        return store.mutate(prefeitura, True, ACTOR, action, {"plano":data["survey"], "versao":str(version), **values})

    for group in range(1,4):
        change("estrato", estrato=f"DEMO-E{group:02}", imoveis_estrato="200", meta_estrato="20", criterio="Território fictício para visualizar os indicadores")
    for block in data["blocks"]:
        change("quarteirao", estrato=block["estrato"], quarteirao=block["quarteirao"], meta_quarteirao="10")
    change("liberar", amostra_validada="sim")
    for code, visits in data["records"].items():
        batch = store.prepare(_csv(visits), prefeitura=prefeitura, actor=ACTOR, source=SOURCE,
            filename=f"{code}.csv", demo=True, plan_reference={"plano":data["survey"],"quarteirao":code})
        store.confirm(batch["id"], prefeitura=prefeitura, actor=ACTOR)
    batch = store.prepare(_csv(data["focal"]), prefeitura=prefeitura, actor=ACTOR, source=SOURCE,
        filename="DEMO-focal.csv", demo=True)
    store.confirm(batch["id"], prefeitura=prefeitura, actor=ACTOR)
    result["changed"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefeitura-id", type=int, required=True)
    parser.add_argument("--data-base", type=date.fromisoformat, default=datetime.now(ZoneInfo("America/Sao_Paulo")).date())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and os.getenv("IJA_ALLOW_TEST_SEED") != "1":
        raise FieldConflict("Defina IJA_ALLOW_TEST_SEED=1 para aplicar a amostra no banco de teste.")
    values = dotenv_values(ROOT/".env", interpolate=False)
    uri = os.getenv("DATABASE_URL") or values.get("DATABASE_URL") or ""
    url = make_url(uri.replace("postgres://", "postgresql://", 1))
    if url.get_backend_name() != "postgresql" or not (url.host or "").endswith(".neon.tech"):
        raise FieldConflict("Este comando aceita somente o PostgreSQL Neon de teste configurado.")
    engine = sa.create_engine(url, poolclass=NullPool, hide_parameters=True, connect_args={"connect_timeout":10})
    try:
        with engine.connect() as conn, conn.begin():
            if not args.apply:
                conn.execute(sa.text("SET TRANSACTION READ ONLY"))
            conn.execute(sa.text("SET LOCAL lock_timeout = '3s'"))
            conn.execute(sa.text("SET LOCAL statement_timeout = '60s'"))
            conn.execute(sa.text("SET LOCAL search_path = public"))
            if args.apply:
                conn.execute(sa.select(sa.func.pg_advisory_xact_lock(1229603073,args.prefeitura_id)))
            result = seed_connection(conn, args.prefeitura_id, args.data_base, apply=args.apply)
        print(json.dumps(result, ensure_ascii=False))
        if args.apply:
            report = ResultsStore(engine).report(args.prefeitura_id, True, filters_from({"levantamento":result["levantamento"]}))
            if [item["iip"] for item in report["indicadores"]] != [5.0,20.0,40.0] or len(report["geografia"]["features"]) != 3:
                raise FieldConflict("A amostra foi gravada, mas a conferência do painel precisa de revisão; nenhum dado anterior foi alterado.")
            print(json.dumps({"verified":True,"atividades":report["atividades"],"iip":[item["iip"] for item in report["indicadores"]],
                              "grupos_no_mapa":len(report["geografia"]["features"])},ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, sa.exc.SQLAlchemyError) as exc:
        print(json.dumps({"status":"error", "message":str(exc) if isinstance(exc,ValueError) else "Falha na conexão ou inserção; a transação foi desfeita."},ensure_ascii=False))
        raise SystemExit(1)
