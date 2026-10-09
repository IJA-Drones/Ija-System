from app.modules.gestao_ti.permissions import route_access
import os
from math import isfinite

from flask import current_app
from sqlalchemy import extract, func, or_

from app.extensions import db
from app.models import OrdemServico, OrdemServicoEquipeUvis, Solicitacao, Usuario
from app.shared.access import (
    apply_prefeitura_scope,
    apply_regiao_scope,
    apply_solicitacao_prefeitura_scope,
    apply_solicitacao_regiao_scope,
    is_admin_global_user,
)


APPROVED_MAP_STATUSES = (
    "APROVADO",
    "APROVADO COM RECOMENDACOES",
    "APROVADO COM RECOMENDA\u00c7\u00d5ES",
)
VISIBLE_MAP_STATUSES = (*APPROVED_MAP_STATUSES, "CONCLUIDO", "CONCLUÍDO")


def normalize_larva_filter(value):
    value = (value or "").strip().upper().replace("Ã", "A")
    if value in {"", "TODOS"}:
        return None
    if value not in {"SIM", "NAO", "NAO_INFORMADO"}:
        raise ValueError("Filtro de larva visualizada inválido.")
    return value


def _normalized_larva_answer(column):
    # SQLite's upper() only handles ASCII; normalize both accented variants first.
    answer = func.replace(func.replace(func.trim(func.coalesce(column, "")), "ã", "a"), "Ã", "A")
    return func.upper(answer)


def build_heatmap_query(user, *, uvis_id=None, mes=None, ano=None, larva_visualizada=None):
    query = Solicitacao.query.filter(
        Solicitacao.latitude.isnot(None),
        Solicitacao.longitude.isnot(None),
        Solicitacao.status.in_(VISIBLE_MAP_STATUSES),
    )
    query = apply_solicitacao_prefeitura_scope(query, user)
    query = apply_solicitacao_regiao_scope(query, user)

    if mes is not None:
        query = query.filter(extract("month", Solicitacao.data_agendamento) == mes)
    if ano is not None:
        query = query.filter(extract("year", Solicitacao.data_agendamento) == ano)

    if getattr(user, "tipo_usuario", None) == "uvis":
        query = query.filter(Solicitacao.usuario_id == user.id)
    elif (is_admin_global_user(user) or getattr(user, "tipo_usuario", None) in {"regional", "prefeitura_admin"}) and uvis_id:
        query = query.filter(Solicitacao.usuario_id == uvis_id)

    larva_filter = normalize_larva_filter(larva_visualizada)
    if larva_filter:
        drone_answer = _normalized_larva_answer(OrdemServico.larva_visualizada)
        uvis_answer = _normalized_larva_answer(OrdemServicoEquipeUvis.larva_visualizada)
        has_larva = or_(
            Solicitacao.ordem_servico.has(drone_answer == "SIM"),
            Solicitacao.ordem_servico_equipe_uvis.has(uvis_answer == "SIM"),
        )
        has_no_larva = or_(
            Solicitacao.ordem_servico.has(drone_answer == "NAO"),
            Solicitacao.ordem_servico_equipe_uvis.has(uvis_answer == "NAO"),
        )
        if larva_filter == "SIM":
            query = query.filter(has_larva)
        elif larva_filter == "NAO":
            query = query.filter(has_no_larva, ~has_larva)
        else:
            query = query.filter(~has_larva, ~has_no_larva)

    return query


def build_heatmap_points(user, *, uvis_id=None, mes=None, ano=None, larva_visualizada=None):
    pontos = []
    solicitacoes = build_heatmap_query(
        user, uvis_id=uvis_id, mes=mes, ano=ano, larva_visualizada=larva_visualizada
    ).all()

    for solicitacao in solicitacoes:
        try:
            lat = float(solicitacao.latitude)
            lng = float(solicitacao.longitude)
        except (TypeError, ValueError):
            continue
        if not isfinite(lat) or not isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
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
    if not route_access(user, is_admin_global_user(user) or getattr(user, 'tipo_usuario', None) in {'regional', 'prefeitura_admin'}):
        return []

    query = db.session.query(Usuario.id, Usuario.nome_uvis).filter(Usuario.tipo_usuario == "uvis")
    query = apply_prefeitura_scope(query, user, Usuario.prefeitura_id)
    query = apply_regiao_scope(query, user, Usuario.regiao)
    return query.order_by(Usuario.nome_uvis.asc()).all()


def get_mapa_relatorio_key():
    return current_app.config.get("Maps_KEY_FRONT") or os.getenv("KEY_API_GOOGLE_MAPS")


def get_consulta_geolocalizacao_key():
    return os.getenv("KEY_API_GOOGLE_MAPS")
