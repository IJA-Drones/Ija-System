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
        from app.modules.mobile.routes import user_from_bearer
        user = user_from_bearer() or (current_user if current_user.is_authenticated else None)
        if user is None:
            return jsonify(error="login"), 401
        data = request.get_json(silent=True) or {}
        lat, lng = _finite(data.get("latitude"), -34, 6), _finite(data.get("longitude"), -74, -28)
        if lat is None or lng is None:
            return jsonify(error="Coordenadas inválidas."), 400
        row = AgentePosicao(usuario_id=user.id, prefeitura_id=getattr(user, "prefeitura_id", None),
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
        painel = painel_agentes(pid, day, day, int(raw) if raw.isdecimal() else None)
        visitas = [v for v in painel["visitas"] if v["latitude"] is not None and v["longitude"] is not None]
        return jsonify(dia=day.isoformat(), agentes=list(tracks.values()), visitas=visitas)


    @bp.get("/api/vigilancia/agentes/painel", endpoint="vigilancia_agentes_painel")
    @_access
    def vigilancia_agentes_painel():
        pid = _prefeitura()
        if pid is None:
            return jsonify(error="Selecione uma prefeitura."), 400
        de, ate = _period()
        raw = request.args.get("usuario_id", "")
        only = int(raw) if raw.isdecimal() else None
        return jsonify(painel_agentes(pid, de, ate, only))

    @bp.get("/vigilancia/agentes/exportar.csv", endpoint="vigilancia_agentes_export")
    @_access
    def vigilancia_agentes_export():
        import csv
        import io
        pid = _prefeitura()
        if pid is None:
            abort(400)
        de, ate = _period()
        data = painel_agentes(pid, de, ate, None)
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["data", "agente", "inicio", "fim", "pontos", "km", "visitas", "inspecionados", "fechados_recusados", "positivos"])
        for row in data["historico"]:
            writer.writerow([row["data"], row["agente"], row["inicio"] or "", row["fim"] or "", row["pontos"], row["km"], row["visitas"], row["inspecionados"], row["nao_inspecionados"], row["positivos"]])
        writer.writerow([])
        writer.writerow(["data", "agente", "quarteirao", "imovel", "situacao", "positivo", "bairro", "latitude", "longitude"])
        for v in data["visitas"]:
            writer.writerow([v["data"], v["agente"], v["quarteirao"], v["imovel"], v["situacao"], v["positivo"], v["bairro"], v["latitude"] or "", v["longitude"] or ""])
        from flask import Response
        return Response("\ufeff" + stream.getvalue(), content_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="agentes-{pid}-{de}-{ate}.csv"'})


def _period():
    """de/ate em AAAA-MM-DD; padrão: últimos 7 dias até hoje; máximo 92 dias."""
    today = date.today()
    try:
        ate = date.fromisoformat(request.args.get("ate", "")) if request.args.get("ate") else today
        de = date.fromisoformat(request.args.get("de", "")) if request.args.get("de") else ate - timedelta(days=6)
    except ValueError:
        abort(400, description="Período inválido.")
    if de > ate:
        de, ate = ate, de
    if (ate - de).days > 92:
        de = ate - timedelta(days=92)
    return de, ate


def painel_agentes(pid, de, ate, only_user=None):
    """KPIs, situação atual por agente, histórico por dia e visitas do período."""
    from app.modules.vigilancia.field_models import CampoInspecao
    from app.modules.vigilancia.planning_models import CampoPlanoQuarteirao, CampoPlanoVisita
    now = datetime.now()
    start = datetime.combine(de, datetime.min.time())
    end = datetime.combine(ate, datetime.min.time()) + timedelta(days=1)
    today_start = datetime.combine(date.today(), datetime.min.time())
    agentes = Usuario.query.filter_by(prefeitura_id=pid, tipo_usuario="agente_endemias").order_by(Usuario.nome_uvis).all()
    if only_user:
        agentes = [a for a in agentes if a.id == only_user]
    ids = [a.id for a in agentes] or [0]
    positions = (AgentePosicao.query.filter(AgentePosicao.usuario_id.in_(ids), AgentePosicao.registrado_em >= start,
                                            AgentePosicao.registrado_em < end).order_by(AgentePosicao.usuario_id, AgentePosicao.registrado_em).all())
    # visitas do período (planejamento -> inspeção) por autor
    rows = (db.session.query(CampoPlanoVisita, CampoInspecao)
            .join(CampoInspecao, (CampoInspecao.prefeitura == CampoPlanoVisita.prefeitura) & (CampoInspecao.demo == CampoPlanoVisita.demo)
                  & (CampoInspecao.origin == CampoPlanoVisita.origin) & (CampoInspecao.code == CampoPlanoVisita.code))
            .filter(CampoPlanoVisita.prefeitura == pid, CampoPlanoVisita.autor.in_([str(i) for i in ids])).all())
    names = {a.id: a.nome_uvis for a in agentes}
    visitas = []
    for visita, insp in rows:
        payload = insp.payload or {}
        dia = payload.get("data_inspecao") or ""
        if not (de.isoformat() <= dia <= ate.isoformat()):
            continue
        try:
            uid = int(visita.autor)
        except ValueError:
            continue
        visitas.append({"data": dia, "usuario_id": uid, "agente": names.get(uid, visita.autor), "plano": visita.plano, "quarteirao": visita.quarteirao,
                        "imovel": payload.get("imovel_codigo"), "situacao": payload.get("situacao"), "positivo": payload.get("positivo_aedes") or "",
                        "bairro": payload.get("bairro"), "latitude": _finite(payload.get("latitude"), -34, 6), "longitude": _finite(payload.get("longitude"), -74, -28),
                        "demo": visita.demo})
    visitas.sort(key=lambda v: (v["data"], v["agente"]), reverse=True)
    # posições agrupadas por agente e dia
    by_day = {}
    for p in positions:
        key = (p.usuario_id, p.registrado_em.date().isoformat())
        by_day.setdefault(key, []).append(p)
    historico = []
    for (uid, dia), pts in sorted(by_day.items(), key=lambda k: (k[0][1], names.get(k[0][0], "")), reverse=True):
        coords = [(q.latitude, q.longitude) for q in pts]
        vs = [v for v in visitas if v["usuario_id"] == uid and v["data"] == dia]
        historico.append({"data": dia, "usuario_id": uid, "agente": names.get(uid, str(uid)), "inicio": pts[0].registrado_em.strftime("%H:%M"),
                          "fim": pts[-1].registrado_em.strftime("%H:%M"), "pontos": len(pts),
                          "km": round(sum(_haversine(a, b) for a, b in zip(coords, coords[1:])), 2), "visitas": len(vs),
                          "inspecionados": sum(1 for v in vs if v["situacao"] == "INSPECIONADO"),
                          "nao_inspecionados": sum(1 for v in vs if v["situacao"] and v["situacao"] != "INSPECIONADO"),
                          "positivos": sum(1 for v in vs if v["positivo"] == "SIM")})
    # dias com visita mas sem GPS também entram no histórico
    seen = {(h["usuario_id"], h["data"]) for h in historico}
    for v in visitas:
        if (v["usuario_id"], v["data"]) not in seen:
            seen.add((v["usuario_id"], v["data"]))
            vs = [x for x in visitas if x["usuario_id"] == v["usuario_id"] and x["data"] == v["data"]]
            historico.append({"data": v["data"], "usuario_id": v["usuario_id"], "agente": v["agente"], "inicio": None, "fim": None, "pontos": 0, "km": 0,
                              "visitas": len(vs), "inspecionados": sum(1 for x in vs if x["situacao"] == "INSPECIONADO"),
                              "nao_inspecionados": sum(1 for x in vs if x["situacao"] and x["situacao"] != "INSPECIONADO"),
                              "positivos": sum(1 for x in vs if x["positivo"] == "SIM")})
    historico.sort(key=lambda h: (h["data"], h["agente"]), reverse=True)
    # situação atual por agente (hoje)
    blocks = {}
    for b in CampoPlanoQuarteirao.query.filter(CampoPlanoQuarteirao.prefeitura == pid, CampoPlanoQuarteirao.agente_id.in_(ids)).all():
        blocks[b.agente_id] = blocks.get(b.agente_id, 0) + 1
    last_by_user = {}
    for p in AgentePosicao.query.filter(AgentePosicao.usuario_id.in_(ids)).order_by(AgentePosicao.registrado_em.desc()).limit(2000):
        last_by_user.setdefault(p.usuario_id, p)
    lista = []
    for a in agentes:
        last = last_by_user.get(a.id)
        today_pts = [p for p in positions if p.usuario_id == a.id and p.registrado_em >= today_start]
        today_v = [v for v in visitas if v["usuario_id"] == a.id and v["data"] == date.today().isoformat()]
        minutes = int((now - last.registrado_em).total_seconds() // 60) if last else None
        if last and last.registrado_em >= today_start and minutes is not None and minutes <= 15:
            status = "em_campo"
        elif last and last.registrado_em >= today_start:
            status = "parado"
        else:
            status = "sem_gps"
        coords = [(p.latitude, p.longitude) for p in today_pts]
        lista.append({"id": a.id, "nome": a.nome_uvis, "login": a.login, "status": status, "parado_min": minutes if status == "parado" else None,
                      "ultimo_ping": last.registrado_em.strftime("%d/%m %H:%M") if last else None, "ultima_posicao": [last.latitude, last.longitude] if last else None,
                      "pontos_hoje": len(today_pts), "km_hoje": round(sum(_haversine(x, y) for x, y in zip(coords, coords[1:])), 2),
                      "visitas_hoje": len(today_v), "positivos_hoje": sum(1 for v in today_v if v["positivo"] == "SIM"),
                      "quarteiroes": blocks.get(a.id, 0), "telegram": bool(getattr(a, "telegram_chat_id", None)),
                      "visitas_periodo": sum(1 for v in visitas if v["usuario_id"] == a.id),
                      "km_periodo": round(sum(h["km"] for h in historico if h["usuario_id"] == a.id), 2),
                      "dias_ativos": len({h["data"] for h in historico if h["usuario_id"] == a.id})})
    kpis = {"atribuidos": len(agentes), "em_campo": sum(1 for x in lista if x["status"] == "em_campo"),
            "parados": sum(1 for x in lista if x["status"] == "parado"), "sem_gps_hoje": sum(1 for x in lista if x["status"] == "sem_gps"),
            "visitas_hoje": sum(x["visitas_hoje"] for x in lista), "positivos_hoje": sum(x["positivos_hoje"] for x in lista),
            "visitas_periodo": len(visitas), "km_periodo": round(sum(h["km"] for h in historico), 2)}
    return {"de": de.isoformat(), "ate": ate.isoformat(), "kpis": kpis, "agentes": lista, "historico": historico, "visitas": visitas[:500]}


def _haversine(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))
