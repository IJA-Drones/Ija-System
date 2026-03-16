import os

from flask import current_app
from sqlalchemy import extract

from app.extensions import db
from app.models import Solicitacao, Usuario


APPROVED_MAP_STATUSES = (
    "APROVADO",
    "APROVADO COM RECOMENDACOES",
    "APROVADO COM RECOMENDA\u00c7\u00d5ES",
)


def build_heatmap_query(user, *, uvis_id=None, mes=None, ano=None):
    query = Solicitacao.query.filter(
        Solicitacao.latitude.isnot(None),
        Solicitacao.longitude.isnot(None),
        Solicitacao.status.in_(APPROVED_MAP_STATUSES),
    )

    if mes and ano:
        query = query.filter(
            extract("month", Solicitacao.data_agendamento) == mes,
            extract("year", Solicitacao.data_agendamento) == ano,
        )

    if getattr(user, "tipo_usuario", None) == "uvis":
        query = query.filter(Solicitacao.usuario_id == user.id)
    elif getattr(user, "tipo_usuario", None) == "admin" and uvis_id:
        query = query.filter(Solicitacao.usuario_id == uvis_id)

    return query


def build_heatmap_points(user, *, uvis_id=None, mes=None, ano=None):
    pontos = []
    solicitacoes = build_heatmap_query(user, uvis_id=uvis_id, mes=mes, ano=ano).all()

    for solicitacao in solicitacoes:
        try:
            lat = float(solicitacao.latitude)
            lng = float(solicitacao.longitude)
        except (TypeError, ValueError):
            continue

        pontos.append(
            {
                "lat": lat,
                "lng": lng,
                "foco": (solicitacao.foco or "").strip() or "Outros",
            }
        )

    return pontos


def build_uvis_disponiveis(user):
    if getattr(user, "tipo_usuario", None) != "admin":
        return []

    return (
        db.session.query(Usuario.id, Usuario.nome_uvis)
        .filter(Usuario.tipo_usuario == "uvis")
        .order_by(Usuario.nome_uvis.asc())
        .all()
    )


def get_mapa_relatorio_key():
    return current_app.config.get("Maps_KEY_FRONT") or os.getenv("KEY_API_GOOGLE_MAPS")


def get_consulta_geolocalizacao_key():
    return os.getenv("KEY_API_GOOGLE_MAPS")
