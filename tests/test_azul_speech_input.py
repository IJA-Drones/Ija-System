import io
import wave
from unittest.mock import patch

import pytest

from app.modules.chatbot import speech_input, azul
from tests.test_portal_azul_companion import env
from tests.test_azul_help import env as private_env


def wav(seconds=.5,rate=16000,channels=1,silence=False):
    output=io.BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setnchannels(channels); audio.setsampwidth(2); audio.setframerate(rate)
        audio.writeframes((b'\0\0' if silence else b'\x01\0') * int(seconds*rate*channels))
    return output.getvalue()


def post(client,body,**kwargs):
    return client.post('/portal-cidadao/transcrever',data=body,content_type='audio/wav',
                       headers={'X-Portal-Chat-Token':'public-session-a'},**kwargs)


def test_transcription_is_bounded_canonical_and_does_not_generate_a_chat_answer(env):
    _, client = env
    raw=wav()
    with patch.object(speech_input,'transcribe',return_value='Como usar o portal?') as provider, patch.object(azul,'OpenAI') as answer:
        response=post(client,raw+b'PRIVATE-TRAILING-BYTES')
    assert response.status_code == 200
    assert response.json == {'text':'Como usar o portal?'}
    assert provider.call_args.args[0] == raw
    assert response.headers['Cache-Control'] == 'private, no-store'
    answer.assert_not_called()


@pytest.mark.parametrize('raw,status',[
    (b'not audio',422),(wav(31),422),(wav(rate=8000),422),
    (wav(channels=2),422),(wav(silence=True),422),(wav()[:-10],422),
    (b'x'*(speech_input.MAX_BODY+1),413),
])
def test_bad_or_oversized_audio_never_reaches_provider(env,raw,status):
    _, client=env
    with patch.object(speech_input,'transcribe') as provider:
        assert post(client,raw).status_code == status
    provider.assert_not_called()


def test_microphone_requires_public_session_or_authenticated_private_chat(env):
    _,client=env
    with patch.object(speech_input,'transcribe') as provider:
        assert client.post('/portal-cidadao/transcrever',data=wav(),content_type='audio/wav').status_code == 403
        assert client.post('/api/azul/transcrever',data=wav(),content_type='audio/wav').status_code == 401
        assert client.post('/portal-cidadao/transcrever',json={},headers={'X-Portal-Chat-Token':'public-session-a'}).status_code == 415
    provider.assert_not_called()


def test_transcription_has_an_independent_quota_and_safe_failures(env):
    app,client=env
    app.config['PORTAL_AZUL_TRANSCRIBE_DAILY_LIMIT']=1
    with patch.object(speech_input,'transcribe',side_effect=RuntimeError('PRIVATE-ERROR')) as provider:
        response=post(client,wav())
        assert response.status_code == 503
        assert 'PRIVATE-ERROR' not in response.get_data(as_text=True)
        assert post(client,wav()).status_code == 429
        assert provider.call_count == 1
    app.config['AZUL_CONVERSATION_ENABLED']=False
    assert post(client,wav()).status_code == 503


def test_private_transcription_rechecks_permission_and_chat_scope(private_env):
    _, client, user=private_env
    first=client.post('/api/azul/ajuda',json={'message':'Qual seu nome?'})
    headers={'X-Azul-Chat-Key':first.json['chat_key']}
    with patch.object(speech_input,'transcribe',return_value='Como usar o sistema?') as provider:
        response=client.post('/api/azul/transcrever',data=wav(),content_type='audio/wav',headers=headers)
        assert response.status_code == 200
        assert response.json['text']=='Como usar o sistema?'
        user.trabalha_agro=False
        assert client.post('/api/azul/transcrever',data=wav(),content_type='audio/wav',headers=headers).status_code==409
        with patch.object(speech_input,'can_access_endpoint',return_value=False):
            assert client.post('/api/azul/transcrever',data=wav(),content_type='audio/wav',headers=headers).status_code==403
    assert provider.call_count==1


def test_transcription_sdk_uses_only_the_validated_audio_and_language_hints(env):
    app,_=env
    from types import SimpleNamespace
    with app.app_context(),patch.object(speech_input,'OpenAI') as sdk:
        create=sdk.return_value.__enter__.return_value.audio.transcriptions.create
        create.return_value=SimpleNamespace(text='Qual seu nome?')
        assert speech_input.transcribe(wav())=='Qual seu nome?'
    assert create.call_args.kwargs['model']=='gpt-transcribe'
    assert create.call_args.kwargs['file'][1]==wav()
    assert create.call_args.kwargs['extra_body']['languages']==['pt']
