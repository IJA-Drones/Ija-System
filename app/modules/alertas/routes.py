"""Telas de regras/disparos para a gestão e API pública de dispositivos push."""

from functools import wraps

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import Prefeitura
from app.modules.gestao_ti.permissions import route_access
from app.modules.vigilancia.access import can_coordinate_field
from app.shared.access import is_admin_global_user
from app.shared.csrf_security import csrf_token
from . import service
from .models import AlertaDisparo, AlertaRegra, DispositivoPush


def _access(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not (is_admin_global_user(current_user) or can_coordinate_field(current_user)) or not route_access(current_user, True):
            abort(403)
        return view(*args, **kwargs)
    return guarded


def _prefeitura():
    raw = request.values.get("prefeitura_id", "")
    if is_admin_global_user(current_user):
        if not raw:
            return None
        if not (raw.isascii() and raw.isdecimal() and len(raw) <= 10):
            abort(400, description="Informe uma prefeitura válida.")
        pid = int(raw)
    else:
        pid = getattr(current_user, "prefeitura_id", None)
        if not pid or (raw and raw != str(pid)):
            abort(403, description="A prefeitura não pertence ao seu acesso.")
    if Prefeitura.query.filter_by(id=pid).first() is None:
        abort(404)
    return pid


def _regra(regra_id, pid):
    regra = db.session.get(AlertaRegra, regra_id)
    if regra is None or regra.prefeitura_id != pid:
        abort(404)
    return regra


def register_routes(bp):
    @bp.get("/alertas", endpoint="alertas")
    @_access
    def alertas():
        pid = _prefeitura()
        prefeituras = Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all() if is_admin_global_user(current_user) else []
        regras = AlertaRegra.query.filter_by(prefeitura_id=pid).order_by(AlertaRegra.criado_em.desc()).all() if pid else []
        disparos = AlertaDisparo.query.filter_by(prefeitura_id=pid).order_by(AlertaDisparo.criado_em.desc()).limit(30).all() if pid else []
        dispositivos = DispositivoPush.query.filter_by(ativo=True).filter(
            (DispositivoPush.prefeitura_id == pid) | (DispositivoPush.prefeitura_id.is_(None))).count() if pid else 0
        contagens = {regra.id: service.contar(regra) for regra in regras}
        from app.shared import mail
        return render_template("alertas.html", prefeitura_id=pid, prefeituras=prefeituras, regras=regras, disparos=disparos,
                               dispositivos=dispositivos, contagens=contagens, fontes=AlertaRegra.FONTES,
                               global_user=is_admin_global_user(current_user), csrf=csrf_token(),
                               push_ok=service.push_configurado(), email_ok=mail.available(),
                               prefeitura_nome=(db.session.get(Prefeitura, pid).nome if pid else ""))

    @bp.post("/alertas/nova", endpoint="alertas_nova")
    @_access
    def alertas_nova():
        pid = _prefeitura()
        if pid is None:
            abort(400, description="Selecione uma prefeitura.")
        try:
            regra = service.criar_regra(request.form, pid, current_user)
            flash(f"Alerta “{regra.nome}” criado.", "success")
        except service.AlertaError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("main.alertas", prefeitura_id=pid), code=303)

    @bp.post("/alertas/<int:regra_id>/alternar", endpoint="alertas_alternar")
    @_access
    def alertas_alternar(regra_id):
        pid = _prefeitura()
        regra = _regra(regra_id, pid)
        regra.ativo = not regra.ativo
        db.session.commit()
        flash(f"Alerta “{regra.nome}” {'ativado' if regra.ativo else 'desativado'}.", "success")
        return redirect(url_for("main.alertas", prefeitura_id=pid), code=303)

    @bp.post("/alertas/<int:regra_id>/excluir", endpoint="alertas_excluir")
    @_access
    def alertas_excluir(regra_id):
        pid = _prefeitura()
        regra = _regra(regra_id, pid)
        db.session.delete(regra)
        db.session.commit()
        flash("Alerta excluído.", "success")
        return redirect(url_for("main.alertas", prefeitura_id=pid), code=303)

    @bp.post("/alertas/<int:regra_id>/testar", endpoint="alertas_testar")
    @_access
    def alertas_testar(regra_id):
        pid = _prefeitura()
        regra = _regra(regra_id, pid)
        disparo = service.disparar(regra, service.contar(regra), teste=True)
        flash(f"Disparo de teste registrado: {disparo.mensagem} Resultado: {disparo.resultado}", "info")
        return redirect(url_for("main.alertas", prefeitura_id=pid), code=303)

    @bp.post("/alertas/push-teste", endpoint="alertas_push_teste")
    @_access
    def alertas_push_teste():
        pid = _prefeitura()
        texto = (request.form.get("mensagem") or "Teste de notificação da vigilância em saúde.").strip()[:400]
        resultado = service.enviar_push(pid, "Vigilância em saúde", texto, url="/portal-cidadao#boletim-saude", tag="teste")
        db.session.commit()
        flash(f"Push enviado: {resultado['enviados']} de {resultado['dispositivos']} dispositivo(s). {resultado['erros'] or ''}", "info")
        return redirect(url_for("main.alertas", prefeitura_id=pid), code=303)

    # ------------------------------------------------------------ API pública
    @bp.get("/api/push/chave-publica", endpoint="push_chave_publica")
    def push_chave_publica():
        return jsonify(publicKey=current_app.config.get("VAPID_PUBLIC_KEY") or None,
                       fcm=bool(current_app.config.get("FCM_SERVICE_ACCOUNT_JSON")))

    @bp.post("/api/push/inscrever", endpoint="push_inscrever")
    def push_inscrever():
        try:
            device = service.registrar_dispositivo(request.get_json(silent=True), usuario=current_user,
                                                   user_agent=request.headers.get("User-Agent"))
        except service.AlertaError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(ok=True, id=device.id, canal=device.canal, prefeitura_id=device.prefeitura_id,
                       localizado=device.latitude is not None)

    @bp.post("/api/push/remover", endpoint="push_remover")
    def push_remover():
        data = request.get_json(silent=True) or {}
        token = data.get("token") or (data.get("subscription") or {}).get("endpoint")
        return jsonify(ok=service.remover_dispositivo(token))
