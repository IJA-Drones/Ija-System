import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from openai import OpenAIError

from app.extensions import db
from app.models import AuditoriaUsuario
from app.modules.chatbot import azul, dev_diagnostics, topics
from tests.test_azul_exports import app, client


def seed_error(app):
    app.add_url_rule('/diagnostic-test', endpoint='main.diagnostic_test', view_func=lambda: '')
    with app.app_context():
        log = AuditoriaUsuario(usuario_nome='PRIVATE_NAME', metodo='POST', path='/private-path',
                               query_string='token=PRIVATE_SECRET', ip='PRIVATE_IP',
                               endpoint='main.diagnostic_test', tipo_evento='ACESSO', status_code=500,
                               criado_em=datetime.now(timezone.utc).replace(tzinfo=None))
        db.session.add(log)
        db.session.commit()
        return log.id


def test_local_diagnosis_works_without_provider_and_preserves_audit(app):
    log_id = seed_error(app)
    with patch.object(dev_diagnostics, 'OpenAI') as sdk:
        response = client(app).post('/api/azul/ajuda', json={
            'message': f'Analise o erro #{log_id} do painel dev', 'intent': f'dev_error:{log_id}'})
    assert response.status_code == 200
    assert response.json['mode'] == 'guided'
    assert 'Correção sugerida' in response.json['answer']
    assert 'causa raiz ainda precisa ser confirmada' in response.json['answer']
    sdk.assert_not_called()
    with app.app_context():
        assert AuditoriaUsuario.query.count() == 1


@pytest.mark.parametrize('uid', [2, 3, 4])
def test_non_dev_cannot_read_error_even_with_forged_intent(app, uid):
    with patch.object(dev_diagnostics, 'get_dev_error_detail') as read, patch.object(dev_diagnostics, 'OpenAI') as sdk:
        response = client(app, uid).post('/api/azul/ajuda', json={
            'message': 'Analise o erro #1', 'intent': 'dev_error:1', 'role': 'dev', 'page': '/dev'})
    assert response.status_code == 403
    read.assert_not_called()
    sdk.assert_not_called()


def test_revoked_detail_permission_blocks_before_lookup(app):
    with patch.object(dev_diagnostics, 'can_access_endpoint', side_effect=lambda u, endpoint, *a, **kw: endpoint != 'main.dev_dashboard_error_detail'), patch.object(dev_diagnostics, 'get_dev_error_detail') as read:
        response = client(app).post('/api/azul/ajuda', json={'message': 'Analise o erro #1'})
    assert response.status_code == 403
    read.assert_not_called()


def test_provider_gets_minimal_evidence_and_grounding_rules(app):
    log_id = seed_error(app)
    app.config['OPENAI_API_KEY'] = 'test-key'
    with patch.object(dev_diagnostics, 'OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status='completed', output_text='Verifique a exceção nos logs.')
        response = client(app).post('/api/azul/ajuda', json={'message': f'Analise o erro #{log_id}'})
        args = create.call_args.kwargs
    assert response.status_code == 200
    assert response.json['mode'] == 'ia'
    assert args['store'] is False
    assert 'tools' not in args
    assert 'Não invente stack trace' in args['instructions']
    assert 'main.diagnostic_test' in args['instructions']
    for private in ['PRIVATE_NAME', 'PRIVATE_SECRET', 'PRIVATE_IP', '/private-path']:
        assert private not in json.dumps(args)


def test_provider_failure_retains_useful_local_diagnosis(app):
    log_id = seed_error(app)
    app.config['OPENAI_API_KEY'] = 'test-key'
    with patch.object(dev_diagnostics, 'OpenAI') as sdk:
        sdk.return_value.__enter__.return_value.responses.create.side_effect = OpenAIError('down')
        response = client(app).post('/api/azul/ajuda', json={'message': f'Analise o erro #{log_id}'})
    assert response.status_code == 200
    assert response.json['mode'] == 'guided'
    assert 'Orientação local' in response.json['answer']


@pytest.mark.parametrize('intent', ['dev_error:0', 'dev_error:nope', 'dev_error:99999'])
def test_invalid_or_missing_error_does_not_call_provider(app, intent):
    with patch.object(dev_diagnostics, 'OpenAI') as sdk:
        response = client(app).post('/api/azul/ajuda', json={'message': 'Analise esse erro', 'intent': intent})
    assert response.status_code == 400
    sdk.assert_not_called()


def test_quota_prevents_lookup(app):
    with patch.object(azul, 'consume_help_quota', return_value=False), patch.object(dev_diagnostics, 'get_dev_error_detail') as read:
        response = client(app).post('/api/azul/ajuda', json={'message': 'Analise o erro #1'})
    assert response.status_code == 429
    read.assert_not_called()


def test_followup_reloads_evidence_and_new_error_wins(app):
    log_id = seed_error(app)
    c = client(app)
    first = c.post('/api/azul/ajuda', json={'message': f'Analise o erro #{log_id}'}).json
    history = [{'role': 'user', 'content': f'Analise o erro #{log_id}'},
               {'role': 'assistant', 'content': first['answer']}]
    with patch.object(dev_diagnostics, 'get_dev_error_detail', wraps=dev_diagnostics.get_dev_error_detail) as read:
        response = c.post('/api/azul/ajuda', json={'message': 'Como corrigir esse erro?', 'history': history, 'chat_key': first['chat_key']})
    assert response.status_code == 200
    read.assert_called_once_with(log_id)
    assert dev_diagnostics.selected_id('Analise o erro #42', history) == 42
    assert dev_diagnostics.selected_id('Como cadastrar um cliente?', history) is None


def test_diagnosis_followups_are_system_topic_and_stop_at_other_task():
    history = [{'role': 'user', 'content': 'Analise o erro #1'}]
    for message in ['Como validar?', 'Onde corrigir?', 'Qual arquivo investigar?']:
        assert topics.evaluate(message, history).kind == 'allowed'
        assert dev_diagnostics.selected_id(message, history) == 1
    history.append({'role': 'user', 'content': 'Como cadastrar um cliente?'})
    assert dev_diagnostics.selected_id('Como corrigir esse erro?', history) is None
