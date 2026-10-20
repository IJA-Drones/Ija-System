"""Plano municipal, importação atômica e publicação de visitas na amostra."""

import importlib.util
import io
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.autogenerate import compare_metadata

from app.extensions import db
from app.models import Usuario
from app.modules.vigilancia.planning import PlanningStore, PLAN_COLUMNS, validate_visits
from app.modules.vigilancia.planning_models import PLANNING_TABLES, CampoPlanoVisita
from app.modules.vigilancia.field_models import CampoLevantamento
from app.modules.vigilancia.field_capture import capture_csv
from app.modules.vigilancia.field_store import FieldConflict
from test_vigilancia_field_routes import client, login, token, confirm, store
from test_vigilancia_capture import record


@pytest.fixture
def planned(client):
    with client.application.app_context():
        db.create_all()
        db.session.add_all([
            Usuario(id=701, nome_uvis='Agente municipal', login='agente-local', senha_hash='unused', tipo_usuario='agente_endemias', prefeitura_id=7),
            Usuario(id=702, nome_uvis='Outro agente', login='agente-outro', senha_hash='unused', tipo_usuario='agente_endemias', prefeitura_id=7),
            Usuario(id=703, nome_uvis='Coordenação Sete', login='covisa-sete', senha_hash='unused', tipo_usuario='visualizar', regiao='COVISA', prefeitura_id=7),
            Usuario(id=704, nome_uvis='Coordenação Oito', login='covisa-oito', senha_hash='unused', tipo_usuario='covisa', prefeitura_id=8),
            Usuario(id=705, nome_uvis='Visualizador comum', login='visualizador-local', senha_hash='unused', tipo_usuario='visualizar', regiao='Outra', prefeitura_id=7),
            Usuario(id=706, nome_uvis='COVISA sem município', login='covisa-sem-municipio', senha_hash='unused', tipo_usuario='covisa'),
            Usuario(id=801, nome_uvis='Outro município', login='outro-local', senha_hash='unused', tipo_usuario='uvis', prefeitura_id=8)])
        db.session.commit()
        planning = PlanningStore(db.engine)
    previous_loader = client.application.login_manager._user_callback
    def load(uid):
        return db.session.get(Usuario, int(uid)) if uid.isdecimal() else previous_loader(uid)
    client.application.login_manager.user_loader(load)
    return client, planning


def create(planning, *, demo=True):
    planning.mutate(7, demo, 'a', 'territorio', dict(quarteirao='Q-01', bairro='Bairro Sintético', area='A-01', imoveis='100', referencia='RG municipal'))
    planning.mutate(7, demo, 'a', 'criar', dict(plano='L-2026-01', titulo='Levantamento municipal', inicio='2026-10-19', fim='2026-10-23', responsavel='Coordenação', fonte='Plano amostral municipal'))
    change(planning, 'estrato', demo=demo, estrato='E-01', imoveis_estrato='1000', meta_estrato='20', criterio='Características semelhantes')
    change(planning, 'quarteirao', demo=demo, estrato='E-01', quarteirao='Q-01', meta_quarteirao='20', agente_id='701')


def change(planning, action, *, demo=True, **values):
    plan = planning.overview(7, demo, 'L-2026-01')['plano']
    return planning.mutate(7, demo, 'a', action, {'plano': 'L-2026-01', 'versao': str(plan['versao']), **values})


def prepare_planned(client, planning, **changes):
    values = record(estrato_codigo='E-01', **changes)
    return planning.prepare(capture_csv(values, prefeitura=7), prefeitura=7, actor='a', source='Registro planejado',
        filename='campo.csv', demo=True, plan_reference={'plano':'L-2026-01','quarteirao':'Q-01'})


def test_plan_lifecycle_preserves_rg_snapshot_and_links_visits(planned):
    client, planning = planned
    create(planning)
    with pytest.raises(FieldConflict, match='liberado'):
        prepare_planned(client, planning)
    change(planning, 'liberar', amostra_validada='sim')
    planning.mutate(7, True, 'a', 'territorio', dict(quarteirao='Q-01', bairro='Novo bairro', area='A-02', imoveis='120', referencia='RG atualizado'))
    assert planning.overview(7, True, 'L-2026-01')['quarteiroes'][0]['territorio']['bairro'] == 'Bairro Sintético'
    batch = prepare_planned(client, planning)
    planning.confirm(batch['id'], prefeitura=7, actor='a')
    overview = planning.overview(7, True, 'L-2026-01')
    assert overview['quarteiroes'][0]['inspecionados'] == 1
    assert planning.confirm(batch['id'], prefeitura=7, actor='a')['status'] == 'CONCLUIDO'
    with planning.connection() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(CampoPlanoVisita)) == 1
    change(planning, 'encerrar')
    with pytest.raises(FieldConflict, match='liberado'):
        prepare_planned(client, planning, inspecao_codigo='VIS-002')


