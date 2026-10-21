import importlib.util
import math

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from rasterio.warp import transform
from sqlalchemy import create_engine, inspect, text

from app.extensions import db
from app.models import Ortomosaico, OrtomosaicoEstimativaAgua
from app.modules.ortomosaicos.water import calculate
from tests.test_ortomosaicos import ROOT, app, client


BOUNDS = [-46, -24, -45, -23]
POINT = {'type': 'Point', 'coordinates': [-45.5, -23.5]}


def test_water_routes_are_registered_in_central_ti_policy(app):
    from app.modules.gestao_ti.permissions import validate_route_policy
    validate_route_policy(app)


def payload(**changes):
    return dict(nome='Piscina 12', tipo='piscina', metodo='retangular', origem='medida',
                geometria=POINT, comprimento_m=8, largura_m=4, profundidade_m=1.5,
                agua_m=1.2) | changes


def test_capacity_current_water_and_unknown_are_distinct():
    result = calculate(payload(), BOUNDS)['resultado']
    assert result == dict(area_m2=32, capacidade_l=48000, agua_l=38400)
    assert calculate(payload(agua_m=''), BOUNDS)['resultado']['agua_l'] is None
    assert calculate(payload(agua_m=0), BOUNDS)['resultado']['agua_l'] == 0
    cylinder = calculate(payload(metodo='cilindrico', diametro_m=2), BOUNDS)['resultado']
    assert cylinder['capacidade_l'] == pytest.approx(math.pi*1500)
    known = calculate(payload(metodo='capacidade', capacidade_l=1000, ocupacao_pct=30), BOUNDS)['resultado']
    assert known == dict(area_m2=None, capacidade_l=1000, agua_l=300)
    assert calculate(payload(metodo='capacidade', capacidade_l=1000), BOUNDS)['resultado']['agua_l'] is None


def test_map_area_uses_metric_projection_not_web_mercator():
    # A real 8 x 4 metre rectangle at southern Brazil's latitude.
    x, y = transform('EPSG:4326', 'EPSG:32723', [-45.5], [-23.5])
    xs = [x[0], x[0]+8, x[0]+8, x[0], x[0]]
    ys = [y[0], y[0], y[0]+4, y[0]+4, y[0]]
    lon, lat = transform('EPSG:32723', 'EPSG:4326', xs, ys)
    polygon = {'type': 'Polygon', 'coordinates': [[list(p) for p in zip(lon, lat)]]}
    result = calculate(payload(metodo='mapa', geometria=polygon), BOUNDS)['resultado']
    assert result['area_m2'] == pytest.approx(32, abs=.0001)
    assert result['agua_l'] == pytest.approx(38400, abs=.1)


@pytest.mark.parametrize('change', [
    {'agua_m': 2}, {'agua_m': -1}, {'agua_m': float('nan')}, {'profundidade_m': float('inf')},
    {'comprimento_m': True}, {'largura_m': ''}, {'profundidade_m': 0},
    {'metodo': 'capacidade', 'capacidade_l': 1000, 'ocupacao_pct': 101},
    {'metodo': 'capacidade', 'capacidade_l': 1000, 'ocupacao_pct': -1},
    {'geometria': {'type': 'Point', 'coordinates': [0, 0]}},
    {'geometria': {'type': 'Point', 'coordinates': [float('nan'), -23.5]}},
    {'geometria': None}, {'metodo': 'mapa'}, {'metodo': 'dem'},
    {'origem': 'automatico'}, {'nome': ' '}, {'observacoes': 'a'*1001},
    {'metodo': 'mapa', 'geometria': {'type': 'Polygon', 'coordinates': [
        [[-45.5,-23.5],[-45.49,-23.49],[-45.49,-23.5],[-45.5,-23.49],[-45.5,-23.5]]]}},
])
def test_invalid_estimates_rejected(change):
    with pytest.raises(ValueError):
        calculate(payload(**change), BOUNDS)


@pytest.fixture
def survey(app):
    with app.app_context():
        row = Ortomosaico(prefeitura_id=1, usuario_id=1, nome='Levantamento', arquivo_nome='test.tif',
            original_path='private', sha256='test', tamanho_bytes=1, status='pronto', metadados={'limites': BOUNDS})
        db.session.add(row)
        db.session.commit()
        return row.id


