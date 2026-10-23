"""Carga planejada em vários quarteirões: polígonos, vínculos e confirmação atômica."""
import csv
import io
import json

import pytest
import sqlalchemy as sa

from app.modules.vigilancia.planning import RG_COLUMNS, PLAN_COLUMNS, PlanningStore
from app.modules.vigilancia.planning_models import CampoPlanoVisita
from app.modules.vigilancia.results import ResultsStore, filters_from
from app.modules.vigilancia.field_store import FieldConflict
from app.modules.vigilancia.domain import CSV_COLUMNS
from test_vigilancia_planning import planned, client, change
from test_vigilancia_field_routes import login, token, confirm
from test_vigilancia_capture import record


def csv_bytes(columns, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, columns, delimiter=';')
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


def territory():
    return [dict(quarteirao=f'Q-{i}', bairro=f'Bairro {i}', area=f'A-{i}', imoveis='100', referencia='DEMO',
        geometria=json.dumps({'type':'Polygon','coordinates':[[[-36.70+i*.003,-8.35],
        [-36.698+i*.003,-8.35],[-36.698+i*.003,-8.352],[-36.70+i*.003,-8.352],[-36.70+i*.003,-8.35]]]})) for i in (1,2)]


def make_plan(planning):
    planning.mutate(7,True,'a','importar_territorio',{'geometrias_confirmadas':'sim'},
        csv_bytes((*RG_COLUMNS,'geometria'),territory()))
    planning.mutate(7,True,'a','criar',dict(plano='L-2026-01',titulo='DEMO',inicio='2026-10-19',
        fim='2026-10-23',responsavel='Coordenação',fonte='Amostra DEMO'))
    plan=planning.overview(7,True,'L-2026-01')['plano']
    planning.mutate(7,True,'a','importar_plano',{'plano':plan['code'],'versao':str(plan['versao'])},
        csv_bytes(PLAN_COLUMNS,[dict(estrato=f'E-{i}',imoveis_estrato='100',meta_estrato='1',criterio='DEMO',
                                   quarteirao=f'Q-{i}',meta_quarteirao='1',agente_id='') for i in (1,2)]))
    change(planning,'liberar',amostra_validada='sim')


def visits(**changes):
    return csv_bytes((*CSV_COLUMNS,'quarteirao_codigo'),[
        dict(municipio_id=7,**record(estrato_codigo=f'E-{i}',bairro=f'Bairro {i}',area_codigo=f'A-{i}',
            imovel_codigo=f'IM-{i}',inspecao_codigo=f'VIS-{i}',positivo_aedes='SIM' if i==1 else 'NAO'),
            quarteirao_codigo=f'Q-{i}') | changes for i in (1,2)])


def test_territory_is_first_and_sample_upload_waits_for_its_blocks(planned):
    c, planning = planned
    login(c)
    page = c.get('/vigilancia/planejamento?demo=true')
    assert 'data-vigilancia-default="territorio"' in page.text
    assert page.text.index('<strong>Quarteirões</strong>') < page.text.index('<strong>Levantamento e amostra</strong>')
    assert '<strong>Visitas</strong>' in page.text and '<strong>Resultados</strong>' in page.text
    assert page.text.index('id="territorio-importacao" open') < page.text.index('id="territorio-mapa"')
    common = dict(demo='true', _csrf_token=token(c))
    # Criar o rascunho não exige o CSV de amostra.
    response = c.post('/vigilancia/planejamento', data=dict(common, acao='criar', plano='L-2026-01',
        titulo='Ensaio de ordem', inicio='2026-10-19', fim='2026-10-23', responsavel='Coordenação', fonte='DEMO'))
    assert response.status_code == 303
    page = c.get(response.location)
    assert 'Importar quarteirões' in page.text
    assert 'id="amostra-importacao"' not in page.text
    assert 'name="acao" value="liberar"' not in page.text
    p = planning.overview(7, True, 'L-2026-01')['plano']
    sample = csv_bytes(PLAN_COLUMNS, [dict(estrato='E-1', imoveis_estrato='100', meta_estrato='1',
        criterio='DEMO', quarteirao='Q-1', meta_quarteirao='1', agente_id='')])
    # POST direto continua protegido, mesmo sem o formulário disponível.
    response = c.post('/vigilancia/planejamento', data=dict(common, acao='importar_plano', plano=p['code'],
        versao=str(p['versao']), arquivo=(io.BytesIO(sample), 'amostra.csv')))
    assert response.status_code == 400 and 'CSV 01' in response.text
    assert planning.overview(7, True, p['code'])['estratos'] == []
    response = c.post('/vigilancia/planejamento', data=dict(common, acao='importar_territorio',
        retorno_plano=p['code'], geometrias_confirmadas='sim',
        arquivo=(io.BytesIO(csv_bytes((*RG_COLUMNS, 'geometria'), territory())), 'territorio.csv')))
    assert response.status_code == 303 and 'plano=L-2026-01' in response.location
    page = c.get(response.location)
    assert 'Continuar para a amostra' in page.text
    assert 'id="amostra-importacao" open' in page.text
    p = planning.overview(7, True, p['code'])['plano']
    response = c.post('/vigilancia/planejamento', data=dict(common, acao='importar_plano', plano=p['code'],
        versao=str(p['versao']), arquivo=(io.BytesIO(sample), 'amostra.csv')))
    assert response.status_code == 303
    assert len(planning.overview(7, True, p['code'])['quarteiroes']) == 1


