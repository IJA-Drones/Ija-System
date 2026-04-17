from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
import os
import uuid

from flask import current_app
from sqlalchemy import false, or_
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.utils import secure_filename

from app.models import (
    BancoAgro,
    ClienteAgro,
    ContratoAgro,
    EquipamentoAgro,
    EquipeAgro,
    FinanceiroAgro,
    FinanceiroAgroCaixaDiario,
    FinanceiroAgroCompetenciaControle,
    FinanceiroAgroEntrada,
    FinanceiroAgroSaida,
    OrcamentoAgro,
    OrdemServicoAgro,
    PilotoAgro,
)
from app.shared.access import (
    ADMIN_PANEL_EDIT_TYPES,
    ADMIN_PANEL_VIEW_TYPES,
    AGRO_FINANCE_EDIT_TYPES,
    AGRO_FINANCE_VIEW_TYPES,
    FINANCEIRO_ADMIN_USER_TYPE,
    FINANCEIRO_USER_TYPE,
    apply_prefeitura_scope,
    normalize_role,
)
from app.shared.formatters import format_cep, format_currency_br, format_documento, only_digits
from app.shared.uploads import get_upload_folder


AGRO_REPORT_MONTHS = (
    (1, "Janeiro"),
    (2, "Fevereiro"),
    (3, "Marco"),
    (4, "Abril"),
    (5, "Maio"),
    (6, "Junho"),
    (7, "Julho"),
    (8, "Agosto"),
    (9, "Setembro"),
    (10, "Outubro"),
    (11, "Novembro"),
    (12, "Dezembro"),
)

AGRO_DRE_MODELO_LINHAS = (
    ("Receita bruta realizada", "receita_bruta_realizada", "Entradas reconhecidas no Agro."),
    ("Comissao principal", "comissao_principal_realizada", "Saida operacional vinculada aos contratos."),
    ("Comissao cooperativa", "comissao_cooperativa_realizada", "Parcela operacional destinada a cooperativa."),
    ("Despesas manuais", "despesas_manuais_realizadas", "Saidas manuais classificadas como despesa."),
    ("Impostos", "impostos_realizados", "Saidas tributarias manuais do Agro."),
    ("Retencoes", "retencoes_realizadas", "Retencoes e encargos financeiros do Agro."),
    ("Despesa total", "despesa_total_realizada", "Soma das saidas operacionais, fiscais e retidas."),
    ("Resultado realizado", "resultado_realizado", "Receita realizada menos despesas realizadas."),
    ("Saldo acumulado", "saldo_acumulado_realizado", "Saldo acumulado mes a mes no Agro."),
)


def build_agro_categoria_composta(categoria, subcategoria) -> str:
    categoria = (categoria or "").strip()
    subcategoria = (subcategoria or "").strip()
    if categoria and subcategoria:
        return f"{categoria} / {subcategoria}"
    return categoria or subcategoria


def can_access_agro_panel(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in (ADMIN_PANEL_VIEW_TYPES | AGRO_FINANCE_VIEW_TYPES)


def can_edit_agro_panel(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in ADMIN_PANEL_EDIT_TYPES


def can_edit_agro_finance_panel(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in (ADMIN_PANEL_EDIT_TYPES | AGRO_FINANCE_EDIT_TYPES)


def is_financeiro_agro_admin(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in {"admin", FINANCEIRO_ADMIN_USER_TYPE}


def is_financeiro_agro_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == FINANCEIRO_USER_TYPE


def is_financeiro_agro_only_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in AGRO_FINANCE_VIEW_TYPES


def can_manage_agro_finance_settings(user) -> bool:
    return is_financeiro_agro_admin(user)


def is_past_agro_competencia(ano: int | None, mes: int | None, *, today: date | None = None) -> bool:
    if not ano or not mes:
        return False

    reference = date(ano, mes, 1)
    current = (today or date.today()).replace(day=1)
    return reference < current


def get_agro_finance_competencia_controle(ano: int | None, mes: int | None):
    if not ano or not mes:
        return None

    return (
        FinanceiroAgroCompetenciaControle.query
        .filter(
            FinanceiroAgroCompetenciaControle.competencia_ano == int(ano),
            FinanceiroAgroCompetenciaControle.competencia_mes == int(mes),
        )
        .first()
    )


def is_agro_finance_competencia_liberada(ano: int | None, mes: int | None) -> bool:
    controle = get_agro_finance_competencia_controle(ano, mes)
    return bool(controle and controle.liberado)


def can_user_write_agro_finance_competencia(user, ano: int | None, mes: int | None) -> bool:
    if not ano or not mes:
        return True

    if is_financeiro_agro_admin(user):
        return True

    if not is_financeiro_agro_user(user):
        return True

    if not is_past_agro_competencia(ano, mes):
        return True

    return is_agro_finance_competencia_liberada(ano, mes)


def build_agro_finance_competencia_settings(months_back: int = 18) -> list[dict]:
    current_month = date.today().replace(day=1)
    controles = {
        (item.competencia_ano, item.competencia_mes): item
        for item in FinanceiroAgroCompetenciaControle.query.all()
    }
    items = []

    for offset in range(months_back, -1, -1):
        year = current_month.year
        month = current_month.month - offset
        while month <= 0:
            month += 12
            year -= 1

        controle = controles.get((year, month))
        is_current = year == current_month.year and month == current_month.month
        is_past = date(year, month, 1) < current_month
        liberado = bool(controle and controle.liberado)

        items.append(
            {
                "ano": year,
                "mes": month,
                "label": date(year, month, 1).strftime("%m/%Y"),
                "nome_mes": AGRO_REPORT_MONTHS[month - 1][1],
                "is_current": is_current,
                "is_past": is_past,
                "liberado": liberado or not is_past,
                "explicitamente_liberado": liberado,
                "controle": controle,
            }
        )

    return items


def build_endereco_agro(cep, logradouro, numero, complemento, bairro, cidade, uf) -> str:
    cep_formatado = format_cep(only_digits(cep or ""))
    logradouro = (logradouro or "").strip()
    numero = (numero or "").strip()
    complemento = (complemento or "").strip()
    bairro = (bairro or "").strip()
    cidade = (cidade or "").strip()
    uf = (uf or "").strip().upper()

    linha_1 = ""
    if logradouro:
        linha_1 += logradouro
    if numero:
        linha_1 += f", {numero}" if linha_1 else numero
    if complemento:
        linha_1 += f" ({complemento})" if linha_1 else complemento

    cidade_uf = f"{cidade}/{uf}" if cidade and uf else cidade or uf
    linha_2 = " - ".join([item for item in [bairro, cidade_uf] if item])
    linha_3 = f"CEP {cep_formatado}" if cep_formatado else ""

    return " - ".join([item for item in [linha_1, linha_2, linha_3] if item])


def serialize_cliente_agro(cliente: ClienteAgro) -> dict:
    return {
        "id": cliente.id,
        "nome": cliente.nome,
        "documento_fmt": format_documento(cliente.documento),
        "cep": format_cep(cliente.cep or ""),
        "endereco_completo": build_endereco_agro(
            cliente.cep,
            cliente.logradouro,
            cliente.numero,
            cliente.complemento,
            cliente.bairro,
            cliente.cidade,
            cliente.uf,
        ),
    }


def build_clientes_agro_query(user, q: str = ""):
    query = ClienteAgro.query
    query = apply_prefeitura_scope(query, user, ClienteAgro.prefeitura_id)

    if q:
        q_digits = only_digits(q)
        like = f"%{q}%"
        query = query.filter(
            or_(
                ClienteAgro.nome.ilike(like)
                , ClienteAgro.logradouro.ilike(like)
                , ClienteAgro.bairro.ilike(like)
                , ClienteAgro.cidade.ilike(like)
                , ClienteAgro.documento.ilike(f"%{q_digits}%") if q_digits else false()
            )
        )

    return query.order_by(ClienteAgro.nome.asc(), ClienteAgro.id.desc())


def build_orcamentos_agro_query(user, q: str = "", cliente_id: int | None = None, mapeamento: str = ""):
    query = OrcamentoAgro.query.options(
        joinedload(OrcamentoAgro.cliente),
        joinedload(OrcamentoAgro.contrato),
        joinedload(OrcamentoAgro.drone_agro),
        joinedload(OrcamentoAgro.drone_mapeamento_agro),
    )
    query = apply_prefeitura_scope(query, user, OrcamentoAgro.prefeitura_id)

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                OrcamentoAgro.cliente_nome.ilike(like),
                OrcamentoAgro.cliente_documento.ilike(like),
                OrcamentoAgro.nome_fazenda.ilike(like),
                OrcamentoAgro.cultura.ilike(like),
                OrcamentoAgro.cultura_alternativa.ilike(like),
                OrcamentoAgro.servico.ilike(like),
                OrcamentoAgro.protocolo.ilike(like),
            )
        )

    if cliente_id:
        query = query.filter(OrcamentoAgro.cliente_agro_id == cliente_id)

    if mapeamento == "SIM":
        query = query.filter(OrcamentoAgro.mapeamento.is_(True))
    elif mapeamento == "NAO":
        query = query.filter(OrcamentoAgro.mapeamento.is_(False))

    return query.order_by(OrcamentoAgro.data_criacao.desc(), OrcamentoAgro.id.desc())


def build_contratos_agro_query(user, q: str = "", status: str = "", equipe_id: int | None = None):
    query = ContratoAgro.query.options(
        joinedload(ContratoAgro.orcamento).joinedload(OrcamentoAgro.cliente),
        joinedload(ContratoAgro.equipe),
        selectinload(ContratoAgro.ordens_servico),
    )
    query = apply_prefeitura_scope(query, user, ContratoAgro.prefeitura_id)

    if status:
        query = query.filter(ContratoAgro.status == status)

    if q:
        like = f"%{q}%"
        query = query.join(ContratoAgro.orcamento).filter(
            or_(
                ContratoAgro.contratante_nome.ilike(like),
                ContratoAgro.propriedade_nome.ilike(like),
                OrcamentoAgro.cliente_nome.ilike(like),
                OrcamentoAgro.nome_fazenda.ilike(like),
                OrcamentoAgro.protocolo.ilike(like),
            )
        )

    if equipe_id:
        query = query.filter(ContratoAgro.equipe_agro_id == equipe_id)

    return query.order_by(ContratoAgro.atualizado_em.desc(), ContratoAgro.id.desc())


def build_contratos_agro_aprovados_query(user, q: str = "", equipe_id: int | None = None):
    return build_contratos_agro_query(
        user,
        q=q,
        status=ContratoAgro.STATUS_APROVADO,
        equipe_id=equipe_id,
    )


def build_ordens_servico_agro_query(user, q: str = "", status: str = "", equipe_id: int | None = None):
    query = OrdemServicoAgro.query.options(
        joinedload(OrdemServicoAgro.contrato).joinedload(ContratoAgro.orcamento),
        joinedload(OrdemServicoAgro.equipe).joinedload(EquipeAgro.pilotos),
        joinedload(OrdemServicoAgro.piloto),
        joinedload(OrdemServicoAgro.drone_pulverizacao),
        joinedload(OrdemServicoAgro.drone_mapeamento),
    )
    query = apply_prefeitura_scope(query, user, OrdemServicoAgro.prefeitura_id)

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                OrdemServicoAgro.identificador_os.ilike(like),
                OrdemServicoAgro.cliente_nome.ilike(like),
                OrdemServicoAgro.propriedade_nome.ilike(like),
                OrdemServicoAgro.protocolo.ilike(like),
            )
        )

    if status:
        query = query.filter(OrdemServicoAgro.status == status)

    if equipe_id:
        query = query.filter(OrdemServicoAgro.equipe_agro_id == equipe_id)

    return query.order_by(
        OrdemServicoAgro.data_aplicacao.desc().nullslast(),
        OrdemServicoAgro.atualizado_em.desc(),
        OrdemServicoAgro.id.desc(),
    )


