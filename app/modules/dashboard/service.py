import json
import os
from datetime import datetime

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload

from app.models import Drones, Equipe, OrdemServicoEquipeUvis, Solicitacao
from app.modules.piloto_os.service import build_os_media_context
from app.shared.os_history_filters import (
    apply_os_history_filters,
    apply_retorno_automatico_filter,
    get_os_history_filters,
)
from app.shared.query_filters import id_search_clause
from app.shared.query_filters import get_multi_values
from app.shared.retorno_ciclo import build_retorno_ciclo_context, build_retorno_ciclo_summaries

UVIS_HISTORICO_TIPO_OS_OPTIONS = ("todas", "piloto", "equipe_uvis")


STATUS_OS_CONCLUIDAS = ["CONCLUIDO", "CONCLU\u00cdDO"]
STATUS_EQUIPE_UVIS_CONCLUIDAS = ["CONCLUIDO", "CONCLU\u00cdDO"]


def _parse_media_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).replace("\\", "/") for item in value if item]
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).replace("\\", "/") for item in parsed if item]


def _has_equipe_uvis_os():
    return or_(
        Solicitacao.ordem_servico_equipe_uvis.has(),
        and_(
            Solicitacao.equipe_uvis_nome.isnot(None),
            func.trim(Solicitacao.equipe_uvis_nome) != "",
        ),
    )


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
            joinedload(Solicitacao.ordem_servico_equipe_uvis),
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

    filtro_tipo_imovel = (args.get("tipo_imovel") or "").strip()
    if filtro_tipo_imovel:
        query = query.filter(Solicitacao.tipo_imovel == filtro_tipo_imovel)

    filtro_tipo_operacao = (args.get("tipo_operacao") or args.get("operacao") or "").strip()
    if filtro_tipo_operacao:
        query = query.filter(Solicitacao.tipo_operacao == filtro_tipo_operacao)

    filtro_foco = get_multi_values(args, "foco")
    if filtro_foco:
        query = query.filter(Solicitacao.foco.in_(filtro_foco))

    filtro_protocolo = (args.get("protocolo") or "").strip()
    if filtro_protocolo:
        query = query.filter(
            or_(
                id_search_clause(Solicitacao.id, filtro_protocolo, prefixes=("id", "os")),
                Solicitacao.protocolo.ilike(f"%{filtro_protocolo}%"),
            )
        )

    query = apply_retorno_automatico_filter(query, args.get("retorno_automatico"))

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

    return {
        "solicitacoes": paginacao.items,
        "paginacao": paginacao,
        "google_maps_key": google_maps_key,
        "equipes": equipes,
        "retorno_ciclos": build_retorno_ciclo_summaries(user, paginacao.items),
        "filtros_multi": {
            "foco": filtro_foco,
        },
    }


