"""Spatial filters, larva classification and bounded public geometry reads."""
import json
from copy import deepcopy
from unittest.mock import patch

import pytest
import requests
from app.extensions import db
from app.modules.mapas import operacional, quadras
from app.modules.mapas.territorial import validate_filters, locate
from tests.test_mapas_filters import HeatmapFilterTests


def feature(identifier=123):
    return {'type':'Feature','properties':{'cd_identificador_original_quadra_fiscal':identifier,
        'cd_setor_fiscal':'001','cd_quadra_fiscal':'002','cd_subquadra_fiscal':'001','tx_tipo_quadra':'FISCAL',
        'dt_carga':'2026-11-18','private_extra':'must not leave the proxy'},
        'geometry':{'type':'Polygon','coordinates':[[[-46.635,-23.552],[-46.632,-23.552],[-46.632,-23.549],[-46.635,-23.549],[-46.635,-23.552]]]}}


class Response:
    def __init__(self,features):self.data=json.dumps({'type':'FeatureCollection','features':features}).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def raise_for_status(self):pass
    def iter_content(self,*args):yield self.data


@pytest.fixture(autouse=True)
def clear_cache():
    quadras._cache.clear()
    yield
    quadras._cache.clear()


@pytest.fixture
def setup():
    c=HeatmapFilterTests();c.setUp()
    yield c
    c.tearDown()


def test_region_aliases_and_real_uvis_relationship():
    assert validate_filters('Coordenadoria Regional de Saúde Norte','0314307')==('NORTE','0314307')
    assert locate(-23.5504,-46.6339)[0]['uvis']=='SE'
    with pytest.raises(ValueError):validate_filters('SUL','0314307')
    with pytest.raises(ValueError):validate_filters('inventado','')


def test_spatial_filter_cannot_restore_foreign_tenant_or_region_records(setup):
    c=setup
    own=c._new_request(latitude='-23.5504',longitude='-46.6339',drone='SIM',equipe_uvis='NAO')
    c._new_request(user=c.uvis_other_city,latitude='-23.5504',longitude='-46.6339',drone='SIM')
    c._new_request(user=c.uvis_other_region,latitude='-23.5504',longitude='-46.6339',drone='SIM')
    c._new_request(latitude=None)
    c._new_request(latitude='-23.503',longitude='-46.625',drone='NAO')
    db.session.commit()
    rows=operacional.points(c.uvis,visao='todos',crs='NORTE',cnes='0314307')['registros']
    assert [r['id'] for r in rows]==[own.id]
    assert rows[0]['larva_visualizada']=='SIM'
    assert operacional.points(c.uvis,visao='todos',crs='SUL')['registros']==[]


def test_classification_matches_existing_any_positive_filter_and_unknown_is_not_negative(setup):
    c=setup
    positive=c._new_request(drone=' não ',equipe_uvis=' SIM ')
    negative=c._new_request(drone='Não')
    unknown=c._new_request(drone=None)
    no_os=c._new_request()
    db.session.commit()
    result={r['id']:r['larva_visualizada'] for r in operacional.points(c.admin,visao='todos')['registros']}
    assert result=={positive.id:'SIM',negative.id:'NAO',unknown.id:'NAO_INFORMADO',no_os.id:'NAO_INFORMADO'}


def test_quadra_geometry_filters_scoped_rows_and_never_guesses_missing_coordinates(setup):
    c=setup;own=c._new_request(latitude='-23.5504',longitude='-46.6339')
    c._new_request(latitude='-23.503',longitude='-46.625');c._new_request(latitude=None)
    c._new_request(user=c.uvis_other_city,latitude='-23.5504',longitude='-46.6339');db.session.commit()
    with patch.object(quadras,'get_quadra',return_value=feature()):
        assert [r['id'] for r in operacional.points(c.uvis,visao='todos',quadra='123')['registros']]==[own.id]


@pytest.mark.parametrize('value',['NaN,-23,-46,-22','0,0,1,1','-46.9,-24.1,-46.3,-23.25','-46.63,-23.55,-46.64,-23.54','a,b,c,d'])
def test_bbox_rejects_invalid_or_expensive_queries_without_network(value):
    with patch.object(quadras.requests,'get') as get:
        with pytest.raises(ValueError):quadras.list_quadras(value)
        get.assert_not_called()


def test_fixed_upstream_response_is_sanitized_and_cached_without_mutable_shared_objects():
    with patch.object(quadras.requests,'get',return_value=Response([feature()])) as get:
        result=quadras.list_quadras('-46.635,-23.552,-46.632,-23.549')
        assert result['features'][0]['id']=='123'
        assert set(result['features'][0]['properties'])=={'id','setor','quadra','subquadra','tipo','atualizado_em'}
        result['features'].clear()
        assert len(quadras.list_quadras('-46.635,-23.552,-46.632,-23.549')['features'])==1
        assert get.call_count==1
        assert get.call_args.args[0]==quadras.URL
        assert get.call_args.kwargs.get('verify',True) is True
        assert get.call_args.kwargs['params']['count']==501


def test_single_quadra_uses_only_numeric_original_id():
    with patch.object(quadras.requests,'get',return_value=Response([feature()])) as get:
        assert quadras.get_quadra('123')['id']=='123'
        assert get.call_args.kwargs['params']['CQL_FILTER']=='cd_identificador_original_quadra_fiscal=123'
    for value in ['123 OR 1=1','http://evil','-1','']:
        with pytest.raises(ValueError):quadras.get_quadra(value)


def test_overflow_and_outage_are_explicit_not_partial_success():
    with patch.object(quadras.requests,'get',return_value=Response([feature(i) for i in range(501)])):
        with pytest.raises(ValueError,match='nenhuma lista parcial'):quadras.list_quadras('-46.635,-23.552,-46.632,-23.549')
    with patch.object(quadras.requests,'get',side_effect=requests.Timeout):
        with pytest.raises(quadras.QuadraUnavailable):quadras.list_quadras('-46.635,-23.552,-46.632,-23.549')


def test_routes_reject_duplicate_filters_and_surface_source_failure(setup):
    client=setup.app.test_client()
    assert client.get('/api/mapa-operacional?crs=NORTE&crs=SUL').status_code==400
    assert client.get('/api/mapa-operacional?crs=SUL&cnes=0314307').status_code==400
    with patch.object(quadras,'list_quadras',side_effect=quadras.QuadraUnavailable('indisponível')):
        response=client.get('/api/mapas/quadras?bbox=-46.635,-23.552,-46.632,-23.549')
        assert response.status_code==503 and response.headers['Cache-Control']=='private, no-store'
    assert client.get('/api/mapas/quadras?bbox=1&bbox=2').status_code==400
