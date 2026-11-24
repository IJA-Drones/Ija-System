"""Only reviewed, generic product phrases can become public voice recordings."""
import hashlib
import json
from pathlib import Path

from flask import current_app, url_for
from app.modules.chatbot import settings, voice_profiles

STYLE = 'marin-suave-ptbr-v1'
DIRECTORY = Path(__file__).resolve().parents[2] / 'static' / 'audio' / 'azul-falas'


def text_key(text, profile='original'):
    value = text if profile == 'original' else profile + '|' + voice_profiles.spec(profile)['style'] + '|' + text
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def manifest_path(profile):
    return DIRECTORY / ('manifest.json' if profile == 'original' else f'manifest-{profile}.json')


def catalog(profile=None):
    # These sources contain generic instructions only: no users, links or records.
    from app.modules.chatbot import guide, topics
    from app.modules.portal_cidadao.companion import QUICK_ANSWERS, WELCOME
    result = {'apresentacao': topics.IDENTITY, 'cumprimento': topics.GREETING,
              'agradecimento': topics.THANKS, 'boas-vindas-portal': WELCOME,
              'convite-dev': 'Gostaria de ouvir suas pendências de hoje?'}
    if (profile or settings.get('voice_profile')) != 'original':
        result.update({'amostra-voz': voice_profiles.SAMPLE, 'abertura-chamada': voice_profiles.WELCOME, 'escopo-chamada': voice_profiles.SCOPE})
    result.update({f'pergunta-portal-{index}': text
                   for index, text in enumerate(QUICK_ANSWERS.values(), 1)})
    result.update({f'guia-{key}': title + '. ' + body
                   for key, (title, body) in guide.RECORDED_STEPS.items()})
    return result


def find(text, profile=None):
    try:
        chosen = voice_profiles.spec(profile)
        manifest = json.loads(manifest_path(chosen['profile']).read_text())
        if (manifest.get('style') != chosen['style']
                or manifest.get('voice') != chosen['voice']
                or manifest.get('model') != chosen['model']):
            return None
        key = text_key(text, chosen['profile'])
        entry = manifest.get('clips', {}).get(key, {})
        path = DIRECTORY / (key + '.wav')
        if entry.get('text') != text or not path.is_file() or path.stat().st_size <= 44:
            return None
        return path, url_for('static', filename='audio/azul-falas/' + path.name,
                             v=entry['audio_sha256'][:12])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def decorate(offer, text):
    offer['profile'] = settings.get('voice_profile')
    offer['style'] = voice_profiles.spec()['style']
    recorded = find(text)
    if recorded:
        offer['clip'] = recorded[1]
    return offer
