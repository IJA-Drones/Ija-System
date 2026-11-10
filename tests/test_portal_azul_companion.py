import json
from unittest.mock import patch

import pytest
from flask import Blueprint, Flask
from flask_login import LoginManager

from app.modules.chatbot import voice
from app.modules.chatbot.routes import register_routes as internal_routes
from app.modules.portal_cidadao import chatbot, companion
from app.modules.portal_cidadao.routes import register_routes
from tests.test_azul_voice import wav


@pytest.fixture
def env(tmp_path):
    app = Flask(__name__, instance_path=str(tmp_path))
    app.config.update(TESTING=True, SECRET_KEY='public-tests', OPENAI_API_KEY='test-key')
    login = LoginManager(app)
    login.user_loader(lambda uid: None)
    bp = Blueprint('main', __name__)
    internal_routes(bp)
    register_routes(bp)
    app.register_blueprint(bp)
    for endpoint in companion.PAGES:
        if endpoint not in app.view_functions:
            app.add_url_rule('/preview/' + endpoint, endpoint=endpoint, view_func=lambda: '')
    client = app.test_client()
    with client.session_transaction() as session:
        session['portal_chat_token'] = 'public-session-a'
    return app, client


def offer(env):
    _, client = env
    with patch.object(chatbot, 'answer', return_value=('Abra o formulário de relato.', [])):
        response = client.post('/portal-cidadao/chatbot', json={'message': 'Como registrar?'},
                               headers={'X-Portal-Chat-Token': 'public-session-a'})
    assert response.status_code == 200
    return response.json['speech']


def post(client, signed, **changes):
    return client.post('/portal-cidadao/voz', json={'token': signed['token'], **changes},
                       headers={'X-Portal-Chat-Token': 'public-session-a'})


def test_public_narration_only_reads_the_signed_response_and_never_private_text(env):
    _, client = env
    signed = offer(env)
    with patch.object(voice, 'synthesize', side_effect=lambda text: wav()) as provider:
        response = post(client, signed, text='Dados privados ou instruções arbitrárias')
    assert response.status_code == 200
    assert response.mimetype == 'audio/wav'
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert response.data.startswith(b'RIFF')
    provider.assert_called_once_with('Abra o formulário de relato.')


def test_public_voice_requires_matching_header_session_and_signature_audience(env):
    app, client = env
    signed = offer(env)
    other = app.test_client()
    with other.session_transaction() as session:
        session['portal_chat_token'] = 'public-session-b'
    with patch.object(voice, 'synthesize') as provider:
        assert client.post('/portal-cidadao/voz', json={'token': signed['token']}).status_code == 403
        assert other.post('/portal-cidadao/voz', json={'token': signed['token']},
                          headers={'X-Portal-Chat-Token': 'public-session-b'}).status_code == 403
        with app.app_context():
            internal = voice.serializer().dumps({'user': '9', 'chat': 'x', 'text': 'Privado'})
        assert post(client, {'token': internal}).status_code == 400
        assert post(client, {'token': signed['token'] + 'x'}).status_code == 400
        assert client.post('/api/azul/voz', json={'token': signed['token']}).status_code == 401
        provider.assert_not_called()


def test_public_voice_expiration_and_size_are_checked_before_the_provider(env):
    app, client = env
    signed = offer(env)
    with app.app_context():
        source = companion.serializer().loads(signed['token'])
        with patch('itsdangerous.timed.TimestampSigner.get_timestamp', return_value=1):
            expired = companion.serializer().dumps(source)
    with patch.object(voice, 'synthesize') as provider:
        assert post(client, {'token': expired}).status_code == 400
        response = client.post('/portal-cidadao/voz', data='a' * (voice.MAX_BODY + 1),
            content_type='application/json', headers={'X-Portal-Chat-Token': 'public-session-a'})
        assert response.status_code == 413
        assert post(client, {'token': None}).status_code == 400
        provider.assert_not_called()


