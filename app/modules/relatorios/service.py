import json
from collections import Counter
from datetime import datetime
from math import ceil

from sqlalchemy import and_, extract, func, or_

from app.extensions import db
from app.models import OrdemServico, Solicitacao, Usuario
from app.shared.access import (
    ADMIN_PANEL_VIEW_TYPES,
    apply_regiao_scope,
    apply_solicitacao_regiao_scope,
    is_regional_user,
    normalize_regiao,
)
from app.shared.query_filters import aplicar_filtros_base


RELATORIOS_MENU_TYPES = ADMIN_PANEL_VIEW_TYPES
RELATORIOS_COLETA_IMAGENS_TYPES = RELATORIOS_MENU_TYPES | {"uvis"}
COLETA_IMAGENS_MONTH_NAMES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Marco",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def can_access_relatorios_menu(user) -> bool:
    return getattr(user, "tipo_usuario", None) in RELATORIOS_MENU_TYPES


def can_access_relatorio_coleta_imagens(user) -> bool:
    return getattr(user, "tipo_usuario", None) in RELATORIOS_COLETA_IMAGENS_TYPES


class SimplePagination:
    def __init__(self, items, page, per_page):
        self.total = len(items)
        self.per_page = per_page
        self.pages = max(1, ceil(self.total / per_page)) if self.total else 1
        self.page = max(1, min(page, self.pages))
        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages
        self.prev_num = self.page - 1
        self.next_num = self.page + 1
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        self.items = items[start:end]

    def iter_pages(self):
        return range(1, self.pages + 1)


def build_uvis_disponiveis(user, regiao: str | None = None):
    user_type = getattr(user, "tipo_usuario", None)
    if user_type not in RELATORIOS_COLETA_IMAGENS_TYPES:
        return []

    query = db.session.query(Usuario.id, Usuario.nome_uvis).filter(Usuario.tipo_usuario == "uvis")
    if user_type == "uvis":
        query = query.filter(Usuario.id == user.id)
    else:
        query = apply_regiao_scope(query, user, Usuario.regiao)
    if regiao and user_type != "uvis":
        query = query.filter(func.upper(func.coalesce(Usuario.regiao, "")) == normalize_regiao(regiao))
    return query.order_by(Usuario.nome_uvis).all()


def build_regioes_disponiveis(user):
    user_type = getattr(user, "tipo_usuario", None)
    if user_type not in RELATORIOS_COLETA_IMAGENS_TYPES:
        return []
    if user_type == "uvis":
        regiao = (getattr(user, "regiao", None) or "").strip()
        return [regiao] if regiao else []

    query = (
        db.session.query(Usuario.regiao)
        .filter(
            Usuario.tipo_usuario == "uvis",
            Usuario.regiao.isnot(None),
            Usuario.regiao != "",
        )
    )
    query = apply_regiao_scope(query, user, Usuario.regiao)
    return [value for (value,) in query.distinct().order_by(Usuario.regiao.asc()).all() if value]


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


def _format_endereco(solicitacao):
    if not solicitacao:
        return "-"
    return (
        f"{solicitacao.logradouro or ''}, {solicitacao.numero or 'S/N'} - "
        f"{solicitacao.bairro or ''} - {solicitacao.cidade or ''}/{solicitacao.uf or ''}"
    ).strip(" -")


def _format_data_coleta(ordem, solicitacao):
    if ordem and ordem.data_aplicacao:
        return ordem.data_aplicacao.strftime("%d/%m/%Y")
    if ordem and ordem.respondido_em:
        return ordem.respondido_em.strftime("%d/%m/%Y")
    if solicitacao and solicitacao.data_agendamento:
        return solicitacao.data_agendamento.strftime("%d/%m/%Y")
    return "-"


