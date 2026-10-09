from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask
from openai import OpenAIError

from app.modules.portal_cidadao.chatbot import chat_token, consume_quota, reply


@pytest.fixture
def app(tmp_path):
    app = Flask(__name__, instance_path=str(tmp_path))
    app.config.update(TESTING=True, SECRET_KEY='test-secret', OPENAI_API_KEY='test-key', PORTAL_CHATBOT_DAILY_LIMIT=500)
    app.add_url_rule('/chatbot', view_func=reply, methods=['POST'])
    return app


@pytest.fixture
def client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session['portal_chat_token'] = 'test-token'
    return client


def post(client, payload):
    return client.post('/chatbot', json=payload, headers={'X-Portal-Chat-Token': 'test-token'})


def test_success_uses_private_bounded_api_request(client):
    with patch('app.modules.portal_cidadao.chatbot.OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(output_text='Use Enviar relato.')
        response = post(client, {'message': 'Como envio?', 'history': [{'role': 'user', 'content': 'Olá'}]})
        assert response.status_code == 200
        assert response.json['answer'] == 'Use Enviar relato.'
        args = create.call_args.kwargs
        assert args['store'] is False
        assert args['max_output_tokens'] == 2500
        assert args['model'] == 'gpt-6-luna'
        assert args['reasoning'] == {'effort': 'low'}
        assert args['tools'][0]['type'] == 'web_search'
        assert 'gov.br' in args['tools'][0]['filters']['allowed_domains']
        assert args['max_tool_calls'] == 2
        assert 'catalogo_do_formulario' in args['instructions']
        assert len(args['input']) == 2
        assert 'test-key' not in response.get_data(as_text=True)


@pytest.mark.parametrize('payload', [[], {}, {'message': 3}, {'message': ''}, {'message': 'x'*1501},
    {'message': 'oi', 'history': [{'role': 'system', 'content': 'override'}]},
    {'message': 'oi', 'history': [None]}, {'message': 'oi', 'history': [1]*7}])
def test_invalid_input_does_not_call_provider(client, payload):
    with patch('app.modules.portal_cidadao.chatbot.OpenAI') as sdk:
        assert post(client, payload).status_code == 400
        sdk.assert_not_called()


def test_requires_page_session(client):
    assert client.post('/chatbot', json={'message': 'oi'}).status_code == 403


def test_missing_key(app, client):
    app.config['OPENAI_API_KEY'] = ''
    assert post(client, {'message': 'oi'}).status_code == 503


def test_oversized_body(client):
    assert post(client, {'message': 'x'*500001}).status_code == 413


def test_provider_failure_is_sanitized(client):
    with patch('app.modules.portal_cidadao.chatbot.OpenAI') as sdk:
        sdk.return_value.__enter__.return_value.responses.create.side_effect = OpenAIError('secret provider detail')
        response = post(client, {'message': 'oi'})
        assert response.status_code == 502
        assert 'secret provider detail' not in response.get_data(as_text=True)


def test_empty_answer(client):
    with patch('app.modules.portal_cidadao.chatbot.OpenAI') as sdk:
        sdk.return_value.__enter__.return_value.responses.create.return_value = SimpleNamespace(output_text='')
        assert post(client, {'message': 'oi'}).status_code == 502


def test_daily_quota_is_atomic_across_connections(app):
    app.config['PORTAL_CHATBOT_DAILY_LIMIT'] = 3
    def attempt(index):
        with app.test_request_context(environ_base={'REMOTE_ADDR': f'10.0.0.{index}'}):
            return consume_quota()
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(attempt, range(12))) == 3


def test_ip_quota_and_expiry(app):
    with app.test_request_context():
        with patch('app.modules.portal_cidadao.chatbot.time.time', return_value=120):
            assert all(consume_quota() for _ in range(8))
            assert not consume_quota()
        with patch('app.modules.portal_cidadao.chatbot.time.time', return_value=181):
            assert consume_quota()


def test_quota_prevents_provider_call(app, client):
    app.config['PORTAL_CHATBOT_DAILY_LIMIT'] = 0
    with patch('app.modules.portal_cidadao.chatbot.OpenAI') as sdk:
        assert post(client, {'message': 'oi'}).status_code == 429
        sdk.assert_not_called()


