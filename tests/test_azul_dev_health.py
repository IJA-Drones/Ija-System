import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from openai import OpenAIError

from app.extensions import db
from app.models import AuditoriaUsuario, Usuario
from app.modules.chatbot import azul, dev_health, dev_diagnostics
from tests.test_azul_exports import app, client


def seed(app):
    app.add_url_rule('/health-test', endpoint='main.health_test', view_func=lambda: '')
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        for status, count, age, event, endpoint in [
            (403, 12, 1, 'ACESSO', 'main.health_test'),
            (500, 2, 2, 'ACESSO', 'main.health_test'),
            (500, 3, 30, 'ACESSO', 'main.health_test'),
            (401, 10, 1, 'SESSAO_EXPIRADA', 'main.health_test'),
            (409, 8, 1, 'ACESSO', 'edit_control.lease'),
            (500, 9, 200, 'ACESSO', 'main.health_test'),
        ]:
            for _ in range(count):
                db.session.add(AuditoriaUsuario(usuario_nome='PRIVATE_NAME', metodo='GET', path='/PRIVATE_PATH',
                    endpoint=endpoint, status_code=status, tipo_evento=event,
                    criado_em=now-timedelta(hours=age), ip='PRIVATE_IP', query_string='token=PRIVATE_SECRET'))
        db.session.commit()


def test_full_ranking_separates_frequency_gravity_and_time_windows(app):
    seed(app)
    with app.test_request_context():
        data = dev_health.evidence(db.session.get(Usuario, 1))
    assert data['metricas']['errors_24h'] == 14
    assert data['metricas']['server_errors_7d'] == 5
    assert data['mais_recorrentes'][0]['status'] == 403
    assert data['mais_recorrentes'][0]['ocorrencias_7d'] == 12
    server = data['prioridade_servidor'][0]
    assert server['ocorrencias_24h'] == 2
    assert server['ocorrencias_24h_anteriores'] == 3
    assert server['ocorrencias_7d'] == 5
    encoded = json.dumps(data)
    for secret in ['PRIVATE_NAME', 'PRIVATE_IP', 'PRIVATE_SECRET', 'PRIVATE_PATH']:
        assert secret not in encoded
    assert all(row['status'] in (403, 500) for row in data['mais_recorrentes'])


@pytest.mark.parametrize('uid', [2, 3, 4])
def test_overview_denies_non_dev_before_reading_or_provider(app, uid):
    with patch.object(dev_health, 'evidence') as read, patch.object(dev_health, 'OpenAI') as provider:
        response = client(app, uid).post('/api/azul/ajuda', json={
            'message': 'Analise a saúde do sistema', 'intent': 'dev_health_overview', 'role': 'dev'})
    assert response.status_code == 403
    read.assert_not_called()
    provider.assert_not_called()


def test_revoked_data_permission_and_quota_block_reads(app):
    c = client(app)
    with patch.object(dev_health, 'can_access_endpoint', return_value=False), patch.object(dev_health, 'build_dev_dashboard_context') as read:
        assert c.post('/api/azul/ajuda', json={'message': 'Analise a saúde do sistema'}).status_code == 403
        read.assert_not_called()
    with patch.object(azul, 'consume_help_quota', return_value=False), patch.object(dev_health, 'evidence') as read:
        assert c.post('/api/azul/ajuda', json={'message': 'Analise os erros mais recorrentes'}).status_code == 429
        read.assert_not_called()


def test_no_provider_returns_actionable_local_overview_without_writes(app):
    seed(app)
    with app.app_context():
        before = AuditoriaUsuario.query.count()
    with patch.object(dev_health, 'OpenAI') as provider:
        response = client(app).post('/api/azul/ajuda', json={'message': 'Analise a saúde do sistema'})
    assert response.status_code == 200
    assert response.json['mode'] == 'guided'
    assert 'Recorrências' in response.json['answer']
    assert '**Investigar:**' in response.json['answer']
    assert '**Validar:**' in response.json['answer']
    assert 'HTTP 500' in response.json['answer']
    assert 'no-store' in response.headers['Cache-Control']
    provider.assert_not_called()
    with app.app_context():
        assert AuditoriaUsuario.query.count() == before


def test_provider_is_grounded_and_failure_falls_back(app):
    seed(app)
    app.config['OPENAI_API_KEY'] = 'test-key'
    c = client(app)
    with patch.object(dev_health, 'OpenAI') as provider:
        create = provider.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status='completed', output_text='Comece pelos erros 5xx e confira os logs.')
        response = c.post('/api/azul/ajuda', json={'message': 'Analise a saúde do sistema'})
        args = create.call_args.kwargs
    assert response.json['mode'] == 'ia'
    assert args['store'] is False
    assert 'mais_recorrentes' in args['instructions']
    assert 'Não invente stack trace' in args['instructions']
    assert 'tools' not in args
    for secret in ['PRIVATE_NAME', 'PRIVATE_IP', 'PRIVATE_PATH', 'PRIVATE_SECRET']:
        assert secret not in json.dumps(args)
    with patch.object(dev_health, 'OpenAI') as provider:
        provider.return_value.__enter__.return_value.responses.create.side_effect = OpenAIError('offline')
        response = c.post('/api/azul/ajuda', json={'message': 'Analise a saúde do sistema'})
    assert response.status_code == 200
    assert response.json['mode'] == 'guided'


