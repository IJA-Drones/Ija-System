"""Imóveis pendentes (fechado, recusado, desabitado) com fotos e vídeos da inspeção (TR 4.8 XIII).

As mídias usam o mesmo armazenamento dos anexos de denúncia: Skybox (WebDAV) quando
configurado, senão a pasta local upload-files/.
"""

import os
import uuid
from datetime import date, datetime

from flask import abort, render_template, request, send_from_directory
from flask_login import current_user

from app.extensions import db
from app.models import Prefeitura, Usuario
from app.shared.access import is_admin_global_user
from app.shared.file_recovery import save_file
from app.shared.skybox import SkyboxError, is_skybox_path, skybox_enabled, stream_skybox_file, upload_file_to_skybox
from app.shared.uploads import get_upload_folder
from .agent_tracking import _access, _finite, _prefeitura
from .field_models import CampoInspecao, CampoLevantamento
from .planning_models import CampoPlanoVisita

PENDING = ("FECHADO", "RECUSADO", "DESABITADO")
SITUACOES = {"INSPECIONADO": "Inspecionado", "FECHADO": "Fechado", "RECUSADO": "Recusado", "DESABITADO": "Desabitado",
             "NAO_INSPECIONADO": "Não inspecionado"}
# extensão -> (tipo, content-type servido); o content-type nunca vem do cliente
MEDIA_TYPES = {"jpg": ("foto", "image/jpeg"), "jpeg": ("foto", "image/jpeg"), "png": ("foto", "image/png"),
               "heic": ("foto", "image/heic"), "mp4": ("video", "video/mp4"), "mov": ("video", "video/quicktime")}
MAX_FILES = 5
MAX_BYTES = 50 * 1024 * 1024


