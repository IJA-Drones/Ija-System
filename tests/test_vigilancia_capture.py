"""Registro HTTP, reconciliação entre lotes e fórmulas do manual LIRAa (2013)."""

import csv
import io
from unittest.mock import patch

import pytest
from werkzeug.datastructures import MultiDict

from test_vigilancia_field_routes import client, login, token, store, confirm
from app.modules.vigilancia.domain import CSV_COLUMNS, DEPOSIT_COLUMNS
from app.modules.vigilancia.field_capture import FieldInputError, capture_csv, consolidate, parse_filters
from app.modules.vigilancia.service import preview_csv


def record(**changes):
    return dict(origem='LIRAA', levantamento_codigo='L-2026-01', estrato_codigo='01',
                imovel_codigo='IM-001', inspecao_codigo='VIS-001', data_inspecao='2026-10-19',
                area_codigo='A-01', bairro='Bairro Sintético', situacao='INSPECIONADO',
                positivo_aedes='SIM', latitude='', longitude='', **{}) | changes


def deposits(**changes):
    return {name: '0' for name in DEPOSIT_COLUMNS} | changes


def save(client, values=None, **changes):
    response = client.post('/vigilancia/campo', data={**record(), **(values or {}),
                           'demo': 'true', '_csrf_token': token(client), **changes})
    if response.status_code == 303:
        batch = store(client).history(7)[0]
        assert confirm(client, batch['id']).status_code == 303
    return response


def test_visit_requires_review_then_survives_reopen_and_repeated_submit(client):
    login(client)
    page = client.get('/vigilancia/campo')
    assert page.status_code == 200 and 'Registrar visita' in page.text
    response = client.post('/vigilancia/campo', data={**record(), **deposits(depositos_d1='3'),
                           'demo': 'true', '_csrf_token': token(client)})
    assert response.status_code == 303
    assert store(client).records(7, demo=True) == []
    batch = store(client).history(7)[0]
    assert confirm(client, batch['id']).status_code == 303
    saved = store(client).records(7, demo=True)
    assert len(saved) == 1 and saved[0]['depositos_d1'] == 3
    page = client.get('/vigilancia/campo')
    assert '100,00%' in page.text and '300,00' in page.text
    assert save(client, deposits(depositos_d1='3')).status_code == 303
    assert len(store(client).records(7, demo=True)) == 1


def test_official_formulas_use_properties_for_iip_and_containers_for_breteau():
    rows = [record(**deposits(depositos_d1='2', depositos_a2='1')),
            record(imovel_codigo='IM-002', inspecao_codigo='VIS-002', positivo_aedes='NAO', **deposits()),
            record(imovel_codigo='IM-003', inspecao_codigo='VIS-003', situacao='FECHADO', positivo_aedes='')]
    data = []
    for row in rows:
        result = preview_csv(capture_csv(row, prefeitura=7), prefeitura_id=7)
        data.extend(result['registros'])
    result = consolidate(data, prefeitura=7, filters=parse_filters({}))
    indicator = result['indicadores'][0]
    assert (indicator['imoveis_inspecionados'], indicator['imoveis_positivos'], indicator['imoveis_pendentes']) == (2, 1, 1)
    assert indicator['iip'] == 50 and indicator['ib'] == 150
    counts = {row['codigo']: row for row in indicator['recipientes']}
    assert counts['D1']['itr'] == 66.67 and counts['A2']['itr'] == 33.33


def test_missing_counts_are_unknown_and_zero_has_a_different_meaning():
    report = preview_csv(capture_csv(record(), prefeitura=7), prefeitura_id=7)
    assert report['indicadores'][0]['iip'] == 100
    assert report['indicadores'][0]['ib'] is None
    report = preview_csv(capture_csv(record(positivo_aedes='NAO', **deposits()), prefeitura=7), prefeitura_id=7)
    assert report['indicadores'][0]['ib'] == 0
    assert all(item['itr'] is None for item in report['indicadores'][0]['recipientes'])


def test_multiple_visits_to_same_property_do_not_inflate_container_counts():
    data = []
    for code in ['VIS-001', 'VIS-002']:
        data.extend(preview_csv(capture_csv(record(inspecao_codigo=code, **deposits(depositos_b='2')), prefeitura=7), prefeitura_id=7)['registros'])
    item = consolidate(data, prefeitura=7, filters=parse_filters({}))['indicadores'][0]
    assert item['iip'] == 100 and item['imoveis_inspecionados'] == 1
    assert item['ib'] is None and 'mais de uma inspeção' in item['motivo_depositos']


@pytest.mark.parametrize('change', [
    {'depositos_b': '1'},
    deposits(depositos_b='-1'), deposits(depositos_b='1.5'), deposits(depositos_b='10001'),
    {'positivo_aedes': 'NAO', **deposits(depositos_b='1')},
    {'situacao': 'FECHADO', 'positivo_aedes': '', **deposits()},
    {'positivo_aedes': '', **deposits(depositos_b='1')},
])
def test_incomplete_invalid_or_conflicting_container_results_are_rejected(change):
    with pytest.raises(FieldInputError):
        capture_csv(record(**change), prefeitura=7)


def test_focal_visits_do_not_create_liraa_indices(client):
    login(client)
    client.get('/vigilancia/campo')
    assert save(client, record(origem='FOCAL', levantamento_codigo='', estrato_codigo='')).status_code == 303
    data = store(client).records(7, demo=True)
    report = consolidate(data, prefeitura=7, filters=parse_filters({}))
    assert report['resumo']['inspecoes'] == 1 and report['indicadores'] == []