def _coleta_period_exprs():
    ano_ref = func.coalesce(
        extract("year", OrdemServico.data_aplicacao),
        extract("year", OrdemServico.respondido_em),
        extract("year", Solicitacao.data_agendamento),
    )
    mes_ref = func.coalesce(
        extract("month", OrdemServico.data_aplicacao),
        extract("month", OrdemServico.respondido_em),
        extract("month", Solicitacao.data_agendamento),
    )
    return ano_ref, mes_ref


def _format_coleta_periodo_label(mes=None, ano=None):
    nome_mes = COLETA_IMAGENS_MONTH_NAMES.get(int(mes)) if mes else None
    if nome_mes and ano:
        return f"{nome_mes} de {ano}"
    if ano:
        return f"Ano {ano}"
    if nome_mes:
        return nome_mes
    return "Todos os periodos"


def _serialize_coleta_imagem_row(ordem, solicitacao, usuario):
    outras_imagens = _parse_media_list(getattr(ordem, "outras_imagens", None))
    regiao_nome = (
        getattr(usuario, "regiao", None)
        or getattr(getattr(solicitacao, "equipe", None), "regiao", None)
        or "Nao informado"
    )
    latitude = solicitacao.latitude if solicitacao and solicitacao.latitude is not None else "-"
    longitude = solicitacao.longitude if solicitacao and solicitacao.longitude is not None else "-"

    return {
        "solicitacao_id": solicitacao.id if solicitacao else None,
        "ordem_id": ordem.id if ordem else None,
        "uvis_nome": (usuario.nome_uvis if usuario else "") or "Nao informado",
        "regiao_nome": regiao_nome,
        "foco": (solicitacao.foco if solicitacao else "") or "Nao informado",
        "endereco": _format_endereco(solicitacao),
        "cep": (solicitacao.cep if solicitacao else "") or "-",
        "coordenadas": f"{latitude}, {longitude}",
        "data_coleta_label": _format_data_coleta(ordem, solicitacao),
        "imagem_principal_path": getattr(ordem, "imagem_principal", None),
        "outras_imagens_paths": outras_imagens,
        "outras_imagens_count": len(outras_imagens),
        "video_path": getattr(ordem, "video", None),
        "tem_video": bool(getattr(ordem, "video", None)),
        "total_midias": 1 + len(outras_imagens) + (1 if getattr(ordem, "video", None) else 0),
        "quantidade_imagens_registradas": getattr(ordem, "quantidade_imagens_registradas", None),
        "quantidade_videos_registradas": getattr(ordem, "quantidade_videos_registradas", None),
    }


def _resolve_coleta_imagens_filters(user, args):
    user_type = getattr(user, "tipo_usuario", None)
    mes = args.get("mes", type=int)
    ano = args.get("ano", type=int)
    if user_type == "uvis":
        return (getattr(user, "regiao", None) or "").strip(), user.id, mes, ano
    if is_regional_user(user):
        return (getattr(user, "regiao", None) or "").strip(), args.get("uvis_id", type=int), mes, ano

    regiao = (args.get("regiao") or "").strip()
    uvis_id = args.get("uvis_id", type=int)
    return regiao, uvis_id, mes, ano


def _build_coleta_imagens_query(user, *, regiao="", uvis_id=None, mes=None, ano=None):
    query = (
        db.session.query(OrdemServico, Solicitacao, Usuario)
        .join(Solicitacao, Solicitacao.id == OrdemServico.solicitacao_id)
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
        .filter(func.length(func.trim(func.coalesce(OrdemServico.imagem_principal, ""))) > 0)
    )
    query = apply_regiao_scope(query, user, Usuario.regiao)

    if regiao:
        query = query.filter(func.upper(func.coalesce(Usuario.regiao, "")) == normalize_regiao(regiao))
    if uvis_id:
        query = query.filter(Solicitacao.usuario_id == uvis_id)
    if ano or mes:
        ano_ref, mes_ref = _coleta_period_exprs()
        if ano:
            query = query.filter(ano_ref == ano)
        if mes:
            query = query.filter(mes_ref == mes)

    return query


