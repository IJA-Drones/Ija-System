from datetime import date
import re

from sqlalchemy import or_

from app.models import OrdemServico, OrdemServicoEquipeUvis, Solicitacao, Usuario
from app.shared.query_filters import id_search_clause


HISTORY_FILTER_KEYS = (
    "status",
    "unidade",
    "regiao",
    "apoio_cet",
    "tipo_visita",
    "tipo_imovel",
    "foco",
    "protocolo",
    "endereco",
    "data_ini",
    "data_fim",
)
CONCLUDED_STATUSES = ("CONCLUIDO", "CONCLUÍDO")


def get_os_history_filters(args, *, status_key="status"):
    filters = {key: (args.get(key) or "").strip() for key in HISTORY_FILTER_KEYS}
    filters["status"] = (args.get(status_key) or "").strip().upper()
    filters["regiao"] = filters["regiao"].upper()
    filters["apoio_cet"] = filters["apoio_cet"].upper()
    return filters


def apply_os_history_filters(query, filters, *, apply_status=True):
    if apply_status:
        status = filters["status"]
        if status == "CONCLUIDAS":
            query = query.filter(Solicitacao.status.in_(CONCLUDED_STATUSES))
        elif status == "EM_ANDAMENTO":
            query = query.filter(~Solicitacao.status.in_(CONCLUDED_STATUSES))
        elif status:
            query = query.filter(Solicitacao.status == status)

    if filters["unidade"]:
        query = query.filter(
            Solicitacao.usuario.has(Usuario.nome_uvis.ilike(f"%{filters['unidade']}%"))
        )

    if filters["regiao"]:
        query = query.filter(Solicitacao.usuario.has(Usuario.regiao.ilike(f"%{filters['regiao']}%")))

    if filters["apoio_cet"] == "SIM":
        query = query.filter(Solicitacao.apoio_cet.is_(True))
    elif filters["apoio_cet"] == "NAO":
        query = query.filter(Solicitacao.apoio_cet.is_(False))

    for field in ("tipo_visita", "tipo_imovel", "foco"):
        if filters[field]:
            query = query.filter(getattr(Solicitacao, field) == filters[field])

    if filters["protocolo"]:
        termo = filters["protocolo"]
        like = f"%{termo}%"
        query = query.filter(
            or_(
                id_search_clause(Solicitacao.id, termo, prefixes=("id", "os")),
                Solicitacao.protocolo.ilike(like),
                Solicitacao.ordem_servico.has(OrdemServico.identificador_os.ilike(like)),
                Solicitacao.ordem_servico_equipe_uvis.has(
                    OrdemServicoEquipeUvis.identificador_os.ilike(like)
                ),
            )
        )

    if filters["endereco"]:
        for token in (token for token in re.split(r"[\s,;/\-]+", filters["endereco"]) if token):
            like = f"%{token}%"
            query = query.filter(
                or_(
                    Solicitacao.logradouro.ilike(like),
                    Solicitacao.numero.ilike(like),
                    Solicitacao.complemento.ilike(like),
                    Solicitacao.bairro.ilike(like),
                    Solicitacao.cidade.ilike(like),
                    Solicitacao.uf.ilike(like),
                    Solicitacao.cep.ilike(like),
                )
            )

    try:
        data_ini = date.fromisoformat(filters["data_ini"]) if filters["data_ini"] else None
    except ValueError:
        data_ini = None
    try:
        data_fim = date.fromisoformat(filters["data_fim"]) if filters["data_fim"] else None
    except ValueError:
        data_fim = None

    if data_ini and data_fim and data_ini > data_fim:
        data_ini, data_fim = data_fim, data_ini
    if data_ini:
        query = query.filter(Solicitacao.data_agendamento >= data_ini)
    if data_fim:
        query = query.filter(Solicitacao.data_agendamento <= data_fim)

    return query