def test_consolidation_uses_published_identities_not_number_of_batches(client):
    login(client)
    client.get('/vigilancia/campo')
    assert save(client, deposits(depositos_b='1')).status_code == 303
    assert save(client, record(imovel_codigo='IM-002', inspecao_codigo='VIS-002', positivo_aedes='NAO', **deposits())).status_code == 303
    login(client, 'other')
    client.get('/vigilancia/campo')
    assert save(client, deposits(depositos_b='1')).status_code == 303
    assert len(store(client).history(7)) == 3
    report = consolidate(store(client).records(7, demo=True), prefeitura=7, filters=parse_filters({}))
    assert report['resumo']['inspecoes'] == 2
    assert report['indicadores'][0]['iip'] == 50 and report['indicadores'][0]['ib'] == 50


def test_filters_export_and_demo_mode_keep_scope(client):
    login(client)
    client.get('/vigilancia/campo')
    assert save(client, deposits(depositos_b='1')).status_code == 303
    response = client.get('/vigilancia/campo/exportar.csv?demo=true&levantamento=L-2026-01')
    assert response.status_code == 200
    exported = list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig')), delimiter=';'))
    assert len(exported) == 1 and exported[0]['depositos_b'] == '1'
    for query in ['demo=false', 'inicio=2026-10-20', 'levantamento=OUTRO', 'origem=FOCAL', 'estrato=02']:
        response = client.get('/vigilancia/campo/exportar.csv?' + query)
        assert response.status_code == 200
        assert len(list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig')), delimiter=';'))) == 0
    login(client, 'b')
    assert client.get('/vigilancia/campo?prefeitura_id=7').status_code == 403
    assert client.get('/vigilancia/campo/exportar.csv?prefeitura_id=7').status_code == 403
    assert client.get('/vigilancia/campo/exportar.csv').status_code == 200
    assert store(client).records(8, demo=True) == []


def test_request_errors_do_not_publish_visits(client):
    login(client)
    client.get('/vigilancia/campo')
    assert client.post('/vigilancia/campo', data={**record(), 'demo':'true'}).status_code == 403
    assert save(client, demo='false').status_code == 400
    assert save(client, demo='bad').status_code == 400
    assert save(client, positivo_aedes='').status_code == 400
    assert client.get('/vigilancia/campo?inicio=2026-10-20&fim=2026-10-19').status_code == 400
    assert client.get('/vigilancia/campo?demo=true&demo=false').status_code == 400
    assert client.get('/vigilancia/campo?pagina=9999999999999999999999999').status_code == 400
    assert store(client).records(7, demo=True) == []


def test_disabled_access_and_bounded_post(client):
    client.application.config['VIGILANCIA_IMPORT_ENABLED'] = False
    assert client.get('/vigilancia/campo').status_code == 404
    client.application.config['VIGILANCIA_IMPORT_ENABLED'] = True
    login(client, 'uvis')
    assert client.get('/vigilancia/campo').status_code == 403
    login(client)
    assert client.post('/vigilancia/campo', data=b'x' * (1024*1024+65537)).status_code == 413


def test_repeated_form_fields_and_spreadsheet_formulas_are_handled(client):
    with pytest.raises(FieldInputError):
        capture_csv(MultiDict([*record().items(), ('origem','FOCAL')]), prefeitura=7)
    login(client)
    client.get('/vigilancia/campo')
    assert save(client, record(imovel_codigo='=1+2')).status_code == 303
    response = client.get('/vigilancia/campo/exportar.csv')
    row = next(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig')), delimiter=';'))
    assert row['imovel_codigo'] == "'=1+2"


def test_consult_only_profile_cannot_write_or_export(client):
    login(client)
    choices = frozenset({'area:prefeitura', 'prefeitura.vigilancia.consultar'})
    with patch('app.modules.gestao_ti.permissions.active_configuration', return_value=choices):
        page = client.get('/vigilancia/campo')
        assert page.status_code == 200
        assert 'id="campo-form"' not in page.text
        assert 'Exportar CSV do recorte' not in page.text
        response = client.post('/vigilancia/campo', data={**record(), 'demo':'true', '_csrf_token':token(client)})
        assert response.status_code == 403
        assert client.get('/vigilancia/campo/exportar.csv').status_code == 403
    assert store(client).records(7, demo=True) == []


def test_changed_container_results_cannot_overwrite_a_confirmed_visit(client):
    login(client)
    client.get('/vigilancia/campo')
    assert save(client, deposits(depositos_b='1')).status_code == 303
    response = client.post('/vigilancia/campo', data={**record(), **deposits(depositos_b='2'),
                           'demo':'true', '_csrf_token':token(client)})
    assert response.status_code == 303
    batch = store(client).history(7)[0]
    assert confirm(client, batch['id']).status_code == 409
    assert store(client).records(7, demo=True)[0]['depositos_b'] == 1


def test_container_csv_extension_requires_all_headers():
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=(*CSV_COLUMNS, 'depositos_b'), delimiter=';')
    writer.writeheader()
    writer.writerow({**record(), 'municipio_id':'7', 'depositos_b':'2'})
    from app.modules.vigilancia.service import PreviewValidationError
    with pytest.raises(PreviewValidationError):
        preview_csv(stream.getvalue().encode(), prefeitura_id=7)
