"""Limites da seleção no mapa, isolamento e preservação do planejamento."""

import importlib.util
import io
import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.modules.vigilancia.geometry import validate_polygon
from app.modules.vigilancia.field_store import FieldConflict
from app.modules.vigilancia.planning import RG_COLUMNS
from tests.test_vigilancia_planning import planned, create, change
from tests.test_vigilancia_field_routes import client, login, token


def polygon(points=None):
    ring = points or [[-36.7000,-8.3500],[-36.6990,-8.3500],[-36.6990,-8.3490],[-36.7000,-8.3490],[-36.7000,-8.3500]]
    return {'type':'Polygon','coordinates':[ring]}


def values(**changes):
    return dict(quarteirao='Q-01', bairro='Bairro Sintético', area='A-01', imoveis='100', referencia='RG municipal',
        geometria_acao='substituir', geometria_confirmada='sim', geometria=json.dumps(polygon()), **{}) | changes


@pytest.mark.parametrize('raw', [
    '', 'null', '{}', '[]', 'NaN', '{invalid', json.dumps({'type':'Point','coordinates':[-36,-8]}),
    json.dumps(polygon([[-36,-8],[-35,-8],[-35,-7]])),
    json.dumps(polygon([[-36,-8],[-35,-7],[-36,-7],[-35,-8],[-36,-8]])),
    json.dumps(polygon([[-36,-8],[-35,-8],[-36,-8],[-36,-8]])),
    json.dumps(polygon([[-36,-8],[-35,-8],[-34,-8],[-36,-8]])),
    json.dumps(polygon([[-36,-8],[181,-8],[-35,-7],[-36,-8]])),
    json.dumps(polygon([[-36,-8],[-35,float('nan')],[-35,-7],[-36,-8]])),
    json.dumps(polygon([[-36,-8],[True,-8],[-35,-7],[-36,-8]])),
    json.dumps({'type':'Polygon','coordinates':[polygon()['coordinates'][0],polygon()['coordinates'][0]]}),
    'x' * 32769,
])
def test_invalid_contours_are_rejected(raw):
    with pytest.raises(FieldConflict):
        validate_polygon(raw)


def test_polygon_is_canonical_lon_lat_and_preserves_winding():
    result = validate_polygon(json.dumps(polygon()))
    assert result == polygon()
    assert validate_polygon(json.dumps(polygon(list(reversed(polygon()['coordinates'][0])))))['type'] == 'Polygon'


def test_rg_requires_confirmation_detects_stale_edit_and_snapshot_is_preserved(planned):
    client, store = planned
    with pytest.raises(FieldConflict, match='confirme'):
        store.mutate(7, True, 'a', 'territorio', values(geometria_confirmada=''))
    assert store.overview(7, True)['territorio'] == []
    store.mutate(7, True, 'a', 'territorio', values())
    saved = store.overview(7, True)['territorio'][0]
    assert saved['geometria'] == polygon()
    create(store)  # atualização textual não apaga a geometria
    assert store.overview(7, True)['territorio'][0]['geometria'] == polygon()
    change(store, 'liberar', amostra_validada='sim')
    snapshot = store.overview(7, True, 'L-2026-01')['quarteiroes'][0]['territorio']['geometria']
    with pytest.raises(FieldConflict, match='atualizado'):
        store.mutate(7, True, 'a', 'territorio', values(territorio_versao=str(saved['atualizado_em'])))
    current = store.overview(7, True)['territorio'][0]
    store.mutate(7, True, 'a', 'territorio', values(geometria_acao='remover', territorio_versao=str(current['atualizado_em'])))
    assert store.overview(7, True)['territorio'][0]['geometria'] is None
    assert store.overview(7, True, 'L-2026-01')['quarteiroes'][0]['territorio']['geometria'] == snapshot


def test_geometry_http_scope_demo_and_safe_json(planned):
    client, store = planned
    login(client, '703')
    page = client.get('/vigilancia/planejamento')
    assert 'Delimitar no mapa' in page.text and 'Concluir desenho' in page.text
    payload = values() | dict(acao='territorio', demo='true', _csrf_token=token(client))
    response = client.post('/vigilancia/planejamento', data=payload)
    assert response.status_code == 303 and 'territorio=Q-01' in response.location
    assert 'coordinates' in client.get(response.location).text
    assert store.overview(7, False)['territorio'] == []
    login(client, '704')
    page = client.get('/vigilancia/planejamento')
    assert 'coordinates' not in page.text
    assert client.get('/vigilancia/planejamento?prefeitura_id=7').status_code == 403
    login(client, '703')
    row = store.overview(7, True)['territorio'][0]
    response = client.post('/vigilancia/planejamento', data=payload | {'bairro':'</script><script>alert(1)</script>',
        'geometria_acao':'manter'})
    assert response.status_code == 303
    page = client.get(response.location)
    assert '</script><script>alert(1)</script>' not in page.text
    assert '\\u003c/script\\u003e' in page.text


def test_invalid_geometry_is_atomic_and_csv_updates_preserve_contour(planned):
    client, store = planned
    store.mutate(7, True, 'a', 'territorio', values())
    previous = store.overview(7, True)['territorio'][0]
    with pytest.raises(FieldConflict):
        store.mutate(7, True, 'a', 'territorio', values(bairro='Não gravar', geometria='{}', territorio_versao=str(previous['atualizado_em'])))
    assert store.overview(7, True)['territorio'][0] == previous
    csv = (';'.join(RG_COLUMNS) + '\nQ-01;Bairro atualizado;A-01;100;RG\n').encode()
    store.mutate(7, True, 'a', 'importar_territorio', {}, csv)
    assert store.overview(7, True)['territorio'][0]['geometria'] == polygon()


def test_geometry_migration_is_only_nullable_column_and_preserves_rows():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('geometry_migration', root/'migrations/versions/e91c7b4a203d_geometria_territorio_liraa.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE vigilancia_campo_quarteiroes (code TEXT PRIMARY KEY)')
        conn.exec_driver_sql("INSERT INTO vigilancia_campo_quarteiroes VALUES ('PRESERVADO')")
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        assert conn.exec_driver_sql('SELECT code, geometria FROM vigilancia_campo_quarteiroes').one() == ('PRESERVADO', None)
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()
        assert conn.exec_driver_sql('SELECT code FROM vigilancia_campo_quarteiroes').scalar_one() == 'PRESERVADO'
    engine.dispose()
    output = io.StringIO()
    with Operations.context(MigrationContext.configure(dialect_name='postgresql', opts={'as_sql':True,'output_buffer':output})):
        module.upgrade()
    assert 'ADD COLUMN geometria JSON' in output.getvalue() and 'CREATE TABLE' not in output.getvalue()
