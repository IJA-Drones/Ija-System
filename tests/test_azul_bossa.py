import base64
import hashlib
from decimal import Decimal
import json
import wave
from unittest.mock import patch

from flask import g
import pytest
import sqlalchemy as sa

from app.modules.chatbot import control_store, live_voice, metering, recordings, settings, voice, voice_profiles
from tests.test_azul_help import env


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 0.1
        return self.value


def provider(connect, transcript, chunk=b'\x00\x02'*240, *, finalize=True, error=False):
    connection = connect.return_value.__enter__.return_value
    events = [{'type':'session.started'},
              {'type':'session.output_audio.delta','delta':base64.b64encode(chunk).decode()},
              {'type':'session.output_transcript.delta','delta':transcript}]
    if error:
        events = [{'type':'error','error':{'message':'PRIVATE-SENTINEL'}}]
    def receive(**kwargs):
        if events:
            return json.dumps(events.pop(0))
        sent = [json.loads(call.args[0])['type'] for call in connection.send.call_args_list]
        if finalize and 'session.close' in sent:
            return json.dumps({'type':'session.closed','usage':{'seconds':3}})
        raise TimeoutError()
    connection.recv.side_effect = receive
    return connection


def test_bossa_narration_uses_approved_voice_exact_text_no_backend_and_a_final_receipt(env):
    app, _, _ = env
    text = 'Confira a solicitação número 12.'
    with app.test_request_context(), patch('websockets.sync.client.connect') as connect, patch.object(
            live_voice.time, 'monotonic', Clock()):
        connection = provider(connect, text)
        audio = voice.synthesize(text, profile='bossa')
        with wave.open(audio) as wav:
            assert wav.getnchannels() == 1 and wav.getframerate() == 24000
        payload = json.loads(connection.send.call_args_list[0].args[0])['session']
        assert payload['audio']['output']['voice'] == 'bossa'
        assert payload['model'] == 'gpt-live-1.1' and payload['store'] is False
        assert payload['delegation'] == {'type':'client'} and 'tools' not in payload
        assert json.loads(payload['input'][1]['content'][0]['text']) == {'narration_text':text}
        assert connect.call_args.args[0] == 'wss://api.openai.com/v1/live/sessions'
        with control_store.current().connection() as conn:
            event = conn.execute(sa.select(control_store.events)).mappings().one()
        assert event['model'] == 'gpt-live-1.1'
        assert event['status'] == 'complete' and event['measured']
        assert event['audio_seconds'] == 3
        assert event['cost_usd'] == metering.nano(Decimal('3')/60*Decimal('0.05'))
        assert event['reserved_brl'] > event['cost_brl']


@pytest.mark.parametrize('transcript,chunk,finalize,error', [
    ('Confira o item 13.',b'\x00\x02'*240,True,False),
    ('Confira o item 12.',b'\x00',True,False),
    ('Confira o item 12.',b'\x00\x00'*240,True,False),
    ('Confira o item 12.',b'\x00\x02'*240,False,False),
    ('Confira o item 12.',b'\x00\x02'*240,True,True),
])
def test_bossa_rejects_changed_numbers_bad_audio_unfinalized_calls_and_provider_errors(env, transcript, chunk, finalize, error):
    app, _, _ = env
    with app.test_request_context(), patch('websockets.sync.client.connect') as connect, patch.object(
            live_voice.time, 'monotonic', Clock()):
        provider(connect, transcript, chunk, finalize=finalize, error=error)
        with pytest.raises((ValueError,TimeoutError)) as failure:
            voice.synthesize('Confira o item 12.', profile='bossa')
        assert 'PRIVATE-SENTINEL' not in str(failure.value)
        with control_store.current().connection() as conn:
            event = conn.execute(sa.select(control_store.events)).mappings().one()
        assert event['status'] == 'failed'
        if not finalize or error or len(chunk)%2:
            assert event['cost_brl'] is None and event['reserved_brl'] > 0


def test_bossa_budget_is_checked_before_connecting_to_provider(env):
    app, _, _ = env
    with app.test_request_context(), patch('websockets.sync.client.connect') as connect:
        settings.save({'daily_budget_brl':'0.01'}, settings.get('revision'), 'test')
        with pytest.raises(control_store.BudgetExceeded):
            voice.synthesize('Uma resposta curta.', profile='bossa')
        connect.assert_not_called()


def test_bossa_cannot_generate_from_an_unmetered_background_context(env):
    app, _, _ = env
    with app.app_context(), patch('websockets.sync.client.connect') as connect:
        with pytest.raises(RuntimeError, match='metered request context'):
            voice.synthesize('Uma resposta curta.', profile='bossa')
        connect.assert_not_called()


