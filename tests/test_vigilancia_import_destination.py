"""Escolha explícita do destino, original íntegro e vínculos validados em SQLite descartável."""
import hashlib
import io
from datetime import date

import pytest
import sqlalchemy as sa

from app.modules.vigilancia.field_store import FieldConflict
from app.modules.vigilancia.planning_models import CampoPlano, CampoPlanoVisita
from app.modules.vigilancia.service import PreviewValidationError
from app.modules.vigilancia.results import ResultsStore, filters_from
from test_vigilancia_planning import planned, client, change
from test_vigilancia_planned_csv import make_plan, visits, csv_bytes
from test_vigilancia_field_routes import login, token, confirm
from app.modules.vigilancia.domain import CSV_COLUMNS


@pytest.fixture
def destination(planned):
    c, store = planned
    make_plan(store)
    login(c)
    c.get('/vigilancia/importacoes?demo=true')
    return c, store


def upload(c, content, **values):
    return c.post('/vigilancia/importacoes', data=dict(acao='preparar', demo='true',
        fonte='Arquivo de demonstração', levantamento_destino='L-2026-01', _csrf_token=token(c),
        arquivo=(io.BytesIO(content), 'visitas.csv'), **values))


@pytest.mark.parametrize('source_code', ['CODIGO-ORIGINAL', ''])
def test_select_destination_preserves_original_and_confirms_into_chosen_plan(destination, source_code):
    c, store = destination
    raw = visits(levantamento_codigo=source_code)
    page = c.get('/vigilancia/importacoes?demo=true')
    assert 'Levantamento de destino' in page.text and 'value="L-2026-01"' in page.text
    response = upload(c, raw)
    assert response.status_code == 303, response.text
    batch = store.history(7)[0]
    saved = store.get(batch['id'], 7)
    assert saved['sha256'] == hashlib.sha256(raw).hexdigest()
    assert store.original(batch['id'], 7) == raw
    assert saved['report']['vinculo_levantamento'] == {'destino':'L-2026-01', 'codigo_csv':source_code}
    assert {row['levantamento_codigo'] for row in saved['report']['registros']} == {'L-2026-01'}
    assert {row['levantamento_codigo'] for row in saved['report']['indicadores']} == {'L-2026-01'}
    page = c.get(response.location)
    assert 'Levantamento selecionado: L-2026-01' in page.text
    # O destino já revisado pertence ao lote; campos extras no POST não o trocam.
    response = confirm(c, batch['id'], levantamento_destino='OUTRO')
    assert response.status_code == 303, response.text
    assert confirm(c, batch['id']).status_code == 303
    records = store.records(7, demo=True)
    assert len(records) == 2 and {r['levantamento_codigo'] for r in records} == {'L-2026-01'}
    assert store.original(batch['id'], 7) == raw
    assert store.get(batch['id'], 7)['report']['vinculo_levantamento']['codigo_csv'] == source_code
    report = ResultsStore(store.engine).report(7, True, filters_from({'levantamento':'L-2026-01'}))
    assert len(report['geografia']['features']) == 2
    with store.connection() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(CampoPlanoVisita)) == 2


@pytest.mark.parametrize('state', ['RASCUNHO', 'ENCERRADO'])
def test_closed_or_draft_destination_is_not_listed_and_is_rejected(destination, state):
    c, store = destination
    with store.connection(write_prefeitura=7) as conn:
        conn.execute(CampoPlano.__table__.update().values(status=state))
    assert c.get('/vigilancia/importacoes/levantamentos?demo=true').json == {'levantamentos':[]}
    response = upload(c, visits(levantamento_codigo='OUTRO'))
    assert response.status_code == 409 and 'precisa estar liberado' in response.text
    assert store.history(7) == [] and store.records(7, demo=True) == []


def test_destination_list_is_scoped_and_confirmation_rechecks_release(destination):
    c, store = destination
    api = c.get('/vigilancia/importacoes/levantamentos?demo=true')
    assert api.status_code == 200 and api.headers['Cache-Control'] == 'private, no-store'
    assert [r['codigo'] for r in api.json['levantamentos']] == ['L-2026-01']
    assert c.get('/vigilancia/importacoes/levantamentos?demo=false').json == {'levantamentos':[]}
    assert c.get('/vigilancia/importacoes/levantamentos?prefeitura_id=8&demo=true').status_code == 403
    assert c.get('/vigilancia/importacoes/levantamentos?demo=true&demo=false').status_code == 400
    assert c.get('/vigilancia/importacoes/levantamentos?demo=invalid').status_code == 400
    response = upload(c, visits(levantamento_codigo='OUTRO'))
    assert response.status_code == 303
    batch = store.history(7)[0]
    change(store, 'encerrar')
    assert confirm(c, batch['id']).status_code == 409
    assert store.records(7, demo=True) == []


