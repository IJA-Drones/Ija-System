import base64
import json
import wave
from unittest.mock import patch

import pytest
from flask import Flask

from app.modules.chatbot import audio_cache, recordings, settings, voice, voice_profiles
from tests.test_azul_help import env


def test_bossa_is_default_and_named_profiles_are_validated(env):
    app, _, _ = env
    with app.app_context():
        app.config.pop('AZUL_VOICE_PROFILE')
        assert settings.defaults()['voice_profile'] == 'bossa'
        for name in ('bossa', 'reyna', 'jett', 'original'):
            assert settings.validate({'voice_profile':name})['voice_profile'] == name
        with pytest.raises(settings.ValidationError):
            settings.validate({'voice_profile':'untrusted-voice'})


@pytest.mark.parametrize('name,base', [('reyna','coral'), ('jett','shimmer')])
def test_new_profiles_use_distinct_timbres_full_model_and_native_brazilian_direction(env, name, base):
    app, _, _ = env
    text = 'Bom dia! Gostaria de ouvir suas pendências de hoje?'
    events = [{'type':'response.output_audio.delta','delta':base64.b64encode(b'\0\0'*240).decode()},
              {'type':'response.output_audio_transcript.done','transcript':text},
              {'type':'response.done','response':{'status':'completed'}}]
    with app.app_context(), patch('websockets.sync.client.connect') as connect:
        connection=connect.return_value.__enter__.return_value
        connection.recv.side_effect=[json.dumps(item) for item in events]
        audio=voice.synthesize(text, profile=name)
        session=json.loads(connection.send.call_args_list[0].args[0])['session']
        assert session['audio']['output']['voice'] == base
        assert 'native Brazilian woman' in session['instructions']
        assert 'French or European Portuguese' in session['instructions']
        assert 'model=gpt-realtime-2.1' in connect.call_args.args[0]
        assert session['tools'] == []
        request = json.loads(connection.send.call_args_list[1].args[0])['response']
        assert json.loads(request['input'][0]['content'][0]['text']) == {'narration_text': text}
        with wave.open(audio) as wav:
            assert wav.getframerate() == 24000


def test_profile_changes_invalidate_memory_audio_and_never_use_the_legacy_recording(env):
    app, _, _ = env
    with app.app_context():
        app.config['AZUL_VOICE_PROFILE']='original'
        old=audio_cache.cache_key(voice_profiles.SAMPLE,['scope'])
        app.config['AZUL_VOICE_PROFILE']='reyna'
        reyna=audio_cache.cache_key(voice_profiles.SAMPLE,['scope'])
        app.config['AZUL_VOICE_PROFILE']='jett'
        jett=audio_cache.cache_key(voice_profiles.SAMPLE,['scope'])
    assert len({old,reyna,jett}) == 3
    assert recordings.text_key(voice_profiles.SAMPLE,'reyna') != recordings.text_key(voice_profiles.SAMPLE,'jett')
    with app.test_request_context():
        for name in ('reyna','jett'):
            for text in (voice_profiles.SAMPLE,voice_profiles.WELCOME,voice_profiles.SCOPE,'Gostaria de ouvir suas pendências de hoje?'):
                found=recordings.find(text, profile=name)
                assert found is not None
                path,url=found
                assert path.name.startswith(recordings.text_key(text,name))
                assert url.startswith('/static/audio/azul-falas/')
                with wave.open(str(path)) as wav:
                    assert 1 < wav.getnframes()/wav.getframerate() < 45


def test_policy_exposes_selected_opening_clips(env):
    app,_,_=env
    app.config['AZUL_VOICE_PROFILE']='jett'
    with app.test_request_context():
        policy=settings.policy()
    assert policy['voice_profile']=='jett'
    assert recordings.text_key(voice_profiles.WELCOME,'jett') in policy['call_welcome']
    assert recordings.text_key(voice_profiles.SCOPE,'jett') in policy['call_scope']


def test_jett_restores_v2_server_voice_and_requires_api_key(env):
    app, _, user = env
    app.config['AZUL_VOICE_PROFILE'] = 'jett'
    app.config['OPENAI_API_KEY'] = ''
    with app.test_request_context(), patch('websockets.sync.client.connect') as connect:
        chosen = voice_profiles.spec('jett')
        offered = voice.offer('Bom dia! Suas pendências estão disponíveis.', user)
        policy = settings.policy()
        direction = voice_profiles.instructions('jett')
    assert chosen['voice'] == 'shimmer'
    assert chosen['model'] == 'gpt-realtime-2.1'
    assert chosen['style'] == 'azul-ptbr-jett-v2'
    assert 'gentle, sweet adult feminine voice' in direction
    assert 'spontaneous pauses' in direction
    assert offered is None
    assert policy['sound_enabled'] is False
    assert policy['voice_engine'] == 'server'
    connect.assert_not_called()