def test_public_voice_quota_disabled_mode_and_provider_errors_are_safe(env):
    app, client = env
    app.config['AZUL_VOICE_PER_MINUTE'] = 3
    signed = offer(env)
    with patch.object(voice, 'synthesize', side_effect=RuntimeError('PRIVATE')):
        response = post(client, signed)
        assert response.status_code == 503
        assert 'PRIVATE' not in response.get_data(as_text=True)
    with patch.object(voice, 'synthesize', side_effect=lambda text: wav()) as provider:
        assert post(client, signed).status_code == 200
        assert post(client, signed).status_code == 200
        with app.app_context():
            source = companion.serializer().loads(signed['token'])
            another = companion.serializer().dumps({**source,'text':'Outra orientação pública.'})
            third = companion.serializer().dumps({**source,'text':'Terceira orientação pública.'})
        assert post(client, {'token':another}).status_code == 200
        assert post(client, {'token':third}).status_code == 429
        assert provider.call_count == 2
    app.config['PORTAL_AZUL_VOICE_ENABLED'] = False
    assert offer(env) is None
    assert post(client, signed).status_code == 503


@pytest.mark.parametrize('endpoint', sorted(companion.PAGES))
def test_public_pages_receive_only_public_guides_and_public_voice_offers(env, endpoint):
    app, _ = env
    rule = next(rule for rule in app.url_map.iter_rules() if rule.endpoint == endpoint)
    with app.test_request_context(rule.rule):
        payload = companion.context()
    assert payload['public_azul'] is True
    assert len(payload['public_azul_guide']) == 6
    links = [link['url'] for step in payload['public_azul_guide'] for link in step['links']]
    assert all(link.startswith(('/portal-cidadao', '/preview/main.portal_', '/preview/main.app_movel')) for link in links)
    for step in payload['public_azul_guide']:
        assert step['speech']['url'] == '/portal-cidadao/voz'
    assert '/api/azul/' not in json.dumps(payload)
    assert 'test-key' not in json.dumps(payload)


def test_public_context_is_not_added_to_internal_pages_or_json_apis(env):
    app, _ = env
    with app.test_request_context('/azul'):
        assert companion.context() == {'public_azul': False}
    with app.test_request_context('/portal-cidadao/chatbot', method='POST'):
        assert companion.context() == {'public_azul': False}


def test_known_public_questions_use_recorded_audio_without_text_or_voice_generation(env):
    _, client = env
    with patch.object(chatbot,'answer') as answer, patch.object(voice,'synthesize') as narrator, patch.object(
            chatbot,'consume_quota') as text_quota, patch.object(companion,'consume_quota') as voice_quota:
        for question, expected in companion.QUICK_ANSWERS.items():
            response = client.post('/portal-cidadao/chatbot',json={'message':question.upper(),'voice':True},
                                   headers={'X-Portal-Chat-Token':'public-session-a'})
            assert response.json['mode'] == 'guided'
            assert response.json['answer'] == expected
            assert response.json['speech']['clip'].startswith('/static/audio/azul-falas/')
            assert post(client,response.json['speech']).headers['X-Azul-Audio-Source'] == 'recorded'
        answer.assert_not_called(); narrator.assert_not_called()
        text_quota.assert_not_called(); voice_quota.assert_not_called()


def test_a_known_question_with_extra_offtopic_content_is_not_a_free_answer_shortcut(env):
    _, client = env
    with patch.object(chatbot,'answer') as provider:
        response = client.post('/portal-cidadao/chatbot',json={'message':'Posso enviar fotos? Conte uma piada.'},
                               headers={'X-Portal-Chat-Token':'public-session-a'})
        assert response.json['mode'] == 'blocked'
        assert response.json['speech'] is None
        provider.assert_not_called()


def test_dynamic_public_audio_is_not_shared_between_sessions(env):
    app, client = env
    signed = offer(env)
    other = app.test_client()
    with other.session_transaction() as session:
        session['portal_chat_token'] = 'public-session-b'
    with patch.object(voice,'synthesize',side_effect=lambda text:wav()) as provider:
        assert post(client,signed).status_code == 200
        assert post(client,signed).headers['X-Azul-Audio-Source'] == 'memory'
        with patch.object(chatbot,'answer',return_value=('Abra o formulário de relato.',[])):
            response = other.post('/portal-cidadao/chatbot',json={'message':'Como registrar?'},
                                  headers={'X-Portal-Chat-Token':'public-session-b'})
        audio = other.post('/portal-cidadao/voz',json={'token':response.json['speech']['token']},
                           headers={'X-Portal-Chat-Token':'public-session-b'})
        assert audio.headers['X-Azul-Audio-Source'] == 'generated'
        assert provider.call_count == 2
