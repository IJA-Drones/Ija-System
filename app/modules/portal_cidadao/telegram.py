"""Azul no Telegram (Bot API). Webhook: POST /webhooks/telegram/<segredo>.

Mesma Azul do portal e do WhatsApp; histórico curto por chat em memória; limite por chat.
Configuração: TELEGRAM_BOT_TOKEN e TELEGRAM_WEBHOOK_SECRET (qualquer texto longo).
"""

import hmac
import threading

import requests
from flask import current_app, jsonify, request
from openai import OpenAIError

from . import chatbot
from .whatsapp import WHATSAPP_NOTE, _allowed, _history_for, _plain, _remember

API = "https://api.telegram.org/bot{token}/{method}"


def configured():
    return bool(current_app.config.get("TELEGRAM_BOT_TOKEN") and current_app.config.get("TELEGRAM_WEBHOOK_SECRET"))


def send_text(chat_id, text):
    url = API.format(token=current_app.config["TELEGRAM_BOT_TOKEN"], method="sendMessage")
    response = requests.post(url, json={"chat_id": chat_id, "text": text[:4000]}, timeout=30)
    response.raise_for_status()
    return response.json()


def bot_link(payload=""):
    user = current_app.config.get("TELEGRAM_BOT_USERNAME") or "ija_vigilancia_bot"
    return f"https://t.me/{user}" + (f"?start={payload}" if payload else "")


def link_code_for(user):
    """Código de vínculo do usuário (gera uma vez). Deep link: t.me/<bot>?start=v_<código>."""
    import secrets
    from app.extensions import db
    if not user.telegram_codigo:
        user.telegram_codigo = secrets.token_urlsafe(24).replace("-", "x").replace("_", "y")[:32]
        db.session.commit()
    return user.telegram_codigo


def link_account(code, chat_id):
    from app.extensions import db
    from app.models import Usuario
    user = Usuario.query.filter_by(telegram_codigo=code).first() if code else None
    if user is None:
        return None
    user.telegram_chat_id = str(chat_id)
    db.session.commit()
    return user


def notify_users(users, title, body):
    """Envia a mensagem aos usuários com Telegram vinculado. Devolve quantos receberam."""
    if not current_app.config.get("TELEGRAM_BOT_TOKEN"):
        return 0
    sent = 0
    for user in users:
        if not getattr(user, "telegram_chat_id", None):
            continue
        try:
            send_text(user.telegram_chat_id, f"{title}\n\n{body}")
            sent += 1
        except requests.RequestException:
            current_app.logger.warning("Telegram: falha ao notificar usuário %s", user.id)
    return sent


def handle(app, chat_id, text, portal_url):
    with app.app_context():
        key = f"tg:{chat_id}"
        if not _allowed(key):
            return
        messages = _history_for(key) + [{"role": "user", "content": text}]
        try:
            if not current_app.config.get("OPENAI_API_KEY"):
                raise chatbot.ChatbotError("Assistente indisponível no momento.")
            reply, _ = chatbot.answer(messages, extra_instructions=WHATSAPP_NOTE.replace("WhatsApp", "Telegram").format(portal=portal_url))
            reply = _plain(reply)
        except (chatbot.ChatbotError, OpenAIError):
            current_app.logger.warning("Telegram chatbot: provedor indisponível")
            reply = f"Não consegui responder agora. Para registrar um foco ou caso suspeito, acesse {portal_url}"
        try:
            send_text(chat_id, reply)
            _remember(key, text, reply)
        except requests.RequestException:
            current_app.logger.warning("Telegram chatbot: falha ao enviar resposta")


def register_routes(bp):
    @bp.post("/webhooks/telegram/<segredo>", endpoint="telegram_webhook")
    def telegram_webhook(segredo):
        if not configured() or not hmac.compare_digest(segredo, current_app.config["TELEGRAM_WEBHOOK_SECRET"]):
            return jsonify(error="não autorizado"), 401
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if header and not hmac.compare_digest(header, current_app.config["TELEGRAM_WEBHOOK_SECRET"]):
            return jsonify(error="não autorizado"), 401
        update = request.get_json(silent=True) or {}
        message = update.get("message") or update.get("edited_message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        text = (message.get("text") or "").strip()[:1500]
        if not chat_id or not text:
            return jsonify(ok=True, skipped=True)
        if text.startswith("/start"):
            payload = text.split(maxsplit=1)[1].strip() if " " in text else ""
            if payload.startswith("v_"):
                user = link_account(payload[2:], chat_id)
                reply = (f"Pronto, {user.nome_uvis}! Seu Telegram está vinculado ao IJA Vigilância. Você receberá aqui os alertas epidemiológicos do seu município."
                         if user else "Código de vínculo inválido ou já usado. Gere um novo link no aplicativo.")
                try:
                    send_text(chat_id, reply)
                except requests.RequestException:
                    current_app.logger.warning("Telegram: falha ao responder vínculo")
                return jsonify(ok=True, vinculado=bool(user))
            text = "Olá! O que você pode fazer por mim?"
        elif text.startswith("/"):
            text = {"/sintomas": "Quais são os sintomas de dengue, zika e chikungunya e os sinais de alarme?",
                    "/atendimento": "Onde procuro atendimento de saúde no município e quais os telefones?",
                    "/prevencao": "Como evitar focos do mosquito Aedes aegypti em casa?"}.get(text.split("@")[0].split()[0], text)
        portal_url = request.url_root.rstrip("/") + "/portal-cidadao"
        app = current_app._get_current_object()
        threading.Thread(target=handle, args=(app, chat_id, text, portal_url), name="telegram-bot", daemon=True).start()
        return jsonify(ok=True)
