"""API JSON mínima para o aplicativo nativo (cidadão e agente de endemias).

Público: config, relato de saúde, alertas recentes, chat. Agente: login com JWT (Bearer).
A denúncia de foco usa o endpoint existente POST /portal-cidadao/denuncias (multipart).
"""

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request
from openai import OpenAIError

from app.extensions import db
from app.models import Prefeitura, Usuario
from app.modules.alertas.models import AlertaDisparo, AlertaRegra
from app.modules.auth.service import authenticate_user
from app.modules.portal_cidadao import chatbot
from app.modules.portal_cidadao.catalog import build_public_focus_catalog
from app.modules.relatos_saude.service import create_report

TOKEN_DAYS = 30
_chat_rate = {}
_lock = threading.Lock()


def issue_token(user):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "tipo": user.tipo_usuario, "iat": now, "exp": now + timedelta(days=TOKEN_DAYS)},
                      current_app.secret_key, algorithm="HS256")


def user_from_bearer():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(header[7:].strip(), current_app.secret_key, algorithms=["HS256"])
        return db.session.get(Usuario, int(payload["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def bearer_required(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        user = user_from_bearer()
        if user is None:
            return jsonify(error="Faça login novamente."), 401
        g.mobile_user = user
        return view(*args, **kwargs)
    return guarded


def _rate_ok(key, limit, window=3600):
    now = time.time()
    with _lock:
        stamps = [t for t in _chat_rate.get(key, []) if now - t < window]
        if len(stamps) >= limit:
            _chat_rate[key] = stamps
            return False
        stamps.append(now)
        _chat_rate[key] = stamps
        return True


def register_routes(bp):
    @bp.get("/api/mobile/config", endpoint="mobile_config")
    def mobile_config():
        catalog = build_public_focus_catalog()
        prefeituras = [{"id": p.id, "nome": p.nome} for p in Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all()]
        return jsonify(prefeituras=prefeituras, catalogo=catalog,
                       push={"fcm": bool(current_app.config.get("FCM_SERVICE_ACCOUNT_JSON"))},
                       chat=bool(current_app.config.get("OPENAI_API_KEY")), versao=1)

    @bp.post("/api/mobile/login", endpoint="mobile_login")
    def mobile_login():
        data = request.get_json(silent=True) or {}
        login_value, password = str(data.get("login") or "")[:50], str(data.get("senha") or "")[:128]
        if not login_value or not password or not _rate_ok("login:" + request.remote_addr, 20, 900):
            return jsonify(error="Login ou senha incorretos."), 401
        user = authenticate_user(login_value, password)
        if user is None:
            return jsonify(error="Login ou senha incorretos."), 401
        return jsonify(token=issue_token(user), usuario={"id": user.id, "nome": user.nome_uvis, "tipo": user.tipo_usuario,
                                                         "prefeitura_id": user.prefeitura_id})

    @bp.get("/api/mobile/me", endpoint="mobile_me")
    @bearer_required
    def mobile_me():
        user = g.mobile_user
        prefeitura = db.session.get(Prefeitura, user.prefeitura_id) if user.prefeitura_id else None
        return jsonify(id=user.id, nome=user.nome_uvis, tipo=user.tipo_usuario, prefeitura_id=user.prefeitura_id,
                       prefeitura=prefeitura.nome if prefeitura else None)

    @bp.post("/api/mobile/relato-saude", endpoint="mobile_relato_saude")
    def mobile_relato_saude():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Envie os dados do relato."), 400
        device = str(data.get("dispositivo") or request.remote_addr or "app")[:120]
        if not _rate_ok("relato:" + device, 10):
            return jsonify(error="Muitos relatos enviados. Tente mais tarde."), 429
        form = {k: ("1" if k == "consentimento" and data.get(k) in (True, 1, "1", "true") else str(data.get(k) or ""))
                for k in ("prefeitura_id", "nome", "telefone", "logradouro", "numero", "bairro", "descricao", "inicio_sintomas", "consentimento")}
        submission = str(data.get("envio_id") or uuid.uuid4())[:64]
        result = create_report(form, submission, "mobile:" + device)
        if isinstance(result, dict):
            return jsonify(success=False, errors=result), 400
        db.session.commit()
        return jsonify(success=True, protocolo=result.protocolo, prefeitura=result.prefeitura.nome), 201

    @bp.get("/api/mobile/alertas", endpoint="mobile_alertas")
    def mobile_alertas():
        raw = request.args.get("prefeitura_id", "")
        if not (raw.isascii() and raw.isdecimal()):
            return jsonify(error="Informe a prefeitura."), 400
        rows = (AlertaDisparo.query.filter_by(prefeitura_id=int(raw), teste=False)
                .order_by(AlertaDisparo.criado_em.desc()).limit(20).all())
        return jsonify(alertas=[{"id": d.id, "titulo": d.regra.nome, "mensagem": d.mensagem, "bairro": d.bairro,
                                 "latitude": d.latitude, "longitude": d.longitude, "quando": d.criado_em.isoformat()} for d in rows])

    @bp.post("/api/mobile/chat", endpoint="mobile_chat")
    def mobile_chat():
        if not current_app.config.get("OPENAI_API_KEY"):
            return jsonify(error="Assistente indisponível."), 503
        data = request.get_json(silent=True) or {}
        message = str(data.get("message") or "").strip()[:1500]
        history = data.get("history") or []
        if not message:
            return jsonify(error="Digite uma mensagem."), 400
        if not isinstance(history, list) or len(history) > 6 or any(
                not isinstance(h, dict) or h.get("role") not in {"user", "assistant"} or not isinstance(h.get("content"), str) for h in history):
            return jsonify(error="Histórico inválido."), 400
        device = str(data.get("dispositivo") or request.remote_addr or "app")[:120]
        if not _rate_ok("chat:" + device, 60):
            return jsonify(error="Limite de mensagens atingido. Tente mais tarde."), 429
        messages = [{"role": h["role"], "content": h["content"][:12000]} for h in history] + [{"role": "user", "content": message}]
        try:
            text, parts = chatbot.answer(messages, extra_instructions="\nCANAL ATUAL: aplicativo móvel oficial; responda em texto simples, sem markdown, até 900 caracteres.")
            return jsonify(answer=text, parts=parts)
        except chatbot.ChatbotError as exc:
            return jsonify(error=exc.message), exc.status
        except OpenAIError:
            return jsonify(error="Não foi possível responder agora."), 502