def build_financeiro_agro_query(
    user,
    q: str = "",
    status: str = "",
    mes: int | None = None,
    ano: int | None = None,
    contrato_id: int | None = None,
):
    query = FinanceiroAgro.query.options(
        joinedload(FinanceiroAgro.contrato).joinedload(ContratoAgro.orcamento),
        joinedload(FinanceiroAgro.ordem_servico),
        joinedload(FinanceiroAgro.cliente),
        joinedload(FinanceiroAgro.banco_agro),
    )
    query = apply_prefeitura_scope(query, user, FinanceiroAgro.prefeitura_id)

    if q:
        like = f"%{q}%"
        query = query.outerjoin(FinanceiroAgro.banco_agro)
        query = query.filter(
            or_(
                FinanceiroAgro.cliente_nome.ilike(like),
                FinanceiroAgro.cultura.ilike(like),
                BancoAgro.nome.ilike(like),
                FinanceiroAgro.forma_recebimento.ilike(like),
                FinanceiroAgro.observacoes.ilike(like),
            )
        )

    if status:
        query = query.filter(FinanceiroAgro.status == status)

    if mes:
        query = query.filter(FinanceiroAgro.competencia_mes == mes)

    if ano:
        query = query.filter(FinanceiroAgro.competencia_ano == ano)

    if contrato_id:
        query = query.filter(FinanceiroAgro.contrato_agro_id == contrato_id)

    return query.order_by(
        FinanceiroAgro.data_vencimento.asc(),
        FinanceiroAgro.criado_em.desc(),
        FinanceiroAgro.id.desc(),
    )


def build_financeiro_agro_entrada_query(
    user,
    q: str = "",
    status: str = "",
    mes: int | None = None,
    ano: int | None = None,
):
    query = FinanceiroAgroEntrada.query.options(
        joinedload(FinanceiroAgroEntrada.cliente),
        joinedload(FinanceiroAgroEntrada.banco_agro),
    )
    query = apply_prefeitura_scope(query, user, FinanceiroAgroEntrada.prefeitura_id)

    if q:
        like = f"%{q}%"
        query = query.outerjoin(FinanceiroAgroEntrada.banco_agro)
        query = query.filter(
            or_(
                FinanceiroAgroEntrada.cliente_nome.ilike(like),
                FinanceiroAgroEntrada.categoria.ilike(like),
                FinanceiroAgroEntrada.subcategoria.ilike(like),
                FinanceiroAgroEntrada.descricao.ilike(like),
                FinanceiroAgroEntrada.documento_referencia.ilike(like),
                BancoAgro.nome.ilike(like),
                FinanceiroAgroEntrada.forma_recebimento.ilike(like),
            )
        )

    if status:
        query = query.filter(FinanceiroAgroEntrada.status == status)

    if mes:
        query = query.filter(FinanceiroAgroEntrada.competencia_mes == mes)

    if ano:
        query = query.filter(FinanceiroAgroEntrada.competencia_ano == ano)

    return query.order_by(
        FinanceiroAgroEntrada.data_recebimento.asc().nullslast(),
        FinanceiroAgroEntrada.data_lancamento.asc().nullslast(),
        FinanceiroAgroEntrada.data_vencimento.asc(),
        FinanceiroAgroEntrada.id.desc(),
    )


def build_financeiro_agro_saida_query(
    user,
    q: str = "",
    status: str = "",
    tipo_saida: str = "",
    mes: int | None = None,
    ano: int | None = None,
):
    query = FinanceiroAgroSaida.query.options(
        joinedload(FinanceiroAgroSaida.cliente),
        joinedload(FinanceiroAgroSaida.banco_agro),
    )
    query = apply_prefeitura_scope(query, user, FinanceiroAgroSaida.prefeitura_id)

    if q:
        like = f"%{q}%"
        query = query.outerjoin(FinanceiroAgroSaida.banco_agro)
        query = query.filter(
            or_(
                FinanceiroAgroSaida.categoria.ilike(like),
                FinanceiroAgroSaida.subcategoria.ilike(like),
                FinanceiroAgroSaida.descricao.ilike(like),
                FinanceiroAgroSaida.documento_referencia.ilike(like),
                FinanceiroAgroSaida.detalhamento_imposto.ilike(like),
                FinanceiroAgroSaida.favorecido.ilike(like),
                BancoAgro.nome.ilike(like),
                FinanceiroAgroSaida.forma_pagamento.ilike(like),
            )
        )

    if status:
        query = query.filter(FinanceiroAgroSaida.status == status)

    if tipo_saida:
        query = query.filter(FinanceiroAgroSaida.tipo_saida == tipo_saida)

    if mes:
        query = query.filter(FinanceiroAgroSaida.competencia_mes == mes)

    if ano:
        query = query.filter(FinanceiroAgroSaida.competencia_ano == ano)

    return query.order_by(
        FinanceiroAgroSaida.data_pagamento.asc().nullslast(),
        FinanceiroAgroSaida.data_lancamento.asc().nullslast(),
        FinanceiroAgroSaida.data_vencimento.asc(),
        FinanceiroAgroSaida.id.desc(),
    )


