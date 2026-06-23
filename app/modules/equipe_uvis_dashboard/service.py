from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import OrdemServicoEquipeUvis, Solicitacao, Usuario
from app.shared.os_history_filters import apply_os_history_filters, get_os_history_filters
from app.shared.query_filters import id_search_clause


class EquipeUvisDashboardError(Exception):
    def __init__(self, message, *, category="danger", redirect_endpoint="main.dashboard"):
        super().__init__(message)
        self.message = message
        self.category = category
        self.redirect_endpoint = redirect_endpoint


STATUS_OS_CONCLUIDAS = {"CONCLUIDO", "CONCLUÍDO"}
STATUS_SOLICITACOES_APROVADAS_EQUIPE_UVIS = {
    "APROVADO",
    "APROVADO COM RECOMENDACOES",
    "APROVADO COM RECOMENDAÇÕES",
}
STATUS_PREENCHIMENTO_EQUIPE_UVIS = {
    "APENAS APLICADO",
    "APENAS MONITORADO",
    "NENHUM VOO REALIZADO",
}


def _resolve_uvis_operational_access(user):
    tipo_usuario = getattr(user, "tipo_usuario", None)
    if tipo_usuario == "uvis":
        uvis_id = getattr(user, "id", None)
        nome_equipe = (getattr(user, "nome_uvis", "") or "UVIS").strip()
    elif tipo_usuario == "equipe_uvis":
        uvis_id = getattr(user, "equipe_uvis_uvis_usuario_id", None)
        uvis_dona = getattr(user, "equipe_uvis_dona", None)
        nome_equipe = (getattr(uvis_dona, "nome_uvis", None) or "").strip()
        if not nome_equipe:
            nome_equipe = (
                getattr(user, "nome_uvis", None)
                or getattr(user, "equipe_uvis_nome", None)
                or "Equipe UVIS"
            ).strip()
    else:
        uvis_id = None
        nome_equipe = ""

    if not uvis_id:
        raise EquipeUvisDashboardError(
            "Conta sem vinculo com UVIS. Contate o administrador.",
            redirect_endpoint="auth.login",
        )

    return uvis_id, nome_equipe or "Equipe UVIS"


def _status_key(value):
    return (
        (value or "")
        .strip()
        .upper()
        .replace("Ç", "C")
        .replace("Õ", "O")
        .replace("Í", "I")
    )


def _is_approved_for_equipe_uvis(solicitacao):
    return _status_key(getattr(solicitacao, "status", None)) in {
        "APROVADO",
        "APROVADO COM RECOMENDACOES",
    }


def _is_concluded(solicitacao):
    return "CONCLU" in _status_key(getattr(solicitacao, "status", None))


def build_dashboard_equipe_uvis_context(user, args, google_maps_key):
    uvis_id, nome_equipe = _resolve_uvis_operational_access(user)

    query = (
        Solicitacao.query.options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico_equipe_uvis),
        )
        .filter(Solicitacao.usuario_id == uvis_id)
        .filter(Solicitacao.status.in_(STATUS_SOLICITACOES_APROVADAS_EQUIPE_UVIS))
    )

    filtro_status = args.get("status")
    if filtro_status:
        if filtro_status in STATUS_SOLICITACOES_APROVADAS_EQUIPE_UVIS:
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

    filtro_foco = args.get("foco")
    if filtro_foco:
        query = query.filter(Solicitacao.foco == filtro_foco)

    filtro_protocolo = (args.get("protocolo") or "").strip()
    if filtro_protocolo:
        query = query.filter(
            or_(
                id_search_clause(Solicitacao.id, filtro_protocolo, prefixes=("id", "os")),
                Solicitacao.protocolo.ilike(f"%{filtro_protocolo}%"),
            )
        )

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


def build_equipe_uvis_os_historico_context(user, args):
    uvis_id, nome_equipe = _resolve_uvis_operational_access(user)

    query = (
        Solicitacao.query.options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico_equipe_uvis),
        )
        .filter(Solicitacao.usuario_id == uvis_id)
        .filter(Solicitacao.ordem_servico_equipe_uvis.has())
        .filter(Solicitacao.status.in_(STATUS_OS_CONCLUIDAS))
    )

    filtros = get_os_history_filters(args)
    query = apply_os_history_filters(query, filtros)

    page = args.get("page", 1, type=int)
    paginacao = (
        query.order_by(Solicitacao.data_criacao.desc(), Solicitacao.id.desc())
        .paginate(page=page, per_page=6, error_out=False)
    )

    return {
        "pedidos": paginacao.items,
        "paginacao": paginacao,
        "nome_equipe": nome_equipe,
        "filtros": filtros,
        "unidades_select": Usuario.query.filter(Usuario.id == uvis_id).all(),
    }


