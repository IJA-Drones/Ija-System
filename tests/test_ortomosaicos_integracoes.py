import io
import json
import zipfile

import shapefile

from app.modules.ortomosaicos import service
from tests.test_dem_contours import upload as upload_dem
from tests.test_ortomosaicos import app, client  # noqa: F401
from tests.test_ortomosaicos_agua import payload, survey  # noqa: F401

POLYGON = {'type': 'Polygon', 'coordinates': [[[-45.5, -23.5], [-45.4999, -23.5], [-45.4999, -23.4999], [-45.5, -23.4999], [-45.5, -23.5]]]}


def read_zip(data):
    archive = zipfile.ZipFile(io.BytesIO(data))
    layers = {}
    for name in archive.namelist():
        if name.endswith('.shp'):
            base = name[:-4]
            assert {f'{base}.shx', f'{base}.dbf', f'{base}.prj', f'{base}.cpg'} <= set(archive.namelist())
            assert 'WGS_1984' in archive.read(f'{base}.prj').decode()
            reader = shapefile.Reader(shp=io.BytesIO(archive.read(name)), shx=io.BytesIO(archive.read(f'{base}.shx')),
                                      dbf=io.BytesIO(archive.read(f'{base}.dbf')), encoding='utf-8')
            layers[base] = reader.shapeRecords()
    return layers


def test_contours_export_geojson_shapefile_and_original(app):
    c = client(app)
    oid = upload_dem(c).json['item']['id']
    with app.app_context():
        assert service.process_one(oid)
    item = c.get(f'/api/ortomosaicos/{oid}').json['item']
    geojson = c.get(item['exportar']['curvas_geojson'])
    assert geojson.status_code == 200 and 'attachment;' in geojson.headers['Content-Disposition']
    features = json.loads(geojson.data)['features']
    layers = read_zip(c.get(item['exportar']['curvas_zip']).data)
    assert list(layers) == [f'curvas-nivel-{oid}']
    shapes = layers[f'curvas-nivel-{oid}']
    assert len(shapes) == len(features)
    assert shapes[0].record['cota'] == features[0]['properties']['cota']
    assert shapes[0].shape.__geo_interface__['type'] == 'LineString'
    original = c.get(item['original_url'])
    assert original.status_code == 200 and original.headers['Content-Disposition'] == 'attachment; filename="dem.tif"'
    assert original.data[:2] in (b'II', b'MM')
    # Water measurements are empty here; RGB-only layers do not have contours.
    assert c.get(item['exportar']['medicoes_geojson']).status_code == 404
    for uid in range(3, 10):
        assert client(app, uid).get(item['exportar']['curvas_zip']).status_code == 403
        assert client(app, uid).get(item['original_url']).status_code == 403


def test_measurements_export_splits_points_and_polygons(app, survey):  # noqa: F811
    c = client(app)
    url = f'/api/ortomosaicos/{survey}/agua'
    headers = {'X-CSRFToken': 'token'}
    assert c.post(url, json=payload(nome='Caixa', tipo='caixa'), headers=headers).status_code == 201
    assert c.post(url, json=payload(nome='Piscina ç', metodo='mapa', geometria=POLYGON), headers=headers).status_code == 201
    assert c.get(f'/ortomosaicos/{survey}/exportar/curvas.zip').status_code == 404
    collection = json.loads(c.get(f'/ortomosaicos/{survey}/exportar/medicoes.geojson').data)
    assert [f['geometry']['type'] for f in collection['features']] == ['Point', 'Polygon']
    assert collection['features'][0]['properties']['capac_l'] == 48000
    layers = read_zip(c.get(f'/ortomosaicos/{survey}/exportar/medicoes.zip').data)
    assert set(layers) == {f'medicoes-{survey}-pontos', f'medicoes-{survey}-areas'}
    area = layers[f'medicoes-{survey}-areas'][0]
    assert area.record['nome'] == 'Piscina ç' and area.record['area_m2'] > 100
    assert area.shape.__geo_interface__['type'] == 'Polygon'


def test_request_form_prefilled_from_map_point(app, monkeypatch):
    from app.extensions import db
    from app.models import Usuario
    from app.modules.solicitacoes import service as requests_service
    monkeypatch.setattr(requests_service, 'reverse_geocode_lat_lng_google_details',
                        lambda lat, lng: {'logradouro': 'Rua A', 'numero': '10', 'cidade': 'Pesqueira', 'uf': 'PE', 'lat': 0})
    with app.test_request_context():
        user = db.session.get(Usuario, 1)
        values = requests_service.build_novo_cadastro_context_from_coordinates(
            user, '', {'latitude': '-8.357', 'longitude': '-36.697', 'observacao': 'Medição'})['form_values']
        assert (values['latitude'], values['longitude'], values['logradouro'], values['observacao']) == \
            ('-8.3570000', '-36.6970000', 'Rua A', 'Medição')
        for bad in ({'latitude': 'nan', 'longitude': '0'}, {'latitude': '91', 'longitude': '0'}, {'latitude': 'x'}):
            assert requests_service.build_novo_cadastro_context_from_coordinates(user, '', bad)['form_values'] == {}