def _agrupar_por(base_query, campo):
    resultados = (
        base_query
        .with_entities(campo, db.func.count(Solicitacao.id))
        .group_by(campo)
        .order_by(db.func.count(Solicitacao.id).desc())
        .all()
    )
    return [(valor or "Nao informado", total) for valor, total in resultados]


def build_relatorios_solicitacoes_context(user, args):
    uvis_disponiveis = build_uvis_disponiveis(user)

    mes_atual = args.get("mes", datetime.now().month, type=int)
    ano_atual = args.get("ano", datetime.now().year, type=int)
    uvis_id = args.get("uvis_id", type=int) if getattr(user, "tipo_usuario", None) != "uvis" else user.id
    filtro_data = f"{ano_atual}-{mes_atual:02d}"

    base_query = aplicar_filtros_base(db.session.query(Solicitacao), filtro_data, uvis_id)
    base_query = apply_solicitacao_regiao_scope(base_query, user)
    print("SQL EXECUTADO:", str(base_query.statement.compile(dialect=db.engine.dialect)))

    status_counts = {
        status: total
        for status, total in (
            base_query
            .with_entities(Solicitacao.status, db.func.count(Solicitacao.id))
            .group_by(Solicitacao.status)
            .all()
        )
    }

    dados_regiao = [
        (regiao or "Nao informado", total)
        for regiao, total in (
            base_query.join(Usuario)
            .with_entities(Usuario.regiao, db.func.count(Solicitacao.id))
            .group_by(Usuario.regiao)
            .order_by(db.func.count(Solicitacao.id).desc())
            .all()
        )
    ]

    dados_unidade = [
        (uvis or "Nao informado", total)
        for uvis, total in (
            base_query.join(Usuario)
            .filter(Usuario.tipo_usuario == "uvis")
            .with_entities(Usuario.nome_uvis, db.func.count(Solicitacao.id))
            .group_by(Usuario.nome_uvis)
            .order_by(db.func.count(Solicitacao.id).desc())
            .all()
        )
    ]

    dados_mensais = [
        (f"{int(ano_h):04d}-{int(mes_h):02d}", total)
        for ano_h, mes_h, total in (
            apply_solicitacao_regiao_scope(
                db.session.query(
                    extract("year", Solicitacao.data_agendamento),
                    extract("month", Solicitacao.data_agendamento),
                    func.count(Solicitacao.id),
                )
                .filter(Solicitacao.data_agendamento.isnot(None)),
                user,
            )
            .group_by(extract("year", Solicitacao.data_agendamento), extract("month", Solicitacao.data_agendamento))
            .order_by(extract("year", Solicitacao.data_agendamento), extract("month", Solicitacao.data_agendamento))
            .all()
        )
    ]

    anos_disponiveis = sorted({mes.split("-")[0] for mes, _ in dados_mensais}, reverse=True) if dados_mensais else [ano_atual]

    print(f"DEBUG FILTRO: Mes selecionado: {mes_atual} | String gerada: {filtro_data}")

    total_concluidas = sum(
        total for status, total in status_counts.items()
        if "CONCLU" in (status or "").upper()
    )
    total_canceladas = status_counts.get("CANCELADO", 0)

    return {
        "total_solicitacoes": sum(status_counts.values()),
        "total_aprovadas": status_counts.get("APROVADO", 0),
        "total_aprovadas_com_recomendacoes": status_counts.get("APROVADO COM RECOMENDAÇÕES", 0),
        "total_concluidas": total_concluidas,
        "total_canceladas": total_canceladas,
        "total_recusadas": status_counts.get("NEGADO", 0),
        "total_analise": status_counts.get("EM ANÁLISE", 0),
        "total_pendentes": status_counts.get("PENDENTE", 0),
        "dados_regiao": dados_regiao,
        "dados_status": _agrupar_por(base_query, Solicitacao.status),
        "dados_foco": _agrupar_por(base_query, Solicitacao.foco),
        "dados_tipo_operacao": _agrupar_por(base_query, Solicitacao.tipo_operacao),
        "dados_tipo_visita": _agrupar_por(base_query, Solicitacao.tipo_visita),
        "dados_altura_voo": _agrupar_por(base_query, Solicitacao.altura_voo),
        "dados_unidade": dados_unidade,
        "dados_mensais": dados_mensais,
        "mes_selecionado": mes_atual,
        "ano_selecionado": ano_atual,
        "anos_disponiveis": anos_disponiveis,
        "uvis_id_selecionado": uvis_id,
        "uvis_disponiveis": uvis_disponiveis,
        "filtros": {"total": sum(status_counts.values())},
    }