@pytest.mark.parametrize('overrides', [dict(estrato_codigo='E-ERRADO'), dict(quarteirao_codigo='Q-ERRADO'),
    dict(bairro='Outro bairro'), dict(data_inspecao='2026-10-18'), dict(municipio_id=8)])
def test_destination_does_not_override_other_validations(destination, overrides):
    c, store = destination
    response = upload(c, visits(levantamento_codigo='OUTRO', **overrides))
    assert response.status_code in {303,409}
    if response.status_code == 303:
        batch = store.history(7)[0]
        assert batch['status'] == 'REJEITADO'
        assert confirm(c, batch['id']).status_code == 409
    assert store.records(7, demo=True) == []


def test_missing_or_wrong_mode_destination_is_reported_without_disclosing_other_scopes(destination):
    c, store = destination
    for demo, selected in [(True,'INEXISTENTE'), (False,'L-2026-01')]:
        with pytest.raises(FieldConflict, match='não foi encontrado nesta prefeitura e origem de dados'):
            store.prepare(visits(), prefeitura=7, demo=demo, actor='a', source='Fonte', filename='csv.csv',
                          levantamento_destino=selected)
    assert store.history(7) == []


def test_destination_rejects_focal_mixed_surveys_and_missing_block_column(destination):
    c, store = destination
    raw = visits().decode('utf-8-sig')
    invalid = [raw.replace('LIRAA','FOCAL'), raw.replace('L-2026-01','OUTRO',1)]
    for data in invalid:
        with pytest.raises(PreviewValidationError):
            store.prepare(data.encode('utf-8'), prefeitura=7, demo=True, actor='a', source='Fonte',
                          filename='csv.csv', levantamento_destino='L-2026-01')
    from app.modules.vigilancia.service import preview_csv
    records = preview_csv(visits(), prefeitura_id=7)['registros']
    plain = csv_bytes(CSV_COLUMNS, [{name: row[name] for name in CSV_COLUMNS} for row in records])
    with pytest.raises(FieldConflict, match='quarteirao_codigo'):
        store.prepare(plain, prefeitura=7, demo=True, actor='a', source='Fonte', filename='csv.csv',
                      levantamento_destino='L-2026-01')


def test_failed_upload_keeps_selected_mode_and_destination(destination):
    c, store = destination
    response = upload(c, visits(levantamento_codigo='OUTRO', data_inspecao='2026-10-18'))
    assert response.status_code == 409
    assert 'value="L-2026-01" selected' in response.text
    assert 'value="true" selected' in response.text


def extend_period(c, store, **overrides):
    plan = store.overview(7, True, 'L-2026-01')['plano']
    values = dict(acao='ampliar_periodo', demo='true', plano=plan['code'], versao=str(plan['versao']),
        inicio='2026-10-18', fim='2026-10-24', justificativa='Incluir as datas originais do arquivo de visitas',
        periodo_confirmado='sim', _csrf_token=token(c))
    values.update(overrides)
    return c.post('/vigilancia/planejamento', data=values)


