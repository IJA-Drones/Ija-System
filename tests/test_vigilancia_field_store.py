"""Persistência, reconciliação e atomicidade de cargas Focal/LIRAa."""

import csv
import io
from concurrent.futures import ThreadPoolExecutor

import pytest
import sqlalchemy as sa
from app.models import Prefeitura
from app.modules.vigilancia.field_models import FIELD_TABLES

from app.modules.vigilancia.field_store import FieldConflict, FieldStore, FieldStoreError
from app.modules.vigilancia.sample import build_sample_csv
from app.modules.vigilancia.service import CSV_COLUMNS


def csv_rows(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def rows():
    return list(csv.DictReader(io.StringIO(build_sample_csv(7).decode("utf-8-sig"))))


@pytest.fixture
def store(tmp_path):
    engine = sa.create_engine('sqlite:///' + str(tmp_path/'campo.sqlite'), connect_args={'timeout': 3})
    @sa.event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Prefeitura.__table__.create(engine)
    for table in FIELD_TABLES:
        table.create(engine)
    with engine.begin() as conn:
        conn.execute(Prefeitura.__table__.insert(), [dict(id=i,nome=str(i),slug=str(i)) for i in (7,8)])
    yield FieldStore(engine)
    engine.dispose()


def prepare(store, content=None, actor="1", prefeitura=7, demo=True, source="Amostra sintética"):
    return store.prepare(content if content is not None else build_sample_csv(prefeitura),
                         prefeitura=prefeitura, actor=actor, demo=demo, source=source, filename="sample.csv")


def confirm(store, batch, actor="1", prefeitura=7):
    return store.confirm(batch["id"], prefeitura=prefeitura, actor=actor)


def counts(store):
    with store.connection() as db:
        return tuple(db.exec_driver_sql(f"SELECT count(*) FROM {name}").fetchone()[0] for name in
                     ("vigilancia_campo_imoveis", "vigilancia_campo_inspecoes", "vigilancia_campo_levantamentos", "vigilancia_campo_lote_inspecoes"))


def test_prepare_preserves_original_without_publishing_then_reopens(store):
    content=build_sample_csv(7)
    batch=prepare(store,content)
    assert batch["status"] == "VALIDADO"
    assert counts(store) == (0,0,0,0)
    assert store.original(batch["id"],7) == content
    saved=confirm(store,batch)
    assert saved["status"] == "CONCLUIDO"
    assert saved["inserted"] == 5 and saved["reused"] == 0
    reopened=FieldStore(store.engine).get(batch["id"],7)
    assert reopened["report"]["persistido"] is True
    assert reopened["report"]["indicadores"][0]["iip"] == 33.33
    assert counts(store) == (5,5,1,5)


def test_repeated_file_and_repeated_confirmation_are_idempotent(store):
    batch=prepare(store)
    confirm(store,batch)
    assert prepare(store)["id"] == batch["id"]
    assert confirm(store,batch)["inserted"] == 5
    assert counts(store) == (5,5,1,5)


def test_another_actor_and_reformatted_file_reuse_inspections(store):
    confirm(store,prepare(store))
    batch=prepare(store,csv_rows(rows()),actor="2")
    saved=confirm(store,batch,actor="2")
    assert (saved["inserted"], saved["reused"]) == (0,5)
    assert counts(store) == (5,5,1,10)


def test_invalid_row_preserves_rejected_report_without_partial_load(store):
    data=rows()
    data[-1]["data_inspecao"]="invalid"
    batch=prepare(store,csv_rows(data))
    assert batch["status"] == "REJEITADO"
    assert batch["report"]["erros"]
    with pytest.raises(FieldConflict):
        confirm(store,batch)
    assert counts(store) == (0,0,0,0)


@pytest.mark.parametrize("change",["inspection","area","stratum","positivity"])
def test_cross_file_conflicts_block_whole_batch(store,change):
    original=rows()[0]
    confirm(store,prepare(store,csv_rows([original])))
    changed={**original,"inspecao_codigo":"NEW"}
    if change == "inspection":
        changed.update(inspecao_codigo=original["inspecao_codigo"],data_inspecao="2026-02-01")
    elif change == "area":
        changed["area_codigo"]="OTHER"
    elif change == "stratum":
        changed["estrato_codigo"]="OTHER"
    else:
        changed["positivo_aedes"]="NAO" if original["positivo_aedes"]=="SIM" else "SIM"
    unrelated={**original,"imovel_codigo":"UNRELATED","inspecao_codigo":"UNRELATED"}
    batch=prepare(store,csv_rows([unrelated,changed]))
    assert batch["status"]=="VALIDADO"
    before=counts(store)
    with pytest.raises(FieldConflict):
        confirm(store,batch)
    assert counts(store)==before
    assert store.get(batch["id"],7)["status"]=="VALIDADO"


def test_database_failure_rolls_back_all_inserts_and_batch_status(store):
    batch=prepare(store)
    with store.connection() as db:
        db.exec_driver_sql("CREATE TRIGGER fail_links BEFORE INSERT ON vigilancia_campo_lote_inspecoes BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    with pytest.raises(FieldStoreError):
        confirm(store,batch)
    assert counts(store)==(0,0,0,0)
    assert store.get(batch["id"],7)["status"]=="VALIDADO"
    with store.connection() as db:
        db.exec_driver_sql("DROP TRIGGER fail_links")
    assert confirm(store,batch)["status"]=="CONCLUIDO"


def test_confirmation_scope_owner_and_raw_file_isolation(store):
    batch=prepare(store)
    for prefeitura,actor in ((8,"1"),(7,"other")):
        with pytest.raises(FieldStoreError):
            confirm(store,batch,prefeitura=prefeitura,actor=actor)
    assert store.get(batch["id"],8) is None
    assert store.original(batch["id"],8) is None
    assert store.history(8)==[]


def test_demo_and_authorized_data_do_not_share_identities(store):
    confirm(store,prepare(store))
    changed=rows()
    changed[0]["bairro"]="Outro bairro"
    saved=confirm(store,prepare(store,csv_rows(changed),demo=False))
    assert saved["inserted"]==5
    assert counts(store)==(10,10,2,10)


def test_concurrent_confirmation_publishes_only_once(store):
    batch=prepare(store)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _: confirm(FieldStore(store.engine),batch),range(2)))
    assert all(result["status"]=="CONCLUIDO" for result in results)
    assert counts(store)==(5,5,1,5)