def build_financeiro_agro_caixa_diario_query(user):
    query = FinanceiroAgroCaixaDiario.query
    query = apply_prefeitura_scope(query, user, FinanceiroAgroCaixaDiario.prefeitura_id)
    return query.order_by(FinanceiroAgroCaixaDiario.data_caixa.desc(), FinanceiroAgroCaixaDiario.id.desc())


def build_bancos_agro_query(user, q: str = "", ativo: str = ""):
    query = BancoAgro.query
    query = apply_prefeitura_scope(query, user, BancoAgro.prefeitura_id)

    if ativo == "ATIVO":
        query = query.filter(BancoAgro.ativo.is_(True))
    elif ativo == "INATIVO":
        query = query.filter(BancoAgro.ativo.is_(False))

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                BancoAgro.nome.ilike(like),
                BancoAgro.banco_nome.ilike(like),
                BancoAgro.agencia.ilike(like),
                BancoAgro.conta.ilike(like),
            )
        )

    return query.order_by(BancoAgro.ativo.desc(), BancoAgro.nome.asc(), BancoAgro.id.desc())


def recalculate_bancos_agro(banco_ids):
    valid_ids = sorted({int(item) for item in (banco_ids or []) if item})
    if not valid_ids:
        return

    bancos = BancoAgro.query.filter(BancoAgro.id.in_(valid_ids)).all()
    for banco in bancos:
        saldo_previsto = banco.saldo_inicial_decimal
        saldo_atual = banco.saldo_inicial_decimal

        for item in FinanceiroAgro.query.filter(FinanceiroAgro.banco_agro_id == banco.id).all():
            valor = FinanceiroAgro._decimal_or_zero(item.valor_total_contrato)
            status = (item.status or "").strip().upper()
            if status != FinanceiroAgro.STATUS_CANCELADO:
                saldo_previsto += valor
            if status == FinanceiroAgro.STATUS_RECEBIDO or item.data_recebimento:
                saldo_atual += valor

        for item in FinanceiroAgroEntrada.query.filter(FinanceiroAgroEntrada.banco_agro_id == banco.id).all():
            valor = FinanceiroAgro._decimal_or_zero(item.valor)
            status = (item.status or "").strip().upper()
            if status != FinanceiroAgroEntrada.STATUS_CANCELADO:
                saldo_previsto += valor
            if status == FinanceiroAgroEntrada.STATUS_RECEBIDO or item.data_recebimento:
                saldo_atual += valor

        for item in FinanceiroAgroSaida.query.filter(FinanceiroAgroSaida.banco_agro_id == banco.id).all():
            valor = FinanceiroAgro._decimal_or_zero(item.valor)
            status = (item.status or "").strip().upper()
            if status != FinanceiroAgroSaida.STATUS_CANCELADO:
                saldo_previsto -= valor
            if status == FinanceiroAgroSaida.STATUS_PAGO or item.data_pagamento:
                saldo_atual -= valor

        banco.saldo_previsto = saldo_previsto
        banco.saldo_atual = saldo_atual


def _agro_report_get(item, field, default=None):
    if isinstance(item, dict):
        return item.get(field, default)
    return getattr(item, field, default)


def _agro_decimal(value) -> Decimal:
    return FinanceiroAgro._decimal_or_zero(value)


def _agro_report_is_cancelled(item) -> bool:
    return (_agro_report_get(item, "status") or "").strip().upper() == FinanceiroAgro.STATUS_CANCELADO


def _agro_report_is_realized(item) -> bool:
    status = (_agro_report_get(item, "status") or "").strip().upper()
    if isinstance(item, FinanceiroAgroSaida):
        return status == FinanceiroAgroSaida.STATUS_PAGO or bool(_agro_report_get(item, "data_pagamento"))
    if isinstance(item, FinanceiroAgroEntrada):
        return status == FinanceiroAgroEntrada.STATUS_RECEBIDO or bool(_agro_report_get(item, "data_recebimento"))
    return status == FinanceiroAgro.STATUS_RECEBIDO or bool(_agro_report_get(item, "data_recebimento"))


def _resolve_agro_cashflow_date(item, realized: bool = False):
    if isinstance(item, FinanceiroAgroSaida):
        if realized:
            return (
                _agro_report_get(item, "data_pagamento")
                or _agro_report_get(item, "data_lancamento")
                or _agro_report_get(item, "data_vencimento")
                or _agro_report_get(item, "data_emissao")
            )
        return (
            _agro_report_get(item, "data_lancamento")
            or _agro_report_get(item, "data_vencimento")
            or _agro_report_get(item, "data_emissao")
        )

    if isinstance(item, FinanceiroAgroEntrada):
        if realized:
            return (
                _agro_report_get(item, "data_recebimento")
                or _agro_report_get(item, "data_lancamento")
                or _agro_report_get(item, "data_vencimento")
                or _agro_report_get(item, "data_emissao")
            )
        return (
            _agro_report_get(item, "data_lancamento")
            or _agro_report_get(item, "data_vencimento")
            or _agro_report_get(item, "data_emissao")
        )

    if realized:
        return (
            _agro_report_get(item, "data_recebimento")
            or _agro_report_get(item, "data_vencimento")
            or _agro_report_get(item, "data_servico_executado")
            or _agro_report_get(item, "data_elaboracao_contrato")
        )
    return (
        _agro_report_get(item, "data_vencimento")
        or _agro_report_get(item, "data_servico_executado")
        or _agro_report_get(item, "data_elaboracao_contrato")
    )


def _resolve_agro_report_date(item):
    return _resolve_agro_cashflow_date(item, realized=True) or _resolve_agro_cashflow_date(item, realized=False)


def _resolve_agro_report_year(items, ano: int | None = None) -> int:
    if ano:
        return ano

    years = []
    for item in items:
        for field in (
            "data_recebimento",
            "data_pagamento",
            "data_lancamento",
            "data_vencimento",
            "data_servico_executado",
            "data_elaboracao_contrato",
            "data_emissao",
        ):
            value = _agro_report_get(item, field)
            if value:
                years.append(value.year)
        competencia_ano = _agro_report_get(item, "competencia_ano")
        if competencia_ano:
            years.append(int(competencia_ano))

    return max(years) if years else datetime.now().year


def _resolve_agro_report_month(item):
    data_base = _agro_report_get(item, "data")
    if data_base:
        return data_base.month
    for field in ("data_realizada", "data_prevista", "data_vencimento", "data_lancamento", "data_emissao"):
        value = _agro_report_get(item, field)
        if value:
            return value.month
    competencia_mes = _agro_report_get(item, "competencia_mes")
    if competencia_mes:
        return int(competencia_mes)
    return None


def _init_agro_month_bucket():
    return {
        "receita_bruta_prevista": Decimal("0"),
        "receita_bruta_realizada": Decimal("0"),
        "comissao_principal_prevista": Decimal("0"),
        "comissao_principal_realizada": Decimal("0"),
        "comissao_cooperativa_prevista": Decimal("0"),
        "comissao_cooperativa_realizada": Decimal("0"),
        "despesas_manuais_previstas": Decimal("0"),
        "despesas_manuais_realizadas": Decimal("0"),
        "impostos_previstos": Decimal("0"),
        "impostos_realizados": Decimal("0"),
        "retencoes_previstas": Decimal("0"),
        "retencoes_realizadas": Decimal("0"),
        "despesa_total_prevista": Decimal("0"),
        "despesa_total_realizada": Decimal("0"),
        "resultado_previsto": Decimal("0"),
        "resultado_realizado": Decimal("0"),
        "saldo_acumulado_previsto": Decimal("0"),
        "saldo_acumulado_realizado": Decimal("0"),
    }