def build_relatorios_os_context(user, args):
    uvis_disponiveis = build_uvis_disponiveis(user)

    mes_atual = args.get("mes", datetime.now().month, type=int)
    ano_atual = args.get("ano", datetime.now().year, type=int)
    uvis_id = args.get("uvis_id", type=int) if getattr(user, "tipo_usuario", None) != "uvis" else user.id

    base_query = (
        db.session.query(OrdemServico)
        .join(Solicitacao, Solicitacao.id == OrdemServico.solicitacao_id)
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
    )
    base_query = apply_regiao_scope(base_query, user, Usuario.regiao)

    base_query = base_query.filter(
        or_(
            and_(
                OrdemServico.respondido_em.isnot(None),
                extract("year", OrdemServico.respondido_em) == ano_atual,
                extract("month", OrdemServico.respondido_em) == mes_atual,
            ),
            and_(
                OrdemServico.respondido_em.is_(None),
                OrdemServico.data_aplicacao.isnot(None),
                extract("year", OrdemServico.data_aplicacao) == ano_atual,
                extract("month", OrdemServico.data_aplicacao) == mes_atual,
            ),
        )
    )

    if uvis_id:
        base_query = base_query.filter(Solicitacao.usuario_id == uvis_id)

    def agrupar_por(campo):
        return [
            (valor or "Nao informado", total)
            for valor, total in (
                base_query
                .with_entities(campo, func.count(OrdemServico.id))
                .group_by(campo)
                .order_by(func.count(OrdemServico.id).desc())
                .all()
            )
        ]

    dados_mensais = []
    mensal_query = (
        db.session.query(
            func.coalesce(
                extract("year", OrdemServico.respondido_em),
                extract("year", OrdemServico.data_aplicacao),
            ).label("ano_ref"),
            func.coalesce(
                extract("month", OrdemServico.respondido_em),
                extract("month", OrdemServico.data_aplicacao),
            ).label("mes_ref"),
            func.count(OrdemServico.id),
        )
        .join(Solicitacao, Solicitacao.id == OrdemServico.solicitacao_id)
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
    )
    mensal_query = apply_regiao_scope(mensal_query, user, Usuario.regiao)

    if uvis_id:
        mensal_query = mensal_query.filter(Solicitacao.usuario_id == uvis_id)

    for ano_h, mes_h, total in (
        mensal_query
        .filter(
            or_(
                OrdemServico.respondido_em.isnot(None),
                OrdemServico.data_aplicacao.isnot(None),
            )
        )
        .group_by("ano_ref", "mes_ref")
        .order_by("ano_ref", "mes_ref")
        .all()
    ):
        if ano_h and mes_h:
            dados_mensais.append((f"{int(ano_h):04d}-{int(mes_h):02d}", total))

    anos_disponiveis = sorted({mes.split("-")[0] for mes, _ in dados_mensais}, reverse=True) if dados_mensais else [ano_atual]

    return {
        "total_os": base_query.count(),
        "total_concluidas": base_query.filter(Solicitacao.status.in_(["CONCLUÍDO", "CONCLUIDO"])).count(),
        "total_larva_sim": base_query.filter(func.upper(func.coalesce(OrdemServico.larva_visualizada, "")) == "SIM").count(),
        "total_tratamento_adicional": base_query.filter(func.upper(func.coalesce(OrdemServico.tratamento_adicional_realizado, "")) == "SIM").count(),
        "total_nao_realizadas": base_query.filter(func.length(func.trim(func.coalesce(OrdemServico.motivo_nao_realizacao, ""))) > 0).count(),
        "dados_situacao_aplicacao": agrupar_por(OrdemServico.situacao_aplicacao),
        "dados_tipo_aplicacao": agrupar_por(OrdemServico.tipo_aplicacao),
        "dados_larva": agrupar_por(OrdemServico.larva_visualizada),
        "dados_piloto": agrupar_por(OrdemServico.piloto),
        "dados_unidade": [
            (uvis or "Nao informado", total)
            for uvis, total in (
                base_query
                .with_entities(Usuario.nome_uvis, func.count(OrdemServico.id))
                .group_by(Usuario.nome_uvis)
                .order_by(func.count(OrdemServico.id).desc())
                .all()
            )
        ],
        "dados_mensais": dados_mensais,
        "mes_selecionado": mes_atual,
        "ano_selecionado": ano_atual,
        "anos_disponiveis": anos_disponiveis,
        "uvis_id_selecionado": uvis_id,
        "uvis_disponiveis": uvis_disponiveis,
    }


