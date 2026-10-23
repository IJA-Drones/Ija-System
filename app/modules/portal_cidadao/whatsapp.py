"""Azul no WhatsApp via Kapso (API compatível com a Meta Cloud API).

Webhook: POST /webhooks/whatsapp/kapso, assinado com HMAC-SHA256 (X-Webhook-Signature).
Responde 200 imediatamente e processa em thread; histórico curto por telefone em memória.
"""

import hashlib
import hmac
import json
import re
import threading
import time

import requests
from flask import current_app, jsonify, request
from openai import OpenAIError

from . import chatbot

KAPSO_BASE = "https://api.kapso.ai/meta/whatsapp/v24.0"
HISTORY_TTL = 3600
HISTORY_MAX = 6
RATE_PER_HOUR = 40
_history = {}  # memória por processo; trocar por tabela se precisar de continuidade entre workers
_rate = {}
_lock = threading.Lock()

WHATSAPP_NOTE = """
CANAL ATUAL: você está respondendo pelo WhatsApp oficial da vigilância em saúde, 24 horas por dia.
Responda em texto simples, sem markdown, sem títulos e sem listas numeradas longas; até 900 caracteres.
Para registrar foco de mosquito ou caso suspeito, oriente a abrir o Portal do Cidadão: {portal}
Não peça dados pessoais pelo WhatsApp. Se perguntarem onde estão as áreas de risco, explique que o boletim
e o mapa de risco estão no portal e resuma o que o CONTEXTO PÚBLICO informar.
"""


def configured():
    return bool(current_app.config.get("KAPSO_API_KEY") and current_app.config.get("KAPSO_PHONE_NUMBER_ID"))


def verify_signature(raw, signature, secret):
    if not secret:
        return True
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.strip(), expected)


def envelopes(body, batch_header=False):
    if not isinstance(body, dict):
        return []
    if (body.get("batch") is True or batch_header or body.get("type") == "whatsapp.message.received") and isinstance(body.get("data"), list):
        return [item for item in body["data"] if isinstance(item, dict)]
    if isinstance(body.get("message"), dict) and isinstance(body.get("conversation"), dict):
        return [body]
    data = body.get("data")
    if isinstance(data, dict) and isinstance(data.get("message"), dict) and isinstance(data.get("conversation"), dict):
        return [data]
    return []


def is_message_received(body, header_event):
    event = (header_event or body.get("event") or body.get("type") or "").strip().lower()
    return event == "whatsapp.message.received" or (isinstance(body.get("message"), dict) and isinstance(body.get("conversation"), dict)) \
        or (body.get("batch") is True and isinstance(body.get("data"), list))


def inbound_text(message):
    kapso = message.get("kapso") or {}
    if isinstance(kapso.get("content"), str) and kapso["content"].strip():
        return kapso["content"].strip()
    kind = message.get("type")
    if kind == "text":
        return ((message.get("text") or {}).get("body") or "").strip()
    if kind == "interactive":
        inter = message.get("interactive") or {}
        return ((inter.get("button_reply") or inter.get("list_reply") or {}).get("title") or "").strip()
    if kind == "audio":
        return ((kapso.get("transcript") or {}).get("text") or "").strip()
    if kind in {"image", "video", "document"}:
        return ((message.get(kind) or {}).get("caption") or "").strip()
    return ""


def customer_digits(envelope):
    conv = envelope.get("conversation") or {}
    raw = conv.get("phone_number") or (envelope.get("message") or {}).get("from") or ""
    return re.sub(r"\D", "", str(raw))


def send_text(to_digits, text):
    url = f"{KAPSO_BASE}/{current_app.config['KAPSO_PHONE_NUMBER_ID']}/messages"
    body = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to_digits, "type": "text", "text": {"body": text[:4000]}}
    response = requests.post(url, json=body, headers={"X-API-Key": current_app.config["KAPSO_API_KEY"], "Content-Type": "application/json"}, timeout=30)
    response.raise_for_status()
    return response.json() if response.content else {}


def _allowed(phone):
    now = time.time()
    with _lock:
        stamps = [t for t in _rate.get(phone, []) if now - t < 3600]
        if len(stamps) >= RATE_PER_HOUR:
            _rate[phone] = stamps
            return False
        stamps.append(now)
        _rate[phone] = stamps
        return True


def _history_for(phone):
    with _lock:
        entry = _history.get(phone)
        if not entry or time.time() - entry[0] > HISTORY_TTL:
            return []
        return list(entry[1])


def _remember(phone, user_text, assistant_text):
    with _lock:
        entry = _history.get(phone)
        messages = list(entry[1]) if entry and time.time() - entry[0] <= HISTORY_TTL else []
        messages += [{"role": "user", "content": user_text}, {"role": "assistant", "content": assistant_text}]
        _history[phone] = (time.time(), messages[-HISTORY_MAX:])


def _plain(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    return text.strip()


def handle(app, envelope, portal_url):
    with app.app_context():
        message = envelope.get("message") or {}
        text, phone = inbound_text(message)[:1500], customer_digits(envelope)
        if not text or not phone:
            return
        if not _allowed(phone):
            return
        messages = _history_for(phone) + [{"role": "user", "content": text}]
        try:
            if not current_app.config.get("OPENAI_API_KEY"):
                raise chatbot.ChatbotError("Assistente indisponível no momento.")
            reply, _ = chatbot.answer(messages, extra_instructions=WHATSAPP_NOTE.format(portal=portal_url))
            reply = _plain(reply)
        except (chatbot.ChatbotError, OpenAIError):
            current_app.logger.warning("WhatsApp chatbot: provedor indisponível")
            reply = f"Não consegui responder agora. Para registrar um foco ou caso suspeito, acesse {portal_url}"
        try:
            send_text(phone, reply)
            _remember(phone, text, reply)
        except requests.RequestException:
            current_app.logger.warning("WhatsApp chatbot: falha ao enviar resposta pela Kapso")


def register_routes(bp):
    @bp.post("/webhooks/whatsapp/kapso", endpoint="whatsapp_kapso_webhook")
    def whatsapp_kapso_webhook():
        if not configured():
            return jsonify(error="WhatsApp não configurado"), 503
        raw = request.get_data(cache=True) or b""
        if len(raw) > 512 * 1024:
            return jsonify(error="payload grande demais"), 413
        if not verify_signature(raw, request.headers.get("X-Webhook-Signature"), current_app.config.get("KAPSO_WEBHOOK_SECRET")):
            return jsonify(error="assinatura inválida"), 401
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            return jsonify(error="JSON inválido"), 400
        if not is_message_received(body, request.headers.get("X-Webhook-Event")):
            return jsonify(ok=True, skipped=True)
        items = envelopes(body, (request.headers.get("X-Webhook-Batch") or "").lower() == "true")
        portal_url = request.url_root.rstrip("/") + "/portal-cidadao"
        app = current_app._get_current_object()
        for envelope in items[:20]:
            threading.Thread(target=handle, args=(app, envelope, portal_url), name="kapso-whatsapp", daemon=True).start()
        return jsonify(ok=True, received=len(items))
