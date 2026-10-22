"""Regras de alerta por bairro/janela e envio a gestores (in-app, e-mail) e cidadãos (push)."""

import hashlib
import json
import math
import re
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models import Denuncia, Notificacao, Prefeitura, RelatoSaude, Usuario
from app.shared.access import is_covisa_user, is_prefeitura_admin_user
from .models import AlertaDisparo, AlertaRegra, DispositivoPush

CANAIS = {"webpush", "fcm"}
LABELS = {"denuncias": "relato(s) de foco", "relatos": "relato(s) de saúde"}


class AlertaError(ValueError):
    pass


def _float(value, low, high):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and low <= number <= high else None


def haversine_km(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- dispositivos
def registrar_dispositivo(data, *, usuario=None, user_agent=None):
    if not isinstance(data, dict):
        raise AlertaError("Envie um JSON com os dados do dispositivo.")
    canal = data.get("canal")
    if canal not in CANAIS:
        raise AlertaError("Canal inválido. Use webpush ou fcm.")
    subscription = {}
    if canal == "webpush":
        sub = data.get("subscription")
        if not isinstance(sub, dict) or not isinstance(sub.get("endpoint"), str) or not sub["endpoint"].startswith("https://"):
            raise AlertaError("Inscrição web push inválida.")
        keys = sub.get("keys") or {}
        if not isinstance(keys, dict) or not keys.get("p256dh") or not keys.get("auth"):
            raise AlertaError("Inscrição web push sem chaves.")
        token = sub["endpoint"][:2000]
        subscription = {"endpoint": token, "keys": {"p256dh": str(keys["p256dh"])[:200], "auth": str(keys["auth"])[:100]}}
    else:
        token = data.get("token")
        if not isinstance(token, str) or not 20 <= len(token) <= 4096 or not re.fullmatch(r"[A-Za-z0-9_:\-]+", token):
            raise AlertaError("Token FCM inválido.")
    prefeitura_id = data.get("prefeitura_id")
    if prefeitura_id not in (None, ""):
        try:
            prefeitura_id = int(prefeitura_id)
        except (TypeError, ValueError):
            raise AlertaError("Prefeitura inválida.") from None
        if not Prefeitura.query.filter_by(id=prefeitura_id, ativa=True).first():
            raise AlertaError("Prefeitura inválida.")
    else:
        prefeitura_id = getattr(usuario, "prefeitura_id", None)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    device = DispositivoPush.query.filter_by(token_hash=token_hash).first() or DispositivoPush(token=token, token_hash=token_hash, canal=canal)
    device.subscription = subscription
    device.prefeitura_id = prefeitura_id
    if usuario is not None and getattr(usuario, "is_authenticated", False):
        device.usuario_id = usuario.id
    device.latitude = _float(data.get("latitude"), -34, 6)
    device.longitude = _float(data.get("longitude"), -74, -28)
    bairro = data.get("bairro")
    device.bairro = str(bairro).strip()[:100] if isinstance(bairro, str) and bairro.strip() else None
    device.user_agent = (user_agent or "")[:255] or None
    device.ativo = True
    device.falhas = 0
    db.session.add(device)
    db.session.commit()
    return device


def remover_dispositivo(token):
    if not isinstance(token, str) or not token:
        return False
    device = DispositivoPush.query.filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest()).first()
    if device:
        device.ativo = False
        db.session.commit()
    return bool(device)


# ---------------------------------------------------------------- envio push
_fcm_credentials = None


def push_configurado():
    return bool(current_app.config.get("VAPID_PRIVATE_KEY") and current_app.config.get("VAPID_PUBLIC_KEY"))


def _send_webpush(device, payload):
    from pywebpush import WebPushException, webpush
    try:
        webpush(subscription_info=device.subscription, data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=current_app.config["VAPID_PRIVATE_KEY"],
                vapid_claims={"sub": current_app.config.get("VAPID_CLAIMS_EMAIL") or "mailto:contato@oceanoazuldrones.com.br"},
                ttl=3600, timeout=10)
        return True, None
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        return False, status or str(exc)[:120]
    except Exception as exc:  # rede, chave inválida
        return False, str(exc)[:120]