def build_relatorio_os_export_data(user, args):
    mes_atual = args.get("mes", datetime.now().month, type=int)
    ano_atual = args.get("ano", datetime.now().year, type=int)
    uvis_id = args.get("uvis_id", type=int) if getattr(user, "tipo_usuario", None) != "uvis" else user.id

    base_query = (
        db.session.query(OrdemServico)
        .join(Solicitacao, Solicitacao.id == OrdemServico.solicitacao_id)
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
    )
    base_query = apply_regiao_scope(base_query, user, Usuario.regiao)

    base_query = base_query.filter(
        or_(
            and_(
                OrdemServico.respondido_em.isnot(None),
                extract("year", OrdemServico.respondido_em) == ano_atual,
                extract("month", OrdemServico.respondido_em) == mes_atual,
            ),
            and_(
                OrdemServico.respondido_em.is_(None),
                OrdemServico.data_aplicacao.isnot(None),
                extract("year", OrdemServico.data_aplicacao) == ano_atual,
                extract("month", OrdemServico.data_aplicacao) == mes_atual,
            ),
        )
    )

    if uvis_id:
        base_query = base_query.filter(Solicitacao.usuario_id == uvis_id)

    total_os = base_query.count()
    total_concluidas = base_query.filter(Solicitacao.status.in_(["CONCLUÃDO", "CONCLUIDO"])).count()
    total_larva_sim = base_query.filter(func.upper(func.coalesce(OrdemServico.larva_visualizada, "")) == "SIM").count()
    total_tratamento_adicional = base_query.filter(
        func.upper(func.coalesce(OrdemServico.tratamento_adicional_realizado, "")) == "SIM"
    ).count()
    total_nao_realizadas = base_query.filter(
        func.length(func.trim(func.coalesce(OrdemServico.motivo_nao_realizacao, ""))) > 0
    ).count()

    def agrupar_por(campo):
        return [
            (valor or "Nao informado", total)
            for valor, total in (
                base_query
                .with_entities(campo, func.count(OrdemServico.id))
                .group_by(campo)
                .order_by(func.count(OrdemServico.id).desc())
                .all()
            )
        ]

    dados_situacao_aplicacao = agrupar_por(OrdemServico.situacao_aplicacao)
    dados_tipo_aplicacao = agrupar_por(OrdemServico.tipo_aplicacao)
    dados_larva = agrupar_por(OrdemServico.larva_visualizada)
    dados_piloto = agrupar_por(OrdemServico.piloto)

    dados_unidade = [
        (uvis or "Nao informado", total)
        for uvis, total in (
            base_query
            .with_entities(Usuario.nome_uvis, func.count(OrdemServico.id))
            .group_by(Usuario.nome_uvis)
            .order_by(func.count(OrdemServico.id).desc())
            .all()
        )
    ]

    mensal_query = (
        db.session.query(
            func.coalesce(
                extract("year", OrdemServico.respondido_em),
                extract("year", OrdemServico.data_aplicacao),
            ).label("ano_ref"),
            func.coalesce(
                extract("month", OrdemServico.respondido_em),
                extract("month", OrdemServico.data_aplicacao),
            ).label("mes_ref"),
            func.count(OrdemServico.id),
        )
        .join(Solicitacao, Solicitacao.id == OrdemServico.solicitacao_id)
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
    )
    mensal_query = apply_regiao_scope(mensal_query, user, Usuario.regiao)

    if uvis_id:
        mensal_query = mensal_query.filter(Solicitacao.usuario_id == uvis_id)

    dados_mensais = [
        (f"{int(ano_h):04d}-{int(mes_h):02d}", total)
        for ano_h, mes_h, total in (
            mensal_query
            .filter(
                or_(
                    OrdemServico.respondido_em.isnot(None),
                    OrdemServico.data_aplicacao.isnot(None),
                )
            )
            .group_by("ano_ref", "mes_ref")
            .order_by("ano_ref", "mes_ref")
            .all()
        )
        if ano_h and mes_h
    ]

    nome_uvis = None
    if uvis_id:
        nome_uvis = (
            apply_regiao_scope(
                db.session.query(Usuario.nome_uvis).filter(Usuario.id == uvis_id),
                user,
                Usuario.regiao,
            )
            .scalar()
        )

    return {
        "mes": mes_atual,
        "ano": ano_atual,
        "uvis_id": uvis_id,
        "uvis_nome": nome_uvis or "Todas as Unidades",
        "total_os": total_os,
        "total_concluidas": total_concluidas,
        "total_larva_sim": total_larva_sim,
        "total_tratamento_adicional": total_tratamento_adicional,
        "total_nao_realizadas": total_nao_realizadas,
        "dados_situacao_aplicacao": dados_situacao_aplicacao,
        "dados_tipo_aplicacao": dados_tipo_aplicacao,
        "dados_larva": dados_larva,
        "dados_piloto": dados_piloto,
        "dados_unidade": dados_unidade,
        "dados_mensais": dados_mensais,
    }


