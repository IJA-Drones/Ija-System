"""API JSON mínima para o aplicativo nativo (cidadão e agente de endemias).

Público: config, relato de saúde, alertas recentes, chat. Agente: login com JWT (Bearer).
A denúncia de foco usa o endpoint existente POST /portal-cidadao/denuncias (multipart).
"""

import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Response, current_app, g, jsonify, make_response, render_template, request, send_from_directory, url_for
from openai import OpenAIError

from app.extensions import db
from app.models import Prefeitura, Usuario
from app.modules.alertas.models import AlertaDisparo, AlertaRegra
from app.modules.auth.service import authenticate_user
from app.modules.portal_cidadao import chatbot
from app.modules.portal_cidadao.catalog import build_public_focus_catalog
from app.modules.relatos_saude.service import create_report
from app.models import Denuncia

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


APP_VERSION = "1.3.0"


def register_routes(bp):
    @bp.get("/app", endpoint="app_download")
    def app_download():
        import os
        path = os.path.join(current_app.static_folder, "downloads", "ija-vigilancia.apk")
        size = round(os.path.getsize(path) / (1024 * 1024)) if os.path.exists(path) else 0
        return render_template("app_download.html", versao=APP_VERSION, tamanho_mb=size)

    @bp.get("/app/ija-vigilancia.apk", endpoint="app_apk")
    def app_apk():
        response = send_from_directory(os.path.join(current_app.static_folder, "downloads"), "ija-vigilancia.apk",
                                       mimetype="application/vnd.android.package-archive", as_attachment=True,
                                       download_name="ija-vigilancia.apk")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @bp.get("/app/qr.svg", endpoint="app_qr")
    def app_qr():
        import io
        import qrcode
        from qrcode.image.svg import SvgPathImage
        image = qrcode.make(url_for("main.app_apk", _external=True), image_factory=SvgPathImage, box_size=10, border=2)
        buffer = io.BytesIO(); image.save(buffer)
        return Response(buffer.getvalue(), mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})

    @bp.get("/m/", endpoint="app_movel")
    def app_movel():
        # Shell do aplicativo web instalável (PWA). O próprio shell redireciona para o portal
        # quando não está em modo standalone (sem ?preview=1).
        from app.shared.csrf_security import csrf_token
        response = make_response(render_template("app_movel.html", csrf=csrf_token()))
        response.headers["Cache-Control"] = "no-cache"
        return response

    @bp.get("/api/mobile/config", endpoint="mobile_config")
    def mobile_config():
        catalog = build_public_focus_catalog()
        prefeituras = [{"id": p.id, "nome": p.nome} for p in Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all()]
        from app.modules.portal_cidadao.telegram import bot_link
        return jsonify(prefeituras=prefeituras, catalogo=catalog, telegram=bot_link(),
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
        from app.modules.portal_cidadao.telegram import bot_link, link_code_for
        return jsonify(id=user.id, nome=user.nome_uvis, tipo=user.tipo_usuario, prefeitura_id=user.prefeitura_id,
                       prefeitura=prefeitura.nome if prefeitura else None,
                       telegram={"vinculado": bool(user.telegram_chat_id), "link": bot_link("v_" + link_code_for(user)), "bot": bot_link()})

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


    # ------------------------------------------------------------ agente de endemias
    def _demo_flag():
        return request.values.get("demo", "false") == "true"

    @bp.get("/api/mobile/agente/painel", endpoint="mobile_agente_painel")
    @bearer_required
    def mobile_agente_painel():
        from datetime import date
        from app.modules.vigilancia.planning import PlanningStore
        from app.modules.vigilancia.planning_models import CampoPlanoVisita
        from app.modules.vigilancia.agent_tracking import AgentePosicao, _haversine
        user, demo = g.mobile_user, _demo_flag()
        pid = user.prefeitura_id
        blocks = PlanningStore().agent_blocks(pid, user.id, demo) if pid else []
        visits = CampoPlanoVisita.query.filter_by(prefeitura=pid, demo=demo, autor=str(user.id)).all() if pid else []
        by_block = {}
        for v in visits:
            by_block[(v.plano, v.quarteirao)] = by_block.get((v.plano, v.quarteirao), 0) + 1
        quarteiroes = [{
            "plano": b["plano"], "titulo": b["titulo"], "quarteirao": b["quarteirao"], "estrato": b["estrato"], "meta": b["meta"],
            "inicio": b["inicio"].isoformat(), "fim": b["fim"].isoformat(),
            "bairro": (b.get("territorio") or {}).get("bairro"), "area": (b.get("territorio") or {}).get("area"),
            "referencia": (b.get("territorio") or {}).get("referencia"), "geometria": (b.get("territorio") or {}).get("geometria"),
            "visitas_registradas": by_block.get((b["plano"], b["quarteirao"]), 0),
        } for b in blocks]
        today = datetime.combine(date.today(), datetime.min.time())
        pts = (AgentePosicao.query.filter(AgentePosicao.usuario_id == user.id, AgentePosicao.registrado_em >= today)
               .order_by(AgentePosicao.registrado_em).all())
        coords = [(p.latitude, p.longitude) for p in pts]
        km = round(sum(_haversine(a, b) for a, b in zip(coords, coords[1:])), 2)
        visitas_total = len(visits)
        abertas = (Denuncia.STATUS_RECEBIDA, Denuncia.STATUS_EM_TRIAGEM_COVISA, Denuncia.STATUS_ENCAMINHADA_COORDENADORIA, Denuncia.STATUS_ENCAMINHADA_UVIS)
        denuncias = (Denuncia.query.filter(Denuncia.prefeitura_id == pid, Denuncia.status.in_(abertas))
                     .order_by(Denuncia.criado_em.desc()).limit(50).all()) if pid else []
        def _f(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        alertas = (AlertaDisparo.query.filter_by(prefeitura_id=pid, teste=False).order_by(AlertaDisparo.criado_em.desc()).limit(5).all()) if pid else []
        return jsonify(
            agente={"id": user.id, "nome": user.nome_uvis, "prefeitura_id": pid},
            demo=demo,
            resumo_hoje={"posicoes": len(pts), "km": km, "inicio": pts[0].registrado_em.strftime("%H:%M") if pts else None,
                         "ultimo": pts[-1].registrado_em.strftime("%H:%M") if pts else None, "visitas": visitas_total},
            rastro_hoje=[[p.latitude, p.longitude] for p in pts],
            quarteiroes=quarteiroes,
            ocorrencias=[{"id": d.id, "protocolo": d.protocolo, "status": d.status, "tipo": d.tipo_visita, "foco": d.foco,
                          "endereco": f"{d.logradouro}, {d.numero} - {d.bairro}", "bairro": d.bairro,
                          "latitude": _f(d.latitude), "longitude": _f(d.longitude), "quando": d.criado_em.isoformat()} for d in denuncias],
            alertas=[{"titulo": a.regra.nome, "mensagem": a.mensagem, "quando": a.criado_em.isoformat()} for a in alertas],
            depositos=[{"codigo": c, "rotulo": l} for c, l in __import__("app.modules.vigilancia.domain", fromlist=["DEPOSIT_TYPES"]).DEPOSIT_TYPES],
        )

    @bp.post("/api/mobile/agente/visitas", endpoint="mobile_agente_visita")
    @bearer_required
    def mobile_agente_visita():
        from app.modules.vigilancia.planning import PlanningStore
        from app.modules.vigilancia.field_store import FieldStore, FieldConflict, FieldStoreError
        from app.modules.vigilancia.field_capture import capture_csv, FieldInputError
        from app.modules.vigilancia.domain import DEPOSIT_TYPES
        user = g.mobile_user
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not user.prefeitura_id:
            return jsonify(error="Envie os dados da visita."), 400
        demo = data.get("demo") in (True, "true", 1)
        blocks = PlanningStore().agent_blocks(user.prefeitura_id, user.id, demo)
        selected = next((b for b in blocks if b["plano"] == data.get("plano") and b["quarteirao"] == data.get("quarteirao")), None)
        if selected is None:
            return jsonify(error="Quarteirão não atribuído a você neste plano."), 404
        form = {k: str(data.get(k) or "") for k in ("imovel_codigo", "inspecao_codigo", "data_inspecao", "situacao", "positivo_aedes", "latitude", "longitude")}
        if not form["inspecao_codigo"]:
            form["inspecao_codigo"] = "APP-" + uuid.uuid4().hex[:10].upper()
        deposits = data.get("depositos") or {}
        for code, _ in DEPOSIT_TYPES:
            value = deposits.get(code, "")
            form["depositos_" + code] = "" if value in (None, "") else str(value)
        form.update(origem="LIRAA", levantamento_codigo=selected["plano"], estrato_codigo=selected["estrato"],
                    area_codigo=selected["territorio"]["area"], bairro=selected["territorio"]["bairro"])
        try:
            content = capture_csv(form, prefeitura=user.prefeitura_id)
            store = FieldStore()
            batch = store.prepare(content, prefeitura=user.prefeitura_id, actor=str(user.id), source="Registro pelo aplicativo do agente",
                                  filename="visita-app.csv", demo=demo,
                                  plan_reference=dict(plano=selected["plano"], quarteirao=selected["quarteirao"], agente_id=user.id))
            batch = store.confirm(batch["id"], prefeitura=user.prefeitura_id, actor=str(user.id))
        except (FieldInputError, FieldConflict, FieldStoreError) as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(ok=True, lote=batch["id"], inspecao_codigo=form["inspecao_codigo"], status=batch.get("status")), 201

    @bp.post("/api/mobile/agente/visitas/<inspecao_codigo>/midias", endpoint="mobile_agente_visita_midias")
    @bearer_required
    def mobile_agente_visita_midias(inspecao_codigo):
        from app.modules.vigilancia.pending import MidiaError, save_media
        try:
            rows = save_media(g.mobile_user, inspecao_codigo[:80], request.files.getlist("midias"),
                              request.form.get("latitude"), request.form.get("longitude"))
        except MidiaError as exc:
            return jsonify(error=str(exc)), exc.status
        return jsonify(ok=True, midias=[{"id": m.id, "tipo": m.tipo} for m in rows]), 201
