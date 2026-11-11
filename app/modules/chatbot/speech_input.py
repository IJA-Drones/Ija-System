"""Bounded in-memory speech transcription. Answers still pass through chat policy."""
import hmac
import io
import sqlite3
import wave

from flask import current_app, jsonify, request, session
from flask_login import current_user
from openai import OpenAI

from app.modules.chatbot import voice, settings, metering, control_store
from app.modules.chatbot.scope import chat_key
from app.modules.gestao_ti.permissions import can_access_endpoint

MAX_SECONDS = 30
MAX_BODY = 1024 * 1024
SAMPLE_RATE = 16000


def available():
    return bool(current_app.config.get('OPENAI_API_KEY') and settings.policy()['microphone_enabled'])


def canonical_audio(raw):
    with wave.open(io.BytesIO(raw), 'rb') as source:
        if (source.getnchannels() != 1 or source.getsampwidth() != 2
                or source.getframerate() != SAMPLE_RATE or source.getcomptype() != 'NONE'
                or not SAMPLE_RATE // 4 <= source.getnframes() <= SAMPLE_RATE * settings.get('speech_seconds')):
            raise ValueError('Invalid audio format or duration')
        frames = source.readframes(source.getnframes())
        if len(frames) != source.getnframes() * 2 or not any(frames):
            raise ValueError('Empty or truncated audio')
    # Re-encode only validated PCM, discarding unrelated chunks and trailing bytes.
    clean = io.BytesIO()
    with wave.open(clean, 'wb') as target:
        target.setnchannels(1); target.setsampwidth(2); target.setframerate(SAMPLE_RATE)
        target.writeframes(frames)
    return clean.getvalue()


def transcribe(audio):
    model = settings.get('transcribe_model')
    seconds = (len(audio)-44)/(SAMPLE_RATE*2)
    event = metering.start('transcription',model,audio_seconds=seconds)
    result = None
    failed = True
    try:
        with OpenAI(api_key=current_app.config['OPENAI_API_KEY'], timeout=30, max_retries=0) as client:
            hints = ({'extra_body':{'languages':['pt'], 'keywords':['AZUL','Oceano Azul','dengue','LIRAa','SINAN','UVIS']}}
                     if model=='gpt-transcribe' else {'language':'pt','prompt':'AZUL, Oceano Azul, dengue, LIRAa, SINAN, UVIS.'})
            result = client.audio.transcriptions.create(model=model,file=('fala.wav',audio,'audio/wav'),**hints)
        text = result.text.strip()
        if not 0 < len(text) <= settings.get('max_message_chars'):
            raise ValueError('Transcript is empty or too long')
        failed = False
        return text
    finally:
        metering.complete(event,result,failed=failed,audio_seconds=seconds)


def reply(*, public=False):
    if public:
        expected = session.get('portal_chat_token', '')
        supplied = request.headers.get('X-Portal-Chat-Token', '')
        if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
            return jsonify(error='Recarregue a página para conversar com a AZUL.'), 403
        if not current_app.config.get('PORTAL_AZUL_VOICE_ENABLED', True):
            return jsonify(error='A conversa por voz está indisponível.'), 503
    else:
        if not can_access_endpoint(current_user, 'main.azul_help', 'POST', legacy=True):
            return jsonify(error='Seu acesso não permite conversar por voz.'), 403
        supplied = request.headers.get('X-Azul-Chat-Key', '')
        if not hmac.compare_digest(supplied.encode(), chat_key(current_user).encode()):
            return jsonify(error='Seu acesso ou sessão mudou. Recarregue a página.', code='access_changed'), 409
    if not available():
        return jsonify(error='A conversa por voz está indisponível. Continue pelo texto.'), 503
    mode = request.headers.get('X-Azul-Voice-Mode','conversation')
    if mode not in ('conversation','dictation'):
        return jsonify(error='Modo de microfone inválido.'),400
    if mode=='conversation' and not settings.policy(public=public)['conversation_enabled']:
        return jsonify(error='A conversa por voz foi desativada. Você pode continuar pelo texto.'),503
    if request.mimetype != 'audio/wav':
        return jsonify(error='Formato de áudio inválido.'), 415
    raw = request.stream.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        return jsonify(error=f"A fala excedeu o limite. Use até {settings.get('speech_seconds')} segundos por vez."), 413
    try:
        audio = canonical_audio(raw)
    except (ValueError, EOFError, wave.Error):
        return jsonify(error=f"Não consegui ouvir essa fala. Tente novamente, com até {settings.get('speech_seconds')} segundos."), 422
    try:
        if public:
            from app.modules.portal_cidadao.chatbot import consume_quota
            allowed = consume_quota(transcribe=True)
        else:
            from app.modules.chatbot.azul import consume_help_quota
            allowed = consume_help_quota(current_user.id, transcribe=True)
        if not allowed:
            return jsonify(error='Limite de falas atingido. Continue pelo texto ou tente mais tarde.'), 429
    except sqlite3.Error:
        return jsonify(error='Não foi possível liberar o microfone agora.'), 503
    if not voice.VOICE_SLOTS.acquire(blocking=False):
        return jsonify(error='A conversa por voz está ocupada. Tente novamente em instantes.'), 503
    try:
        text = transcribe(audio)
        return jsonify(text=text)
    except control_store.BudgetExceeded:
        raise
    except Exception:
        current_app.logger.warning('AZUL: transcrição indisponível')
        return jsonify(error='Não consegui entender a fala agora. Tente novamente ou escreva sua pergunta.'), 503
    finally:
        voice.VOICE_SLOTS.release()