def build_relatorio_coleta_imagens_export_data(user, args):
    user_type = getattr(user, "tipo_usuario", None)
    is_uvis = user_type == "uvis"
    is_regional = is_regional_user(user)

    regiao_selecionada, uvis_id, mes_selecionado, ano_selecionado = _resolve_coleta_imagens_filters(user, args)
    periodos_query = _build_coleta_imagens_query(user, regiao=regiao_selecionada, uvis_id=uvis_id)
    base_query = _build_coleta_imagens_query(
        user,
        regiao=regiao_selecionada,
        uvis_id=uvis_id,
        mes=mes_selecionado,
        ano=ano_selecionado,
    )

    rows = (
        base_query
        .order_by(
            Usuario.nome_uvis.asc(),
            OrdemServico.data_aplicacao.desc(),
            OrdemServico.respondido_em.desc(),
            OrdemServico.id.desc(),
        )
        .all()
    )

    levantamentos = [_serialize_coleta_imagem_row(ordem, solicitacao, usuario) for ordem, solicitacao, usuario in rows]

    dados_unidade_counter = Counter(item["uvis_nome"] for item in levantamentos)
    dados_regiao_counter = Counter(item["regiao_nome"] for item in levantamentos)

    total_imagens_complementares = sum(item["outras_imagens_count"] for item in levantamentos)
    total_videos = sum(1 for item in levantamentos if item["tem_video"])
    total_midias = sum(item["total_midias"] for item in levantamentos)
    total_uvis = len({item["uvis_nome"] for item in levantamentos if item["uvis_nome"] and item["uvis_nome"] != "Nao informado"})
    total_regioes = len({item["regiao_nome"] for item in levantamentos if item["regiao_nome"] and item["regiao_nome"] != "Nao informado"})

    uvis_disponiveis = build_uvis_disponiveis(user, regiao_selecionada)
    regioes_disponiveis = build_regioes_disponiveis(user)
    ano_ref, mes_ref = _coleta_period_exprs()
    dados_mensais = [
        (f"{int(ano_h):04d}-{int(mes_h):02d}", total)
        for ano_h, mes_h, total in (
            periodos_query
            .with_entities(ano_ref.label("ano_ref"), mes_ref.label("mes_ref"), func.count(OrdemServico.id))
            .filter(ano_ref.isnot(None), mes_ref.isnot(None))
            .group_by("ano_ref", "mes_ref")
            .order_by("ano_ref", "mes_ref")
            .all()
        )
        if ano_h and mes_h
    ]
    anos_disponiveis = sorted({int(periodo.split("-")[0]) for periodo, _ in dados_mensais}, reverse=True) if dados_mensais else [datetime.now().year]

    nome_uvis = None
    if uvis_id:
        nome_uvis = (
            apply_regiao_scope(
                db.session.query(Usuario.nome_uvis).filter(Usuario.id == uvis_id),
                user,
                Usuario.regiao,
            )
            .scalar()
        )
    if is_uvis and not nome_uvis:
        nome_uvis = getattr(user, "nome_uvis", None)

    if is_uvis:
        descricao_painel = "Acompanhe as fotos vinculadas as suas OS e exporte o relatorio em PDF."
        voltar_endpoint = "main.dashboard"
        voltar_label = "Voltar ao painel"
    elif is_regional:
        descricao_painel = "Acompanhe as fotos vinculadas as OS das UVIS da sua regiao e exporte o relatorio em PDF."
        voltar_endpoint = "main.relatorios"
        voltar_label = "Voltar aos relatorios"
    else:
        descricao_painel = "Painel administrativo dos levantamentos com foto principal vinculados as OS."
        voltar_endpoint = "main.relatorios"
        voltar_label = "Voltar"

    periodo_label = _format_coleta_periodo_label(mes_selecionado, ano_selecionado)

    return {
        "levantamentos": levantamentos,
        "total_levantamentos": len(levantamentos),
        "total_uvis_com_registro": total_uvis,
        "total_regioes_com_registro": total_regioes,
        "total_imagens_complementares": total_imagens_complementares,
        "total_videos": total_videos,
        "total_midias": total_midias,
        "dados_unidade": sorted(dados_unidade_counter.items(), key=lambda item: (-item[1], item[0])),
        "dados_regiao": sorted(dados_regiao_counter.items(), key=lambda item: (-item[1], item[0])),
        "uvis_disponiveis": uvis_disponiveis,
        "regioes_disponiveis": regioes_disponiveis,
        "uvis_id_selecionado": uvis_id,
        "regiao_selecionada": regiao_selecionada,
        "mes_selecionado": mes_selecionado,
        "ano_selecionado": ano_selecionado,
        "anos_disponiveis": anos_disponiveis,
        "dados_mensais": dados_mensais,
        "periodo_label": periodo_label,
        "uvis_nome_selecionado": nome_uvis or "Todas as Unidades",
        "regiao_nome_selecionada": regiao_selecionada or "Todas as Regioes",
        "descricao_painel": descricao_painel,
        "voltar_endpoint": voltar_endpoint,
        "voltar_label": voltar_label,
        "os_detail_endpoint": "main.uvis_os_formulario_view" if is_uvis else "main.admin_os_formulario_view",
        "pode_filtrar_uvis": not is_uvis,
        "pode_filtrar_regiao": not (is_uvis or is_regional),
    }


def build_relatorios_coleta_imagens_context(user, args):
    data = build_relatorio_coleta_imagens_export_data(user, args)
    page = args.get("page", 1, type=int)
    paginacao = SimplePagination(data["levantamentos"], page, per_page=9)

    return {
        **data,
        "levantamentos": paginacao.items,
        "paginacao": paginacao,
    }