def _build_agro_report_monthly_totals(itens):
    mensal = {month: _init_agro_month_bucket() for month, _name in AGRO_REPORT_MONTHS}

    for item in itens:
        month = _resolve_agro_report_month(item)
        if month not in mensal:
            continue
        bucket = mensal[month]
        bucket["receita_bruta_prevista"] += _agro_decimal(_agro_report_get(item, "entrada_prevista"))
        bucket["receita_bruta_realizada"] += _agro_decimal(_agro_report_get(item, "entrada_realizada"))
        bucket["comissao_principal_prevista"] += _agro_decimal(_agro_report_get(item, "comissao_principal_prevista"))
        bucket["comissao_principal_realizada"] += _agro_decimal(_agro_report_get(item, "comissao_principal_realizada"))
        bucket["comissao_cooperativa_prevista"] += _agro_decimal(_agro_report_get(item, "comissao_cooperativa_prevista"))
        bucket["comissao_cooperativa_realizada"] += _agro_decimal(_agro_report_get(item, "comissao_cooperativa_realizada"))
        bucket["despesas_manuais_previstas"] += _agro_decimal(_agro_report_get(item, "despesas_manuais_previstas"))
        bucket["despesas_manuais_realizadas"] += _agro_decimal(_agro_report_get(item, "despesas_manuais_realizadas"))
        bucket["impostos_previstos"] += _agro_decimal(_agro_report_get(item, "impostos_previstos"))
        bucket["impostos_realizados"] += _agro_decimal(_agro_report_get(item, "impostos_realizados"))
        bucket["retencoes_previstas"] += _agro_decimal(_agro_report_get(item, "retencoes_previstas"))
        bucket["retencoes_realizadas"] += _agro_decimal(_agro_report_get(item, "retencoes_realizadas"))

    saldo_previsto = Decimal("0")
    saldo_realizado = Decimal("0")
    for month, _name in AGRO_REPORT_MONTHS:
        bucket = mensal[month]
        bucket["despesa_total_prevista"] = (
            bucket["comissao_principal_prevista"]
            + bucket["comissao_cooperativa_prevista"]
            + bucket["despesas_manuais_previstas"]
            + bucket["impostos_previstos"]
            + bucket["retencoes_previstas"]
        )
        bucket["despesa_total_realizada"] = (
            bucket["comissao_principal_realizada"]
            + bucket["comissao_cooperativa_realizada"]
            + bucket["despesas_manuais_realizadas"]
            + bucket["impostos_realizados"]
            + bucket["retencoes_realizadas"]
        )
        bucket["resultado_previsto"] = bucket["receita_bruta_prevista"] - bucket["despesa_total_prevista"]
        bucket["resultado_realizado"] = bucket["receita_bruta_realizada"] - bucket["despesa_total_realizada"]
        saldo_previsto += bucket["resultado_previsto"]
        saldo_realizado += bucket["resultado_realizado"]
        bucket["saldo_acumulado_previsto"] = saldo_previsto
        bucket["saldo_acumulado_realizado"] = saldo_realizado

    return mensal


def _apply_agro_cashflow_running_balance(itens, opening_balance: Decimal | None = None):
    saldo_previsto = _agro_decimal(opening_balance)
    saldo_realizado = _agro_decimal(opening_balance)
    for item in itens:
        saldo_previsto += _agro_decimal(item.get("entrada_prevista")) - _agro_decimal(item.get("saida_prevista"))
        saldo_realizado += _agro_decimal(item.get("entrada_realizada")) - _agro_decimal(item.get("saida_realizada"))
        item["saldo_previsto_acumulado"] = saldo_previsto
        item["saldo_realizado_acumulado"] = saldo_realizado


def _sort_agro_cashflow_items(itens):
    return sorted(
        itens,
        key=lambda item: (
            (item.get("data_realizada") or item.get("data_prevista") or item.get("data") or date.min).toordinal(),
            item.get("criado_em") or datetime.min,
            item.get("documento_referencia") or "",
            item.get("id") or 0,
        ),
    )


