"""Amostra visual: repetição sem duplicar, modos separados e falha sem carga parcial."""

from datetime import date
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from app.extensions import db
from app.models import Prefeitura
from app.modules.vigilancia.field_models import CampoInspecao, CampoLote
from app.modules.vigilancia.planning_models import CampoPlano, CampoQuarteirao
from app.modules.vigilancia.results import ResultsStore, filters_from
from app.modules.vigilancia.field_store import FieldConflict
from scripts.seed_liraa_demo import seed_connection, TransactionStore
from test_vigilancia_planning import planned
from test_vigilancia_field_routes import client

BASE = date(2026,10,19)


def demo_engine(planned):
    client, store = planned
    with client.application.app_context():
        db.session.get(Prefeitura,7).nome='Prefeitura de demonstração'
        db.session.commit()
    return store.engine


def test_preview_apply_and_repeat_preserve_counts_and_other_scopes(planned):
    engine=demo_engine(planned)
    with engine.begin() as conn:
        plan=seed_connection(conn,7,BASE)
        assert not plan['changed'] and not plan['existing']
        assert conn.scalar(sa.select(sa.func.count()).select_from(CampoPlano))==0
    with engine.begin() as conn:
        result=seed_connection(conn,7,BASE,apply=True)
    assert result['changed']
    report=ResultsStore(engine).report(7,True,filters_from({'levantamento':result['levantamento']}))
    assert report['atividades']=={'LIRAA':66,'FOCAL':12}
    assert [item['iip'] for item in report['indicadores']]==[5,20,40]
    assert [item['ib'] for item in report['indicadores']]==[15,60,120]
    assert sum(item['imoveis_pendentes'] for item in report['indicadores'])==6
    assert len(report['geografia']['features'])==3
    assert ResultsStore(engine).records(7,demo=False)==[]
    assert ResultsStore(engine).records(8,demo=True)==[]
    with engine.begin() as conn:
        again=seed_connection(conn,7,BASE,apply=True)
        assert not again['changed'] and again['existing']
        assert conn.scalar(sa.select(sa.func.count()).select_from(CampoLote))==7
        assert conn.scalar(sa.select(sa.func.count()).select_from(CampoInspecao))==78
    # Uma edição externa na amostra não é sobrescrita pelo seed.
    with engine.begin() as conn:
        table=CampoInspecao.__table__
        row=conn.execute(sa.select(table).limit(1)).mappings().one()
        conn.execute(table.update().where(table.c.prefeitura==7,table.c.demo.is_(True),table.c.code==row['code'])
            .values(payload={**row['payload'],'bairro':'Alterado manualmente'}))
    with engine.begin() as conn, pytest.raises(FieldConflict,match='alterada'):
        seed_connection(conn,7,BASE,apply=True)


def test_error_rolls_back_whole_fixture_and_generic_prefeitura_is_required(planned):
    client,store=planned
    with store.engine.begin() as conn,pytest.raises(FieldConflict,match='prefeitura ativa'):
        seed_connection(conn,7,BASE,apply=True)
    engine=demo_engine(planned)
    with patch.object(TransactionStore,'confirm',side_effect=RuntimeError('falha fictícia')):
        with pytest.raises(RuntimeError,match='falha fictícia'):
            with engine.begin() as conn:
                seed_connection(conn,7,BASE,apply=True)
    with engine.begin() as conn:
        for model in (CampoPlano,CampoQuarteirao,CampoLote,CampoInspecao):
            assert conn.scalar(sa.select(sa.func.count()).select_from(model))==0
