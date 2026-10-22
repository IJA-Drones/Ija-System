"""Rastro GPS dos agentes de endemias enquanto o app está aberto (supervisão de campo)."""

from datetime import date, datetime, timedelta
from functools import wraps
import math

from flask import abort, current_app, jsonify, render_template, request
from flask_login import current_user

from app.extensions import db
from app.models import Prefeitura, Usuario
from app.modules.gestao_ti.permissions import route_access
from app.shared.access import is_admin_global_user
from .access import can_coordinate_field


class AgentePosicao(db.Model):
    __tablename__ = "vigilancia_agente_posicoes"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    precisao_m = db.Column(db.Float)
    registrado_em = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    origem = db.Column(db.String(10), nullable=False, default="web")  # app | web


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
    raw = request.args.get("prefeitura_id", "")
    if is_admin_global_user(current_user):
        if not raw:
            return None
        if not (raw.isascii() and raw.isdecimal() and len(raw) <= 10):
            abort(400)
        return int(raw)
    pid = getattr(current_user, "prefeitura_id", None)
    if not pid or (raw and raw != str(pid)):
        abort(403)
    return pid


def _day():
    raw = request.args.get("data", "")
    try:
        return date.fromisoformat(raw) if raw else date.today()
    except ValueError:
        abort(400, description="Data inválida.")


def _finite(value, low, high):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and low <= number <= high else None


def register_routes(bp):
    @bp.post("/api/agente/posicao", endpoint="agente_posicao")
    def agente_posicao():
        if not current_user.is_authenticated:
            return jsonify(error="login"), 401
        data = request.get_json(silent=True) or {}
        lat, lng = _finite(data.get("latitude"), -34, 6), _finite(data.get("longitude"), -74, -28)
        if lat is None or lng is None:
            return jsonify(error="Coordenadas inválidas."), 400
        row = AgentePosicao(usuario_id=current_user.id, prefeitura_id=getattr(current_user, "prefeitura_id", None),
                            latitude=lat, longitude=lng, precisao_m=_finite(data.get("precisao"), 0, 100000),
                            origem="app" if data.get("origem") == "app" else "web")
        db.session.add(row)
        db.session.commit()
        return jsonify(ok=True, id=row.id)

    @bp.get("/vigilancia/agentes", endpoint="vigilancia_agentes")
    @_access
    def vigilancia_agentes():
        pid, day = _prefeitura(), _day()
        prefeituras = Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all() if is_admin_global_user(current_user) else []
        agentes = Usuario.query.filter_by(prefeitura_id=pid, tipo_usuario="agente_endemias").order_by(Usuario.nome_uvis).all() if pid else []
        return render_template("vigilancia_agentes.html", prefeitura_id=pid, prefeituras=prefeituras, agentes=agentes, dia=day,
                               global_user=is_admin_global_user(current_user),
                               prefeitura_nome=(db.session.get(Prefeitura, pid).nome if pid else ""))

    @bp.get("/api/vigilancia/agentes/rastro", endpoint="vigilancia_agentes_rastro")
    @_access
    def vigilancia_agentes_rastro():
        pid, day = _prefeitura(), _day()
        if pid is None:
            return jsonify(error="Selecione uma prefeitura."), 400
        start = datetime.combine(day, datetime.min.time())
        query = (AgentePosicao.query.filter(AgentePosicao.prefeitura_id == pid, AgentePosicao.registrado_em >= start,
                                            AgentePosicao.registrado_em < start + timedelta(days=1))
                 .order_by(AgentePosicao.usuario_id, AgentePosicao.registrado_em))
        raw = request.args.get("usuario_id", "")
        if raw.isdecimal():
            query = query.filter(AgentePosicao.usuario_id == int(raw))
        tracks = {}
        for row in query.limit(20000):
            track = tracks.setdefault(row.usuario_id, {"usuario_id": row.usuario_id, "pontos": [], "inicio": None, "fim": None})
            track["pontos"].append([row.latitude, row.longitude, row.registrado_em.strftime("%H:%M"), row.precisao_m])
            track["inicio"] = track["inicio"] or row.registrado_em.strftime("%H:%M")
            track["fim"] = row.registrado_em.strftime("%H:%M")
        names = {u.id: u.nome_uvis for u in Usuario.query.filter(Usuario.id.in_(list(tracks) or [0])).all()}
        for uid, track in tracks.items():
            track["nome"] = names.get(uid, f"Usuário {uid}")
            track["distancia_km"] = round(sum(_haversine(a, b) for a, b in zip(track["pontos"], track["pontos"][1:])), 2)
        return jsonify(dia=day.isoformat(), agentes=list(tracks.values()))


def _haversine(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))
