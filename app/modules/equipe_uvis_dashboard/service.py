from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.models import Solicitacao


class EquipeUvisDashboardError(Exception):
    def __init__(self, message, *, category="danger", redirect_endpoint="main.dashboard"):
        super().__init__(message)
        self.message = message
        self.category = category
        self.redirect_endpoint = redirect_endpoint


def build_dashboard_equipe_uvis_context(user, args, google_maps_key):
    uvis_id = getattr(user, "equipe_uvis_uvis_usuario_id", None)
    nome_equipe = (getattr(user, "equipe_uvis_nome", "") or "").strip()

    if not uvis_id or not nome_equipe:
        raise EquipeUvisDashboardError(
            "Conta de equipe sem vinculo com UVIS/equipe. Contate o administrador.",
            redirect_endpoint="auth.login",
        )

    query = (
        Solicitacao.query.options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .filter(Solicitacao.usuario_id == uvis_id)
        .filter(Solicitacao.equipe_uvis_nome == nome_equipe)
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

    return {
        "solicitacoes": paginacao.items,
        "paginacao": paginacao,
        "google_maps_key": google_maps_key,
        "nome_equipe": nome_equipe,
    }