@pytest.mark.parametrize('bad', [{'data_inspecao':'2026-10-18'}, {'bairro':'Fora do plano'}, {'estrato_codigo':'E-02'}])
def test_rejects_visits_outside_period_territory_or_stratum(planned, bad):
    client, planning = planned
    create(planning)
    change(planning, 'liberar', amostra_validada='sim')
    values = record(estrato_codigo='E-01') | bad
    with pytest.raises(FieldConflict):
        planning.prepare(capture_csv(values, prefeitura=7), prefeitura=7, actor='a', source='Tentativa inválida',
            filename='campo.csv', demo=True, plan_reference={'plano':'L-2026-01','quarteirao':'Q-01'})
    assert planning.records(7, demo=True) == []


def test_plan_cannot_be_bypassed_with_legacy_csv_or_changed_after_release(planned):
    client, planning = planned
    create(planning)
    change(planning, 'liberar', amostra_validada='sim')
    with pytest.raises(FieldConflict, match='quarteirão'):
        planning.prepare(capture_csv(record(estrato_codigo='E-01'), prefeitura=7), prefeitura=7,
            actor='a', source='CSV sem vínculo', filename='campo.csv', demo=True)
    with pytest.raises(FieldConflict, match='protegido'):
        change(planning, 'estrato', estrato='E-02', imoveis_estrato='100', meta_estrato='20', criterio='teste')
    assert planning.overview(8, True, 'L-2026-01')['plano'] is None
    assert planning.overview(7, False, 'L-2026-01')['plano'] is None