def build_agro_fluxo_caixa_report(user, ano: int | None = None) -> dict:
    lancamentos_contrato = build_financeiro_agro_query(user).all()
    lancamentos_entradas = build_financeiro_agro_entrada_query(user).all()
    lancamentos_saidas = build_financeiro_agro_saida_query(user).all()

    ano = _resolve_agro_report_year([*lancamentos_contrato, *lancamentos_entradas, *lancamentos_saidas], ano)
    itens = []

    for item in lancamentos_contrato:
        if _resolve_agro_report_year([item]) != ano:
            continue

        valor_receita = _agro_decimal(item.valor_total_contrato)
        valor_comissao = _agro_decimal(item.valor_comissao)
        valor_comissao_cooperativa = _agro_decimal(item.valor_comissao_cooperativa)
        data_prevista = _resolve_agro_cashflow_date(item, realized=False)
        data_realizada = _resolve_agro_cashflow_date(item, realized=True) if _agro_report_is_realized(item) else None
        entrada_prevista = Decimal("0") if _agro_report_is_cancelled(item) else valor_receita
        entrada_realizada = valor_receita if _agro_report_is_realized(item) else Decimal("0")
        comissao_principal_prevista = Decimal("0") if _agro_report_is_cancelled(item) else valor_comissao
        comissao_principal_realizada = valor_comissao if _agro_report_is_realized(item) else Decimal("0")
        comissao_cooperativa_prevista = Decimal("0") if _agro_report_is_cancelled(item) else valor_comissao_cooperativa
        comissao_cooperativa_realizada = valor_comissao_cooperativa if _agro_report_is_realized(item) else Decimal("0")
        saida_prevista = comissao_principal_prevista + comissao_cooperativa_prevista
        saida_realizada = comissao_principal_realizada + comissao_cooperativa_realizada
        protocolo = ""
        if item.contrato and item.contrato.orcamento:
            protocolo = item.contrato.orcamento.protocolo or ""

        itens.append(
            {
                "id": item.id,
                "origem": "CONTRATO",
                "data": data_realizada or data_prevista or _resolve_agro_report_date(item),
                "data_prevista": data_prevista,
                "data_realizada": data_realizada,
                "data_emissao": None,
                "cliente_nome": item.cliente_nome,
                "contrato_id": item.contrato_agro_id,
                "cultura": item.cultura,
                "categoria": "Recebivel de contrato",
                "descricao": "Entrada vinculada ao contrato do Agro.",
                "documento_referencia": protocolo or f"Contrato #{item.contrato_agro_id}",
                "detalhamento_imposto": "",
                "favorecido": item.cliente_nome,
                "forma_recebimento": item.forma_recebimento or "",
                "status": item.status,
                "tipo_saida": "",
                "entrada_prevista": entrada_prevista,
                "entrada_realizada": entrada_realizada,
                "comissao_principal_prevista": comissao_principal_prevista,
                "comissao_principal_realizada": comissao_principal_realizada,
                "comissao_cooperativa_prevista": comissao_cooperativa_prevista,
                "comissao_cooperativa_realizada": comissao_cooperativa_realizada,
                "despesas_manuais_previstas": Decimal("0"),
                "despesas_manuais_realizadas": Decimal("0"),
                "impostos_previstos": Decimal("0"),
                "impostos_realizados": Decimal("0"),
                "retencoes_previstas": Decimal("0"),
                "retencoes_realizadas": Decimal("0"),
                "saida_prevista": saida_prevista,
                "saida_realizada": saida_realizada,
                "resultado_previsto": entrada_prevista - saida_prevista,
                "resultado_realizado": entrada_realizada - saida_realizada,
                "observacoes": item.observacoes or "",
                "criado_em": item.criado_em,
            }
        )

    for item in lancamentos_entradas:
        if _resolve_agro_report_year([item]) != ano:
            continue

        valor = _agro_decimal(item.valor)
        entrada_prevista = Decimal("0") if _agro_report_is_cancelled(item) else valor
        entrada_realizada = valor if _agro_report_is_realized(item) else Decimal("0")
        data_prevista = _resolve_agro_cashflow_date(item, realized=False)
        data_realizada = _resolve_agro_cashflow_date(item, realized=True) if _agro_report_is_realized(item) else None

        itens.append(
            {
                "id": item.id,
                "origem": "ENTRADA_MANUAL",
                "data": data_realizada or data_prevista or _resolve_agro_report_date(item),
                "data_prevista": data_prevista,
                "data_realizada": data_realizada,
                "data_emissao": item.data_emissao,
                "cliente_nome": item.cliente_nome,
                "contrato_id": None,
                "cultura": "",
                "categoria": build_agro_categoria_composta(item.categoria, item.subcategoria),
                "categoria_grupo": item.categoria,
                "subcategoria": item.subcategoria or "",
                "descricao": item.descricao,
                "documento_referencia": item.documento_referencia or "",
                "detalhamento_imposto": "",
                "favorecido": item.cliente_nome,
                "forma_recebimento": item.forma_recebimento or "",
                "status": item.status,
                "tipo_saida": "",
                "entrada_prevista": entrada_prevista,
                "entrada_realizada": entrada_realizada,
                "comissao_principal_prevista": Decimal("0"),
                "comissao_principal_realizada": Decimal("0"),
                "comissao_cooperativa_prevista": Decimal("0"),
                "comissao_cooperativa_realizada": Decimal("0"),
                "despesas_manuais_previstas": Decimal("0"),
                "despesas_manuais_realizadas": Decimal("0"),
                "impostos_previstos": Decimal("0"),
                "impostos_realizados": Decimal("0"),
                "retencoes_previstas": Decimal("0"),
                "retencoes_realizadas": Decimal("0"),
                "saida_prevista": Decimal("0"),
                "saida_realizada": Decimal("0"),
                "resultado_previsto": entrada_prevista,
                "resultado_realizado": entrada_realizada,
                "observacoes": item.observacoes or "",
                "criado_em": item.criado_em,
            }
        )

    for item in lancamentos_saidas:
        if _resolve_agro_report_year([item]) != ano:
            continue

        valor = _agro_decimal(item.valor)
        data_prevista = _resolve_agro_cashflow_date(item, realized=False)
        data_realizada = _resolve_agro_cashflow_date(item, realized=True) if _agro_report_is_realized(item) else None
        tipo_saida = (item.tipo_saida or "").strip().upper()

        despesas_manuais_previstas = Decimal("0")
        despesas_manuais_realizadas = Decimal("0")
        impostos_previstos = Decimal("0")
        impostos_realizados = Decimal("0")
        retencoes_previstas = Decimal("0")
        retencoes_realizadas = Decimal("0")

        if tipo_saida == FinanceiroAgroSaida.TIPO_IMPOSTO:
            impostos_previstos = Decimal("0") if _agro_report_is_cancelled(item) else valor
            impostos_realizados = valor if _agro_report_is_realized(item) else Decimal("0")
        elif tipo_saida == FinanceiroAgroSaida.TIPO_RETENCAO:
            retencoes_previstas = Decimal("0") if _agro_report_is_cancelled(item) else valor
            retencoes_realizadas = valor if _agro_report_is_realized(item) else Decimal("0")
        else:
            despesas_manuais_previstas = Decimal("0") if _agro_report_is_cancelled(item) else valor
            despesas_manuais_realizadas = valor if _agro_report_is_realized(item) else Decimal("0")

        saida_prevista = despesas_manuais_previstas + impostos_previstos + retencoes_previstas
        saida_realizada = despesas_manuais_realizadas + impostos_realizados + retencoes_realizadas

        itens.append(
            {
                "id": item.id,
                "origem": "SAIDA_MANUAL",
                "data": data_realizada or data_prevista or _resolve_agro_report_date(item),
                "data_prevista": data_prevista,
                "data_realizada": data_realizada,
                "data_emissao": item.data_emissao,
                "cliente_nome": item.cliente.nome if item.cliente else (item.favorecido or item.descricao),
                "contrato_id": None,
                "cultura": "",
                "categoria": build_agro_categoria_composta(item.categoria, item.subcategoria),
                "categoria_grupo": item.categoria,
                "subcategoria": item.subcategoria or "",
                "descricao": item.descricao,
                "documento_referencia": item.documento_referencia or "",
                "detalhamento_imposto": item.detalhamento_imposto or "",
                "favorecido": item.favorecido or "",
                "forma_recebimento": item.forma_pagamento or "",
                "status": item.status,
                "tipo_saida": tipo_saida,
                "entrada_prevista": Decimal("0"),
                "entrada_realizada": Decimal("0"),
                "comissao_principal_prevista": Decimal("0"),
                "comissao_principal_realizada": Decimal("0"),
                "comissao_cooperativa_prevista": Decimal("0"),
                "comissao_cooperativa_realizada": Decimal("0"),
                "despesas_manuais_previstas": despesas_manuais_previstas,
                "despesas_manuais_realizadas": despesas_manuais_realizadas,
                "impostos_previstos": impostos_previstos,
                "impostos_realizados": impostos_realizados,
                "retencoes_previstas": retencoes_previstas,
                "retencoes_realizadas": retencoes_realizadas,
                "saida_prevista": saida_prevista,
                "saida_realizada": saida_realizada,
                "resultado_previsto": Decimal("0") - saida_prevista,
                "resultado_realizado": Decimal("0") - saida_realizada,
                "observacoes": item.observacoes or "",
                "criado_em": item.criado_em,
            }
        )

    lancamentos_ordenados = _sort_agro_cashflow_items(itens)
    _apply_agro_cashflow_running_balance(lancamentos_ordenados)
    mensal = _build_agro_report_monthly_totals(lancamentos_ordenados)
    totais = _init_agro_month_bucket()
    for month, _name in AGRO_REPORT_MONTHS:
        bucket = mensal[month]
        for key in totais:
            totais[key] += bucket[key]

    return {
        "ano": ano,
        "lancamentos": lancamentos_ordenados,
        "totais": totais,
        "mensal": [mensal[month] for month, _name in AGRO_REPORT_MONTHS],
    }


def build_agro_dre_gerencial_report(user, ano: int | None = None) -> dict:
    fluxo = build_agro_fluxo_caixa_report(user, ano=ano)
    mensal = fluxo["mensal"]
    linhas = []
    totais = {
        "receita_bruta_realizada": Decimal("0"),
        "comissao_principal_realizada": Decimal("0"),
        "comissao_cooperativa_realizada": Decimal("0"),
        "despesas_manuais_realizadas": Decimal("0"),
        "impostos_realizados": Decimal("0"),
        "retencoes_realizadas": Decimal("0"),
        "despesa_total_realizada": Decimal("0"),
        "resultado_realizado": Decimal("0"),
        "saldo_acumulado_realizado": Decimal("0"),
    }

    for label, key, description in AGRO_DRE_MODELO_LINHAS:
        valores = []
        total = Decimal("0")
        for bucket in mensal:
            valor = bucket[key]
            if key in {
                "comissao_principal_realizada",
                "comissao_cooperativa_realizada",
                "despesas_manuais_realizadas",
                "impostos_realizados",
                "retencoes_realizadas",
                "despesa_total_realizada",
            }:
                valor = valor * Decimal("-1")
            valores.append(valor)
            total = valor if key == "saldo_acumulado_realizado" else total + valor

        linhas.append(
            {
                "label": label,
                "kind": key,
                "description": description,
                "valores": valores,
                "total": total,
            }
        )
        totais[key] = total

    return {
        "ano": fluxo["ano"],
        "meses": [name for _month, name in AGRO_REPORT_MONTHS],
        "linhas": linhas,
        "faturamento_total": totais["receita_bruta_realizada"],
        "comissao_principal_total": totais["comissao_principal_realizada"],
        "comissao_cooperativa_total": totais["comissao_cooperativa_realizada"],
        "despesas_manuais_total": totais["despesas_manuais_realizadas"],
        "impostos_total": totais["impostos_realizados"],
        "retencoes_total": totais["retencoes_realizadas"],
        "despesas_total": totais["despesa_total_realizada"],
        "resultado_total": totais["resultado_realizado"],
        "saldo_total": totais["saldo_acumulado_realizado"],
    }