def test_overview_does_not_inherit_individual_selection_and_keeps_selected_error_flow(app):
    seed(app)
    c = client(app)
    first = c.post('/api/azul/ajuda', json={'message': 'Analise o erro #1'}).json
    with patch.object(dev_diagnostics, 'evidence') as individual:
        response = c.post('/api/azul/ajuda', json={
            'message': 'Agora analise os erros que mais se repetem e a saúde do sistema',
            'history': [{'role': 'user', 'content': 'Analise o erro #1'}], 'chat_key': first['chat_key']})
    assert response.status_code == 200
    assert 'Situação agora' in response.json['answer']
    individual.assert_not_called()
    assert not dev_health.requested('Analise o erro #1 e a saúde do sistema')


def test_empty_window_and_acknowledgement_are_honored(app):
    seed(app)
    from app.modules.dev_dashboard.service import clear_dev_errors
    with app.test_request_context():
        clear_dev_errors()
        data = dev_health.evidence(db.session.get(Usuario, 1))
    assert data['mais_recorrentes'] == []
    assert data['prioridade_servidor'] == []
    assert data['metricas']['errors_24h'] == 0
    assert 'Nenhuma falha auditada' in dev_health.local_answer(data)


def test_ranking_includes_repeated_group_beyond_dashboard_limit(app):
    seed(app)
    with app.app_context():
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for index in range(31):
            db.session.add(AuditoriaUsuario(usuario_nome='Teste', metodo='GET', path=f'/distinct/{index}',
                endpoint='main.health_test', status_code=500, tipo_evento='ACESSO', criado_em=now))
        db.session.commit()
    with app.test_request_context():
        context = dev_health.build_dev_dashboard_context()
        assert all(row.status_code == 500 for row in context['recent_errors'])
        data = dev_health.evidence(db.session.get(Usuario, 1))
    assert data['mais_recorrentes'][0]['status'] == 403
    assert data['mais_recorrentes'][0]['ocorrencias_7d'] == 12


def test_overview_followups_keep_scope_but_stop_at_other_task():
    history = [{'role': 'user', 'content': 'Analise a saúde do sistema'}]
    assert dev_health.requested('Por onde começo a corrigir?', history=history)
    assert not dev_health.requested('Analise o erro #42', history=history)
    history.append({'role': 'user', 'content': 'Como cadastrar um cliente?'})
    assert not dev_health.requested('Como validar?', history=history)


def test_unknown_paths_are_classified_without_exposing_private_segments(app):
    from app.modules.chatbot.dev_health_context import route_context
    app.add_url_rule('/test-resource/<int:item_id>', endpoint='main.test_resource', view_func=lambda item_id: '', methods=['GET'])
    with app.test_request_context():
        method = route_context(None, '/test-resource/1234', 'POST')
        assert method['categoria'] == 'metodo_incompativel'
        assert method['endpoint'] == 'main.test_resource'
        assert method['destino'] == '/test-resource/<int:item_id>'
        assert 'GET' in method['metodos_aceitos']
        assert '1234' not in json.dumps(method)
        resource = route_context('main.test_resource', '/test-resource/5678', 'GET')
        assert resource['categoria'] == 'funcao_registrada'
        unknown = route_context(None, '/PRIVATE_EMAIL/PRIVATE_TOKEN', 'GET')
        assert unknown['categoria'] == 'endereco_sem_rota'
        assert 'PRIVATE_' not in json.dumps(unknown)
        probe = route_context(None, '/.env', 'GET')
        assert probe['categoria'] == 'sondagem_comum'
        assert 'não confirma ataque' in probe['explicacao']
        asset = route_context(None, '/static/private.css', 'GET')
        assert asset['categoria'] == 'arquivo_estatico'
        assert 'private.css' not in json.dumps(asset)


def test_plan_prefers_active_server_failures_and_includes_captured_exception(app):
    seed(app)
    with app.app_context():
        row = AuditoriaUsuario.query.filter_by(status_code=500).order_by(AuditoriaUsuario.criado_em.desc(), AuditoriaUsuario.id.desc()).first()
        row.detalhes = {'diagnostico': {'versao': 1, 'excecao': {'tipo': 'ValueError', 'frames': []}, 'logs': []}}
        # Latest record is old; add a smaller active group to prove ordering uses current activity.
        db.session.add(AuditoriaUsuario(usuario_nome='Teste', metodo='POST', path='/active',
            endpoint='main.health_test', status_code=502, tipo_evento='ACESSO',
            criado_em=datetime.now(timezone.utc).replace(tzinfo=None)))
        db.session.commit()
    with app.test_request_context():
        data = dev_health.evidence(db.session.get(Usuario, 1))
    assert data['plano'][0]['status'] == 500
    assert data['plano'][0]['ocorrencias_24h'] == 2
    assert data['plano'][0]['excecao']['tipo'] == 'ValueError'
    assert data['plano'][1]['status'] == 502
    assert all('acao' in item and 'validacao' in item for item in data['plano'])
    assert all('acao' in item for item in data['verificacoes'])


def test_overview_respects_audit_permission_for_technical_evidence(app):
    seed(app)
    from app.modules.chatbot import dev_health_context
    with app.test_request_context(), patch.object(dev_health_context, 'can_access_endpoint', return_value=False), patch.object(dev_health_context.dev_audit, 'context') as audit:
        data = dev_health.evidence(db.session.get(Usuario, 1))
    audit.assert_not_called()
    assert all('não autorizada' in item['cobertura'] for item in data['plano'])
