"""Map improvements reuse operational rows; disposable SQLite, no .env."""
from datetime import date, datetime
from types import SimpleNamespace
import pytest
from werkzeug.exceptions import NotFound
from app.extensions import db
from app.modules.mapas import operacional
from tests.test_mapas_filters import HeatmapFilterTests


@pytest.fixture
def setup():
    case=HeatmapFilterTests();case.setUp()
    yield case
    case.tearDown()


def test_pending_returns_and_missing_coordinates_use_existing_requests(setup):
    case=setup
    original=case._new_request(status='CONCLUÍDO',drone='SIM')
    child=case._new_request(status='PENDENTE',origem_retorno_id=original.id,latitude=None)
    closed=case._new_request(status='CANCELADO')
    future=case._new_request(status='APROVADO',data_agendamento=date(2099,1,1))
    db.session.commit()
    allrows=operacional.points(case.admin,visao='todos')['registros']
    assert len(allrows)==4
    pending=operacional.points(case.admin,visao='pendentes')['registros']
    assert {r['id'] for r in pending}=={child.id,future.id}
    assert next(r for r in pending if r['id']==child.id)['lat'] is None
    returns=operacional.points(case.admin,visao='retornos')['registros']
    assert [r['id'] for r in returns]==[child.id]
    assert returns[0]['retorno'] is True
    assert next(r for r in allrows if r['id']==closed.id)['situacao']=='ENCERRADO'


def test_history_follows_explicit_links_and_not_address(setup):
    c=setup
    first=c._new_request(data_agendamento=date(2025,1,1),drone='SIM')
    second=c._new_request(origem_retorno_id=first.id,equipe_uvis='NAO')
    third=c._new_request(origem_retorno_id=second.id)
    c._new_request() # same address but no link: not the same focus by assumption
    db.session.commit()
    h=operacional.history(c.admin,second.id)
    assert [r['id'] for r in h['registros']]==[first.id,second.id,third.id]
    assert h['registros'][0]['ordens'][0]['larvas']=='SIM'
    assert h['registros'][1]['ordens'][0]['origem']=='Equipe UVIS'
    assert 'fora do período' in h['criterio']


def test_history_each_hop_obeys_tenant_uvis_and_region(setup):
    c=setup
    foreign=c._new_request(user=c.uvis_other_city)
    first=c._new_request(origem_retorno_id=foreign.id)
    same=c._new_request(origem_retorno_id=first.id)
    c._new_request(user=c.uvis_other_city,origem_retorno_id=first.id)
    c._new_request(user=c.uvis_other_region,origem_retorno_id=first.id)
    db.session.commit()
    assert {r['id'] for r in operacional.history(c.uvis,same.id)['registros']}=={first.id,same.id}
    with pytest.raises(NotFound):operacional.history(c.uvis,foreign.id)
    regional=SimpleNamespace(tipo_usuario='regional',prefeitura_id=1,regiao='OESTE')
    assert {r['id'] for r in operacional.history(regional,same.id)['registros']}=={first.id,same.id}
    missing=SimpleNamespace(tipo_usuario='covisa',prefeitura_id=None)
    assert operacional.points(missing,visao='todos')['registros']==[]


def test_corrupt_cycles_and_record_limits_fail_explicitly(setup,monkeypatch):
    c=setup;a=c._new_request();b=c._new_request(origem_retorno_id=a.id)
    a.origem_retorno_id=b.id;db.session.commit()
    with pytest.raises(ValueError,match='inconsistentes'):operacional.history(c.admin,a.id)
    monkeypatch.setattr(operacional,'MAX_RECORDS',1)
    with pytest.raises(ValueError,match='nenhum resultado foi cortado'):operacional.points(c.admin,visao='todos')


def test_period_larva_filters_and_response_status(setup):
    c=setup;a=c._new_request(drone='SIM',status='APROVADO')
    c._new_request(drone='NAO',status='PENDENTE')
    a.ordem_servico.respondido_em=datetime(2026,10,9,12);db.session.commit()
    out=c.app.test_client().get('/api/mapa-operacional?visao=todos&mes=10&ano=2026&larva_visualizada=SIM')
    assert out.status_code==200 and out.headers['Cache-Control']=='private, no-store'
    rows=out.get_json()['registros'];assert len(rows)==1 and rows[0]['situacao']=='CONCLUIDO'
    assert c.app.test_client().get('/api/mapa-operacional?visao=xyz').status_code==400
    assert c.app.test_client().get('/api/mapa-operacional/999999/historico').status_code==404