def _fcm_token():
    global _fcm_credentials
    raw = current_app.config.get("FCM_SERVICE_ACCOUNT_JSON") or ""
    if not raw:
        return None, None
    import google.auth.transport.requests
    from google.oauth2 import service_account
    if _fcm_credentials is None:
        info = json.loads(raw)
        _fcm_credentials = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/firebase.messaging"])
    if not _fcm_credentials.valid:
        _fcm_credentials.refresh(google.auth.transport.requests.Request())
    return _fcm_credentials.token, _fcm_credentials.project_id


def _send_fcm(device, payload):
    import requests
    try:
        token, project = _fcm_token()
        if not token:
            return False, "fcm_nao_configurado"
        body = {"message": {"token": device.token,
                            "notification": {"title": payload["title"], "body": payload["body"]},
                            "data": {k: str(v) for k, v in payload.items()},
                            "android": {"priority": "high"},
                            "apns": {"payload": {"aps": {"sound": "default"}}}}}
        response = requests.post(f"https://fcm.googleapis.com/v1/projects/{project}/messages:send",
                                 json=body, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if response.status_code == 200:
            return True, None
        return False, response.status_code
    except Exception as exc:
        return False, str(exc)[:120]


def enviar_push(prefeitura_id, titulo, corpo, *, latitude=None, longitude=None, raio_km=None, url=None, tag=None):
    """Envia aos dispositivos da prefeitura; com coordenada e raio, só aos que estão perto (ou sem localização)."""
    query = DispositivoPush.query.filter_by(ativo=True)
    if prefeitura_id:
        query = query.filter((DispositivoPush.prefeitura_id == prefeitura_id) | (DispositivoPush.prefeitura_id.is_(None)))
    devices = query.all()
    if latitude is not None and longitude is not None and raio_km:
        devices = [d for d in devices if d.latitude is None or d.longitude is None
                   or haversine_km(latitude, longitude, d.latitude, d.longitude) <= raio_km]
    payload = {"title": titulo[:120], "body": corpo[:400], "url": url or "/portal-cidadao", "tag": tag or "ija-alerta"}
    result = {"dispositivos": len(devices), "enviados": 0, "falhas": 0, "erros": []}
    for device in devices:
        if device.canal == "webpush" and not push_configurado():
            ok, error = False, "vapid_nao_configurado"
        else:
            ok, error = (_send_webpush if device.canal == "webpush" else _send_fcm)(device, payload)
        if ok:
            result["enviados"] += 1
            device.falhas = 0
        else:
            result["falhas"] += 1
            device.falhas = (device.falhas or 0) + 1
            if error in (404, 410) or device.falhas >= 5:
                device.ativo = False
            if len(result["erros"]) < 5:
                result["erros"].append(str(error))
    return result


# ---------------------------------------------------------------- regras
def contar(regra, agora=None):
    agora = agora or datetime.now()
    desde = agora - timedelta(days=regra.janela_dias)
    if regra.fonte == "denuncias":
        query = Denuncia.query.filter(Denuncia.prefeitura_id == regra.prefeitura_id, Denuncia.criado_em >= desde)
        if regra.bairro:
            query = query.filter(func.lower(Denuncia.bairro) == regra.bairro.strip().lower())
    elif regra.fonte == "relatos":
        query = RelatoSaude.query.filter(RelatoSaude.prefeitura_id == regra.prefeitura_id, RelatoSaude.criado_em >= desde)
        if regra.bairro:
            query = query.filter(func.lower(RelatoSaude.bairro) == regra.bairro.strip().lower())
    else:
        return 0
    return query.count()


def _gestores(prefeitura_id):
    people = Usuario.query.filter(Usuario.prefeitura_id == prefeitura_id).all()
    ids = [u.id for u in people if is_covisa_user(u) or is_prefeitura_admin_user(u)]
    if not ids:
        ids = [u.id for u in Usuario.query.filter(Usuario.tipo_usuario.in_(["dev", "diretor", "admin"])).all()]
    return ids


def disparar(regra, valor, *, bairro=None, latitude=None, longitude=None, teste=False, commit=True):
    agora = datetime.now()
    onde = f" no bairro {bairro}" if bairro else (f" no bairro {regra.bairro}" if regra.bairro else "")
    titulo = f"Alerta epidemiológico: {regra.nome}"
    mensagem = (f"{valor} {LABELS.get(regra.fonte, 'registro(s)')} nos últimos {regra.janela_dias} dia(s){onde} "
                f"(limite configurado: {regra.limiar}).{' [TESTE]' if teste else ''}")
    disparo = AlertaDisparo(regra_id=regra.id, prefeitura_id=regra.prefeitura_id, valor=valor, limiar=regra.limiar,
                            mensagem=mensagem, bairro=(bairro or regra.bairro or None), latitude=latitude,
                            longitude=longitude, teste=teste, resultado={})
    db.session.add(disparo)
    resultado = {}
    if regra.notificar_app:
        ids = _gestores(regra.prefeitura_id)
        for uid in ids:
            db.session.add(Notificacao(usuario_id=uid, titulo=titulo[:140], mensagem=mensagem, link="/alertas"))
        resultado["app"] = len(ids)
    if regra.notificar_email:
        from app.shared import mail
        recipients = [e.strip() for e in re.split(r"[,;\s]+", regra.emails or "") if e.strip()]
        try:
            resultado["email"] = mail.send(recipients, titulo, mensagem + "\n\nAcesse o IJA System para detalhes: /alertas") if recipients else 0
        except Exception as exc:
            resultado["email_erro"] = str(exc)[:200]
    if regra.notificar_push:
        resultado["push"] = enviar_push(regra.prefeitura_id, titulo, mensagem, latitude=latitude, longitude=longitude,
                                        raio_km=regra.raio_km, url="/portal-cidadao#boletim-saude", tag=f"alerta-{regra.id}")
    disparo.resultado = resultado
    regra.ultimo_disparo_em = agora
    if commit:
        db.session.commit()
    return disparo


def avaliar(prefeitura_id, fonte, *, bairro=None, latitude=None, longitude=None, commit=True):
    """Chamado após cada registro do cidadão. Nunca levanta exceção para o chamador."""
    try:
        agora = datetime.now()
        latitude, longitude = _float(latitude, -34, 6), _float(longitude, -74, -28)
        disparos = []
        for regra in AlertaRegra.query.filter_by(prefeitura_id=prefeitura_id, fonte=fonte, ativo=True).all():
            if regra.bairro and (bairro or "").strip().lower() != regra.bairro.strip().lower():
                continue
            if regra.ultimo_disparo_em and regra.ultimo_disparo_em > agora - timedelta(hours=regra.intervalo_horas):
                continue
            valor = contar(regra, agora)
            if valor >= regra.limiar:
                disparos.append(disparar(regra, valor, bairro=bairro, latitude=latitude, longitude=longitude, commit=commit))
        return disparos
    except Exception:
        current_app.logger.exception("Alertas: falha ao avaliar regras")
        if commit:
            db.session.rollback()
        return []


def criar_regra(form, prefeitura_id, usuario):
    nome = (form.get("nome") or "").strip()[:120]
    fonte = form.get("fonte")
    if not nome or fonte not in AlertaRegra.FONTES:
        raise AlertaError("Informe nome e fonte do alerta.")
    def inteiro(nome_campo, low, high, default):
        try:
            value = int(form.get(nome_campo, default))
        except (TypeError, ValueError):
            raise AlertaError(f"Valor inválido em {nome_campo}.") from None
        if not low <= value <= high:
            raise AlertaError(f"{nome_campo} deve estar entre {low} e {high}.")
        return value
    raio = _float(form.get("raio_km", 2), 0, 100)
    if raio is None:
        raise AlertaError("Raio inválido.")
    regra = AlertaRegra(prefeitura_id=prefeitura_id, nome=nome, fonte=fonte,
                        bairro=((form.get("bairro") or "").strip()[:100] or None),
                        janela_dias=inteiro("janela_dias", 1, 365, 7), limiar=inteiro("limiar", 1, 100000, 3),
                        raio_km=raio, intervalo_horas=inteiro("intervalo_horas", 0, 720, 24),
                        notificar_app=form.get("notificar_app") == "on", notificar_email=form.get("notificar_email") == "on",
                        notificar_push=form.get("notificar_push") == "on",
                        emails=((form.get("emails") or "").strip()[:1000] or None), criado_por_id=getattr(usuario, "id", None))
    db.session.add(regra)
    db.session.commit()
    return regra