class InspecaoMidia(db.Model):
    __tablename__ = "vigilancia_inspecao_midias"
    id = db.Column(db.Integer, primary_key=True)
    prefeitura = db.Column(db.Integer, nullable=False)
    demo = db.Column(db.Boolean, nullable=False)
    origin = db.Column(db.String(10), nullable=False)
    inspecao_code = db.Column(db.String(80), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    arquivo_path = db.Column(db.String(500), nullable=False)  # *_path: protegido pelo file_recovery
    content_type = db.Column(db.String(100), nullable=False)
    tamanho = db.Column(db.Integer, nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    autor = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    __table_args__ = (
        db.ForeignKeyConstraint(["prefeitura", "demo", "origin", "inspecao_code"],
            ["vigilancia_campo_inspecoes.prefeitura", "vigilancia_campo_inspecoes.demo", "vigilancia_campo_inspecoes.origin", "vigilancia_campo_inspecoes.code"],
            name="fk_inspecao_midia_inspecao", ondelete="CASCADE"),
        db.CheckConstraint("tipo IN ('foto','video')", name="ck_inspecao_midia_tipo"),
        db.Index("ix_inspecao_midia_inspecao", "prefeitura", "demo", "origin", "inspecao_code"),
    )


class MidiaError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _size(arquivo):
    stream = arquivo.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    return size


def save_media(user, inspecao_code, arquivos, latitude=None, longitude=None):
    """Grava as mídias da visita do próprio agente. Tudo ou nada: valida todos os arquivos antes de salvar."""
    visita = CampoPlanoVisita.query.filter_by(prefeitura=user.prefeitura_id, code=inspecao_code, autor=str(user.id)).first()
    if visita is None:
        raise MidiaError("Visita não encontrada entre as registradas por você.", 404)
    arquivos = [a for a in arquivos if a and a.filename]
    existentes = InspecaoMidia.query.filter_by(prefeitura=visita.prefeitura, demo=visita.demo, origin=visita.origin,
                                               inspecao_code=visita.code).count()
    if not arquivos:
        raise MidiaError("Envie ao menos uma foto ou vídeo.")
    if len(arquivos) + existentes > MAX_FILES:
        raise MidiaError(f"Cada visita aceita no máximo {MAX_FILES} fotos ou vídeos.")
    prepared = []
    for arquivo in arquivos:
        ext = arquivo.filename.rsplit(".", 1)[-1].lower() if "." in arquivo.filename else ""
        if ext not in MEDIA_TYPES:
            raise MidiaError("Envie fotos JPG, PNG ou HEIC, ou vídeos MP4 ou MOV.")
        size = _size(arquivo)
        if size <= 0 or size > MAX_BYTES:
            raise MidiaError("Cada arquivo deve ter até 50 MB.")
        prepared.append((arquivo, ext, size))
    lat, lng = _finite(latitude, -34, 6), _finite(longitude, -74, -28)
    safe_code = "".join(c for c in visita.code if c.isalnum() or c in "-_")[:80] or "inspecao"
    relative_dir = "/".join(["vigilancia", "inspecoes", str(visita.prefeitura), safe_code])
    rows = []
    try:
        for arquivo, ext, size in prepared:
            tipo, content_type = MEDIA_TYPES[ext]
            name = f"{uuid.uuid4().hex}.{ext}"
            if skybox_enabled():
                path = upload_file_to_skybox(arquivo, f"{relative_dir}/{name}")
            else:
                folder = os.path.join(get_upload_folder(), *relative_dir.split("/"))
                os.makedirs(folder, exist_ok=True)
                save_file(arquivo, os.path.join(folder, name))
                path = f"{relative_dir}/{name}"
            rows.append(InspecaoMidia(prefeitura=visita.prefeitura, demo=visita.demo, origin=visita.origin, inspecao_code=visita.code,
                                      tipo=tipo, arquivo_path=path, content_type=content_type, tamanho=size,
                                      latitude=lat, longitude=lng, autor=user.id))
    except SkyboxError as exc:
        raise MidiaError("Não foi possível salvar a mídia enviada. Tente novamente.", 503) from exc
    db.session.add_all(rows)
    db.session.commit()
    return rows


def _filters():
    f = {k: (request.args.get(k) or "").strip()[:80] for k in ("levantamento", "quarteirao", "bairro", "situacao", "de", "ate")}
    for k in ("de", "ate"):
        if f[k]:
            try:
                date.fromisoformat(f[k])
            except ValueError:
                abort(400, description="Período inválido.")
    if f["situacao"] and f["situacao"] not in PENDING:
        abort(400, description="Situação inválida.")
    return f


def pending_report(pid, demo, f):
    """Última situação por imóvel; pendente = última visita FECHADO/RECUSADO/DESABITADO."""
    query = (db.session.query(CampoInspecao, CampoPlanoVisita)
             .outerjoin(CampoPlanoVisita, (CampoPlanoVisita.prefeitura == CampoInspecao.prefeitura) & (CampoPlanoVisita.demo == CampoInspecao.demo)
                        & (CampoPlanoVisita.origin == CampoInspecao.origin) & (CampoPlanoVisita.code == CampoInspecao.code))
             .filter(CampoInspecao.prefeitura == pid, CampoInspecao.demo == demo))
    if f["levantamento"]:
        query = query.filter(CampoInspecao.survey_code == f["levantamento"])
    imoveis = {}
    for insp, visita in query.all():
        p = insp.payload or {}
        dia = p.get("data_inspecao") or ""
        if (f["de"] and dia < f["de"]) or (f["ate"] and dia > f["ate"]):
            continue
        imoveis.setdefault(insp.property_code, []).append((dia, insp, visita))
    autores = set()
    linhas = []
    for code, visitas in imoveis.items():
        visitas.sort(key=lambda v: (v[0], v[1].code))
        dia, last, last_visita = visitas[-1]
        p = last.payload or {}
        quarteirao = next((v[2].quarteirao for v in reversed(visitas) if v[2]), None) or "Sem quarteirão"
        lat, lng = _finite(p.get("latitude"), -34, 6), _finite(p.get("longitude"), -74, -28)
        if lat is None:
            lat, lng = next(((_finite(v[1].payload.get("latitude"), -34, 6), _finite(v[1].payload.get("longitude"), -74, -28))
                             for v in reversed(visitas) if _finite(v[1].payload.get("latitude"), -34, 6) is not None), (None, None))
        autor = last_visita.autor if last_visita else None
        if autor and autor.isdecimal():
            autores.add(int(autor))
        linhas.append({"imovel": code, "situacao": p.get("situacao"), "data": dia, "tentativas": len(visitas),
                       "quarteirao": quarteirao, "bairro": p.get("bairro") or "", "levantamento": last.survey_code or "",
                       "autor": autor, "latitude": lat, "longitude": lng,
                       "inspecoes": [(v[1].origin, v[1].code) for v in visitas], "pendente": p.get("situacao") in PENDING})
    bairros = sorted({x["bairro"] for x in linhas if x["bairro"]})
    quarteiroes = sorted({x["quarteirao"] for x in linhas})
    linhas = [x for x in linhas if (not f["bairro"] or x["bairro"] == f["bairro"]) and (not f["quarteirao"] or x["quarteirao"] == f["quarteirao"])]
    # % de pendência por quarteirão = imóveis pendentes / imóveis visitados (antes do filtro de situação)
    por_quarteirao = {}
    for x in linhas:
        q = por_quarteirao.setdefault(x["quarteirao"], {"quarteirao": x["quarteirao"], "visitados": 0, "pendentes": 0})
        q["visitados"] += 1
        q["pendentes"] += x["pendente"]
    for q in por_quarteirao.values():
        q["percentual"] = round(100 * q["pendentes"] / q["visitados"], 1) if q["visitados"] else 0
    pendentes = [x for x in linhas if x["pendente"] and (not f["situacao"] or x["situacao"] == f["situacao"])]
    nomes = {u.id: u.nome_uvis for u in Usuario.query.filter(Usuario.id.in_(autores or {0})).all()}
    codes = {c for x in pendentes for _, c in x["inspecoes"]}
    midias = {}
    if codes:
        for m in (InspecaoMidia.query.filter(InspecaoMidia.prefeitura == pid, InspecaoMidia.demo == demo, InspecaoMidia.inspecao_code.in_(codes))
                  .order_by(InspecaoMidia.criado_em).all()):
            midias.setdefault((m.origin, m.inspecao_code), []).append(m)
    for x in pendentes:
        x["agente"] = nomes.get(int(x["autor"]), x["autor"]) if x["autor"] and x["autor"].isdecimal() else (x["autor"] or "—")
        own = [m for key in x.pop("inspecoes") for m in midias.get(key, [])]
        x["midias"] = [{"id": m.id, "tipo": m.tipo, "content_type": m.content_type, "data": m.criado_em.strftime("%d/%m/%Y %H:%M"),
                        "inspecao": m.inspecao_code} for m in own]
        if x["latitude"] is None:  # sem GPS na inspeção: usa o da mídia, se houver
            gps = next((m for m in own if m.latitude is not None), None)
            if gps:
                x["latitude"], x["longitude"] = gps.latitude, gps.longitude
        x.pop("autor")
    pendentes.sort(key=lambda x: (x["data"], x["imovel"]), reverse=True)
    resumo = {"pendentes": len(pendentes), "com_midia": sum(1 for x in pendentes if x["midias"]),
              "visitados": len(linhas), "percentual": round(100 * sum(x["pendente"] for x in linhas) / len(linhas), 1) if linhas else 0}
    return {"resumo": resumo, "quarteiroes": sorted(por_quarteirao.values(), key=lambda q: (-q["percentual"], q["quarteirao"])),
            "imoveis": pendentes, "opcoes": {"bairros": bairros, "quarteiroes": quarteiroes}}


def register_routes(bp):
    @bp.get("/vigilancia/pendentes", endpoint="vigilancia_pendentes")
    @_access
    def vigilancia_pendentes():
        pid, f = _prefeitura(), _filters()
        demo = request.args.get("demo") == "true"
        report = pending_report(pid, demo, f) if pid else None
        levantamentos = [c for (c,) in db.session.query(CampoLevantamento.code).filter_by(prefeitura=pid, demo=demo).order_by(CampoLevantamento.code)] if pid else []
        prefeituras = Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all() if is_admin_global_user(current_user) else []
        return render_template("vigilancia_pendentes.html", prefeitura_id=pid, prefeituras=prefeituras, filtros=f, demo=demo,
                               report=report, levantamentos=levantamentos, situacoes=SITUACOES, pending=PENDING,
                               global_user=is_admin_global_user(current_user))

    @bp.get("/vigilancia/pendentes/midias/<int:midia_id>", endpoint="vigilancia_pendentes_midia")
    @_access
    def vigilancia_pendentes_midia(midia_id):
        midia = db.session.get(InspecaoMidia, midia_id) or abort(404)
        if not is_admin_global_user(current_user) and midia.prefeitura != getattr(current_user, "prefeitura_id", None):
            abort(404)
        if is_skybox_path(midia.arquivo_path):
            try:
                response = stream_skybox_file(midia.arquivo_path, request.headers.get("Range"), conditional_headers=request.headers)
            except SkyboxError:
                abort(404)
        else:
            rel = midia.arquivo_path.replace("\\", "/")
            if rel.startswith("/") or any(part in {"", ".", ".."} for part in rel.split("/")):
                abort(404)
            response = send_from_directory(get_upload_folder(), rel, mimetype=midia.content_type, max_age=86400)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "private, max-age=86400"
        return response
