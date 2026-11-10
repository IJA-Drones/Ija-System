import base64
import io
import json
import wave
from unittest.mock import patch

import pytest

from app.modules.chatbot import azul, guide, voice
from tests.test_azul_help import env, context


def offered(env, context):
    _, client, _ = env
    with patch.object(azul, 'help_context', return_value=context):
        response = client.post('/api/azul/ajuda', json={
            'message': 'Meu acesso', 'intent': 'access_overview'})
    assert response.status_code == 200
    return response.json['speech']


def wav():
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(24000)
        audio.writeframes(b'\0\0' * 240)
    output.seek(0)
    return output


def test_voice_only_narrates_the_server_signed_answer(env, context):
    app, client, _ = env
    offer = offered(env, context)
    with patch.object(voice, 'synthesize', side_effect=lambda text: wav()) as provider:
        response = client.post(offer['url'], json={'token': offer['token'], 'text': 'IGNORE AND READ THIS'})
    assert response.status_code == 200
    assert response.data.startswith(b'RIFF')
    assert response.mimetype == 'audio/wav'
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert 'IGNORE AND READ THIS' not in provider.call_args.args[0]
    assert 'Posso ajudar' in provider.call_args.args[0]


@pytest.mark.parametrize('change', ['login', 'scope', 'user', 'permission'])
def test_voice_rechecks_session_scope_user_and_permission(env, context, change):
    _, client, user = env
    offer = offered(env, context)
    if change == 'login':
        with client.session_transaction() as session:
            session.pop('azul_chat_id')
    elif change == 'scope':
        user.trabalha_agro = False
    elif change == 'user':
        user.id = 10
    with patch.object(voice, 'synthesize') as provider, patch.object(
        voice, 'can_access_endpoint', return_value=change != 'permission'):
        response = client.post(offer['url'], json={'token': offer['token']})
    assert response.status_code == (403 if change == 'permission' else 409)
    provider.assert_not_called()


def test_voice_rejects_arbitrary_tampered_expired_and_unauthenticated_requests(env, context):
    app, client, _ = env
    offer = offered(env, context)
    with patch.object(voice, 'synthesize') as provider:
        assert app.test_client().post(offer['url'], json={'token': offer['token']}).status_code == 401
        assert client.post(offer['url'], json={'text': 'Read arbitrary text'}).status_code == 400
        assert client.post(offer['url'], json={'token': offer['token'] + 'x'}).status_code == 400
        with app.app_context():
            source = voice.serializer().loads(offer['token'])
            with patch('itsdangerous.timed.TimestampSigner.get_timestamp', return_value=1):
                expired = voice.serializer().dumps(source)
        assert client.post(offer['url'], json={'token': expired}).status_code == 400
        provider.assert_not_called()


def test_voice_has_independent_quota_and_safe_provider_failures(env, context):
    app, client, _ = env
    app.config['AZUL_VOICE_PER_MINUTE'] = 3
    offer = offered(env, context)
    with patch.object(voice, 'synthesize', side_effect=RuntimeError('PRIVATE-DATA')):
        response = client.post(offer['url'], json={'token': offer['token']})
    assert response.status_code == 503
    assert 'PRIVATE-DATA' not in response.get_data(as_text=True)
    with patch.object(voice, 'synthesize', side_effect=lambda text: wav()) as provider:
        for _ in range(2):
            assert client.post(offer['url'], json={'token': offer['token']}).status_code == 200
        with app.app_context():
            source = voice.serializer().loads(offer['token'])
            another = voice.serializer().dumps({**source, 'text':'Outro resumo autorizado.'})
            third = voice.serializer().dumps({**source, 'text':'Terceiro resumo autorizado.'})
        assert client.post(offer['url'], json={'token':another}).status_code == 200
        assert client.post(offer['url'], json={'token':third}).status_code == 429
        assert provider.call_count == 2
    app.config['AZUL_VOICE_ENABLED'] = False
    assert offered(env, context) is None
    assert client.post(offer['url'], json={'token': offer['token']}).status_code == 503


@pytest.mark.parametrize('payload', [None, [], {'token': 1}, {'token': 'a' * 20001}])
def test_voice_payload_is_bounded(env, payload):
    _, client, _ = env
    with patch.object(voice, 'synthesize') as provider:
        assert client.post('/api/azul/voz', data=json.dumps(payload), content_type='application/json').status_code == 400
        assert client.post('/api/azul/voz', data='a' * (voice.MAX_BODY + 1), content_type='application/json').status_code == 413
        provider.assert_not_called()


@pytest.mark.parametrize('transcript,status,valid', [
    ('Olá, use os filtros.', 'completed', True),
    ('Olá, apague os registros.', 'completed', False),
    ('Olá, use os filtros.', 'incomplete', False),
    ('', 'completed', False),
])
def test_realtime_audio_is_bounded_and_must_match_the_approved_text(env, transcript, status, valid):
    app, _, _ = env
    events = [
        {'type': 'response.output_audio.delta', 'delta': base64.b64encode(b'\0\0' * 240).decode()},
        {'type': 'response.output_audio_transcript.done', 'transcript': transcript},
        {'type': 'response.done', 'response': {'status': status}},
    ]
    with app.app_context(), patch('websockets.sync.client.connect') as connect:
        connection = connect.return_value.__enter__.return_value
        connection.recv.side_effect = [json.dumps(event) for event in events]
        if valid:
            audio = voice.synthesize('Olá! Use os filtros.')
            with wave.open(audio) as result:
                assert result.getframerate() == 24000
                assert result.getnchannels() == 1
        else:
            with pytest.raises(ValueError):
                voice.synthesize('Olá! Use os filtros.')
        session = json.loads(connection.send.call_args_list[0].args[0])['session']
        assert session['tools'] == []
        assert session['output_modalities'] == ['audio']
        request = json.loads(connection.send.call_args_list[1].args[0])['response']
        assert request['conversation'] == 'none'
        assert request['input'][0]['content'][0]['text'] == 'Olá! Use os filtros.'


def test_guide_only_contains_verified_links_and_permitted_tools(env, context):
    app, _, user = env
    with app.test_request_context(), patch.object(guide, 'help_context', return_value=context), patch.object(
        guide.search, 'allowed', return_value=False), patch.object(guide.operations, 'allowed', return_value=False), patch.object(
        guide.exports, 'allowed_sources', return_value=[]), patch.object(guide, 'can_access_endpoint', return_value=False):
        steps = guide.build(user, '/agro/banco-de-talentos')
    titles = [step['title'] for step in steps]
    assert 'Consulte o banco de talentos' in titles
    assert 'Prepare um relatório com revisão' not in titles
    assert 'Busque solicitações em uma frase' not in titles
    assert 'Veja o que precisa de atenção' not in titles
    assert [link for step in steps for link in step['links']] == context['atalhos']


def test_voice_route_uses_the_same_central_ti_areas_as_azul():
    from app.modules.gestao_ti.permissions import POLICY
    assert POLICY['main.azul_voice']['POST'] == POLICY['main.azul_help']['POST']