@pytest.mark.parametrize('plan_code,csv_code,select_destination', [
    ('L-2026-01','L-2026-01',False),
    ('teste-1','DEMO-POC-PESQUEIRA-2026',True),
])
def test_three_csv_http_flow_links_multiple_blocks_and_renders_iip_polygons(planned,plan_code,csv_code,select_destination):
    c,planning=planned;login(c)
    c.get('/vigilancia/planejamento')
    common={'demo':'true','_csrf_token':token(c)}
    response=c.post('/vigilancia/planejamento',data={**common,'acao':'importar_territorio',
        'geometrias_confirmadas':'sim','arquivo':(io.BytesIO(csv_bytes((*RG_COLUMNS,'geometria'),territory())),'territorio.csv')})
    assert response.status_code==303,response.text
    response=c.post('/vigilancia/planejamento',data={**common,'acao':'criar','plano':plan_code,
        'titulo':'DEMO','inicio':'2026-10-19','fim':'2026-10-23','responsavel':'Coordenação','fonte':'DEMO'})
    assert response.status_code==303,response.text
    p=planning.overview(7,True,plan_code)['plano']
    assert p['status']=='RASCUNHO'
    response=c.post('/vigilancia/planejamento',data={**common,'acao':'importar_plano','plano':p['code'],'versao':str(p['versao']),
        'arquivo':(io.BytesIO(csv_bytes(PLAN_COLUMNS,[dict(estrato=f'E-{i}',imoveis_estrato='100',meta_estrato='1',
            criterio='DEMO',quarteirao=f'Q-{i}',meta_quarteirao='1',agente_id='') for i in (1,2)])),'amostra.csv')})
    assert response.status_code==303,response.text
    overview=planning.overview(7,True,plan_code)
    assert overview['plano']['status']=='RASCUNHO'
    assert len(overview['estratos'])==2 and len(overview['quarteiroes'])==2
    page=c.get('/vigilancia/planejamento?demo=true&plano='+plan_code)
    assert 'Importar amostra</button>' in page.text
    planning.mutate(7,True,'a','liberar',{'plano':plan_code,
        'versao':str(overview['plano']['versao']),'amostra_validada':'sim'})
    original=visits(levantamento_codigo=csv_code)
    response=c.post('/vigilancia/importacoes',data={**common,'acao':'preparar','fonte':'CSV planejado',
        **({'levantamento_destino':plan_code} if select_destination else {}),
        'arquivo':(io.BytesIO(original),'visitas.csv')})
    assert response.status_code==303,response.text
    batch=planning.history(7)[0]
    assert planning.records(7,demo=True)==[]
    assert confirm(c,batch['id']).status_code==303
    assert confirm(c,batch['id']).status_code==303
    assert planning.original(batch['id'],7)==original
    overview=planning.overview(7,True,plan_code)
    assert [b['inspecionados'] for b in overview['quarteiroes']]==[1,1]
    with planning.connection() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(CampoPlanoVisita))==2
    report=ResultsStore(planning.engine).report(7,True,filters_from({'levantamento':plan_code}))
    assert len(report['geografia']['features'])==2
    assert sorted(f['properties']['iip'] for f in report['geografia']['features'])==[0,100]
    page=c.get('/vigilancia/importacoes?lote='+batch['id'])
    assert page.status_code==200 and 'Q-1, Q-2' in page.text


def test_csv_geometry_requires_confirmation_is_atomic_and_cannot_overwrite_other_outline(planned):
    _,planning=planned
    raw=csv_bytes((*RG_COLUMNS,'geometria'),territory())
    with pytest.raises(FieldConflict,match='confirmação'):
        planning.mutate(7,True,'a','importar_territorio',{},raw)
    assert not planning.overview(7,True)['territorio']
    bad=territory();bad[1]['geometria']='{"type":"Point","coordinates":[0,0]}'
    with pytest.raises(FieldConflict):
        planning.mutate(7,True,'a','importar_territorio',{'geometrias_confirmadas':'sim'},csv_bytes((*RG_COLUMNS,'geometria'),bad))
    assert not planning.overview(7,True)['territorio']
    planning.mutate(7,True,'a','importar_territorio',{'geometrias_confirmadas':'sim'},raw)
    planning.mutate(7,True,'a','importar_territorio',{'geometrias_confirmadas':'sim'},raw)
    different=territory();different[0]['geometria']=territory()[1]['geometria']
    with pytest.raises(FieldConflict,match='outro contorno'):
        planning.mutate(7,True,'a','importar_territorio',{'geometrias_confirmadas':'sim'},csv_bytes((*RG_COLUMNS,'geometria'),different))


@pytest.mark.parametrize('change_values',[{'quarteirao_codigo':'Q-INEXISTENTE'},{'estrato_codigo':'E-INEXISTENTE'},
    {'bairro':'Fora do território'},{'data_inspecao':'2026-10-18'},{'levantamento_codigo':'OUTRO'}])
def test_invalid_planned_csv_is_rejected_without_saving_visits(planned,change_values):
    _,planning=planned;make_plan(planning)
    with pytest.raises(FieldConflict):
        planning.prepare(visits(**change_values),prefeitura=7,actor='a',source='DEMO',filename='visitas.csv',demo=True)
    assert planning.records(7,demo=True)==[]


def test_planning_is_rechecked_at_confirmation_and_scope_is_not_bypassed(planned):
    _,planning=planned;make_plan(planning)
    with pytest.raises(FieldConflict):
        planning.prepare(visits(),prefeitura=7,actor='a',source='DEMO',filename='visitas.csv',demo=False)
    batch=planning.prepare(visits(),prefeitura=7,actor='a',source='DEMO',filename='visitas.csv',demo=True)
    change(planning,'encerrar')
    with pytest.raises(FieldConflict,match='liberado'):
        planning.confirm(batch['id'],prefeitura=7,actor='a')
    assert planning.records(7,demo=True)==[]