def concluir_os_equipe_uvis(user, os_id):
    context = build_equipe_uvis_os_form_context(user, os_id)
    solicitacao = context["solicitacao"]
    ordem = context["ordem"]

    if _is_concluded(solicitacao):
        raise EquipeUvisDashboardError(
            "Esta solicitacao ja esta concluida.",
            category="warning",
            redirect_endpoint="main.dashboard_equipe_uvis",
        )

    if ordem is None:
        raise EquipeUvisDashboardError(
            "Preencha e salve a OS da equipe UVIS antes de concluir.",
            category="warning",
            redirect_endpoint="main.dashboard_equipe_uvis",
        )

    if not (ordem.situacao_aplicacao or "").strip():
        raise EquipeUvisDashboardError(
            "Informe a situacao da aplicacao no formulario antes de concluir.",
            category="warning",
            redirect_endpoint="main.dashboard_equipe_uvis",
        )

    solicitacao.status = "CONCLUÍDO"
    db.session.commit()
    return f"OS #{solicitacao.id} concluida pela equipe UVIS."


def build_equipe_uvis_os_form_context(user, os_id):
    if getattr(user, "tipo_usuario", None) not in {"equipe_uvis", "uvis"}:
        raise EquipeUvisDashboardError("Acesso restrito.")

    uvis_id, nome_equipe = _resolve_uvis_operational_access(user)

    solicitacao = (
        Solicitacao.query.options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico_equipe_uvis),
        )
        .get_or_404(os_id)
    )

    if solicitacao.usuario_id != uvis_id:
        raise EquipeUvisDashboardError("Voce nao tem permissao para acessar esta solicitacao.")

    if (solicitacao.status or "").strip().upper() == "CANCELADO":
        raise EquipeUvisDashboardError(
            "Esta solicitacao foi cancelada.",
            category="warning",
            redirect_endpoint="main.dashboard_equipe_uvis",
        )

    if not _is_approved_for_equipe_uvis(solicitacao) and not _is_concluded(solicitacao):
        raise EquipeUvisDashboardError(
            "Esta solicitacao ainda nao esta aprovada para a UVIS operacional.",
            category="warning",
            redirect_endpoint="main.dashboard_equipe_uvis",
        )

    ordem = solicitacao.ordem_servico_equipe_uvis
    retorno_existente = (
        Solicitacao.query
        .filter(
            Solicitacao.origem_retorno_id == solicitacao.id,
            Solicitacao.gerada_automaticamente.is_(True),
        )
        .order_by(Solicitacao.id.desc())
        .first()
    )
    retorno_monitoramento_value = ""
    if ordem and ordem.retorno_monitoramento_em:
        retorno_monitoramento_value = ordem.retorno_monitoramento_em.strftime("%Y-%m-%dT%H:%M")
    elif retorno_existente and retorno_existente.data_agendamento and retorno_existente.hora_agendamento:
        retorno_monitoramento_value = datetime.combine(
            retorno_existente.data_agendamento,
            retorno_existente.hora_agendamento,
        ).strftime("%Y-%m-%dT%H:%M")

    respondido_em_value = datetime.now().strftime("%Y-%m-%dT%H:%M")
    if ordem and ordem.respondido_em:
        respondido_em_value = ordem.respondido_em.strftime("%Y-%m-%dT%H:%M")

    return {
        "solicitacao": solicitacao,
        "ordem": ordem,
        "modo_visualizacao": _is_concluded(solicitacao),
        "nome_equipe": nome_equipe,
        "uvis_nome": getattr(getattr(solicitacao, "usuario", None), "nome_uvis", "") or "",
        "endereco_os": (
            f"{solicitacao.logradouro or ''}, {solicitacao.numero or 'S/N'} - "
            f"{solicitacao.bairro or ''} - {solicitacao.cidade or ''}/{solicitacao.uf or ''}"
        ),
        "respondido_por_padrao": (getattr(user, "nome_uvis", "") or nome_equipe),
        "respondido_em_value": respondido_em_value,
        "retorno_existente": retorno_existente,
        "retorno_monitoramento_value": retorno_monitoramento_value,
    }