def test_save_reload_edit_delete_and_authoritative_calculation(app, survey):
    c = client(app)
    url = f'/api/ortomosaicos/{survey}/agua'
    headers = {'X-CSRFToken': 'token'}
    body = payload(resultado={'capacidade_l': 1}, area_m2=999)
    preview = c.post(url+'/calcular', json=body, headers=headers)
    assert preview.status_code == 200
    with app.app_context():
        assert OrtomosaicoEstimativaAgua.query.count() == 0
    saved = c.post(url, json=body, headers=headers)
    assert saved.status_code == 201
    item = saved.json['item']
    assert item['resultado']['capacidade_l'] == 48000
    listing = client(app, 2).get(url)
    assert listing.json['items'] == [item]
    assert listing.headers['Cache-Control'] == 'private, no-store'
    target = f"{url}/{item['id']}"
    updated = c.put(target, json=payload(agua_m=0), headers=headers)
    assert updated.status_code == 200
    assert updated.json['item']['resultado']['agua_l'] == 0
    assert c.put(target, json=payload(agua_m=2), headers=headers).status_code == 400
    assert c.get(url).json['items'][0]['resultado']['agua_l'] == 0
    assert c.delete(target, headers=headers).status_code == 204
    assert c.get(url).json['items'] == []


def test_access_csrf_and_record_isolation(app, survey, monkeypatch):
    url = f'/api/ortomosaicos/{survey}/agua'
    c = client(app)
    headers = {'X-CSRFToken': 'token'}
    assert c.post(url, json=payload()).status_code == 403
    saved = c.post(url, json=payload(), headers=headers).json['item']
    target = f"{url}/{saved['id']}"
    assert app.test_client().get(url).status_code == 401
    assert c.put(target, json=payload()).status_code == 403
    assert c.delete(target).status_code == 403
    for uid in range(3, 10):
        other = client(app, uid)
        assert other.get(url).status_code == 403
        assert other.post(url, json=payload(), headers=headers).status_code == 403
        assert other.post(url+'/calcular', json=payload(), headers=headers).status_code == 403
        assert other.put(target, json=payload(), headers=headers).status_code == 403
        assert other.delete(target, headers=headers).status_code == 403
    with app.app_context():
        # A second survey in the same city may not modify the first survey's records.
        row = Ortomosaico(prefeitura_id=1, usuario_id=1, nome='Segundo', arquivo_nome='test.tif',
            original_path='private', sha256='test', tamanho_bytes=1, status='pronto', metadados={'limites': BOUNDS})
        db.session.add(row);db.session.commit();second=row.id
    wrong = f"/api/ortomosaicos/{second}/agua/{saved['id']}"
    assert c.put(wrong, json=payload(), headers=headers).status_code == 404
    assert c.delete(wrong, headers=headers).status_code == 404
    assert len(c.get(url).json['items']) == 1
    # DEV/DIRETOR are global roles today; verify the shared city-access guard is
    # still consulted by every new route, without inventing a different policy.
    monkeypatch.setattr('app.modules.ortomosaicos.routes.can_access_prefeitura', lambda *_: False)
    assert c.get(url).status_code == 404
    assert c.post(url, json=payload(), headers=headers).status_code == 404
    assert c.post(url+'/calcular', json=payload(), headers=headers).status_code == 404
    assert c.put(target, json=payload(), headers=headers).status_code == 404
    assert c.delete(target, headers=headers).status_code == 404


def test_not_ready_and_bad_request(app, survey):
    c = client(app);url=f'/api/ortomosaicos/{survey}/agua'
    assert c.post(url, json=[], headers={'X-CSRFToken':'token'}).status_code == 400
    assert c.post(url, json=payload(observacoes='a'*70000), headers={'X-CSRFToken':'token'}).status_code == 400
    with app.app_context():
        db.session.get(Ortomosaico, survey).status='processando';db.session.commit()
    assert c.get(url).status_code == 409
    assert c.post(url, json=payload(), headers={'X-CSRFToken':'token'}).status_code == 409


def test_migration_preserves_existing_surveys(tmp_path):
    spec=importlib.util.spec_from_file_location('water_migration', ROOT/'migrations/versions/b84f20d19a6e_estimativas_agua.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite:///'+str(tmp_path/'migration.sqlite'))
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE ortomosaicos (id INTEGER PRIMARY KEY, nome TEXT)'))
        connection.execute(text("INSERT INTO ortomosaicos VALUES (1, 'Existente')"))
        connection.execute(text('CREATE TABLE usuarios (id INTEGER PRIMARY KEY)'))
        module.op=Operations(MigrationContext.configure(connection))
        module.upgrade()
        assert 'ortomosaico_estimativas_agua' in inspect(connection).get_table_names()
        module.downgrade()
        assert connection.execute(text('SELECT nome FROM ortomosaicos')).scalar() == 'Existente'
        assert 'ortomosaico_estimativas_agua' not in inspect(connection).get_table_names()
