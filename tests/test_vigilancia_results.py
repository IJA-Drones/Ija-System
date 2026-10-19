"""Resultados reais de fixtures: índices, geografia histórica e privacidade SINAN."""

import csv
import io
import json
from unittest.mock import patch

import pytest

from app.extensions import db
from app.modules.vigilancia.results import ResultsStore, filters_from, municipality_ibge
from app.modules.vigilancia.sinan_database import DatabaseStore
from app.modules.vigilancia import sinan_import
from app.modules.vigilancia.field_capture import capture_csv
from test_vigilancia_planning import planned, create, change, prepare_planned
from test_vigilancia_field_routes import client, login
from test_vigilancia_capture import record, deposits


POLYGON = {'type':'Polygon','coordinates':[[[-36.701,-8.351],[-36.699,-8.351],[-36.699,-8.349],[-36.701,-8.349],[-36.701,-8.351]]]}


def setup_results(planned):
    client, store = planned
    create(store)
    before = store.overview(7, True)['territorio'][0]
    store.mutate(7, True, 'a', 'territorio', dict(quarteirao='Q-01',bairro='Bairro Sintético',area='A-01',imoveis='100',referencia='RG',
        geometria_acao='substituir',geometria_confirmada='sim',territorio_versao=str(before['atualizado_em']),geometria=json.dumps(POLYGON)))
    change(store, 'quarteirao', estrato='E-01',quarteirao='Q-01',meta_quarteirao='20',agente_id='701')
    change(store, 'liberar', amostra_validada='sim')
    first = prepare_planned(client, store, **deposits(depositos_b='2'), latitude='-8.35',longitude='-36.7')
    store.confirm(first['id'],prefeitura=7,actor='a')
    second = prepare_planned(client, store, imovel_codigo='IM-002', inspecao_codigo='VIS-002', positivo_aedes='NAO', **deposits())
    store.confirm(second['id'],prefeitura=7,actor='a')
    third = prepare_planned(client, store, imovel_codigo='IM-003', inspecao_codigo='VIS-003', situacao='FECHADO',positivo_aedes='')
    store.confirm(third['id'],prefeitura=7,actor='a')
    focal=record(origem='FOCAL',levantamento_codigo='',estrato_codigo='',imovel_codigo='FOCAL-1',inspecao_codigo='F-01',latitude='-8.351',longitude='-36.701')
    batch=store.prepare(capture_csv(focal,prefeitura=7),prefeitura=7,actor='a',source='Focal fictício',filename='focal.csv',demo=True)
    store.confirm(batch['id'],prefeitura=7,actor='a')
    return client, ResultsStore(store.engine)


def test_report_keeps_sources_separate_and_preserves_historical_polygon(planned):
    client, results = setup_results(planned)
    report=results.report(7,True,filters_from({'levantamento':'L-2026-01'}))
    assert report['atividades']=={'LIRAA':3,'FOCAL':1}
    item=report['indicadores'][0]
    assert (item['iip'],item['ib'],item['imoveis_inspecionados'],item['imoveis_positivos'],item['imoveis_pendentes'])==(50,100,2,1,1)
    feature=report['geografia']['features'][0]
    assert feature['geometry']['coordinates']==[POLYGON['coordinates']]
    assert feature['properties']['quarteiroes']==['Q-01']
    store=planned[1]
    before=store.overview(7,True)['territorio'][0]
    store.mutate(7,True,'a','territorio',dict(quarteirao='Q-01',bairro='Atualizado',area='OUTRA',imoveis='150',referencia='RG novo',
        geometria_acao='remover',geometria_confirmada='sim',territorio_versao=str(before['atualizado_em'])))
    assert results.report(7,True,filters_from({'levantamento':'L-2026-01'}))['geografia']==report['geografia']
    assert results.report(8,True,filters_from({}))['registros']==[]
    assert results.report(7,False,filters_from({}))['registros']==[]
    assert not results.report(7,True,filters_from({'inicio':'2026-10-20'}))['registros']
    all_surveys=results.report(7,True,filters_from({}))
    assert all_surveys['geografia']['features']==[] and 'Selecione um levantamento' in all_surveys['avisos'][0]


def test_results_http_export_filters_and_access(planned):
    client, results=setup_results(planned)
    login(client)
    response=client.get('/vigilancia/resultados?levantamento=L-2026-01')
    assert response.status_code==200 and '50,00%' in response.text
    assert 'Imprimir / salvar PDF' in response.text and 'Depósitos preferenciais' in response.text
    assert response.headers['Cache-Control']=='private, no-store'
    exported=client.get('/vigilancia/resultados/exportar?levantamento=L-2026-01')
    rows=list(csv.DictReader(io.StringIO(exported.data.decode('utf-8-sig')),delimiter=';'))
    assert rows[0]['iip']=='50.0' and rows[0]['positivos_b']=='2'
    geo=client.get('/vigilancia/resultados/exportar?levantamento=L-2026-01&formato=geojson').json
    assert geo['preliminar'] is True and geo['features'][0]['properties']['iip']==50
    for query in ['area=FORA','bairro=FORA','demo=false']:
        assert not client.get('/vigilancia/resultados/exportar?formato=geojson&'+query).json['features']
    for query in ['demo=true&demo=false','inicio=2026-10-23&fim=2026-10-19','semana_inicio=202600','semana_inicio=202643&semana_fim=202640','ano_sinan=9999','doenca=outra']:
        assert client.get('/vigilancia/resultados?'+query).status_code==400
    login(client,'b')
    assert client.get('/vigilancia/resultados?prefeitura_id=7').status_code==403
    login(client,'701')
    assert client.get('/vigilancia/resultados').status_code==403
    login(client)
    choices=frozenset({'area:prefeitura','prefeitura.vigilancia.consultar'})
    with patch('app.modules.gestao_ti.permissions.active_configuration',return_value=choices):
        assert client.get('/vigilancia/resultados').status_code==200
        assert 'Exportar índices CSV' not in client.get('/vigilancia/resultados').text
        assert client.get('/vigilancia/resultados/exportar').status_code==403