def salvar_equipe_uvis_os_form(user, os_id, form_data):
    context = build_equipe_uvis_os_form_context(user, os_id)
    if context["modo_visualizacao"]:
        raise EquipeUvisDashboardError(
            "Esta solicitacao ja foi concluida e esta em modo de visualizacao.",
            category="warning",
        )

    solicitacao = context["solicitacao"]
    if not _is_approved_for_equipe_uvis(solicitacao):
        raise EquipeUvisDashboardError(
            "Somente solicitacoes aprovadas podem ser preenchidas pela UVIS operacional.",
            category="warning",
        )

    ordem = context["ordem"]
    if ordem is None:
        ordem = OrdemServicoEquipeUvis(
            solicitacao_id=solicitacao.id,
            equipe_uvis_nome=solicitacao.equipe_uvis_nome or context["nome_equipe"],
            equipe_id=solicitacao.equipe_id,
        )
        db.session.add(ordem)
    else:
        ordem.equipe_uvis_nome = solicitacao.equipe_uvis_nome or context["nome_equipe"]
        ordem.equipe_id = solicitacao.equipe_id

    status_execucao = _normalize_upper(form_data.get("situacao_aplicacao"))
    if status_execucao not in STATUS_PREENCHIMENTO_EQUIPE_UVIS:
        raise EquipeUvisDashboardError("Selecione um status valido para a OS.", category="warning")

    retorno_flag = _normalize_upper(form_data.get("retornar_proxima_semana_monitorar_larvas"))
    retorno_em = None
    if retorno_flag == "SIM":
        retorno_em = _to_datetime_local(form_data.get("retorno_monitoramento_em"))
        if retorno_em is None:
            raise EquipeUvisDashboardError(
                "Informe a data e hora para o retorno de monitoramento.",
                category="warning",
            )

    motivo_nao_realizacao = _clean_str(form_data.get("motivo_nao_realizacao"))
    if status_execucao == "NENHUM VOO REALIZADO" and not motivo_nao_realizacao:
        raise EquipeUvisDashboardError(
            "Informe o motivo de nao realizacao quando nenhum voo for realizado.",
            category="warning",
        )

    ordem.identificador_os = _clean_str(form_data.get("identificador_os"))
    ordem.respondido_por = _clean_str(form_data.get("respondido_por")) or context["respondido_por_padrao"]
    ordem.respondido_em = _to_datetime_local(form_data.get("respondido_em")) or datetime.now()
    ordem.situacao_aplicacao = status_execucao
    ordem.tratamento_adicional_realizado = _normalize_upper(form_data.get("tratamento_adicional_realizado"))
    ordem.quantos_quais = _clean_str(form_data.get("quantos_quais"))
    ordem.quantidade_produto_administrada_ml = _to_float(form_data.get("quantidade_produto_administrada_ml"))
    ordem.motivo_nao_realizacao = motivo_nao_realizacao
    ordem.larva_visualizada = _normalize_upper(form_data.get("larva_visualizada"))
    ordem.retornar_proxima_semana_monitorar_larvas = retorno_flag if retorno_flag in {"SIM", "NAO"} else "NAO"
    ordem.retorno_monitoramento_em = retorno_em if ordem.retornar_proxima_semana_monitorar_larvas == "SIM" else None
    ordem.observacoes = _clean_str(form_data.get("observacoes"))

    retorno_existente = context["retorno_existente"]
    if ordem.retornar_proxima_semana_monitorar_larvas == "SIM":
        if retorno_existente is None:
            _criar_solicitacao_retorno_monitoramento_equipe_uvis(solicitacao, retorno_em)
        else:
            retorno_existente.data_agendamento = retorno_em.date()
            retorno_existente.hora_agendamento = retorno_em.time().replace(second=0, microsecond=0)
            retorno_existente.equipe_uvis_nome = solicitacao.equipe_uvis_nome
            retorno_existente.usuario_id = solicitacao.usuario_id
    elif (
        retorno_existente is not None
        and retorno_existente.gerada_automaticamente
        and (retorno_existente.status or "").strip().upper() == "PENDENTE"
    ):
        db.session.delete(retorno_existente)

    db.session.commit()
    return "OS da equipe UVIS salva com sucesso!"


def _clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None


def _clean_str(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_upper(value):
    cleaned = _clean(value)
    return cleaned.upper() if cleaned else ""


def _to_float(value):
    value = _clean(value)
    if value is None:
        return None
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(",", ".")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_datetime_local(value):
    value = _clean(value)
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _criar_solicitacao_retorno_monitoramento_equipe_uvis(solicitacao_original, retorno_em):
    nova_observacao = (solicitacao_original.observacao or "").strip() or None
    nova_solicitacao = Solicitacao(
        data_agendamento=retorno_em.date(),
        hora_agendamento=retorno_em.time().replace(second=0, microsecond=0),
        foco=solicitacao_original.foco,
        tipo_operacao=solicitacao_original.tipo_operacao,
        tipo_visita=solicitacao_original.tipo_visita,
        altura_voo=solicitacao_original.altura_voo,
        criadouro=solicitacao_original.criadouro,
        apoio_cet=solicitacao_original.apoio_cet,
        observacao=nova_observacao,
        area_restrita=solicitacao_original.area_restrita,
        cep=solicitacao_original.cep,
        logradouro=solicitacao_original.logradouro,
        bairro=solicitacao_original.bairro,
        cidade=solicitacao_original.cidade,
        uf=solicitacao_original.uf,
        numero=solicitacao_original.numero,
        complemento=solicitacao_original.complemento,
        latitude=solicitacao_original.latitude,
        longitude=solicitacao_original.longitude,
        perimetro_planejado=solicitacao_original.perimetro_planejado,
        perimetro_executado=None,
        anexo_path=solicitacao_original.anexo_path,
        anexo_nome=solicitacao_original.anexo_nome,
        protocolo=None,
        justificativa=None,
        equipe_uvis_nome=solicitacao_original.equipe_uvis_nome,
        status="PENDENTE",
        usuario_id=solicitacao_original.usuario_id,
        piloto_id=solicitacao_original.piloto_id,
        equipe_id=solicitacao_original.equipe_id,
        origem_retorno_id=solicitacao_original.id,
        gerada_automaticamente=True,
    )
    db.session.add(nova_solicitacao)
    return nova_solicitacao