def build_agro_caixa_diario_report(user, data_caixa: date | None = None) -> dict:
    data_caixa = data_caixa or datetime.now().date()
    caixa_query = build_financeiro_agro_caixa_diario_query(user)
    caixa = caixa_query.filter(FinanceiroAgroCaixaDiario.data_caixa == data_caixa).first()
    caixa_anterior = (
        caixa_query.filter(FinanceiroAgroCaixaDiario.data_caixa < data_caixa)
        .order_by(FinanceiroAgroCaixaDiario.data_caixa.desc(), FinanceiroAgroCaixaDiario.id.desc())
        .first()
    )

    saldo_anterior = caixa_anterior.saldo_fechamento_decimal if caixa_anterior else Decimal("0")
    saldo_abertura = caixa.saldo_abertura_decimal if caixa else saldo_anterior
    movimentos = []

    for item in build_financeiro_agro_query(user).all():
        data_movimento = _resolve_agro_cashflow_date(item, realized=True) or _resolve_agro_cashflow_date(item, realized=False)
        if data_movimento != data_caixa or _agro_report_is_cancelled(item):
            continue
        valor = _agro_decimal(item.valor_total_contrato)
        movimentos.append(
            {
                "id": item.id,
                "origem": "CONTRATO",
                "tipo": "Entrada",
                "data": data_movimento,
                "documento_referencia": (item.contrato.orcamento.protocolo if item.contrato and item.contrato.orcamento else "") or f"Contrato #{item.contrato_agro_id}",
                "descricao": item.cliente_nome,
                "categoria": "Recebivel de contrato",
                "categoria_grupo": "Contratos do Agro",
                "subcategoria": "Recebivel de contrato",
                "status": item.status,
                "entrada": valor,
                "saida": Decimal("0"),
                "observacoes": item.observacoes or "",
                "criado_em": item.criado_em,
            }
        )

    for item in build_financeiro_agro_entrada_query(user).all():
        data_movimento = _resolve_agro_cashflow_date(item, realized=True) or _resolve_agro_cashflow_date(item, realized=False)
        if data_movimento != data_caixa or _agro_report_is_cancelled(item):
            continue
        valor = _agro_decimal(item.valor)
        movimentos.append(
            {
                "id": item.id,
                "origem": "ENTRADA_MANUAL",
                "tipo": "Entrada",
                "data": data_movimento,
                "documento_referencia": item.documento_referencia or "",
                "descricao": item.descricao,
                "categoria": build_agro_categoria_composta(item.categoria, item.subcategoria),
                "categoria_grupo": item.categoria or "",
                "subcategoria": item.subcategoria or "",
                "status": item.status,
                "entrada": valor,
                "saida": Decimal("0"),
                "observacoes": item.observacoes or "",
                "criado_em": item.criado_em,
            }
        )

    for item in build_financeiro_agro_saida_query(user).all():
        data_movimento = _resolve_agro_cashflow_date(item, realized=True) or _resolve_agro_cashflow_date(item, realized=False)
        if data_movimento != data_caixa or _agro_report_is_cancelled(item):
            continue
        valor = _agro_decimal(item.valor)
        descricao = item.descricao
        if item.detalhamento_imposto:
            descricao = f"{descricao} | {item.detalhamento_imposto}"
        movimentos.append(
            {
                "id": item.id,
                "origem": "SAIDA_MANUAL",
                "tipo": "Saida",
                "data": data_movimento,
                "documento_referencia": item.documento_referencia or "",
                "descricao": descricao,
                "categoria": build_agro_categoria_composta(item.categoria, item.subcategoria),
                "categoria_grupo": item.categoria or "",
                "subcategoria": item.subcategoria or "",
                "status": item.status,
                "entrada": Decimal("0"),
                "saida": valor,
                "observacoes": item.observacoes or "",
                "criado_em": item.criado_em,
            }
        )

    movimentos = sorted(
        movimentos,
        key=lambda item: (
            item["data"].toordinal() if item.get("data") else 0,
            item.get("criado_em") or datetime.min,
            item.get("tipo") or "",
            item.get("id") or 0,
        ),
    )

    saldo = saldo_abertura
    total_entradas = Decimal("0")
    total_saidas = Decimal("0")
    for item in movimentos:
        total_entradas += _agro_decimal(item["entrada"])
        total_saidas += _agro_decimal(item["saida"])
        saldo += _agro_decimal(item["entrada"]) - _agro_decimal(item["saida"])
        item["saldo"] = saldo

    historico = (
        caixa_query.filter(FinanceiroAgroCaixaDiario.data_caixa >= data_caixa - timedelta(days=14))
        .order_by(FinanceiroAgroCaixaDiario.data_caixa.desc(), FinanceiroAgroCaixaDiario.id.desc())
        .all()
    )

    return {
        "data_caixa": data_caixa,
        "caixa": caixa,
        "caixa_anterior": caixa_anterior,
        "historico": historico,
        "saldo_anterior": saldo_anterior,
        "saldo_sugerido_abertura": saldo_anterior,
        "saldo_abertura": saldo_abertura,
        "total_entradas": total_entradas,
        "total_saidas": total_saidas,
        "saldo_fechamento_calculado": saldo,
        "movimentos": movimentos,
        "caixa_aberto": bool(caixa and caixa.status == FinanceiroAgroCaixaDiario.STATUS_ABERTO),
        "caixa_fechado": bool(caixa and caixa.status == FinanceiroAgroCaixaDiario.STATUS_FECHADO),
        "possui_fechamento_anterior": caixa_anterior is not None,
        "dia_anterior_pendente": bool(caixa_anterior and caixa_anterior.status != FinanceiroAgroCaixaDiario.STATUS_FECHADO),
    }


def get_agro_dashboard_context(user) -> dict:
    clientes_query = apply_prefeitura_scope(ClienteAgro.query, user, ClienteAgro.prefeitura_id)
    orcamentos_query = apply_prefeitura_scope(OrcamentoAgro.query, user, OrcamentoAgro.prefeitura_id)
    contratos_query = apply_prefeitura_scope(ContratoAgro.query, user, ContratoAgro.prefeitura_id)
    pilotos_query = apply_prefeitura_scope(PilotoAgro.query, user, PilotoAgro.prefeitura_id)
    equipes_query = apply_prefeitura_scope(EquipeAgro.query, user, EquipeAgro.prefeitura_id)
    equipamentos_query = apply_prefeitura_scope(EquipamentoAgro.query, user, EquipamentoAgro.prefeitura_id)
    ordens_servico_query = apply_prefeitura_scope(OrdemServicoAgro.query, user, OrdemServicoAgro.prefeitura_id)
    financeiro_query = apply_prefeitura_scope(FinanceiroAgro.query, user, FinanceiroAgro.prefeitura_id)

    return {
        "total_clientes_agro": clientes_query.count(),
        "total_orcamentos_agro": orcamentos_query.count(),
        "total_contratos_agro": contratos_query.count(),
        "total_contratos_agro_aprovados": contratos_query.filter(
            ContratoAgro.status == ContratoAgro.STATUS_APROVADO
        ).count(),
        "total_ordens_servico_agro": ordens_servico_query.count(),
        "total_financeiros_agro": financeiro_query.count(),
        "total_financeiros_agro_pendentes": financeiro_query.filter(
            FinanceiroAgro.status.in_(
                (
                    FinanceiroAgro.STATUS_PENDENTE,
                    FinanceiroAgro.STATUS_VENCIDO,
                )
            )
        ).count(),
        "total_pilotos_agro": pilotos_query.count(),
        "total_equipes_agro": equipes_query.count(),
        "total_equipamentos_agro": equipamentos_query.count(),
        "ultimos_orcamentos": orcamentos_query.order_by(OrcamentoAgro.data_criacao.desc()).limit(8).all(),
    }