def build_uvis_historico_os_context(user, args):
    if getattr(user, "tipo_usuario", None) != "uvis":
        raise DashboardError("Acesso restrito.", category="danger")

    filtro_tipo_os = (args.get("tipo_os") or "todas").strip().lower()
    if filtro_tipo_os not in UVIS_HISTORICO_TIPO_OS_OPTIONS:
        filtro_tipo_os = "todas"

    query = (
        Solicitacao.query.options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico_equipe_uvis),
        )
        .filter(
            Solicitacao.usuario_id == user.id,
        )
        .filter(Solicitacao.status != "CANCELADO")
    )

    if filtro_tipo_os == "piloto":
        query = query.filter(Solicitacao.status.in_(STATUS_OS_CONCLUIDAS))
    elif filtro_tipo_os == "equipe_uvis":
        query = query.filter(_has_equipe_uvis_os())
    else:
        query = query.filter(
            or_(
                Solicitacao.status.in_(STATUS_OS_CONCLUIDAS),
                _has_equipe_uvis_os(),
            )
        )

    filtros = get_os_history_filters(args)
    if filtro_tipo_os == "equipe_uvis":
        query = apply_os_history_filters(query, filtros, apply_status=False)
        if filtros["status"] == "CONCLUIDAS":
            query = query.filter(
                Solicitacao.ordem_servico_equipe_uvis.has(
                    OrdemServicoEquipeUvis.status.in_(STATUS_EQUIPE_UVIS_CONCLUIDAS)
                )
            )
        elif filtros["status"] == "EM_ANDAMENTO":
            query = query.filter(
                or_(
                    ~Solicitacao.ordem_servico_equipe_uvis.has(),
                    Solicitacao.ordem_servico_equipe_uvis.has(
                        ~OrdemServicoEquipeUvis.status.in_(STATUS_EQUIPE_UVIS_CONCLUIDAS)
                    ),
                )
            )
    else:
        query = apply_os_history_filters(query, filtros)

    total_todas = (
        Solicitacao.query
        .filter(Solicitacao.usuario_id == user.id)
        .filter(Solicitacao.status != "CANCELADO")
        .filter(
            or_(
                Solicitacao.status.in_(STATUS_OS_CONCLUIDAS),
                _has_equipe_uvis_os(),
            )
        )
        .count()
    )
    total_piloto = (
        Solicitacao.query
        .filter(
            Solicitacao.usuario_id == user.id,
            Solicitacao.status.in_(STATUS_OS_CONCLUIDAS),
        )
        .filter(Solicitacao.status != "CANCELADO")
        .count()
    )
    total_equipe_uvis = (
        Solicitacao.query
        .filter(Solicitacao.usuario_id == user.id)
        .filter(Solicitacao.status != "CANCELADO")
        .filter(_has_equipe_uvis_os())
        .count()
    )

    page = args.get("page", 1, type=int)
    paginacao = (
        query.order_by(Solicitacao.data_criacao.desc(), Solicitacao.id.desc())
        .paginate(page=page, per_page=6, error_out=False)
    )

    return {
        "pedidos": paginacao.items,
        "paginacao": paginacao,
        "filtro_tipo_os": filtro_tipo_os,
        "filtros": filtros,
        "unidades_select": [user],
        "retorno_ciclos": build_retorno_ciclo_summaries(user, paginacao.items),
        "historico_totais": {
            "todas": total_todas,
            "piloto": total_piloto,
            "equipe_uvis": total_equipe_uvis,
        },
    }


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
    imagem_principal_path = getattr(ordem, "imagem_principal", None) if ordem else None
    outras_imagens_paths = _parse_media_list(getattr(ordem, "outras_imagens", None) if ordem else None)
    video_path = getattr(ordem, "video", None) if ordem else None
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
        "retorno_ciclo": build_retorno_ciclo_context(user, os_id),
        "imagem_principal_path": imagem_principal_path,
        "outras_imagens_paths": outras_imagens_paths,
        "video_path": video_path,
        "video_filename": os.path.basename(str(video_path or "").replace("\\", "/")) if video_path else "",
        "total_midias_formulario": (
            (1 if imagem_principal_path else 0)
            + len(outras_imagens_paths)
            + (1 if video_path else 0)
        ),
        **build_os_media_context(ordem),
    }


def build_uvis_equipe_os_form_context(user, os_id):
    if getattr(user, "tipo_usuario", None) != "uvis":
        raise DashboardError("Acesso restrito.", category="danger")

    solicitacao = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico_equipe_uvis),
        )
        .get_or_404(os_id)
    )

    if solicitacao.usuario_id != user.id:
        raise DashboardError("Voce nao tem permissao para acessar esta OS da equipe.", category="danger")

    ordem = solicitacao.ordem_servico_equipe_uvis
    if ordem is None:
        raise DashboardError(
            "A equipe UVIS ainda nao preencheu o formulario desta solicitacao.",
            category="warning",
            redirect_endpoint="main.dashboard",
        )

    retorno_existente = (
        Solicitacao.query
        .filter(
            Solicitacao.origem_retorno_id == solicitacao.id,
            Solicitacao.gerada_automaticamente.is_(True),
        )
        .order_by(Solicitacao.id.desc())
        .first()
    )

    return {
        "solicitacao": solicitacao,
        "ordem": ordem,
        "modo_visualizacao": True,
        "nome_equipe": ordem.equipe_uvis_nome or solicitacao.equipe_uvis_nome or "",
        "uvis_nome": solicitacao.usuario.nome_uvis if solicitacao.usuario else "",
        "endereco_os": (
            f"{solicitacao.logradouro or ''}, {solicitacao.numero or 'S/N'} - "
            f"{solicitacao.bairro or ''} - {solicitacao.cidade or ''}/{solicitacao.uf or ''}"
        ),
        "respondido_por_padrao": ordem.respondido_por or "",
        "respondido_em_value": (
            ordem.respondido_em.strftime("%Y-%m-%dT%H:%M")
            if ordem.respondido_em else ""
        ),
        "retorno_existente": retorno_existente,
        "retorno_monitoramento_value": (
            ordem.retorno_monitoramento_em.strftime("%Y-%m-%dT%H:%M")
            if ordem.retorno_monitoramento_em else ""
        ),
        "retorno_ciclo": build_retorno_ciclo_context(user, os_id),
    }
