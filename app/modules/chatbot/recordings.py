"""Only reviewed, generic product phrases can become public voice recordings."""
import hashlib
import json
from pathlib import Path

from flask import current_app, url_for
from app.modules.chatbot import settings

STYLE = 'marin-suave-ptbr-v1'
DIRECTORY = Path(__file__).resolve().parents[2] / 'static' / 'audio' / 'azul-falas'


def text_key(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def catalog():
    # These sources contain generic instructions only: no users, links or records.
    from app.modules.chatbot import guide, topics
    from app.modules.portal_cidadao.companion import QUICK_ANSWERS, WELCOME
    result = {'apresentacao': topics.IDENTITY, 'cumprimento': topics.GREETING,
              'agradecimento': topics.THANKS, 'boas-vindas-portal': WELCOME}
    result.update({f'pergunta-portal-{index}': text
                   for index, text in enumerate(QUICK_ANSWERS.values(), 1)})
    result.update({f'guia-{key}': title + '. ' + body
                   for key, (title, body) in guide.RECORDED_STEPS.items()})
    return result


def find(text):
    try:
        manifest = json.loads((DIRECTORY / 'manifest.json').read_text())
        if (manifest.get('style') != STYLE
                or manifest.get('voice') != settings.get('voice_name')
                or manifest.get('model') != settings.get('voice_model')):
            return None
        key = text_key(text)
        entry = manifest.get('clips', {}).get(key, {})
        path = DIRECTORY / (key + '.wav')
        if entry.get('text') != text or not path.is_file() or path.stat().st_size <= 44:
            return None
        return path, url_for('static', filename='audio/azul-falas/' + path.name,
                             v=entry['audio_sha256'][:12])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def decorate(offer, text):
    recorded = find(text)
    if recorded:
        offer['clip'] = recorded[1]
    return offer
