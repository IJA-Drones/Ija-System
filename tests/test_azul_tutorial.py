import json
import re
from unittest.mock import patch

import pytest
from flask import Blueprint, Flask
from flask_login import LoginManager

from app.modules.chatbot import tutorial, voice
from app.modules.chatbot.routes import register_routes
from app.modules.portal_cidadao.routes import register_routes as public_routes
from tests.test_azul_help import User


@pytest.fixture
def env(tmp_path):
    app = Flask(__name__, instance_path=str(tmp_path), template_folder='../app/templates',
                static_folder='../app/static')
    app.config.update(TESTING=True, SECRET_KEY='training-tests', OPENAI_API_KEY='test-not-a-key')
    login = LoginManager(app)
    login.user_loader(lambda uid: User())
    bp = Blueprint('main', __name__)
    register_routes(bp)
    public_routes(bp)
    app.register_blueprint(bp)
    return app, app.test_client()


def catalog(response):
    content = response.get_data(as_text=True)
    return json.loads(re.search(r'id="tutorialCatalog">(.*?)</script>', content, re.S)[1])


def login(client):
    with client.session_transaction() as session:
        session['_user_id'] = '9'
        session['_fresh'] = True


def test_public_room_never_reads_internal_navigation_or_generates_audio(env):
    _, client = env
    with patch.object(tutorial, 'help_context', side_effect=AssertionError('private read')), patch.object(
            voice, 'synthesize') as provider:
        response = client.get('/azul/tutorial?publico=publico&prefeitura_id=123&nome=PRIVATE-SENTINEL')
    assert response.status_code == 200
    lessons = catalog(response)
    assert {lesson['id'] for lesson in lessons} == {'foco', 'saude', 'boletim'}
    assert 'PRIVATE-SENTINEL' not in response.get_data(as_text=True)
    assert '/api/azul/' not in response.get_data(as_text=True)
    assert all(item['speech']['url'] == '/portal-cidadao/voz' for lesson in lessons for item in lesson['steps'])
    assert response.headers['Cache-Control'] == 'private, no-store'
    provider.assert_not_called()


def test_practice_room_blocks_network_forms_and_privileged_frames(env):
    _, client = env
    response = client.get('/azul/tutorial')
    policy = response.headers['Content-Security-Policy']
    for directive in ["connect-src 'none'", "form-action 'none'", "default-src 'none'",
                      'sandbox allow-scripts', "frame-ancestors 'self'", "script-src 'self'"]:
        assert directive in policy
    assert 'allow-same-origin' not in policy
    assert 'allow-top-navigation' not in policy
    assert 'unsafe-inline' not in policy
    assert client.post('/azul/tutorial', json={'action': 'send'}).status_code == 405


def test_internal_room_requires_authentication_and_current_azul_permission(env):
    _, client = env
    assert client.get('/azul/tutorial?publico=sistema').status_code == 401
    login(client)
    with patch.object(tutorial, 'can_access_endpoint', return_value=False), patch.object(
            tutorial, 'help_context') as navigation:
        assert client.get('/azul/tutorial?publico=sistema').status_code == 403
        navigation.assert_not_called()
    assert client.get('/azul/tutorial?publico=untrusted').status_code == 400


def test_internal_catalog_is_filtered_by_verified_modules_not_query_parameters(env):
    _, client = env
    login(client)
    with patch.object(tutorial, 'help_context', return_value={'atalhos': [
            {'modulo': 'agro.clientes', 'url': '/private/actual-resource'}]}):
        response = client.get('/azul/tutorial?publico=sistema&module=financeiro')
    assert response.status_code == 200
    lessons = catalog(response)
    assert {lesson['id'] for lesson in lessons} == {'clientes', 'foco', 'saude', 'boletim'}
    assert '/private/actual-resource' not in response.get_data(as_text=True)
    assert all(item['speech']['url'] == '/api/azul/voz' for lesson in lessons for item in lesson['steps'])


def test_all_authorized_training_tracks_have_synthetic_records_and_bounded_narration(env):
    _, client = env
    login(client)
    modules = list(tutorial.INTERNAL) + ['financeiro.lancamentos']
    with patch.object(tutorial, 'help_context', return_value={'atalhos': [{'modulo': module} for module in modules]}):
        response = client.get('/azul/tutorial?publico=sistema')
    lessons = catalog(response)
    assert len({lesson['id'] for lesson in lessons}) == 11
    for lesson in lessons:
        assert 4 <= len(lesson['steps']) <= 7
        assert all(0 < len(item['title'] + '. ' + item['body']) <= voice.MAX_TEXT for item in lesson['steps'])
        assert all(item['target'] and item['action'] for item in lesson['steps'])
        if lesson['kind'] == 'lista':
            assert any('DEMO' in value or 'Exemplo' in value for _, value in lesson['fields'])


def test_missing_voice_key_keeps_every_practice_step_available(env):
    app, client = env
    app.config['OPENAI_API_KEY'] = ''
    response = client.get('/azul/tutorial')
    assert response.status_code == 200
    assert all(item['speech'] is None for lesson in catalog(response) for item in lesson['steps'])