@pytest.mark.parametrize('use_plan', [False, True])
def test_visit_validation_does_not_query_the_database_for_each_csv_row(planned, use_plan):
    _, planning = planned
    reference = None
    if use_plan:
        create(planning)
        change(planning, 'liberar', amostra_validada='sim')
        reference = {'plano': 'L-2026-01', 'quarteirao': 'Q-01', 'agente_id': 701}
    values = record(estrato_codigo='E-01')
    statements = []

    def count_queries(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa.event.listen(planning.engine, 'before_cursor_execute', count_queries)
    try:
        with planning.connection() as conn:
            validate_visits(conn, [values], 7, True, reference, '701')
            single_count = len(statements)
            statements.clear()
            visits = [values | {'imovel_codigo': f'IM-{i}', 'inspecao_codigo': f'VIS-{i}'} for i in range(500)]
            validate_visits(conn, visits, 7, True, reference, '701')
            assert len(statements) <= single_count + 1
    finally:
        sa.event.remove(planning.engine, 'before_cursor_execute', count_queries)


@pytest.mark.parametrize('bad', [{'data_inspecao': '2026-10-18'}, {'bairro': 'Outra área'}, {'estrato_codigo': 'E-02'}])
def test_bulk_validation_still_checks_each_visit_after_reusing_the_plan(planned, bad):
    _, planning = planned
    create(planning)
    change(planning, 'liberar', amostra_validada='sim')
    values = record(estrato_codigo='E-01')
    reference = {'plano': 'L-2026-01', 'quarteirao': 'Q-01', 'agente_id': 701}
    with planning.connection() as conn, pytest.raises(FieldConflict):
        validate_visits(conn, [values, values | bad], 7, True, reference, '701')


def test_pending_batch_revalidates_after_plan_closure(planned):
    client, planning = planned
    create(planning)
    change(planning, 'liberar', amostra_validada='sim')
    batch = prepare_planned(client, planning)
    change(planning, 'encerrar')
    with pytest.raises(FieldConflict):
        planning.confirm(batch['id'], prefeitura=7, actor='a')
    assert planning.get(batch['id'], 7)['status'] == 'VALIDADO'
    assert planning.records(7, demo=True) == []


def test_revision_conflict_and_release_require_matching_targets_and_review(planned):
    client, planning = planned
    create(planning)
    with pytest.raises(FieldConflict, match='outra pessoa'):
        planning.mutate(7, True, 'a', 'liberar', dict(plano='L-2026-01', versao='1', amostra_validada='sim'))
    with pytest.raises(FieldConflict, match='Confirme'):
        change(planning, 'liberar')
    change(planning, 'estrato', estrato='E-01', imoveis_estrato='1000', meta_estrato='21', criterio='Revisado')
    with pytest.raises(FieldConflict, match='fecham'):
        change(planning, 'liberar', amostra_validada='sim')
    with pytest.raises(FieldConflict, match='mesma prefeitura'):
        change(planning, 'quarteirao', estrato='E-01', quarteirao='Q-01', meta_quarteirao='20', agente_id='801')


def test_invalid_rg_and_replacement_sample_roll_back_every_row(planned):
    client, planning = planned
    create(planning)
    bad_rg = 'quarteirao;bairro;area;imoveis;referencia\nQ-02;Bairro;A-01;50;RG\nQ-03;Bairro;A-01;-1;RG\n'.encode()
    with pytest.raises(FieldConflict):
        planning.mutate(7, True, 'a', 'importar_territorio', {}, bad_rg)
    assert len(planning.overview(7, True)['territorio']) == 1
    bad_plan = (';'.join(PLAN_COLUMNS) + '\nE-02;1000;20;Critério;Q-01;20;\nE-02;1000;20;Critério;Q-99;20;\n').encode()
    previous = planning.overview(7, True, 'L-2026-01')
    with pytest.raises(FieldConflict):
        planning.mutate(7, True, 'a', 'importar_plano', dict(plano='L-2026-01', versao=str(previous['plano']['versao'])), bad_plan)
    current = planning.overview(7, True, 'L-2026-01')
    assert current['estratos'] == previous['estratos']
    assert current['quarteiroes'] == previous['quarteiroes']
    assert current['plano']['versao'] == previous['plano']['versao']


def test_http_scope_csrf_read_only_and_planned_visit_flow(planned):
    client, planning = planned
    login(client)
    create(planning)
    change(planning, 'liberar', amostra_validada='sim')
    page = client.get('/vigilancia/planejamento?plano=L-2026-01')
    assert page.status_code == 200 and 'Registrar visita em Q-01' in page.text
    assert page.headers['Cache-Control'] == 'private, no-store'
    page = client.get('/vigilancia/campo?plano=L-2026-01&quarteirao=Q-01')
    assert page.status_code == 200 and 'value="E-01"' in page.text
    values = {**record(estrato_codigo='E-01'), 'plano':'L-2026-01', 'quarteirao':'Q-01', 'demo':'true', '_csrf_token':token(client)}
    assert client.post('/vigilancia/campo', data=values).status_code == 303
    batch = planning.history(7)[0]
    assert confirm(client, batch['id']).status_code == 303
    assert planning.overview(7, True, 'L-2026-01')['quarteiroes'][0]['inspecionados'] == 1
    assert client.post('/vigilancia/planejamento', data={'acao':'territorio','demo':'true'}).status_code == 403
    assert client.post('/vigilancia/planejamento', data=b'x' * (1024*1024+65537)).status_code == 413
    choices = frozenset({'area:prefeitura','prefeitura.vigilancia.consultar'})
    with patch('app.modules.gestao_ti.permissions.active_configuration', return_value=choices):
        page = client.get('/vigilancia/planejamento')
        assert page.status_code == 200 and 'Criar rascunho' not in page.text
        assert client.post('/vigilancia/planejamento', data={'demo':'true', '_csrf_token':token(client)}).status_code == 403
    login(client, 'b')
    assert client.get('/vigilancia/planejamento?prefeitura_id=7').status_code == 403
    assert client.get('/vigilancia/planejamento?plano=L-2026-01').status_code == 404


def test_migration_matches_models_and_preserves_existing_survey(planned):
    client, planning = planned
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('planning_migration', root/'migrations/versions/d8a31e62bc09_planejamento_liraa.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    geometry_spec = importlib.util.spec_from_file_location('geometry_migration', root/'migrations/versions/e91c7b4a203d_geometria_territorio_liraa.py')
    geometry_migration = importlib.util.module_from_spec(geometry_spec)
    geometry_spec.loader.exec_module(geometry_migration)
    with planning.engine.begin() as conn:
        for table in reversed(PLANNING_TABLES):
            table.drop(conn)
        conn.execute(CampoLevantamento.__table__.insert().values(prefeitura=7, demo=True, code='LEGADO'))
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            module.upgrade()
            geometry_migration.upgrade()
        present = set(sa.inspect(conn).get_table_names())
        context = MigrationContext.configure(conn, opts={
            'include_object': lambda obj, name, kind, reflected, target: kind != 'table' or name in present})
        assert compare_metadata(context, db.metadata) == []
        with Operations.context(context):
            geometry_migration.downgrade()
            module.downgrade()
        assert conn.scalar(sa.select(CampoLevantamento.code)) == 'LEGADO'
    stream = io.StringIO()
    with Operations.context(MigrationContext.configure(dialect_name='postgresql', opts={'as_sql':True,'output_buffer':stream})):
        module.upgrade()
    assert stream.getvalue().count('CREATE TABLE') == 5
    assert 'ALTER TABLE' not in stream.getvalue() and 'DROP TABLE' not in stream.getvalue()


def test_agent_sees_only_assigned_blocks_and_cannot_reach_management(planned):
    client, planning = planned
    create(planning)
    change(planning, 'liberar', amostra_validada='sim')
    login(client, '701')
    page = client.get('/vigilancia/agente?demo=true')
    assert page.status_code == 200 and 'Registrar em Q-01' in page.text
    assert page.headers['Cache-Control'] == 'private, no-store'
    for path in ['/vigilancia/planejamento', '/vigilancia/campo', '/vigilancia/importacoes', '/vigilancia/sinan']:
        assert client.get(path).status_code == 403
    assert client.get('/vigilancia/agente?demo=true&prefeitura_id=8').status_code == 403
    login(client, '702')
    page = client.get('/vigilancia/agente?demo=true')
    assert 'Registrar em Q-01' not in page.text
    assert client.get('/vigilancia/agente?demo=true&plano=L-2026-01&quarteirao=Q-01').status_code == 404
    # Mesmo uma configuração de TI ampla não remove o escopo do perfil agente.
    with patch('app.modules.gestao_ti.permissions.active_configuration', return_value=frozenset({'area:prefeitura','prefeitura.vigilancia.consultar','prefeitura.vigilancia.editar'})):
        assert client.get('/vigilancia/planejamento').status_code == 403


def test_agent_review_confirm_author_and_cross_agent_batch_privacy(planned):
    client, planning = planned
    create(planning)
    change(planning, 'liberar', amostra_validada='sim')
    login(client, '701')
    client.get('/vigilancia/agente?demo=true')
    payload = dict(demo='true', acao='registrar', plano='L-2026-01', quarteirao='Q-01',
        imovel_codigo='IM-01', inspecao_codigo='VIS-01', data_inspecao='2026-10-19', situacao='FECHADO',
        amostra_liraa='sim', bairro='Tentativa de alterar o bairro', _csrf_token=token(client))
    response = client.post('/vigilancia/agente', data=payload)
    assert response.status_code == 303
    batch = planning.history(7)[0]
    assert batch['actor'] == '701'
    assert planning.records(7, demo=True) == []
    assert client.get(response.location).status_code == 200
    login(client, '702')
    assert client.get(response.location).status_code == 404
    assert client.post('/vigilancia/agente', data=dict(demo='true', acao='confirmar', lote=batch['id'], _csrf_token=token(client))).status_code == 404
    login(client, '701')
    assert client.post('/vigilancia/agente', data=dict(demo='true', acao='confirmar', lote=batch['id'], _csrf_token=token(client))).status_code == 303
    saved = planning.records(7, demo=True)[0]
    assert saved['bairro'] == 'Bairro Sintético' and saved['situacao'] == 'FECHADO'
    with planning.connection() as conn:
        assert conn.scalar(sa.select(CampoPlanoVisita.autor)) == '701'
    assert planning.overview(7, True, 'L-2026-01')['quarteiroes'][0]['pendentes'] == 1


def test_agent_review_cannot_publish_after_account_changes_municipality(planned):
    client, planning = planned
    create(planning)
    change(planning, 'liberar', amostra_validada='sim')
    batch = planning.prepare(capture_csv(record(estrato_codigo='E-01'), prefeitura=7), prefeitura=7, actor='701',
        source='Agente', filename='campo.csv', demo=True,
        plan_reference=dict(plano='L-2026-01', quarteirao='Q-01', agente_id=701))
    with planning.engine.begin() as conn:
        conn.execute(Usuario.__table__.update().where(Usuario.id == 701).values(prefeitura_id=8))
    with pytest.raises(FieldConflict, match='agente'):
        planning.confirm(batch['id'], prefeitura=7, actor='701')
    assert planning.records(7, demo=True) == []


def test_agent_rejects_ambiguous_repeated_fields(planned):
    from werkzeug.datastructures import MultiDict
    client, planning = planned
    create(planning)
    change(planning, 'liberar', amostra_validada='sim')
    login(client, '701')
    client.get('/vigilancia/agente?demo=true')
    response = client.post('/vigilancia/agente', data=MultiDict([
        ('acao','registrar'), ('demo','true'), ('plano','L-2026-01'), ('quarteirao','Q-01'),
        ('amostra_liraa','sim'), ('_csrf_token',token(client)), ('imovel_codigo','IM-01'), ('imovel_codigo','IM-02')]))
    assert response.status_code == 400 and 'único valor' in response.text
    assert planning.history(7) == []


def test_covisa_coordinates_own_municipality_through_http(planned):
    client, planning = planned
    login(client, '703')
    page = client.get('/vigilancia')
    assert page.status_code == 200 and 'Acessar Focal e LIRAa' in page.text
    # SINAN integra a coordenação; a prévia técnica mantém a regra anterior.
    assert 'Acessar SINAN' in page.text and 'Validar sem gravar dados' not in page.text
    page = client.get('/vigilancia/planejamento')
    assert page.status_code == 200 and 'Criar rascunho' in page.text
    assert client.get('/vigilancia/campo').status_code == 200
    def post(action, **values):
        response = client.post('/vigilancia/planejamento', data=dict(
            acao=action, demo='true', _csrf_token=token(client), **values))
        assert response.status_code == 303, response.text
        # O destino explícito substitui o fragmento do formulário anterior.
        assert response.location.endswith('#territorio' if action == 'territorio' else '#amostra')
    post('territorio', quarteirao='Q-01', bairro='Bairro Sete', area='A-01', imoveis='100', referencia='RG municipal')
    post('criar', plano='L-COVISA', titulo='Levantamento da COVISA', inicio='2026-10-19', fim='2026-10-23', responsavel='Coordenação municipal', fonte='Plano municipal')
    post('estrato', plano='L-COVISA', versao='1', estrato='E-01', imoveis_estrato='1000', meta_estrato='20', criterio='Área contínua')
    post('quarteirao', plano='L-COVISA', versao='2', estrato='E-01', quarteirao='Q-01', meta_quarteirao='20', agente_id='701')
    post('liberar', plano='L-COVISA', versao='3', amostra_validada='sim')
    plan = planning.overview(7, True, 'L-COVISA')['plano']
    assert plan['status'] == 'LIBERADO' and all(event['autor'] == '703' for event in plan['historico'])
    login(client, '701')
    assert 'Registrar em Q-01' in client.get('/vigilancia/agente?demo=true').text
    login(client, '704')
    assert client.get('/vigilancia/planejamento').status_code == 200
    assert client.get('/vigilancia/planejamento?plano=L-COVISA').status_code == 404
    assert client.get('/vigilancia/planejamento?prefeitura_id=7').status_code == 403
    assert client.get('/vigilancia/campo?prefeitura_id=7').status_code == 403
    assert client.get('/vigilancia/importacoes?prefeitura_id=7').status_code == 403
    assert client.post('/vigilancia/planejamento', data=dict(acao='encerrar', plano='L-COVISA', versao='4',
        demo='true', prefeitura_id='7', _csrf_token=token(client))).status_code == 403
    assert planning.overview(7, True, 'L-COVISA')['plano']['status'] == 'LIBERADO'
    assert planning.overview(8, True)['territorio'] == []


@pytest.mark.parametrize('user', ['705', '706'])
def test_other_visualizer_or_covisa_without_municipality_cannot_coordinate(planned, user):
    client, planning = planned
    login(client, user)
    assert client.get('/vigilancia').status_code == 403
    assert client.get('/vigilancia/planejamento').status_code == 403
    assert client.get('/vigilancia/campo').status_code == 403


def test_covisa_explicit_ti_revocation_and_read_only_are_preserved(planned):
    from app.modules.gestao_ti.current_rules import current_rules
    client, planning = planned
    login(client, '703')
    assert {'prefeitura.vigilancia.consultar', 'prefeitura.vigilancia.editar'} <= set(current_rules('covisa')['permissions'])
    choices = frozenset({'area:prefeitura', 'prefeitura.vigilancia.consultar'})
    with patch('app.modules.gestao_ti.permissions.active_configuration', return_value=choices):
        page = client.get('/vigilancia/planejamento')
        assert page.status_code == 200 and 'Criar rascunho' not in page.text
        assert client.post('/vigilancia/planejamento', data=dict(acao='criar', demo='true', _csrf_token=token(client))).status_code == 403
    with patch('app.modules.gestao_ti.permissions.active_configuration', return_value=frozenset()):
        assert client.get('/vigilancia').status_code == 403
        assert client.get('/vigilancia/planejamento').status_code == 403