def test_saved_legacy_prices_gain_live_price_without_overwriting_custom_prices(env):
    app, _, _ = env
    with app.test_request_context():
        old_prices = {key:dict(value) for key,value in settings.RATES.items() if key != 'gpt-live-1.1'}
        old_prices['gpt-realtime-2.1']['audio_output'] = '71.00'
        with control_store.current().connection(write=True) as conn:
            conn.execute(control_store.configuration.update().values(data=json.dumps({'rates':old_prices})))
        g.pop('azul_settings',None)
        cfg = settings.current()
        assert cfg['rates']['gpt-live-1.1'] == {'minute':'0.05'}
        assert cfg['rates']['gpt-realtime-2.1']['audio_output'] == '71.00'


@pytest.mark.parametrize('seconds', [0, -1, 181, True, float('inf'), float('nan')])
def test_duration_reservation_requires_a_finite_positive_bound(seconds):
    with pytest.raises(ValueError):
        metering.estimate_reservation('voice', {'minute':'0.05'}, {}, seconds)


def test_bossa_settings_policy_never_offers_recordings_from_another_voice(env):
    app, _, _ = env
    app.config['AZUL_VOICE_PROFILE'] = 'bossa'
    with app.test_request_context():
        chosen = voice_profiles.spec()
        assert chosen['voice'] == 'bossa' and chosen['model'] == 'gpt-live-1.1'
        assert recordings.find(voice_profiles.SAMPLE, profile='jett')
        # Bossa may only serve its own approved, content-versioned library.
        found = recordings.find(voice_profiles.SAMPLE)
        if found:
            assert recordings.text_key(voice_profiles.SAMPLE,'bossa') in found[1]


def test_bossa_policy_also_builds_relative_clip_urls_during_startup(env):
    app, _, _ = env
    app.config['AZUL_VOICE_PROFILE'] = 'bossa'
    with app.app_context():
        policy = settings.policy()
        assert policy['call_welcome'].startswith('/static/audio/azul-falas/')
        assert '?v=' in policy['call_welcome']


@pytest.mark.parametrize('profile', ['bossa','jet'])
def test_live_generic_library_is_complete_and_matches_the_approved_text_and_hashes(env, profile):
    app, _, _ = env
    with app.test_request_context():
        manifest = json.loads(recordings.manifest_path(profile).read_text())
        catalog = recordings.catalog(profile)
        assert len(catalog) == 16
        for text in catalog.values():
            path, url = recordings.find(text, profile=profile)
            entry = manifest['clips'][recordings.text_key(text,profile)]
            assert entry['text'] == text
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['audio_sha256']
            assert url.endswith('?v='+entry['audio_sha256'][:12])
            with wave.open(str(path)) as wav:
                assert wav.getnchannels() == 1 and wav.getframerate() == 24000
                assert 1 < wav.getnframes()/wav.getframerate() < live_voice.MAX_SESSION_SECONDS


@pytest.mark.parametrize('profile', ['bossa','jet'])
def test_live_recorded_identity_needs_no_provider_or_generation_quota(env, profile):
    app, client, _ = env
    app.config['AZUL_VOICE_PROFILE'] = profile
    with patch.object(voice,'synthesize') as provider, patch(
            'app.modules.chatbot.azul.consume_help_quota') as quota:
        result = client.post('/api/azul/ajuda', json={'message':'Qual seu nome?'})
        signed = result.json['speech']
        assert signed['profile'] == profile and signed['clip']
        response = client.post(signed['url'], json={'token':signed['token']})
        assert response.status_code == 200
        assert response.headers['X-Azul-Audio-Source'] == 'recorded'
        assert response.data.startswith(b'RIFF')
        provider.assert_not_called(); quota.assert_not_called()


def test_jet_uses_the_approved_deep_velvety_direction_and_its_own_cache(env):
    app, _, _ = env
    assert voice_profiles.PROFILES['jet']['label'].startswith('JET ·')
    chosen = voice_profiles.spec('jet')
    assert chosen['model'] == 'gpt-live-1.1' and chosen['voice'] == 'bossa'
    assert chosen['style'] == 'azul-ptbr-jet-v1'
    direction = voice_profiles.instructions('jet')
    assert 'grave e confortável' in direction and 'baixo, quente e aveludado' in direction
    assert 'sensualidade discreta' in direction
    assert voice_profiles.spec('jett')['voice'] == 'shimmer'
    from app.modules.chatbot import audio_cache
    with app.app_context():
        app.config['AZUL_VOICE_PROFILE'] = 'bossa'
        previous = audio_cache.cache_key(voice_profiles.SAMPLE,['internal','same-user'])
        app.config['AZUL_VOICE_PROFILE'] = 'jet'
        current = audio_cache.cache_key(voice_profiles.SAMPLE,['internal','same-user'])
    assert current != previous
