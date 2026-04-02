from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Drones, Equipe, EquipeUvis, Solicitacao


STATUS_OS_CONCLUIDAS = ["CONCLUIDO", "CONCLUÍDO"]


class DashboardError(Exception):
    def __init__(self, message, *, category="warning", redirect_endpoint="main.dashboard"):
        super().__init__(message)
        self.message = message
        self.category = category
        self.redirect_endpoint = redirect_endpoint


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
        if filtro_status in {"CONCLUIDO", "CONCLUÍDO"}:
            query = query.filter(
                or_(
                    Solicitacao.status == "CONCLUIDO",
                    Solicitacao.status == "CONCLUÍDO",
                )
            )
        else:
            query = query.filter(Solicitacao.status == filtro_status)

    filtro_tipo_visita = args.get("tipo_visita")
    if filtro_tipo_visita:
        query = query.filter(Solicitacao.tipo_visita == filtro_tipo_visita)

    filtro_tipo_operacao = (args.get("tipo_operacao") or args.get("operacao") or "").strip()
    if filtro_tipo_operacao:
        query = query.filter(Solicitacao.tipo_operacao == filtro_tipo_operacao)

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


def build_uvis_historico_os_context(user, args):
    if getattr(user, "tipo_usuario", None) != "uvis":
        raise DashboardError("Acesso restrito.", category="danger")

    query = (
        Solicitacao.query.options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .filter(
            Solicitacao.usuario_id == user.id,
            Solicitacao.status.in_(STATUS_OS_CONCLUIDAS),
        )
    )

    page = args.get("page", 1, type=int)
    paginacao = (
        query.order_by(Solicitacao.data_criacao.desc(), Solicitacao.id.desc())
        .paginate(page=page, per_page=6, error_out=False)
    )

    return {"pedidos": paginacao.items, "paginacao": paginacao}


def build_uvis_os_form_context(user, os_id):
    if getattr(user, "tipo_usuario", None) != "uvis":
        raise DashboardError("Acesso restrito.", category="danger")

    solicitacao = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico),
        )
        .get_or_404(os_id)
    )

    if solicitacao.usuario_id != user.id:
        raise DashboardError("Voce nao tem permissao para acessar esta OS.", category="danger")

    if (solicitacao.status or "").strip().upper() not in STATUS_OS_CONCLUIDAS:
        raise DashboardError(
            "Esta OS ainda nao esta concluida.",
            category="warning",
            redirect_endpoint="main.uvis_historico_os",
        )

    equipe = solicitacao.equipe
    ordem = solicitacao.ordem_servico
    drones_equipe = []
    if solicitacao.equipe_id:
        drones_equipe = (
            Drones.query
            .filter(Drones.equipe_id == solicitacao.equipe_id)
            .order_by(Drones.renomacao.asc())
            .all()
        )

    return {
        "solicitacao": solicitacao,
        "equipe": equipe,
        "ordem": ordem,
        "modo_visualizacao": True,
        "uvis_nome": solicitacao.usuario.nome_uvis if solicitacao.usuario else "",
        "endereco_os": (
            f"{solicitacao.logradouro or ''}, {solicitacao.numero or 'S/N'} - "
            f"{solicitacao.bairro or ''} - {solicitacao.cidade or ''}/{solicitacao.uf or ''}"
        ),
        "piloto_padrao": (
            equipe.piloto_titular.nome_piloto if equipe and equipe.piloto_titular else ""
        ) if equipe else "",
        "auxiliar_padrao": (
            equipe.piloto_auxiliar.nome_piloto if equipe and equipe.piloto_auxiliar else ""
        ) if equipe else "",
        "respondido_por_padrao": "",
        "respondido_em_value": (
            ordem.respondido_em.strftime("%Y-%m-%dT%H:%M")
            if ordem and ordem.respondido_em else ""
        ),
        "drones_equipe": drones_equipe,
    }