def test_explicit_period_extension_unblocks_csv_and_preserves_existing_visits(destination):
    c, store = destination
    response = upload(c, visits())
    assert response.status_code == 303
    first = store.history(7)[0]
    assert confirm(c, first['id']).status_code == 303
    previous_records = store.records(7, demo=True)
    previous = store.overview(7, True, 'L-2026-01')
    raw = visits(data_inspecao='2026-10-18').replace(b'2026-10-18', b'2026-10-24', 1)
    raw = raw.replace(b'VIS-', b'NOV-VIS-').replace(b'IM-', b'NOV-IM-')
    rejected = upload(c, raw)
    assert rejected.status_code == 409
    assert '18/10/2026 a 24/10/2026' in rejected.text
    assert 'plano=L-2026-01#periodo-levantamento' in rejected.text
    assert store.records(7, demo=True) == previous_records
    assert len(store.history(7)) == 1
    page = c.get('/vigilancia/planejamento?demo=true&plano=L-2026-01')
    assert 'Salvar ampliação do período' in page.text
    response = extend_period(c, store)
    assert response.status_code == 303, response.text
    current = store.overview(7, True, 'L-2026-01')
    assert current['plano']['status'] == 'LIBERADO'
    assert current['plano']['inicio'] == date(2026, 10, 18)
    assert current['plano']['fim'] == date(2026, 10, 24)
    assert current['plano']['versao'] == previous['plano']['versao'] + 1
    assert current['quarteiroes'] == previous['quarteiroes']
    assert current['estratos'] == previous['estratos']
    event = current['plano']['historico'][-1]
    assert event['acao'] == 'ampliar_periodo' and event['autor'] == 'a'
    assert event['periodo_anterior'] == {'inicio':'2026-10-19', 'fim':'2026-10-23'}
    assert event['periodo_novo'] == {'inicio':'2026-10-18', 'fim':'2026-10-24'}
    assert event['justificativa']
    assert store.records(7, demo=True) == previous_records
    assert upload(c, raw).status_code == 303
    second = store.history(7)[0]
    assert confirm(c, second['id']).status_code == 303
    assert store.original(second['id'], 7) == raw
    assert len(store.records(7, demo=True)) == 4
    assert {r['data_inspecao'] for r in store.records(7, demo=True) if r['inspecao_codigo'].startswith('NOV-')} == {'2026-10-18','2026-10-24'}


@pytest.mark.parametrize('overrides', [
    {'periodo_confirmado':''}, {'justificativa':''}, {'inicio':'2026-10-20'}, {'fim':'2026-10-22'},
    {'inicio':'2026-10-19','fim':'2026-10-23'}, {'inicio':'invalido'}, {'versao':'1'},
])
def test_invalid_period_extension_is_atomic(destination, overrides):
    c, store = destination
    previous = store.overview(7, True, 'L-2026-01')['plano']
    response = extend_period(c, store, **overrides)
    assert response.status_code == 400
    assert store.overview(7, True, 'L-2026-01')['plano'] == previous


@pytest.mark.parametrize('status', ['RASCUNHO','ENCERRADO'])
def test_period_extension_keeps_draft_and_closed_rules(destination, status):
    c, store = destination
    with store.connection(write_prefeitura=7) as conn:
        conn.execute(CampoPlano.__table__.update().values(status=status))
    previous = store.overview(7, True, 'L-2026-01')['plano']
    response = extend_period(c, store)
    assert response.status_code == 400
    assert store.overview(7, True, 'L-2026-01')['plano'] == previous


def test_period_extension_requires_csrf_and_same_municipality(destination):
    c, store = destination
    previous = store.overview(7, True, 'L-2026-01')['plano']
    assert extend_period(c, store, _csrf_token='invalid').status_code == 403
    login(c, 'b')
    assert extend_period(c, store, prefeitura_id='7').status_code == 403
    assert store.overview(7, True, 'L-2026-01')['plano'] == previous


def test_released_plan_opens_import_with_explicit_destination(destination):
    c, store = destination
    page = c.get('/vigilancia/planejamento?prefeitura_id=7&demo=true&plano=L-2026-01')
    assert page.status_code == 200
    assert 'Importar visitas deste levantamento' in page.text
    assert 'levantamento_destino=L-2026-01' in page.text
    page = c.get('/vigilancia/importacoes?prefeitura_id=7&demo=true&levantamento_destino=L-2026-01')
    assert page.status_code == 200 and 'value="L-2026-01" selected' in page.text
    assert 'id="campo-planejamento-link"' in page.text
    with store.connection(write_prefeitura=7) as conn:
        conn.execute(CampoPlano.__table__.update().values(status='RASCUNHO'))
    page = c.get('/vigilancia/planejamento?prefeitura_id=7&demo=true&plano=L-2026-01')
    assert 'Importar visitas deste levantamento' not in page.text


def test_other_tenant_cannot_use_destination_endpoint_or_upload(destination):
    c, store = destination
    login(c, 'b')
    assert c.get('/vigilancia/importacoes/levantamentos?prefeitura_id=7&demo=true').status_code == 403
    assert c.post('/vigilancia/importacoes', data={'prefeitura_id':'7','levantamento_destino':'L-2026-01'}).status_code == 403

