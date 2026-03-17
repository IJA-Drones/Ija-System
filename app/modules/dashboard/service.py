from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Equipe, EquipeUvis, Solicitacao


def build_dashboard_context(user, args, google_maps_key):
    query = (
        Solicitacao.query.options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .filter(Solicitacao.usuario_id == user.id)
        .filter(Solicitacao.status != "CANCELADO")
    )

    filtro_status = args.get("status")
    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    filtro_tipo_visita = args.get("tipo_visita")
    if filtro_tipo_visita:
        query = query.filter(Solicitacao.tipo_visita == filtro_tipo_visita)

    filtro_foco = args.get("foco")
    if filtro_foco:
        query = query.filter(Solicitacao.foco == filtro_foco)

    data_ini = args.get("data_ini")
    data_fim = args.get("data_fim")

    if data_ini:
        try:
            dt_ini = datetime.strptime(data_ini, "%Y-%m-%d").date()
            query = query.filter(Solicitacao.data_agendamento >= dt_ini)
        except ValueError:
            pass

    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
            query = query.filter(Solicitacao.data_agendamento <= dt_fim)
        except ValueError:
            pass

    page = args.get("page", 1, type=int)
    paginacao = query.order_by(Solicitacao.data_criacao.desc()).paginate(
        page=page,
        per_page=6,
        error_out=False,
    )

    equipes_query = Equipe.query.filter_by(ativa=True)
    if user.regiao:
        equipes_query = equipes_query.filter(Equipe.regiao == user.regiao)
    equipes = equipes_query.order_by(Equipe.nome_equipe.asc()).all()

    rows = (
        db.session.query(EquipeUvis.nome_equipe, func.count(EquipeUvis.id).label("total"))
        .filter(EquipeUvis.uvis_usuario_id == user.id)
        .group_by(EquipeUvis.nome_equipe)
        .order_by(EquipeUvis.nome_equipe.asc())
        .all()
    )
    equipes_uvis = [{"nome_equipe": row[0], "total": int(row[1])} for row in rows]

    return {
        "solicitacoes": paginacao.items,
        "paginacao": paginacao,
        "google_maps_key": google_maps_key,
        "equipes": equipes,
        "equipes_uvis": equipes_uvis,
    }
