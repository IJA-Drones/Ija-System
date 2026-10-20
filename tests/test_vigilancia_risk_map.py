"""Fluxo CSV -> confirmação -> mapa com malha real e isolamento municipal."""
import io
import json
from datetime import date

import pytest
from shapely.geometry import Point, shape

from app.modules.vigilancia.field_store import _csv
from app.modules.vigilancia.risk import analyze, example_files
from app.modules.vigilancia.risk_store import RiskStore
from app.modules.vigilancia.sample import build_geolocated_sample_csv
from app.modules.vigilancia.service import preview_csv
from app.modules.vigilancia.territory import condomar_territory, municipality_feature, pernambuco_context
from test_vigilancia_field_routes import client, login, token, prepare, confirm
from test_vigilancia_planning import planned
from test_vigilancia_results import setup_results, POLYGON


def map_data(response):
    return json.loads(response.text.split('id="campo-territorio-data">', 1)[1].split('</script>', 1)[0])


def sample():
    return build_geolocated_sample_csv(7, '2610905', date(2026, 10, 20))


def test_official_boundaries_replace_the_grid_and_keep_their_source():
    geography = condomar_territory()
    assert len(geography['features']) == 15
    assert len(pernambuco_context()['features']) == 184
    pesqueira = municipality_feature('2610905')
    assert pesqueira['properties']['nome'] == 'Pesqueira'
    assert len(pesqueira['geometry']['coordinates'][0]) > 10
    assert shape(pesqueira['geometry']).is_valid
    assert geography['metadata']['url'].startswith('https://servicodados.ibge.gov.br/')
    # Chamadas não compartilham estruturas mutáveis com o cache territorial.
    geography['features'].clear()
    assert len(condomar_territory()['features']) == 15


def test_geolocated_csv_is_deterministic_and_every_point_is_inside_the_municipality():
    content = sample()
    assert content == sample()
    report = preview_csv(content, prefeitura_id=7)
    assert report['status'] == 'VALIDADO' and not report['erros']
    assert len(report['registros']) == 20
    boundary = shape(municipality_feature('2610905')['geometry'])
    assert all(boundary.covers(Point(row['longitude'], row['latitude'])) for row in report['registros'])
    assert all(row['imovel_codigo'].startswith('DEMO-MAPA-') for row in report['registros'])
    index = report['indicadores'][0]
    assert (index['imoveis_inspecionados'], index['imoveis_positivos'], index['imoveis_pendentes'], index['iip']) == (16, 4, 4, 25)


def test_real_csv_import_confirmation_and_risk_map_share_the_persisted_records(planned):
    client, store = planned
    client.application.config['VIGILANCIA_MUNICIPIOS_IBGE'] = '{"7":"2610905"}'
    login(client)
    client.get('/vigilancia/importacoes')
    response = prepare(client, arquivo=(io.BytesIO(sample()), 'demo-geolocalizado.csv'))
    assert response.status_code == 303
    batch = store.history(7)[0]
    assert batch['status'] == 'VALIDADO'
    assert map_data(client.get('/vigilancia/risco'))['pontos'] == []
    assert confirm(client, batch['id']).status_code == 303
    response = client.get('/vigilancia/risco')
    assert response.status_code == 200 and '25,00%' in response.text
    assert 'Somente cargas confirmadas' in response.text
    assert 'Baixar CSV de demonstração com coordenadas' in response.text
    data = map_data(response)
    assert len(data['pontos']) == 20 and data['ibge'] == '2610905'
    assert data['levantamento'] == 'DEMO-MAPA-2610905-20261020'
    assert all(point['origem'] == 'LIRAA' for point in data['pontos'])
    assert len(data['contexto']['features']) == 184
    assert data['geografia']['features'] == []  # Não inventa área amostrada.
    assert map_data(client.get('/vigilancia/risco?demo=false'))['pontos'] == []
    assert RiskStore(store.engine).history(7, True) == []  # Nenhuma análise paralela/falsa.
    assert client.get('/vigilancia/risco?prefeitura_id=8').status_code == 403
    for query in ['demo=true&demo=false', 'camada=invalida', 'inicio=2026-10-21&fim=2026-10-20']:
        assert client.get('/vigilancia/risco?' + query).status_code == 400
    login(client, '701')
    assert client.get('/vigilancia/risco').status_code == 403


def test_confirmed_csv_without_coordinates_keeps_indices_and_explains_the_empty_points(planned):
    client, store = planned
    rows = preview_csv(sample(), prefeitura_id=7)['registros']
    for row in rows:
        row['latitude'] = row['longitude'] = None
    batch = store.prepare(_csv(rows), prefeitura=7, actor='a', source='Sem coordenadas', filename='sem-gps.csv', demo=True)
    store.confirm(batch['id'], prefeitura=7, actor='a')
    login(client)
    response = client.get('/vigilancia/risco')
    assert '25,00%' in response.text
    assert '20 visitas deste recorte não têm coordenadas' in response.text
    assert map_data(response)['pontos'] == []


def test_manual_planned_visits_and_their_preserved_boundaries_feed_the_same_map(planned):
    client, _ = setup_results(planned)
    login(client)
    response = client.get('/vigilancia/risco')
    assert response.status_code == 200 and '50,00%' in response.text
    data = map_data(response)
    assert len(data['pontos']) == 1 and data['pontos'][0]['origem'] == 'LIRAA'
    assert data['pontos'][0]['inspecao_codigo'] == 'VIS-001'
    assert data['geografia']['features'][0]['geometry']['coordinates'] == [POLYGON['coordinates']]


def test_demo_download_requires_municipal_scope_mapping_and_demo_mode(planned):
    client, _ = planned
    login(client)
    assert client.get('/vigilancia/risco/modelo/liraa').status_code == 400
    client.application.config['VIGILANCIA_MUNICIPIOS_IBGE'] = '{"7":"2610905"}'
    response = client.get('/vigilancia/risco/modelo/liraa?demo=true')
    assert response.status_code == 200
    assert len(preview_csv(response.data, prefeitura_id=7)['registros']) == 20
    assert client.get('/vigilancia/risco/modelo/liraa?demo=false').status_code == 400
    assert client.get('/vigilancia/risco/modelo/liraa?prefeitura_id=8').status_code == 403


def test_historical_demo_uses_official_geojson_and_the_normal_analysis_and_storage(planned):
    client, store = planned
    login(client)
    response = client.get('/vigilancia/risco?camada=historico')
    assert response.status_code == 200 and 'limites reais do IBGE' in response.text
    geo, history = example_files()
    expected = analyze(geo, history)
    response = client.post('/vigilancia/risco', data={
        'acao': 'analisar', 'demo': 'true', '_csrf_token': token(client), 'conferido': 'sim',
        'fonte': 'Teste fictício sobre malha real',
        'territorio': (io.BytesIO(geo), 'territorio.geojson'), 'historico': (io.BytesIO(history), 'casos.csv')})
    assert response.status_code == 303 and 'camada=historico' in response.location
    page = client.get(response.location)
    assert page.status_code == 200 and 'Pesqueira' in page.text
    saved = RiskStore(store.engine).history(7, True)
    assert len(saved) == 1
    assert RiskStore(store.engine).get(saved[0]['id'], 7, True)['report'] == json.loads(json.dumps(expected))
    assert not RiskStore(store.engine).history(8, True)
    assert not RiskStore(store.engine).history(7, False)