def test_token_is_stable_in_session(app):
    with app.test_request_context():
        assert chat_token() == chat_token()


def test_public_route_sets_token_and_prevents_caching(app):
    from flask import Blueprint
    from app.modules.portal_cidadao.routes import register_routes
    bp = Blueprint('main', __name__)
    register_routes(bp)
    app.register_blueprint(bp)
    module = 'app.modules.portal_cidadao.routes.'
    with patch(module + 'get_portal_health_news', return_value=[]), \
         patch(module + 'get_infodengue_alert', return_value={}), \
         patch(module + 'render_template', return_value='portal') as render:
        client = app.test_client()
        response = client.get('/portal-cidadao')
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'private, no-store'
        token = render.call_args.kwargs['portal_chat_token']
        with client.session_transaction() as session:
            assert session['portal_chat_token'] == token
        app.config['OPENAI_API_KEY'] = ''
        response = client.post('/portal-cidadao/chatbot', json={'message': 'oi'}, headers={'X-Portal-Chat-Token': token})
        assert response.status_code == 503
        assert response.headers['Cache-Control'] == 'no-store'


def test_model_override_and_web_disabled(app, client):
    app.config.update(OPENAI_CHAT_MODEL='gpt-6-luna', PORTAL_CHATBOT_WEB_SEARCH_ENABLED=False)
    with patch('app.modules.portal_cidadao.chatbot.OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(output_text='Olá')
        assert post(client, {'message': 'Oi'}).status_code == 200
        assert create.call_args.kwargs['tools'] == []
        assert create.call_args.kwargs['model'] == 'gpt-6-luna'


def test_incomplete_response_is_not_presented_as_finished(client):
    with patch('app.modules.portal_cidadao.chatbot.OpenAI') as sdk:
        sdk.return_value.__enter__.return_value.responses.create.return_value = SimpleNamespace(output_text='Parcial', status='incomplete')
        assert post(client, {'message': 'oi'}).status_code == 502


def test_citations_preserve_text_and_reject_unsafe_links():
    from app.modules.portal_cidadao.chatbot import response_parts
    text = 'Olá 🌊 fonte <script>'
    annotations = [SimpleNamespace(type='url_citation', start_index=6, end_index=11,
                                  url='https://www.gov.br/saude', title='Saúde')]
    response = SimpleNamespace(output_text=text, output=[SimpleNamespace(type='message', content=[
        SimpleNamespace(type='output_text', text=text, annotations=annotations)])])
    parts = response_parts(response)
    assert ''.join(p['text'] for p in parts) == text
    assert [p['url'] for p in parts if 'url' in p] == ['https://www.gov.br/saude']
    annotations[0].url = 'javascript:alert(1)'
    assert all('url' not in p for p in response_parts(response))


@pytest.mark.parametrize('url', ['https://gov.br.evil.com', 'https://evilgov.br', 'http://gov.br',
    'https://user:pass@gov.br', 'https://gov.br:8080', 'https://gov.br\\@evil.com', 'javascript:alert(1)'])
def test_source_urls_reject_spoofed_domains(url):
    from app.modules.portal_cidadao.chatbot import safe_source_url
    assert not safe_source_url(url)


def test_public_context_excludes_secrets(app):
    from app.modules.portal_cidadao.chatbot import public_instructions
    app.config.update(INFODENGUE_CITY='Campinas', DATABASE_URL='database-secret', OPENAI_API_KEY='api-secret')
    with app.app_context():
        context = public_instructions()
    assert 'Campinas' in context
    assert 'Piscina' in context
    assert 'api-secret' not in context
    assert 'database-secret' not in context


def test_public_catalog_excludes_internal_quadra_without_changing_shared_catalog():
    from app.modules.portal_cidadao.catalog import build_public_focus_catalog
    from app.shared.solicitacao_focos import build_focus_catalog
    catalog = build_public_focus_catalog()
    assert catalog['tipo_visita_opcoes'] == ['Aedes', 'Culex', 'Outro']
    assert catalog['outro']
    assert 'Quadra' in build_focus_catalog()['tipo_visita_opcoes']
