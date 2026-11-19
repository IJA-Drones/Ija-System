"""Public reference integrity and isolated Geolocation map; no configured DB."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Blueprint, Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader
from shapely.geometry import Point, shape
from app.modules.mapas.routes import register_routes
from app.modules.mapas.service import get_consulta_geolocalizacao_key

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'app/static/data/uvis-sao-paulo'


def test_reference_has_96_districts_and_28_uvis_and_only_public_attributes():
    data=json.loads((DATA/'distritos-referencia.geojson').read_text())
    assert len(data['features'])==96
    assert len({f['properties']['codigo_distrito'] for f in data['features']})==96
    assert len({f['properties']['cnes'] for f in data['features']})==28
    assert data['metadata']['atualizado_em']=='2026-07-27'
    for f in data['features']:
        assert set(f['properties'])=={'distrito','codigo_distrito','uvis','cnes','crs'}
        assert shape(f['geometry']).is_valid
    for name,count in [('uvis',28),('distritos',96)]:
        display=json.loads((DATA/f'{name}.geojson').read_text())
        assert len(display['features'])==count
        assert all(shape(f['geometry']).is_valid for f in display['features'])
        assert (DATA/f'{name}.geojson').stat().st_size<500_000


@pytest.mark.parametrize('lat,lng,uvis',[(-23.5504,-46.6339,'SE'),(-23.503,-46.625,'SANTANA/TUCURUVI'),(-23.454,-46.582,'JACANA/TREMEMBE')])
def test_known_locations_in_the_preserved_source(lat,lng,uvis):
    data=json.loads((DATA/'distritos-referencia.geojson').read_text())
    matches=[f['properties']['uvis'] for f in data['features'] if shape(f['geometry']).covers(Point(lng,lat))]
    assert matches==[uvis]


def test_se_preserves_cnes_leading_zero_and_its_five_districts():
    data=json.loads((DATA/'uvis.geojson').read_text())
    se=next(f for f in data['features'] if f['properties']['cnes']=='0314307')
    assert set(se['properties']['distritos'])=={'SE','REPUBLICA','BELA VISTA','CAMBUCI','LIBERDADE'}


def test_uvis_have_distinct_stable_colors_and_labels_inside_their_display_geometry():
    features=json.loads((DATA/'uvis.geojson').read_text())['features']
    assert len({f['properties']['cor'] for f in features})==28
    for feature in features:
        assert shape(feature['geometry']).covers(Point(*feature['properties']['rotulo']))


@pytest.mark.parametrize('crs',['LESTE','NORTE','OESTE','SUDESTE','SUL'])
def test_coordinator_mask_keeps_its_uvis_open_and_whitens_other_regions(crs):
    mask=json.loads((DATA/f'mascara-{crs.lower()}.geojson').read_text())
    assert mask['features'][0]['properties']['crs']==crs
    geometry=shape(mask['features'][0]['geometry'])
    assert geometry.is_valid
    features=json.loads((DATA/'uvis.geojson').read_text())['features']
    for feature in features:
        assert geometry.covers(Point(*feature['properties']['rotulo']))==(feature['properties']['crs']!=crs)


def test_each_uvis_mask_keeps_only_its_own_territory_open():
    features=json.loads((DATA/'uvis.geojson').read_text())['features']
    for selected in features:
        code=selected['properties']['cnes']
        mask=json.loads((DATA/f'mascara-uvis-{code}.geojson').read_text())
        assert mask['features'][0]['properties']['cnes']==code
        geometry=shape(mask['features'][0]['geometry'])
        assert geometry.is_valid
        assert geometry.intersection(shape(selected['geometry'])).area<1e-12
        for feature in features:
            assert geometry.covers(Point(*feature['properties']['rotulo']))==(feature['properties']['cnes']!=code)


def test_display_geometry_stays_within_declared_simplification_tolerance():
    original=json.loads((DATA/'distritos-referencia.geojson').read_text())
    display=json.loads((DATA/'distritos.geojson').read_text())
    by_code={f['properties']['codigo_distrito']:shape(f['geometry']) for f in original['features']}
    for f in display['features']:
        assert shape(f['geometry']).hausdorff_distance(by_code[f['properties']['codigo_distrito']])<=0.00003001


def test_satellite_mask_leaves_sao_paulo_open_and_covers_neighboring_municipalities():
    city=json.loads((DATA/'municipio.geojson').read_text())
    mask=json.loads((DATA/'mascara.geojson').read_text())
    municipal=shape(city['features'][0]['geometry'])
    surroundings=shape(mask['features'][0]['geometry'])
    assert municipal.is_valid and surroundings.is_valid
    assert municipal.intersection(surroundings).area < 1e-12
    assert municipal.covers(Point(-46.6339,-23.5504))
    assert not surroundings.covers(Point(-46.6339,-23.5504))
    assert surroundings.covers(Point(-46.7916,-23.5325)) # Osasco
    assert mask['metadata']['limite_bbox']==city['metadata']['limite_bbox']


def test_geolocation_key_uses_same_configured_frontend_key_as_other_maps():
    app=Flask(__name__)
    with app.app_context(),patch.dict('os.environ',{'KEY_API_GOOGLE_MAPS':'env-test-key'}):
        app.config['Maps_KEY_FRONT']='config-test-key'
        assert get_consulta_geolocalizacao_key()=='config-test-key'
        app.config['Maps_KEY_FRONT']=''
        assert get_consulta_geolocalizacao_key()=='env-test-key'


def test_map_reuses_existing_authenticated_route_and_never_initializes_a_database():
    app=Flask(__name__,template_folder=str(ROOT/'app/templates'),static_folder=str(ROOT/'app/static'))
    app.config.update(SECRET_KEY='isolated-uvis-test',TESTING=True,Maps_KEY_FRONT='synthetic-test-key')
    manager=LoginManager(app);manager.login_view='test_login'
    manager.user_loader(lambda uid:SimpleNamespace(is_authenticated=True,id=uid))
    app.add_url_rule('/login',endpoint='test_login',view_func=lambda:'login')
    bp=Blueprint('main',__name__);register_routes(bp);app.register_blueprint(bp)
    for endpoint,rule in [('api_cep','/cep/<cep>'),('api_cep_by_address','/cep-endereco')]:
        app.add_url_rule(rule,endpoint='main.'+endpoint,view_func=lambda **kw:'')
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block extra_styles %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}'}),app.jinja_loader])
    client=app.test_client()
    assert client.get('/consultar_endereco_geolocalizacao').status_code==302
    with client.session_transaction() as s:s['_user_id']='1';s['_fresh']=True
    html=client.get('/consultar_endereco_geolocalizacao').text
    assert 'data-uvis-map' in html and 'São Paulo · limites das UVIS' in html
    assert html.count('role="tab"')==2
    assert 'Buscar endereço' in html and 'Consultar áreas das UVIS' in html
    assert html.count('id="map"')==1 and html.count('id="uvisTerritoryMap"')==1
    assert html.count('data-satellite-context')==1
    assert 'filter-card' in html and 'data-uvis-labels' in html and 'data-map-pois' in html
    assert 'data-bs-toggle="pill"' not in html and 'Teste ·' not in html
    assert 'vigilancia' not in html.lower()
    assert 'maps.googleapis.com' not in html # shared base is the only Google API loader
    assert 'sqlalchemy' not in app.extensions