def test_original_values_and_normalized_values_are_both_available(store):
    data=rows()
    data[0]["origem"]=" liraa "
    content=csv_rows(data)
    batch=prepare(store,content)
    saved=confirm(store,batch)
    assert store.original(batch["id"],7)==content
    assert saved["report"]["registros"][0]["origem"]=="LIRAA"
    assert saved["report"]["resumo"]["linhas"]==5


def test_storage_ceiling_blocks_new_stage_without_touching_previous(store):
    batch=prepare(store)
    with store.connection() as db:
        db.exec_driver_sql("CREATE TRIGGER stop_new_batches BEFORE INSERT ON vigilancia_campo_lotes BEGIN SELECT RAISE(ABORT,'disk full'); END")
    with pytest.raises(FieldStoreError):
        prepare(store,actor="other")
    assert store.original(batch["id"],7)==build_sample_csv(7)


def test_tampered_original_cannot_confirm_against_a_stale_hash(store):
    batch=prepare(store)
    with store.connection() as db:
        db.exec_driver_sql('UPDATE vigilancia_campo_lotes SET original=? WHERE id=?', (build_sample_csv(7)+b'\n',batch['id']))
    with pytest.raises(FieldConflict):
        confirm(store,batch)
    assert counts(store)==(0,0,0,0)


def test_reconciliation_keeps_duplicate_source_lines_in_original_report(store):
    data=rows()
    batch=prepare(store,csv_rows(data+[data[0]]))
    saved=confirm(store,batch)
    assert saved['report']['resumo']['linhas']==6
    assert saved['report']['resumo']['duplicadas']==1
    assert saved['inserted']==5
    assert counts(store)==(5,5,1,5)


def test_cumulative_capacity_rejects_without_losing_existing_data(store,monkeypatch):
    from app.modules.vigilancia import field_store
    confirm(store,prepare(store))
    extra={**rows()[0],'imovel_codigo':'extra','inspecao_codigo':'extra'}
    batch=prepare(store,csv_rows([extra]))
    monkeypatch.setattr(field_store,'MAX_ROWS',5)
    with pytest.raises(FieldConflict,match='5.000'):
        confirm(store,batch)
    assert counts(store)==(5,5,1,5)
