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
            text = "Olá! O que você pode fazer por mim?"
        portal_url = request.url_root.rstrip("/") + "/portal-cidadao"
        app = current_app._get_current_object()
        threading.Thread(target=handle, args=(app, chat_id, text, portal_url), name="telegram-bot", daemon=True).start()
        return jsonify(ok=True)