def get_agro_finance_dashboard_context(user) -> dict:
    financeiro_query = apply_prefeitura_scope(FinanceiroAgro.query, user, FinanceiroAgro.prefeitura_id)
    entradas_query = apply_prefeitura_scope(FinanceiroAgroEntrada.query, user, FinanceiroAgroEntrada.prefeitura_id)
    saidas_query = apply_prefeitura_scope(FinanceiroAgroSaida.query, user, FinanceiroAgroSaida.prefeitura_id)
    bancos_query = apply_prefeitura_scope(BancoAgro.query, user, BancoAgro.prefeitura_id)
    hoje = date.today()
    caixa_hoje = (
        apply_prefeitura_scope(FinanceiroAgroCaixaDiario.query, user, FinanceiroAgroCaixaDiario.prefeitura_id)
        .filter(FinanceiroAgroCaixaDiario.data_caixa == hoje)
        .first()
    )

    return {
        "total_recebiveis": financeiro_query.count(),
        "total_recebiveis_pendentes": financeiro_query.filter(
            FinanceiroAgro.status.in_((FinanceiroAgro.STATUS_PENDENTE, FinanceiroAgro.STATUS_VENCIDO))
        ).count(),
        "total_entradas_manuais": entradas_query.count(),
        "total_saidas_manuais": saidas_query.count(),
        "total_bancos_agro": bancos_query.count(),
        "caixa_hoje": caixa_hoje,
        "competencias_configuradas": sum(
            1 for item in build_agro_finance_competencia_settings() if item["explicitamente_liberado"]
        ),
        "can_manage_competencias": can_manage_agro_finance_settings(user),
    }


def update_orcamento_snapshot_from_cliente(orcamento: OrcamentoAgro, cliente: ClienteAgro):
    orcamento.cliente_agro_id = cliente.id
    orcamento.cliente_nome = cliente.nome
    orcamento.cliente_documento = cliente.documento
    orcamento.cep = cliente.cep
    orcamento.logradouro = cliente.logradouro
    orcamento.numero = cliente.numero
    orcamento.complemento = cliente.complemento
    orcamento.bairro = cliente.bairro
    orcamento.cidade = cliente.cidade
    orcamento.uf = cliente.uf


def build_descricao_servico_contrato(orcamento: OrcamentoAgro) -> str:
    descricao = orcamento.servico or "Prestacao de servicos agro"
    if orcamento.culturas_formatadas:
        return f"{descricao} na cultura de {orcamento.culturas_formatadas}"
    return descricao


def build_contrato_agro_defaults(orcamento: OrcamentoAgro) -> dict:
    cliente = orcamento.cliente

    return {
        "contratante_nome": ((getattr(cliente, "nome", None) or orcamento.cliente_nome or "")).strip(),
        "contratante_documento": format_documento((getattr(cliente, "documento", None) or orcamento.cliente_documento or "")),
        "contratante_rg": "",
        "contratante_cep": format_cep(getattr(cliente, "cep", None) or ""),
        "contratante_logradouro": (getattr(cliente, "logradouro", None) or "").strip(),
        "contratante_numero": (getattr(cliente, "numero", None) or "").strip(),
        "contratante_complemento": (getattr(cliente, "complemento", None) or "").strip(),
        "contratante_bairro": (getattr(cliente, "bairro", None) or "").strip(),
        "contratante_cidade": (getattr(cliente, "cidade", None) or "").strip(),
        "contratante_uf": (getattr(cliente, "uf", None) or "").strip().upper(),
        "propriedade_nome": (orcamento.nome_fazenda or "").strip(),
        "propriedade_cep": format_cep(orcamento.cep or ""),
        "propriedade_logradouro": (orcamento.logradouro or "").strip(),
        "propriedade_numero": (orcamento.numero or "").strip(),
        "propriedade_complemento": (orcamento.complemento or "").strip(),
        "propriedade_bairro": (orcamento.bairro or "").strip(),
        "propriedade_cidade": (orcamento.cidade or "").strip(),
        "propriedade_uf": (orcamento.uf or "").strip().upper(),
        "descricao_servico": build_descricao_servico_contrato(orcamento),
        "cultura": (orcamento.cultura or "").strip(),
        "cultura_alternativa": (orcamento.cultura_alternativa or "").strip(),
        "area_contratada": orcamento.area_ha_formatada,
        "valor_total": format_currency_br(orcamento.valor_total_calculado),
        "valor_mapeamento_ha": format_currency_br(orcamento.preco_mapeamento),
        "valor_pulverizacao_ha": format_currency_br(orcamento.preco_pulverizacao),
        "valor_pulverizacao_adicional_ha": format_currency_br(orcamento.preco_pulverizacao_adicional),
        "prazo_inicio_dias": "10",
        "prazo_pagamento_dias": "10",
        "cidade_assinatura": "São Paulo",
        "foro_cidade": "São Paulo",
        "data_assinatura": datetime.now().date().isoformat(),
        "observacoes_adicionais": "",
        "status": ContratoAgro.STATUS_EM_ELABORACAO,
    }


def serialize_contrato_agro_form(contrato: ContratoAgro) -> dict:
    return {
        "contratante_nome": contrato.contratante_nome or "",
        "contratante_documento": format_documento(contrato.contratante_documento or ""),
        "contratante_rg": contrato.contratante_rg or "",
        "contratante_cep": format_cep(contrato.contratante_cep or ""),
        "contratante_logradouro": contrato.contratante_logradouro or "",
        "contratante_numero": contrato.contratante_numero or "",
        "contratante_complemento": contrato.contratante_complemento or "",
        "contratante_bairro": contrato.contratante_bairro or "",
        "contratante_cidade": contrato.contratante_cidade or "",
        "contratante_uf": contrato.contratante_uf or "",
        "propriedade_nome": contrato.propriedade_nome or "",
        "propriedade_cep": format_cep(contrato.propriedade_cep or ""),
        "propriedade_logradouro": contrato.propriedade_logradouro or "",
        "propriedade_numero": contrato.propriedade_numero or "",
        "propriedade_complemento": contrato.propriedade_complemento or "",
        "propriedade_bairro": contrato.propriedade_bairro or "",
        "propriedade_cidade": contrato.propriedade_cidade or "",
        "propriedade_uf": contrato.propriedade_uf or "",
        "descricao_servico": contrato.descricao_servico or "",
        "cultura": contrato.cultura or "",
        "cultura_alternativa": contrato.cultura_alternativa or "",
        "area_contratada": contrato.area_contratada or "",
        "valor_total": format_currency_br(contrato.valor_total),
        "valor_mapeamento_ha": format_currency_br(contrato.valor_mapeamento_ha),
        "valor_pulverizacao_ha": format_currency_br(contrato.valor_pulverizacao_ha),
        "valor_pulverizacao_adicional_ha": format_currency_br(contrato.valor_pulverizacao_adicional_ha),
        "prazo_inicio_dias": str(contrato.prazo_inicio_dias or ""),
        "prazo_pagamento_dias": str(contrato.prazo_pagamento_dias or ""),
        "cidade_assinatura": contrato.cidade_assinatura or "",
        "foro_cidade": contrato.foro_cidade or "",
        "data_assinatura": contrato.data_assinatura.isoformat() if contrato.data_assinatura else "",
        "observacoes_adicionais": contrato.observacoes_adicionais or "",
        "status": contrato.status or ContratoAgro.STATUS_EM_ELABORACAO,
    }


