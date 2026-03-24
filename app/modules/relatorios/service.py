from datetime import datetime

from sqlalchemy import and_, extract, func, or_

from app.extensions import db
from app.models import OrdemServico, Solicitacao, Usuario
from app.shared.access import ADMIN_PANEL_VIEW_TYPES, apply_regiao_scope, apply_solicitacao_regiao_scope
from app.shared.query_filters import aplicar_filtros_base


RELATORIOS_MENU_TYPES = ADMIN_PANEL_VIEW_TYPES


def can_access_relatorios_menu(user) -> bool:
    return getattr(user, "tipo_usuario", None) in RELATORIOS_MENU_TYPES


def build_uvis_disponiveis(user):
    if getattr(user, "tipo_usuario", None) not in RELATORIOS_MENU_TYPES:
        return []

    query = db.session.query(Usuario.id, Usuario.nome_uvis).filter(Usuario.tipo_usuario == "uvis")
    query = apply_regiao_scope(query, user, Usuario.regiao)
    return query.order_by(Usuario.nome_uvis).all()


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
