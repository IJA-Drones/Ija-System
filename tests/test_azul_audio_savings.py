import hashlib
import json
from pathlib import Path
import wave
from unittest.mock import patch

from app.modules.chatbot import audio_cache, recordings, topics, voice
from tests.test_azul_help import context, env
from tests.test_azul_voice import offered, wav


def test_recorded_identity_uses_no_provider_or_generation_quota(env):
    _, client, _ = env
    with patch.object(voice, 'synthesize') as provider, patch(
            'app.modules.chatbot.azul.consume_help_quota') as quota:
        response = client.post('/api/azul/ajuda', json={'message':'Qual seu nome?'})
        signed = response.json['speech']
        assert signed['clip'].startswith('/static/audio/azul-falas/')
        audio = client.post(signed['url'], json={'token':signed['token']})
        assert audio.status_code == 200
        assert audio.data.startswith(b'RIFF')
        assert audio.headers['X-Azul-Audio-Source'] == 'recorded'
        provider.assert_not_called()
        quota.assert_not_called()


def test_dynamic_audio_reuses_content_across_new_tokens_only_in_the_same_scope(env, context):
    app, client, user = env
    signed = offered(env, context)
    with app.app_context():
        source = voice.serializer().loads(signed['token'])
        renewed = voice.serializer().dumps({**source,'renewed':True})
    with patch.object(voice, 'synthesize', side_effect=lambda text:wav()) as provider:
        first = client.post(signed['url'], json={'token':signed['token']})
        second = client.post(signed['url'], json={'token':renewed})
        assert first.headers['X-Azul-Audio-Source'] == 'generated'
        assert second.headers['X-Azul-Audio-Source'] == 'memory'
        assert first.data == second.data
        assert provider.call_count == 1
        user.trabalha_agro = False
        assert client.post(signed['url'], json={'token':renewed}).status_code == 409
        updated = offered(env, context)
        assert client.post(updated['url'], json={'token':updated['token']}).headers['X-Azul-Audio-Source'] == 'generated'
        assert provider.call_count == 2
    assert not list(Path(app.instance_path).rglob('*.wav'))


def test_cached_audio_expires_and_voice_configuration_invalidates_reuse(env, context):
    app, client, _ = env
    signed = offered(env, context)
    with patch.object(voice, 'synthesize', side_effect=lambda text:wav()) as provider:
        assert client.post(signed['url'], json={'token':signed['token']}).status_code == 200
        now = audio_cache.time.monotonic()
        with patch.object(audio_cache.time, 'monotonic', return_value=now+audio_cache.TTL+1):
            assert client.post(signed['url'], json={'token':signed['token']}).headers['X-Azul-Audio-Source'] == 'generated'
        app.config['AZUL_VOICE'] = 'another-voice'
        assert client.post(signed['url'], json={'token':signed['token']}).headers['X-Azul-Audio-Source'] == 'generated'
        assert provider.call_count == 3


def test_duplicate_pending_audio_never_spends_a_second_generation(env, context):
    app, client, _ = env
    signed = offered(env, context)
    with app.app_context():
        source = voice.serializer().loads(signed['token'])
        cache = audio_cache.current()
        key = audio_cache.cache_key(source['text'], ['internal',source['user'],source['chat']])
        assert cache.claim(key)
    with patch.object(voice, 'synthesize') as provider, patch(
            'app.modules.chatbot.azul.consume_help_quota') as quota:
        assert client.post(signed['url'], json={'token':signed['token']}).status_code == 503
        provider.assert_not_called(); quota.assert_not_called()
    cache.release(key)


def test_cache_stays_bounded_and_releases_expired_bytes(monkeypatch):
    monkeypatch.setattr(audio_cache,'MAX_BYTES',8)
    monkeypatch.setattr(audio_cache,'MAX_ENTRIES',2)
    cache = audio_cache.AudioCache()
    cache.put('a',b'1234'); cache.put('b',b'5678')
    assert cache.get('a') == b'1234'
    cache.put('c',b'abcd')
    assert cache.get('b') is None
    assert cache.size == 8
    now = audio_cache.time.monotonic()
    with patch.object(audio_cache.time,'monotonic',return_value=now+audio_cache.TTL+1):
        assert cache.get('a') is None
        assert cache.size == 0


def test_every_reviewed_recording_matches_its_manifest_and_current_script(env):
    app, _, _ = env
    manifest = json.loads((recordings.DIRECTORY/'manifest.json').read_text())
    with app.test_request_context():
        for text in recordings.catalog().values():
            recorded = recordings.find(text)
            assert recorded is not None
            path, url = recorded
            assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest['clips'][recordings.text_key(text)]['audio_sha256']
            with wave.open(str(path)) as audio:
                assert audio.getnchannels() == 1
                assert audio.getframerate() == 24000
                assert 1 < audio.getnframes()/audio.getframerate() < 45
            assert url.startswith('/static/audio/azul-falas/')
        assert recordings.find(topics.IDENTITY+' Dado privado adicional.') is None


def test_missing_or_stale_recording_falls_back_without_publishing_a_wrong_clip(env, tmp_path, monkeypatch):
    app, _, _ = env
    manifest = json.loads((recordings.DIRECTORY/'manifest.json').read_text())
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(recordings,'DIRECTORY',tmp_path)
    with app.test_request_context():
        assert recordings.find(topics.IDENTITY) is None