def build_financeiro_agro_defaults(contrato: ContratoAgro) -> dict:
    orcamento = contrato.orcamento
    latest_os = None
    if contrato.ordens_servico:
        latest_os = max(
            contrato.ordens_servico,
            key=lambda item: (item.data_aplicacao or datetime.min.date(), item.id),
        )

    data_referencia = (
        getattr(latest_os, "data_aplicacao", None)
        or contrato.data_assinatura
        or datetime.now().date()
    )
    prazo_pagamento = contrato.prazo_pagamento_dias or 0
    data_vencimento = data_referencia
    if prazo_pagamento:
        from datetime import timedelta

        data_vencimento = data_referencia + timedelta(days=prazo_pagamento)

    area_referencia = orcamento.area_ha if orcamento else None
    area_formatada = format_currency_br(area_referencia).replace("R$ ", "") if area_referencia is not None else ""
    area_mapeamento = area_formatada if orcamento and orcamento.inclui_mapeamento else ""
    area_pulverizacao = area_formatada if orcamento and orcamento.inclui_pulverizacao else ""
    area_real = area_pulverizacao

    total_mapeamento = (
        format_currency_br(orcamento.valor_mapeamento_total)
        if orcamento and orcamento.inclui_mapeamento
        else ""
    )
    total_pulverizacao = (
        format_currency_br(orcamento.valor_pulverizacao_total + orcamento.valor_pulverizacao_adicional_total)
        if orcamento and orcamento.inclui_pulverizacao
        else ""
    )

    area_real_decimal = orcamento.area_ha if orcamento and orcamento.inclui_pulverizacao else 0
    valor_comissao = format_currency_br(
        FinanceiroAgro.calcular_total_comissao(area_real_decimal, 8)
    )
    valor_comissao_cooperativa = format_currency_br(
        FinanceiroAgro.calcular_total_comissao(area_real_decimal, 10)
    )

    return {
        "contrato_agro_id": str(contrato.id),
        "banco_agro_id": "",
        "cliente_nome": (orcamento.cliente_nome or contrato.contratante_nome or "").strip(),
        "cultura": ((contrato.culturas_formatadas or getattr(orcamento, "culturas_formatadas", "")) or "").strip(),
        "data_elaboracao_contrato": contrato.data_assinatura.isoformat() if contrato.data_assinatura else "",
        "data_servico_executado": latest_os.data_aplicacao.isoformat() if latest_os and latest_os.data_aplicacao else "",
        "data_vencimento": data_vencimento.isoformat() if data_vencimento else "",
        "data_recebimento": "",
        "area_mapeamento_ha": area_mapeamento,
        "valor_mapeamento_ha": format_currency_br(contrato.valor_mapeamento_ha),
        "total_mapeamento": total_mapeamento,
        "area_pulverizacao_ha": area_pulverizacao,
        "area_pulverizada_real_ha": area_real,
        "valor_pulverizacao_ha": format_currency_br(
            (contrato.valor_pulverizacao_ha or 0) + (contrato.valor_pulverizacao_adicional_ha or 0)
        ),
        "total_pulverizacao": total_pulverizacao,
        "valor_total_contrato": format_currency_br(contrato.valor_total),
        "comissao_por_ha": format_currency_br(8),
        "valor_comissao": valor_comissao,
        "comissao_cooperativa_por_ha": format_currency_br(10),
        "valor_comissao_cooperativa": valor_comissao_cooperativa,
        "forma_recebimento": "",
        "status": FinanceiroAgro.STATUS_PENDENTE,
        "observacoes": "",
    }


def serialize_financeiro_agro_form(lancamento: FinanceiroAgro) -> dict:
    return {
        "contrato_agro_id": str(lancamento.contrato_agro_id or ""),
        "banco_agro_id": str(lancamento.banco_agro_id or ""),
        "cliente_nome": lancamento.cliente_nome or "",
        "cultura": lancamento.cultura or "",
        "data_elaboracao_contrato": (
            lancamento.data_elaboracao_contrato.isoformat() if lancamento.data_elaboracao_contrato else ""
        ),
        "data_servico_executado": (
            lancamento.data_servico_executado.isoformat() if lancamento.data_servico_executado else ""
        ),
        "data_vencimento": lancamento.data_vencimento.isoformat() if lancamento.data_vencimento else "",
        "data_recebimento": lancamento.data_recebimento.isoformat() if lancamento.data_recebimento else "",
        "area_mapeamento_ha": format_currency_br(lancamento.area_mapeamento_ha).replace("R$ ", ""),
        "valor_mapeamento_ha": format_currency_br(lancamento.valor_mapeamento_ha),
        "total_mapeamento": format_currency_br(lancamento.total_mapeamento),
        "area_pulverizacao_ha": format_currency_br(lancamento.area_pulverizacao_ha).replace("R$ ", ""),
        "area_pulverizada_real_ha": format_currency_br(lancamento.area_pulverizada_real_ha).replace("R$ ", ""),
        "valor_pulverizacao_ha": format_currency_br(lancamento.valor_pulverizacao_ha),
        "total_pulverizacao": format_currency_br(lancamento.total_pulverizacao),
        "valor_total_contrato": format_currency_br(lancamento.valor_total_contrato),
        "comissao_por_ha": format_currency_br(lancamento.comissao_por_ha),
        "valor_comissao": format_currency_br(lancamento.valor_comissao),
        "comissao_cooperativa_por_ha": format_currency_br(lancamento.comissao_cooperativa_por_ha),
        "valor_comissao_cooperativa": format_currency_br(lancamento.valor_comissao_cooperativa),
        "forma_recebimento": lancamento.forma_recebimento or "",
        "status": lancamento.status or FinanceiroAgro.STATUS_PENDENTE,
        "observacoes": lancamento.observacoes or "",
    }


def serialize_banco_agro_form(banco: BancoAgro) -> dict:
    return {
        "nome": banco.nome or "",
        "banco_nome": banco.banco_nome or "",
        "agencia": banco.agencia or "",
        "conta": banco.conta or "",
        "tipo_conta": banco.tipo_conta or BancoAgro.TIPO_CORRENTE,
        "saldo_inicial": format_currency_br(banco.saldo_inicial),
        "ativo": "SIM" if banco.ativo else "NAO",
        "observacoes": banco.observacoes or "",
    }


def get_orcamento_attachment_folder() -> str:
    folder = os.path.join(get_upload_folder(), "agro", "orcamentos")
    os.makedirs(folder, exist_ok=True)
    return folder


def get_os_agro_attachment_folder() -> str:
    folder = os.path.join(get_upload_folder(), "agro", "os")
    os.makedirs(folder, exist_ok=True)
    return folder


def save_orcamento_attachment(orcamento: OrcamentoAgro, uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None

    original_filename = secure_filename(uploaded_file.filename)
    if "." not in original_filename or original_filename.rsplit(".", 1)[1].lower() != "pdf":
        raise ValueError("O anexo do orçamento deve ser um arquivo PDF.")

    folder = get_orcamento_attachment_folder()
    stored_filename = f"orcamento_agro_{orcamento.id}_{uuid.uuid4().hex}.pdf"
    absolute_path = os.path.join(folder, stored_filename)

    uploaded_file.save(absolute_path)

    if orcamento.anexo_path:
        remove_orcamento_attachment(orcamento, commit=False)

    orcamento.anexo_path = os.path.join("agro", "orcamentos", stored_filename).replace("\\", "/")
    orcamento.anexo_nome = original_filename
    return original_filename


def remove_orcamento_attachment(orcamento: OrcamentoAgro, *, commit: bool = False):
    relative_path = (orcamento.anexo_path or "").strip()
    if relative_path:
        absolute_path = os.path.join(get_upload_folder(), relative_path.replace("/", os.sep))
        if os.path.exists(absolute_path):
            try:
                os.remove(absolute_path)
            except OSError:
                current_app.logger.warning("Falha ao remover anexo do orcamento agro %s", orcamento.id)

    orcamento.anexo_path = None
    orcamento.anexo_nome = None

    if commit:
        from app.extensions import db

        db.session.commit()


def resolve_orcamento_attachment(orcamento: OrcamentoAgro):
    relative_path = (orcamento.anexo_path or "").strip()
    if not relative_path:
        raise FileNotFoundError("Orçamento sem anexo.")

    upload_folder = get_upload_folder()
    absolute_path = os.path.join(upload_folder, relative_path.replace("/", os.sep))
    if not os.path.exists(absolute_path):
        raise FileNotFoundError("Arquivo não encontrado.")

    return upload_folder, relative_path.replace("\\", "/"), orcamento.anexo_nome or os.path.basename(relative_path)


def agro_bool_label(value: bool) -> str:
    return "Sim" if value else "Não"


def now_brazil_label() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")