def case_job(client,owner='7:a',ibge='2610905',demo=True):
    with client.application.app_context():
        store=DatabaseStore(db.engine)
        scope=dict(disease='dengue',ibge=ibge,year=2026)
        job,_=store.create(owner,kind='csv',**scope,demo=demo)
        sinan_import.run_cases(store,job,scope,sinan_import.sample_csv(scope).encode(),demo)
        return job


def test_sinan_overlay_requires_explicit_municipality_owner_mode_and_week(planned):
    client,results=setup_results(planned)
    login(client)
    job=case_job(client)
    url='/vigilancia/resultados?levantamento=L-2026-01&lote_sinan='+job
    assert 'código IBGE precisa ser configurada' in client.get(url).text
    client.application.config['VIGILANCIA_MUNICIPIOS_IBGE']='{"7":"2610905"}'
    response=client.get(url)
    assert response.status_code==200 and 'SINAN no mesmo painel' in response.text
    def map_data(response):
        return json.loads(response.text.split('id="resultados-mapa-data">',1)[1].split('</script>',1)[0])
    data=map_data(response)
    assert len(data['sinan'])==2 and all('reference' not in point for point in data['sinan'])
    assert not map_data(client.get(url+'&semana_inicio=202640'))['sinan']
    for bad_job in [case_job(client,owner='7:other'),case_job(client,ibge='3550308')]:
        assert client.get('/vigilancia/resultados?lote_sinan='+bad_job).status_code==400
    assert client.get(url+'&demo=false').status_code==400
    assert municipality_ibge('{"7":"2610905"}',7)=='2610905'
    assert municipality_ibge('{"7":2610905}',7) is None
    assert municipality_ibge('invalid',7) is None


def test_covisa_sees_sinan_hub_and_route_without_exposing_other_accounts(planned):
    client,_=planned
    for uid in ['703','704']:
        login(client,uid)
        assert 'Acessar SINAN' in client.get('/vigilancia').text
        assert client.get('/vigilancia/sinan').status_code==200
    login(client,'706')
    assert client.get('/vigilancia/sinan').status_code==403
    login(client,'703')
    choices=frozenset({'area:prefeitura'})
    with patch('app.modules.gestao_ti.permissions.active_configuration',return_value=choices):
        assert client.get('/vigilancia/sinan').status_code==403


def test_api_snapshot_is_aggregated_partial_and_dashboard_does_not_expire_jobs(planned):
    client, _ = setup_results(planned)
    client.application.config['VIGILANCIA_MUNICIPIOS_IBGE']={'7':'2610905'}
    login(client)
    with client.application.app_context():
        store=DatabaseStore(db.engine)
        job,_=store.create('7:a',kind='api',disease='dengue',ibge='2610905',year=2026,demo=True)
        store.finish(job,'partial',summary={'total':3,'groups':[{'week':'202643','classification':'10','residence':'local','count':3}]})
        active,_=store.create('7:a',kind='api',disease='dengue',ibge='2610905',year=2026,demo=True)
        from app.modules.vigilancia.sinan_models import SinanJob
        with store.connection(write=True) as conn:
            conn.execute(SinanJob.__table__.update().where(SinanJob.id==active).values(updated=0))
    response=client.get('/vigilancia/resultados?levantamento=L-2026-01&lote_sinan='+job)
    assert response.status_code==200 and 'IMPORTAÇÃO PARCIAL' in response.text
    assert 'não fornece coordenadas individuais' in response.text
    data=json.loads(response.text.split('id="resultados-mapa-data">',1)[1].split('</script>',1)[0])
    assert data['sinan']==[]
    assert store.get(active,'7:a')['status']=='running'


def test_missing_containers_stay_unknown_in_export_and_chart(planned):
    client, results=setup_results(planned)
    planning=planned[1]
    batch=prepare_planned(client,planning,imovel_codigo='IM-004',inspecao_codigo='VIS-004')
    planning.confirm(batch['id'],prefeitura=7,actor='a')
    login(client)
    response=client.get('/vigilancia/resultados?levantamento=L-2026-01')
    assert response.status_code==200 and 'Indisponível' in response.text
    exported=client.get('/vigilancia/resultados/exportar?levantamento=L-2026-01')
    row=next(csv.DictReader(io.StringIO(exported.data.decode('utf-8-sig')),delimiter=';'))
    assert row['ib']=='' and row['positivos_b']==''
    assert row['iip']=='66.67'
