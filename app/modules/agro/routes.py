import os
import math
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import abort, flash, redirect, render_template, request, send_file, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import (
    ClienteAgro,
    ContratoAgro,
    EquipamentoAgro,
    EquipeAgro,
    FinanceiroAgro,
    OrcamentoAgro,
    OrdemServicoAgro,
    PilotoAgro,
    Usuario,
)
from app.modules.agro.exporters import (
    build_contrato_agro_pdf,
    build_orcamento_agro_pdf,
    build_ordem_servico_agro_pdf,
    merge_orcamento_agro_with_attachment,
)
from app.modules.agro.service import (
    agro_bool_label,
    build_contrato_agro_defaults,
    build_contratos_agro_query,
    build_contratos_agro_aprovados_query,
    build_clientes_agro_query,
    build_endereco_agro,
    build_financeiro_agro_defaults,
    build_financeiro_agro_query,
    build_ordens_servico_agro_query,
    build_orcamentos_agro_query,
    can_access_agro_panel,
    can_edit_agro_panel,
    get_os_agro_attachment_folder,
    get_agro_dashboard_context,
    remove_orcamento_attachment,
    resolve_orcamento_attachment,
    save_orcamento_attachment,
    serialize_contrato_agro_form,
    serialize_cliente_agro,
    serialize_financeiro_agro_form,
    update_orcamento_snapshot_from_cliente,
)
from app.shared.access import apply_prefeitura_scope
from app.shared.formatters import format_cep, format_currency_br, format_documento, format_phone_br, only_digits, parse_currency_br
from app.shared.validators import validate_documento


AGRO_SERVICO_OPTIONS = (
    OrcamentoAgro.SERVICO_MAPEAMENTO,
    OrcamentoAgro.SERVICO_MAPEAMENTO_PULVERIZACAO,
    OrcamentoAgro.SERVICO_PULVERIZACAO,
)

AGRO_CONTRATO_STATUS_OPTIONS = ContratoAgro.STATUS_OPTIONS
AGRO_OS_STATUS_OPTIONS = OrdemServicoAgro.STATUS_OPTIONS
AGRO_FINANCEIRO_STATUS_OPTIONS = FinanceiroAgro.STATUS_OPTIONS
AGRO_OS_MAP_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def _redirect_back_to_agro(default_endpoint: str, **values):
    return redirect(request.referrer or url_for(default_endpoint, **values))


def _require_agro_access():
    if not can_access_agro_panel(current_user):
        abort(403)


def _require_agro_edit():
    if not can_edit_agro_panel(current_user):
        abort(403)


def _require_agro_admin():
    if getattr(current_user, "tipo_usuario", None) != "admin":
        abort(403)


def _require_piloto_agro():
    if getattr(current_user, "tipo_usuario", None) != "piloto_agro":
        abort(403)


def _get_cliente_agro_or_404(cliente_id: int):
    query = apply_prefeitura_scope(ClienteAgro.query, current_user, ClienteAgro.prefeitura_id)
    return query.filter(ClienteAgro.id == cliente_id).first_or_404()


def _get_cliente_agro(cliente_id: int | None):
    if not cliente_id:
        return None
    query = apply_prefeitura_scope(ClienteAgro.query, current_user, ClienteAgro.prefeitura_id)
    return query.filter(ClienteAgro.id == cliente_id).first()


def _get_orcamento_agro_or_404(orcamento_id: int):
    query = apply_prefeitura_scope(OrcamentoAgro.query, current_user, OrcamentoAgro.prefeitura_id)
    return query.filter(OrcamentoAgro.id == orcamento_id).first_or_404()


def _get_contrato_agro_or_404(contrato_id: int):
    query = apply_prefeitura_scope(ContratoAgro.query, current_user, ContratoAgro.prefeitura_id)
    return query.filter(ContratoAgro.id == contrato_id).first_or_404()


def _get_equipe_agro_or_404(equipe_id: int):
    query = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id)
    return query.filter(EquipeAgro.id == equipe_id).first_or_404()


def _build_agro_equipes_ativas():
    return (
        apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id)
        .filter(EquipeAgro.ativa.is_(True))
        .order_by(EquipeAgro.nome.asc(), EquipeAgro.id.asc())
        .all()
    )


def _get_piloto_agro_or_404(piloto_id: int):
    query = apply_prefeitura_scope(PilotoAgro.query, current_user, PilotoAgro.prefeitura_id)
    return query.filter(PilotoAgro.id == piloto_id).first_or_404()


def _get_equipamento_agro_or_404(equipamento_id: int):
    query = apply_prefeitura_scope(EquipamentoAgro.query, current_user, EquipamentoAgro.prefeitura_id)
    return query.filter(EquipamentoAgro.id == equipamento_id).first_or_404()


def _get_os_agro_or_404(os_id: int):
    query = apply_prefeitura_scope(OrdemServicoAgro.query, current_user, OrdemServicoAgro.prefeitura_id)
    return query.filter(OrdemServicoAgro.id == os_id).first_or_404()


def _get_financeiro_agro_or_404(lancamento_id: int):
    query = apply_prefeitura_scope(FinanceiroAgro.query, current_user, FinanceiroAgro.prefeitura_id)
    return query.filter(FinanceiroAgro.id == lancamento_id).first_or_404()


def _current_user_display_name():
    for value in (
        getattr(current_user, "nome_uvis", None),
        getattr(current_user, "equipe_uvis_nome", None),
        getattr(current_user, "login", None),
    ):
        text = (value or "").strip()
        if text:
            return text
    return "Nao informado"


def _get_logged_piloto_agro():
    return getattr(current_user, "piloto_agro", None)


def _build_latest_os_by_contrato(contratos):
    latest_os = {}
    for contrato in contratos:
        if contrato.ordens_servico:
            latest_os[contrato.id] = max(
                contrato.ordens_servico,
                key=lambda item: (item.criado_em or datetime.min, item.id),
            )
    return latest_os


def _build_os_agro_form_options(*, piloto_logado=None):
    if piloto_logado is not None:
        equipe = piloto_logado.equipe
        equipes = [equipe] if equipe is not None else []
        pilotos = [piloto_logado]
        if equipe is None:
            return equipes, pilotos, []

        equipamentos = (
            apply_prefeitura_scope(EquipamentoAgro.query, current_user, EquipamentoAgro.prefeitura_id)
            .filter(EquipamentoAgro.equipe_agro_id == equipe.id)
            .order_by(EquipamentoAgro.identificacao.asc(), EquipamentoAgro.id.asc())
            .all()
        )
        return equipes, pilotos, equipamentos

    equipes = _build_agro_equipes_ativas()
    pilotos = (
        apply_prefeitura_scope(PilotoAgro.query, current_user, PilotoAgro.prefeitura_id)
        .filter(PilotoAgro.ativo.is_(True))
        .order_by(PilotoAgro.nome.asc())
        .all()
    )
    equipamentos = (
        apply_prefeitura_scope(EquipamentoAgro.query, current_user, EquipamentoAgro.prefeitura_id)
        .order_by(EquipamentoAgro.identificacao.asc(), EquipamentoAgro.id.asc())
        .all()
    )
    return equipes, pilotos, equipamentos


def _equipamento_agro_pode_ser_drone(equipamento):
    if equipamento is None:
        return False

    tipo = (equipamento.tipo or "").strip().lower()
    funcao = (equipamento.funcao_operacional or "").strip().lower()
    return "drone" in tipo or funcao in {"pulverizacao", "mapeamento", "apoio"}


def _build_orcamento_agro_drone_options(*, funcao_operacional=None):
    equipamentos = (
        apply_prefeitura_scope(EquipamentoAgro.query, current_user, EquipamentoAgro.prefeitura_id)
        .order_by(EquipamentoAgro.identificacao.asc(), EquipamentoAgro.id.asc())
        .all()
    )
    drones = [item for item in equipamentos if _equipamento_agro_pode_ser_drone(item)]
    if funcao_operacional:
        filtro = funcao_operacional.strip().lower()
        drones = [
            item for item in drones
            if (item.funcao_operacional or "").strip().lower() == filtro
        ]
    return drones


def _build_orcamento_agro_form_context(
    *,
    modo,
    form,
    errors,
    clientes,
    drones_agro,
    drones_mapeamento_agro,
    orcamento=None,
):
    return {
        "modo": modo,
        "form": form,
        "errors": errors,
        "clientes": clientes,
        "servico_options": AGRO_SERVICO_OPTIONS,
        "drones_agro": drones_agro,
        "drones_mapeamento_agro": drones_mapeamento_agro,
        "drones_agro_meta": {item.id: _build_equipamento_agro_meta(item) for item in drones_agro},
        "drones_mapeamento_agro_meta": {item.id: _build_equipamento_agro_meta(item) for item in drones_mapeamento_agro},
        "orcamento": orcamento,
    }


def _build_os_agro_form_context(
    *,
    modo,
    contrato,
    form,
    errors,
    equipes,
    pilotos,
    equipamentos,
    ordem_servico=None,
    pilot_form_mode=False,
    piloto_logado=None,
):
    return {
        "modo": modo,
        "contrato": contrato,
        "ordem_servico": ordem_servico,
        "form": form,
        "errors": errors,
        "equipes": equipes,
        "pilotos": pilotos,
        "equipamentos": equipamentos,
        "equipamentos_meta": {item.id: _build_equipamento_agro_meta(item) for item in equipamentos},
        "status_options": AGRO_OS_STATUS_OPTIONS,
        "pilot_form_mode": pilot_form_mode,
        "piloto_logado": piloto_logado,
    }


def _build_financeiro_agro_form_context(*, modo, form, errors, contratos, lancamento=None):
    contratos_defaults = {str(contrato.id): build_financeiro_agro_defaults(contrato) for contrato in contratos}
    return {
        "modo": modo,
        "form": form,
        "errors": errors,
        "contratos": contratos,
        "contratos_defaults": contratos_defaults,
        "status_options": AGRO_FINANCEIRO_STATUS_OPTIONS,
        "lancamento": lancamento,
    }


def _normalize_cliente_form(form_source):
    return {
        "nome": (form_source.get("nome") or "").strip(),
        "documento": (form_source.get("documento") or "").strip(),
        "cep": format_cep(form_source.get("cep") or ""),
        "logradouro": (form_source.get("logradouro") or "").strip(),
        "numero": (form_source.get("numero") or "").strip(),
        "complemento": (form_source.get("complemento") or "").strip(),
        "bairro": (form_source.get("bairro") or "").strip(),
        "cidade": (form_source.get("cidade") or "").strip(),
        "uf": (form_source.get("uf") or "").strip().upper(),
    }


def _normalize_financeiro_agro_form(form_source):
    return {
        "contrato_agro_id": (form_source.get("contrato_agro_id") or "").strip(),
        "cliente_nome": (form_source.get("cliente_nome") or "").strip(),
        "cultura": (form_source.get("cultura") or "").strip(),
        "data_elaboracao_contrato": (form_source.get("data_elaboracao_contrato") or "").strip(),
        "data_servico_executado": (form_source.get("data_servico_executado") or "").strip(),
        "data_vencimento": (form_source.get("data_vencimento") or "").strip(),
        "data_recebimento": (form_source.get("data_recebimento") or "").strip(),
        "area_mapeamento_ha": (form_source.get("area_mapeamento_ha") or "").strip(),
        "valor_mapeamento_ha": (form_source.get("valor_mapeamento_ha") or "").strip(),
        "total_mapeamento": (form_source.get("total_mapeamento") or "").strip(),
        "area_pulverizacao_ha": (form_source.get("area_pulverizacao_ha") or "").strip(),
        "area_pulverizada_real_ha": (form_source.get("area_pulverizada_real_ha") or "").strip(),
        "valor_pulverizacao_ha": (form_source.get("valor_pulverizacao_ha") or "").strip(),
        "total_pulverizacao": (form_source.get("total_pulverizacao") or "").strip(),
        "valor_total_contrato": (form_source.get("valor_total_contrato") or "").strip(),
        "comissao_por_ha": (form_source.get("comissao_por_ha") or "").strip(),
        "valor_comissao": (form_source.get("valor_comissao") or "").strip(),
        "comissao_cooperativa_por_ha": (form_source.get("comissao_cooperativa_por_ha") or "").strip(),
        "valor_comissao_cooperativa": (form_source.get("valor_comissao_cooperativa") or "").strip(),
        "forma_recebimento": (form_source.get("forma_recebimento") or "").strip(),
        "status": (form_source.get("status") or FinanceiroAgro.STATUS_PENDENTE).strip().upper(),
        "observacoes": (form_source.get("observacoes") or "").strip(),
    }


def _validate_cliente_agro_form(form, *, cliente_atual=None):
    errors = {}

    if not form["nome"]:
        errors["nome"] = "Informe o nome do cliente."

    if not form["documento"]:
        errors["documento"] = "Informe o documento do cliente."

    doc_ok = False
    doc_digits = ""
    doc_fmt = ""
    if form["documento"]:
        doc_ok, _doc_tipo, doc_digits, doc_fmt, doc_error = validate_documento(form["documento"])
        if not doc_ok:
            errors["documento"] = doc_error

    cep_digits = only_digits(form["cep"])
    if len(cep_digits) != 8:
        errors["cep"] = "Informe um CEP válido com 8 dígitos."

    for field, label in (
        ("logradouro", "logradouro"),
        ("numero", "numero"),
        ("bairro", "bairro"),
        ("cidade", "cidade"),
        ("uf", "UF"),
    ):
        if not form[field]:
            errors[field] = f"Informe {label}."

    if form["uf"] and len(form["uf"]) != 2:
        errors["uf"] = "UF deve ter 2 letras."

    if doc_ok:
        query = ClienteAgro.query.filter(ClienteAgro.documento == doc_digits)
        if cliente_atual is not None:
            query = query.filter(ClienteAgro.id != cliente_atual.id)
        query = apply_prefeitura_scope(query, current_user, ClienteAgro.prefeitura_id)
        if query.first():
            errors["documento"] = "Já existe um cliente agro com esse documento."

    return errors, doc_digits, doc_fmt, cep_digits


def _normalize_orcamento_form(form_source):
    return {
        "cliente_agro_id": (form_source.get("cliente_agro_id") or "").strip(),
        "cliente_nome": (form_source.get("cliente_nome") or "").strip(),
        "cliente_documento": (form_source.get("cliente_documento") or "").strip(),
        "elaborado_por_nome": (form_source.get("elaborado_por_nome") or "").strip(),
        "nome_fazenda": (form_source.get("nome_fazenda") or "").strip(),
        "servico": (form_source.get("servico") or OrcamentoAgro.SERVICO_MAPEAMENTO).strip(),
        "mapeamento": (form_source.get("mapeamento") or "NAO").strip().upper(),
        "drone_agro_id": (form_source.get("drone_agro_id") or "").strip(),
        "drone_mapeamento_agro_id": (form_source.get("drone_mapeamento_agro_id") or "").strip(),
        "possui_produto_aplicado": (form_source.get("possui_produto_aplicado") or "NAO").strip().upper(),
        "produto_aplicado_receituario": (form_source.get("produto_aplicado_receituario") or "").strip(),
        "inicio_aplicacao_prevista": (form_source.get("inicio_aplicacao_prevista") or "").strip(),
        "fim_aplicacao_prevista": (form_source.get("fim_aplicacao_prevista") or "").strip(),
        "estimativa_aplicacao_dias": (form_source.get("estimativa_aplicacao_dias") or "").strip(),
        "risco_operacional": (form_source.get("risco_operacional") or "").strip(),
        "cultura": (form_source.get("cultura") or "").strip(),
        "cultura_alternativa": (form_source.get("cultura_alternativa") or "").strip(),
        "protocolo": (form_source.get("protocolo") or "").strip(),
        "area_ha": (form_source.get("area_ha") or "").strip(),
        "preco_mapeamento": (form_source.get("preco_mapeamento") or "").strip(),
        "preco_pulverizacao": (form_source.get("preco_pulverizacao") or "").strip(),
        "preco_pulverizacao_adicional": (form_source.get("preco_pulverizacao_adicional") or "").strip(),
        "valor_total_calculado": (form_source.get("valor_total_calculado") or "").strip(),
        "cep": format_cep(form_source.get("cep") or ""),
        "logradouro": (form_source.get("logradouro") or "").strip(),
        "numero": (form_source.get("numero") or "").strip(),
        "complemento": (form_source.get("complemento") or "").strip(),
        "bairro": (form_source.get("bairro") or "").strip(),
        "cidade": (form_source.get("cidade") or "").strip(),
        "uf": (form_source.get("uf") or "").strip().upper(),
    }


def _normalize_bool_form(value, default=True):
    raw = (value or "").strip().upper()
    if not raw:
        return default
    return raw in {"1", "SIM", "TRUE", "ATIVO"}


def _normalize_optional_int(value):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_area_contratada_decimal(value):
    text = str(value or "").strip().lower()
    if not text:
        return None

    normalized = text.replace("ha", "").replace("hectares", "").replace("hectare", "").strip()
    normalized = "".join(ch for ch in normalized if ch.isdigit() or ch in ",.")
    if not normalized:
        return None

    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")

    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None


def _parse_decimal_input(value):
    text = str(value or "").strip().lower()
    if not text:
        return None

    normalized = "".join(ch for ch in text if ch.isdigit() or ch in ",.")
    if not normalized:
        return None

    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")

    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None


def _format_decimal_br_value(value):
    if value is None:
        return ""
    return f"{Decimal(value):.2f}".replace(".", ",")


def _parse_iso_date(value):
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _calculate_application_days(start_date, end_date):
    if not start_date or not end_date or end_date < start_date:
        return None
    return (end_date - start_date).days + 1


def _resolve_financeiro_agro_status(status, data_vencimento, data_recebimento):
    if status == FinanceiroAgro.STATUS_CANCELADO:
        return FinanceiroAgro.STATUS_CANCELADO
    if data_recebimento:
        return FinanceiroAgro.STATUS_RECEBIDO
    if data_vencimento and data_vencimento < datetime.now().date():
        return FinanceiroAgro.STATUS_VENCIDO
    return FinanceiroAgro.STATUS_PENDENTE


def _build_financeiro_agro_summary(lancamentos):
    total_receber = Decimal("0")
    total_comissoes = Decimal("0")
    total_liquido = Decimal("0")
    total_recebido = Decimal("0")

    for item in lancamentos:
        total_receber += FinanceiroAgro._decimal_or_zero(item.valor_total_contrato)
        total_comissoes += FinanceiroAgro._decimal_or_zero(item.total_comissoes)
        total_liquido += FinanceiroAgro._decimal_or_zero(item.valor_liquido_previsto)
        if item.status == FinanceiroAgro.STATUS_RECEBIDO:
            total_recebido += FinanceiroAgro._decimal_or_zero(item.valor_total_contrato)

    return {
        "total_receber": total_receber,
        "total_comissoes": total_comissoes,
        "total_liquido": total_liquido,
        "total_recebido": total_recebido,
    }


def _validate_financeiro_agro_form(form, contratos):
    errors = {}
    contrato = None
    ordem_servico = None

    contrato_id = _normalize_optional_int(form["contrato_agro_id"])
    if contrato_id is None:
        errors["contrato_agro_id"] = "Selecione um contrato agro."
    else:
        contrato = next((item for item in contratos if item.id == contrato_id), None)
        if contrato is None:
            errors["contrato_agro_id"] = "O contrato selecionado nao foi encontrado."

    if not form["cliente_nome"]:
        errors["cliente_nome"] = "Informe o nome do cliente."

    data_elaboracao_contrato = _parse_iso_date(form["data_elaboracao_contrato"])
    if form["data_elaboracao_contrato"] and data_elaboracao_contrato is None:
        errors["data_elaboracao_contrato"] = "Informe uma data valida."

    data_servico_executado = _parse_iso_date(form["data_servico_executado"])
    if form["data_servico_executado"] and data_servico_executado is None:
        errors["data_servico_executado"] = "Informe uma data valida."

    data_vencimento = _parse_iso_date(form["data_vencimento"])
    if not form["data_vencimento"]:
        errors["data_vencimento"] = "Informe a data de vencimento."
    elif data_vencimento is None:
        errors["data_vencimento"] = "Informe uma data de vencimento valida."

    data_recebimento = _parse_iso_date(form["data_recebimento"])
    if form["data_recebimento"] and data_recebimento is None:
        errors["data_recebimento"] = "Informe uma data valida."

    area_mapeamento_ha = _parse_decimal_input(form["area_mapeamento_ha"]) or Decimal("0")
    valor_mapeamento_ha = parse_currency_br(form["valor_mapeamento_ha"]) or Decimal("0")
    total_mapeamento = parse_currency_br(form["total_mapeamento"])
    if form["total_mapeamento"] and total_mapeamento is None:
        errors["total_mapeamento"] = "Informe um valor monetario valido."
    if total_mapeamento is None:
        total_mapeamento = FinanceiroAgro.calcular_total_item(area_mapeamento_ha, valor_mapeamento_ha)

    area_pulverizacao_ha = _parse_decimal_input(form["area_pulverizacao_ha"]) or Decimal("0")
    area_pulverizada_real_ha = _parse_decimal_input(form["area_pulverizada_real_ha"]) or area_pulverizacao_ha
    valor_pulverizacao_ha = parse_currency_br(form["valor_pulverizacao_ha"]) or Decimal("0")
    total_pulverizacao = parse_currency_br(form["total_pulverizacao"])
    if form["total_pulverizacao"] and total_pulverizacao is None:
        errors["total_pulverizacao"] = "Informe um valor monetario valido."
    if total_pulverizacao is None:
        total_pulverizacao = FinanceiroAgro.calcular_total_item(area_pulverizada_real_ha, valor_pulverizacao_ha)

    valor_total_contrato = parse_currency_br(form["valor_total_contrato"])
    if form["valor_total_contrato"] and valor_total_contrato is None:
        errors["valor_total_contrato"] = "Informe um valor monetario valido."
    if valor_total_contrato is None:
        valor_total_contrato = (total_mapeamento or Decimal("0")) + (total_pulverizacao or Decimal("0"))

    comissao_por_ha = parse_currency_br(form["comissao_por_ha"]) or Decimal("0")
    valor_comissao = parse_currency_br(form["valor_comissao"])
    if form["valor_comissao"] and valor_comissao is None:
        errors["valor_comissao"] = "Informe um valor monetario valido."
    if valor_comissao is None:
        valor_comissao = FinanceiroAgro.calcular_total_comissao(
            area_pulverizada_real_ha,
            comissao_por_ha,
        )

    comissao_cooperativa_por_ha = parse_currency_br(form["comissao_cooperativa_por_ha"]) or Decimal("0")
    valor_comissao_cooperativa = parse_currency_br(form["valor_comissao_cooperativa"])
    if form["valor_comissao_cooperativa"] and valor_comissao_cooperativa is None:
        errors["valor_comissao_cooperativa"] = "Informe um valor monetario valido."
    if valor_comissao_cooperativa is None:
        valor_comissao_cooperativa = FinanceiroAgro.calcular_total_comissao(
            area_pulverizada_real_ha,
            comissao_cooperativa_por_ha,
        )

    if form["status"] not in AGRO_FINANCEIRO_STATUS_OPTIONS:
        errors["status"] = "Selecione um status valido."

    numeric_fields = {
        "area_mapeamento_ha": area_mapeamento_ha,
        "valor_mapeamento_ha": valor_mapeamento_ha,
        "total_mapeamento": total_mapeamento,
        "area_pulverizacao_ha": area_pulverizacao_ha,
        "area_pulverizada_real_ha": area_pulverizada_real_ha,
        "valor_pulverizacao_ha": valor_pulverizacao_ha,
        "total_pulverizacao": total_pulverizacao,
        "valor_total_contrato": valor_total_contrato,
        "comissao_por_ha": comissao_por_ha,
        "valor_comissao": valor_comissao,
        "comissao_cooperativa_por_ha": comissao_cooperativa_por_ha,
        "valor_comissao_cooperativa": valor_comissao_cooperativa,
    }

    if contrato and contrato.ordens_servico:
        ordem_servico = max(
            contrato.ordens_servico,
            key=lambda item: (item.data_aplicacao or datetime.min.date(), item.id),
        )

    resolved_status = _resolve_financeiro_agro_status(form["status"], data_vencimento, data_recebimento)

    return (
        errors,
        contrato,
        ordem_servico,
        data_elaboracao_contrato,
        data_servico_executado,
        data_vencimento,
        data_recebimento,
        numeric_fields,
        resolved_status,
    )


def _sync_financeiro_agro_form_numbers(form, numeric_fields, status):
    form["area_mapeamento_ha"] = _format_decimal_br_value(numeric_fields["area_mapeamento_ha"])
    form["valor_mapeamento_ha"] = format_currency_br(numeric_fields["valor_mapeamento_ha"])
    form["total_mapeamento"] = format_currency_br(numeric_fields["total_mapeamento"])
    form["area_pulverizacao_ha"] = _format_decimal_br_value(numeric_fields["area_pulverizacao_ha"])
    form["area_pulverizada_real_ha"] = _format_decimal_br_value(numeric_fields["area_pulverizada_real_ha"])
    form["valor_pulverizacao_ha"] = format_currency_br(numeric_fields["valor_pulverizacao_ha"])
    form["total_pulverizacao"] = format_currency_br(numeric_fields["total_pulverizacao"])
    form["valor_total_contrato"] = format_currency_br(numeric_fields["valor_total_contrato"])
    form["comissao_por_ha"] = format_currency_br(numeric_fields["comissao_por_ha"])
    form["valor_comissao"] = format_currency_br(numeric_fields["valor_comissao"])
    form["comissao_cooperativa_por_ha"] = format_currency_br(numeric_fields["comissao_cooperativa_por_ha"])
    form["valor_comissao_cooperativa"] = format_currency_br(numeric_fields["valor_comissao_cooperativa"])
    form["status"] = status


def _orcamento_servico_inclui_mapeamento(servico):
    return servico in (
        OrcamentoAgro.SERVICO_MAPEAMENTO,
        OrcamentoAgro.SERVICO_MAPEAMENTO_PULVERIZACAO,
    )


def _orcamento_servico_inclui_pulverizacao(servico):
    return True


def _orcamento_mapeamento_ativo(form):
    preco_mapeamento = parse_currency_br(form.get("preco_mapeamento"))
    return (
        (form.get("mapeamento") or "").strip().upper() == "SIM"
        or _orcamento_servico_inclui_mapeamento(form.get("servico"))
        or (preco_mapeamento is not None and preco_mapeamento > 0)
    )


def _orcamento_pulverizacao_adicional_ativa(form):
    preco_pulverizacao_adicional = parse_currency_br(form.get("preco_pulverizacao_adicional"))
    return bool((form.get("cultura_alternativa") or "").strip()) or (
        preco_pulverizacao_adicional is not None and preco_pulverizacao_adicional > 0
    )


def _apply_orcamento_agro_drone_snapshot(orcamento, equipamento):
    orcamento.drone_agro_id = getattr(equipamento, "id", None) if equipamento else None
    orcamento.drone_tipo = getattr(equipamento, "tipo", None) if equipamento else None
    orcamento.drone_identificacao = getattr(equipamento, "identificacao", None) if equipamento else None
    orcamento.drone_modelo = getattr(equipamento, "modelo", None) if equipamento else None
    orcamento.drone_funcao_operacional = getattr(equipamento, "funcao_operacional", None) if equipamento else None
    orcamento.drone_registro_anatel = getattr(equipamento, "registro_anatel", None) if equipamento else None
    orcamento.drone_registro_anac = getattr(equipamento, "registro_anac", None) if equipamento else None
    orcamento.drone_capacidade_tanque_l = getattr(equipamento, "capacidade_tanque_l", None) if equipamento else None


def _apply_orcamento_agro_drone_mapeamento_snapshot(orcamento, equipamento):
    orcamento.drone_mapeamento_agro_id = getattr(equipamento, "id", None) if equipamento else None
    orcamento.drone_mapeamento_identificacao = getattr(equipamento, "identificacao", None) if equipamento else None
    orcamento.drone_mapeamento_modelo = getattr(equipamento, "modelo", None) if equipamento else None
    orcamento.drone_mapeamento_funcao_operacional = getattr(equipamento, "funcao_operacional", None) if equipamento else None
    orcamento.drone_mapeamento_registro_anatel = getattr(equipamento, "registro_anatel", None) if equipamento else None
    orcamento.drone_mapeamento_registro_anac = getattr(equipamento, "registro_anac", None) if equipamento else None


def _normalize_equipe_form(form_source):
    return {
        "nome": (form_source.get("nome") or "").strip(),
        "descricao": (form_source.get("descricao") or "").strip(),
        "ativa": (form_source.get("ativa") or "SIM").strip().upper(),
    }


def _validate_equipe_agro_form(form, *, equipe_atual=None):
    errors = {}
    if not form["nome"]:
        errors["nome"] = "Informe o nome da equipe."

    if form["nome"]:
        query = apply_prefeitura_scope(
            EquipeAgro.query.filter(db.func.lower(EquipeAgro.nome) == form["nome"].lower()),
            current_user,
            EquipeAgro.prefeitura_id,
        )
        if equipe_atual is not None:
            query = query.filter(EquipeAgro.id != equipe_atual.id)
        if query.first():
            errors["nome"] = "Já existe uma equipe agro com esse nome."

    return errors, _normalize_bool_form(form["ativa"], default=True)


def _normalize_piloto_form(form_source):
    return {
        "nome": (form_source.get("nome") or "").strip(),
        "telefone": (form_source.get("telefone") or "").strip(),
        "equipe_agro_id": (form_source.get("equipe_agro_id") or "").strip(),
        "login": (form_source.get("login") or "").strip(),
        "senha": (form_source.get("senha") or "").strip(),
        "confirmar_senha": (form_source.get("confirmar_senha") or "").strip(),
        "ativo": (form_source.get("ativo") or "SIM").strip().upper(),
    }


def _validate_piloto_agro_form(form, equipes, *, piloto_atual=None):
    errors = {}
    equipe = None
    if not form["nome"]:
        errors["nome"] = "Informe o nome do piloto."

    telefone_digits = only_digits(form["telefone"])
    if form["telefone"] and len(telefone_digits) not in (10, 11):
        errors["telefone"] = "Informe um telefone com DDD e 10 ou 11 dígitos."

    equipe_id = _normalize_optional_int(form["equipe_agro_id"])
    if form["equipe_agro_id"] and equipe_id is None:
        errors["equipe_agro_id"] = "Selecione uma equipe válida."
    elif equipe_id:
        equipe = next((item for item in equipes if item.id == equipe_id), None)
        if not equipe:
            errors["equipe_agro_id"] = "A equipe selecionada não foi encontrada."

    if not form["login"]:
        errors["login"] = "Informe o login de acesso do piloto agro."
    elif len(form["login"]) < 4:
        errors["login"] = "O login deve ter pelo menos 4 caracteres."
    else:
        query = Usuario.query.filter(db.func.lower(Usuario.login) == form["login"].lower())
        if piloto_atual is not None and piloto_atual.usuario is not None:
            query = query.filter(Usuario.id != piloto_atual.usuario.id)
        if query.first():
            errors["login"] = "Este login já está em uso por outro usuário."

    if (piloto_atual is None or piloto_atual.usuario is None) and not form["senha"]:
        errors["senha"] = "Informe uma senha inicial para o piloto agro."
    elif form["senha"] and len(form["senha"]) < 6:
        errors["senha"] = "A senha deve ter pelo menos 6 caracteres."

    if form["senha"] or form["confirmar_senha"]:
        if form["senha"] != form["confirmar_senha"]:
            errors["confirmar_senha"] = "A confirmação de senha não confere."

    return errors, telefone_digits, equipe_id, equipe, _normalize_bool_form(form["ativo"], default=True)


def _normalize_equipamento_form(form_source):
    return {
        "tipo": (form_source.get("tipo") or "").strip(),
        "modelo": (form_source.get("modelo") or "").strip(),
        "identificacao": (form_source.get("identificacao") or "").strip(),
        "numero_serie": (form_source.get("numero_serie") or "").strip(),
        "status": (form_source.get("status") or "Ativo").strip(),
        "funcao_operacional": (form_source.get("funcao_operacional") or "").strip(),
        "registro_anatel": (form_source.get("registro_anatel") or "").strip(),
        "registro_anac": (form_source.get("registro_anac") or "").strip(),
        "capacidade_tanque_l": (form_source.get("capacidade_tanque_l") or "").strip(),
        "largura_faixa_m": (form_source.get("largura_faixa_m") or "").strip(),
        "altura_voo_padrao_m": (form_source.get("altura_voo_padrao_m") or "").strip(),
        "ponta_pulverizacao": (form_source.get("ponta_pulverizacao") or "").strip(),
        "equipe_agro_id": (form_source.get("equipe_agro_id") or "").strip(),
    }


def _validate_equipamento_agro_form(form, equipes, *, equipamento_atual=None):
    errors = {}
    equipe = None

    for field, label in (
        ("tipo", "o tipo do equipamento"),
        ("modelo", "o modelo"),
        ("identificacao", "a identificação"),
        ("status", "o status"),
    ):
        if not form[field]:
            errors[field] = f"Informe {label}."

    equipe_id = _normalize_optional_int(form["equipe_agro_id"])
    if form["equipe_agro_id"] and equipe_id is None:
        errors["equipe_agro_id"] = "Selecione uma equipe válida."
    elif equipe_id:
        equipe = next((item for item in equipes if item.id == equipe_id), None)
        if not equipe:
            errors["equipe_agro_id"] = "A equipe selecionada não foi encontrada."

    numero_serie = (form["numero_serie"] or "").strip() or None
    if numero_serie:
        query = EquipamentoAgro.query.filter(EquipamentoAgro.numero_serie == numero_serie)
        query = apply_prefeitura_scope(query, current_user, EquipamentoAgro.prefeitura_id)
        if equipamento_atual is not None:
            query = query.filter(EquipamentoAgro.id != equipamento_atual.id)
        if query.first():
            errors["numero_serie"] = "Já existe um equipamento agro com esse número de série."

    capacidade_tanque_l = _parse_decimal_input(form["capacidade_tanque_l"])
    largura_faixa_m = _parse_decimal_input(form["largura_faixa_m"])
    altura_voo_padrao_m = _parse_decimal_input(form["altura_voo_padrao_m"])

    if form["capacidade_tanque_l"] and capacidade_tanque_l is None:
        errors["capacidade_tanque_l"] = "Informe uma capacidade valida em litros."
    elif capacidade_tanque_l is not None and capacidade_tanque_l < 0:
        errors["capacidade_tanque_l"] = "A capacidade nao pode ser negativa."

    if form["largura_faixa_m"] and largura_faixa_m is None:
        errors["largura_faixa_m"] = "Informe uma largura de faixa valida."
    elif largura_faixa_m is not None and largura_faixa_m < 0:
        errors["largura_faixa_m"] = "A largura de faixa nao pode ser negativa."

    if form["altura_voo_padrao_m"] and altura_voo_padrao_m is None:
        errors["altura_voo_padrao_m"] = "Informe uma altura de voo valida."
    elif altura_voo_padrao_m is not None and altura_voo_padrao_m < 0:
        errors["altura_voo_padrao_m"] = "A altura de voo nao pode ser negativa."

    return errors, numero_serie, equipe_id, equipe, capacidade_tanque_l, largura_faixa_m, altura_voo_padrao_m


def _validate_orcamento_form_legacy(form):
    errors = {}
    cliente = None
    area_ha = _parse_decimal_input(form.get("area_ha"))
    preco_mapeamento = parse_currency_br(form.get("preco_mapeamento"))
    preco_pulverizacao = parse_currency_br(form.get("preco_pulverizacao"))
    mapeamento_ativo = _orcamento_mapeamento_ativo(form)
    pulverizacao_ativa = _orcamento_servico_inclui_pulverizacao(form.get("servico"))

    try:
        cliente_id = int(form["cliente_agro_id"])
    except (TypeError, ValueError):
        cliente_id = None

    if not cliente_id:
        errors["cliente_agro_id"] = "Selecione o cliente."
    else:
        cliente = _get_cliente_agro_or_404(cliente_id)

    if not form["nome_fazenda"]:
        errors["nome_fazenda"] = "Informe o nome da fazenda."

    if form["servico"] not in AGRO_SERVICO_OPTIONS:
        errors["servico"] = "Selecione um serviço válido."

    if not form["area_ha"]:
        errors["preco_base"] = "Informe o preço base do orçamento."
    elif preco_base is None:
        errors["preco_base"] = "Informe um valor monetário válido. Ex.: 1500,00"
    elif preco_base < 0:
        errors["preco_base"] = "O preço base não pode ser negativo."

    mapeamento_ativo = form["mapeamento"] == "SIM"

    if mapeamento_ativo:
        if not form["preco_mapeamento"]:
            errors["preco_mapeamento"] = "Informe o preço do mapeamento."
        elif preco_mapeamento is None:
            errors["preco_mapeamento"] = "Informe um valor monetário válido. Ex.: 1500,00"
        elif preco_mapeamento < 0:
            errors["preco_mapeamento"] = "O preço do mapeamento não pode ser negativo."
    elif preco_mapeamento is None:
        preco_mapeamento = 0

    if not form["preco_pulverizacao"]:
        errors["preco_pulverizacao"] = "Informe o preço da pulverização."
    elif preco_pulverizacao is None:
        errors["preco_pulverizacao"] = "Informe um valor monetário válido. Ex.: 1500,00"
    elif preco_pulverizacao < 0:
        errors["preco_pulverizacao"] = "O preço da pulverização não pode ser negativo."

    if len(form["cultura"]) > 100:
        errors["cultura"] = "Cultura deve ter no máximo 100 caracteres."

    cep_digits = only_digits(form["cep"])
    if len(cep_digits) != 8:
        errors["cep"] = "Informe um CEP válido com 8 dígitos."

    for field, label in (
        ("logradouro", "logradouro"),
        ("numero", "numero"),
        ("bairro", "bairro"),
        ("cidade", "cidade"),
        ("uf", "UF"),
    ):
        if not form[field]:
            errors[field] = f"Informe {label}."

    if form["uf"] and len(form["uf"]) != 2:
        errors["uf"] = "UF deve ter 2 letras."

    return errors, cliente, cep_digits, preco_base, preco_mapeamento, preco_pulverizacao


def _validate_orcamento_form(form):
    errors = {}
    cliente = None
    drone_agro = None
    drone_mapeamento_agro = None
    area_ha = _parse_decimal_input(form.get("area_ha"))
    preco_mapeamento = parse_currency_br(form.get("preco_mapeamento"))
    preco_pulverizacao = parse_currency_br(form.get("preco_pulverizacao"))
    preco_pulverizacao_adicional = parse_currency_br(form.get("preco_pulverizacao_adicional"))
    mapeamento_ativo = _orcamento_mapeamento_ativo(form)
    pulverizacao_ativa = _orcamento_servico_inclui_pulverizacao(form.get("servico"))
    pulverizacao_adicional_ativa = _orcamento_pulverizacao_adicional_ativa(form)
    cliente_documento_digits = ""
    possui_produto_aplicado = (form.get("possui_produto_aplicado") or "NAO") == "SIM"
    inicio_aplicacao_prevista = _parse_iso_date(form.get("inicio_aplicacao_prevista"))
    fim_aplicacao_prevista = _parse_iso_date(form.get("fim_aplicacao_prevista"))

    try:
        cliente_id = int(form["cliente_agro_id"])
    except (TypeError, ValueError):
        cliente_id = None

    if cliente_id:
        cliente = _get_cliente_agro(cliente_id)
        if cliente is None:
            errors["cliente_agro_id"] = "Selecione um cliente valido."

    drone_agro_id = _normalize_optional_int(form.get("drone_agro_id"))
    if form.get("drone_agro_id") and drone_agro_id is None:
        errors["drone_agro_id"] = "Selecione um drone valido."
    elif drone_agro_id:
        drone_query = apply_prefeitura_scope(
            EquipamentoAgro.query,
            current_user,
            EquipamentoAgro.prefeitura_id,
        )
        drone_agro = drone_query.filter(EquipamentoAgro.id == drone_agro_id).first()
        if drone_agro is None or not _equipamento_agro_pode_ser_drone(drone_agro):
            errors["drone_agro_id"] = "O drone selecionado nao foi encontrado no cadastro do Agro."
            drone_agro = None

    drone_mapeamento_agro_id = _normalize_optional_int(form.get("drone_mapeamento_agro_id"))
    if form.get("drone_mapeamento_agro_id") and drone_mapeamento_agro_id is None:
        errors["drone_mapeamento_agro_id"] = "Selecione um drone de mapeamento valido."
    elif drone_mapeamento_agro_id:
        drone_map_query = apply_prefeitura_scope(
            EquipamentoAgro.query,
            current_user,
            EquipamentoAgro.prefeitura_id,
        )
        drone_mapeamento_agro = drone_map_query.filter(EquipamentoAgro.id == drone_mapeamento_agro_id).first()
        funcao_mapeamento = (getattr(drone_mapeamento_agro, "funcao_operacional", None) or "").strip().lower()
        if drone_mapeamento_agro is None or funcao_mapeamento != "mapeamento":
            errors["drone_mapeamento_agro_id"] = "Selecione um drone com funcao operacional de mapeamento."
            drone_mapeamento_agro = None

    if not form["cliente_nome"]:
        errors["cliente_nome"] = "Informe o nome do cliente."

    if form["cliente_documento"]:
        doc_ok, _doc_tipo, cliente_documento_digits, _doc_fmt, doc_error = validate_documento(form["cliente_documento"])
        if not doc_ok:
            errors["cliente_documento"] = doc_error
    elif cliente is not None:
        cliente_documento_digits = cliente.documento or ""

    if not form["nome_fazenda"]:
        errors["nome_fazenda"] = "Informe o nome da fazenda."

    if form["servico"] not in AGRO_SERVICO_OPTIONS:
        errors["servico"] = "Selecione um servico valido."

    if mapeamento_ativo and not form.get("drone_mapeamento_agro_id"):
        errors["drone_mapeamento_agro_id"] = "Selecione o drone de mapeamento."

    if not form["area_ha"]:
        errors["area_ha"] = "Informe a area em hectares."
    elif area_ha is None:
        errors["area_ha"] = "Informe uma area valida. Ex.: 59,27"
    elif area_ha <= 0:
        errors["area_ha"] = "A area em hectares deve ser maior que zero."

    if mapeamento_ativo:
        if not form["preco_mapeamento"]:
            errors["preco_mapeamento"] = "Informe o preco do mapeamento por ha."
        elif preco_mapeamento is None:
            errors["preco_mapeamento"] = "Informe um valor monetario valido. Ex.: 1500,00"
        elif preco_mapeamento < 0:
            errors["preco_mapeamento"] = "O preco do mapeamento nao pode ser negativo."
    elif form["preco_mapeamento"] and preco_mapeamento is None:
        errors["preco_mapeamento"] = "Informe um valor monetario valido. Ex.: 1500,00"

    if preco_mapeamento is None or not mapeamento_ativo:
        preco_mapeamento = Decimal("0")

    if pulverizacao_ativa:
        if not form["preco_pulverizacao"]:
            errors["preco_pulverizacao"] = "Informe o preco da pulverizacao por ha."
        elif preco_pulverizacao is None:
            errors["preco_pulverizacao"] = "Informe um valor monetario valido. Ex.: 1500,00"
        elif preco_pulverizacao < 0:
            errors["preco_pulverizacao"] = "O preco da pulverizacao nao pode ser negativo."
    elif form["preco_pulverizacao"] and preco_pulverizacao is None:
        errors["preco_pulverizacao"] = "Informe um valor monetario valido. Ex.: 1500,00"

    if preco_pulverizacao is None or not pulverizacao_ativa:
        preco_pulverizacao = Decimal("0")

    if len(form["cultura_alternativa"]) > 100:
        errors["cultura_alternativa"] = "Cultura adicional deve ter no maximo 100 caracteres."

    if possui_produto_aplicado:
        if not form["produto_aplicado_receituario"]:
            errors["produto_aplicado_receituario"] = "Informe o produto aplicado ou o receituario agronomico."
    elif form["produto_aplicado_receituario"]:
        form["produto_aplicado_receituario"] = ""

    if not form["inicio_aplicacao_prevista"]:
        errors["inicio_aplicacao_prevista"] = "Informe o inicio da aplicacao."
    elif inicio_aplicacao_prevista is None:
        errors["inicio_aplicacao_prevista"] = "Informe uma data valida para o inicio da aplicacao."

    if not form["fim_aplicacao_prevista"]:
        errors["fim_aplicacao_prevista"] = "Informe o fim da aplicacao."
    elif fim_aplicacao_prevista is None:
        errors["fim_aplicacao_prevista"] = "Informe uma data valida para o fim da aplicacao."

    if (
        inicio_aplicacao_prevista is not None
        and fim_aplicacao_prevista is not None
        and fim_aplicacao_prevista < inicio_aplicacao_prevista
    ):
        errors["fim_aplicacao_prevista"] = "O fim da aplicacao nao pode ser anterior ao inicio."

    if form["cultura_alternativa"]:
        if not form["preco_pulverizacao_adicional"]:
            errors["preco_pulverizacao_adicional"] = "Informe o preco da pulverizacao adicional por ha."
        elif preco_pulverizacao_adicional is None:
            errors["preco_pulverizacao_adicional"] = "Informe um valor monetario valido. Ex.: 1500,00"
        elif preco_pulverizacao_adicional < 0:
            errors["preco_pulverizacao_adicional"] = "O preco da pulverizacao adicional nao pode ser negativo."
    elif form["preco_pulverizacao_adicional"]:
        if preco_pulverizacao_adicional is None:
            errors["preco_pulverizacao_adicional"] = "Informe um valor monetario valido. Ex.: 1500,00"
        elif preco_pulverizacao_adicional < 0:
            errors["preco_pulverizacao_adicional"] = "O preco da pulverizacao adicional nao pode ser negativo."
        else:
            errors["cultura_alternativa"] = "Informe a cultura adicional para usar a pulverizacao adicional."

    if preco_pulverizacao_adicional is None or not pulverizacao_adicional_ativa:
        preco_pulverizacao_adicional = Decimal("0")

    valor_total_calculado = OrcamentoAgro.calcular_valor_total(
        area_ha,
        preco_pulverizacao,
        preco_mapeamento,
        mapeamento_ativo=mapeamento_ativo,
        preco_pulverizacao_adicional=preco_pulverizacao_adicional,
        pulverizacao_adicional_ativa=pulverizacao_adicional_ativa,
    )

    if (
        area_ha is not None
        and area_ha > 0
        and "preco_mapeamento" not in errors
        and "preco_pulverizacao" not in errors
        and valor_total_calculado <= 0
    ):
        errors["valor_total_calculado"] = "Informe valores por hectare maiores que zero para calcular o orcamento."

    if len(form["cultura"]) > 100:
        errors["cultura"] = "Cultura deve ter no maximo 100 caracteres."

    cep_digits = only_digits(form["cep"])
    if len(cep_digits) != 8:
        errors["cep"] = "Informe um CEP valido com 8 digitos."

    for field, label in (
        ("logradouro", "logradouro"),
        ("numero", "numero"),
        ("bairro", "bairro"),
        ("cidade", "cidade"),
        ("uf", "UF"),
    ):
        if not form[field]:
            errors[field] = f"Informe {label}."

    if form["uf"] and len(form["uf"]) != 2:
        errors["uf"] = "UF deve ter 2 letras."

    return (
        errors,
        cliente,
        drone_agro,
        drone_mapeamento_agro,
        cliente_documento_digits,
        cep_digits,
        area_ha,
        valor_total_calculado,
        preco_mapeamento,
        preco_pulverizacao,
        preco_pulverizacao_adicional,
        mapeamento_ativo,
        possui_produto_aplicado,
        inicio_aplicacao_prevista,
        fim_aplicacao_prevista,
    )


def _normalize_contrato_form(form_source):
    status = (form_source.get("status") or ContratoAgro.STATUS_EM_ELABORACAO).strip().upper()
    if status not in AGRO_CONTRATO_STATUS_OPTIONS:
        status = ContratoAgro.STATUS_EM_ELABORACAO

    return {
        "contratante_nome": (form_source.get("contratante_nome") or "").strip(),
        "contratante_documento": (form_source.get("contratante_documento") or "").strip(),
        "contratante_rg": (form_source.get("contratante_rg") or "").strip(),
        "contratante_cep": format_cep(form_source.get("contratante_cep") or ""),
        "contratante_logradouro": (form_source.get("contratante_logradouro") or "").strip(),
        "contratante_numero": (form_source.get("contratante_numero") or "").strip(),
        "contratante_complemento": (form_source.get("contratante_complemento") or "").strip(),
        "contratante_bairro": (form_source.get("contratante_bairro") or "").strip(),
        "contratante_cidade": (form_source.get("contratante_cidade") or "").strip(),
        "contratante_uf": (form_source.get("contratante_uf") or "").strip().upper(),
        "propriedade_nome": (form_source.get("propriedade_nome") or "").strip(),
        "propriedade_cep": format_cep(form_source.get("propriedade_cep") or ""),
        "propriedade_logradouro": (form_source.get("propriedade_logradouro") or "").strip(),
        "propriedade_numero": (form_source.get("propriedade_numero") or "").strip(),
        "propriedade_complemento": (form_source.get("propriedade_complemento") or "").strip(),
        "propriedade_bairro": (form_source.get("propriedade_bairro") or "").strip(),
        "propriedade_cidade": (form_source.get("propriedade_cidade") or "").strip(),
        "propriedade_uf": (form_source.get("propriedade_uf") or "").strip().upper(),
        "descricao_servico": (form_source.get("descricao_servico") or "").strip(),
        "cultura": (form_source.get("cultura") or "").strip(),
        "cultura_alternativa": (form_source.get("cultura_alternativa") or "").strip(),
        "area_contratada": (form_source.get("area_contratada") or "").strip(),
        "valor_total": (form_source.get("valor_total") or "").strip(),
        "valor_mapeamento_ha": (form_source.get("valor_mapeamento_ha") or "").strip(),
        "valor_pulverizacao_ha": (form_source.get("valor_pulverizacao_ha") or "").strip(),
        "valor_pulverizacao_adicional_ha": (form_source.get("valor_pulverizacao_adicional_ha") or "").strip(),
        "prazo_inicio_dias": (form_source.get("prazo_inicio_dias") or "").strip(),
        "prazo_pagamento_dias": (form_source.get("prazo_pagamento_dias") or "").strip(),
        "cidade_assinatura": (form_source.get("cidade_assinatura") or "").strip(),
        "foro_cidade": (form_source.get("foro_cidade") or "").strip(),
        "data_assinatura": (form_source.get("data_assinatura") or "").strip(),
        "observacoes_adicionais": (form_source.get("observacoes_adicionais") or "").strip(),
        "status": status,
    }


def _validate_contrato_form(form):
    errors = {}

    for field, label in (
        ("contratante_nome", "o nome do contratante"),
        ("contratante_documento", "o CPF/CNPJ do contratante"),
        ("contratante_logradouro", "o logradouro do contratante"),
        ("contratante_numero", "o numero do contratante"),
        ("contratante_bairro", "o bairro do contratante"),
        ("contratante_cidade", "a cidade do contratante"),
        ("contratante_uf", "a UF do contratante"),
        ("propriedade_nome", "o nome da propriedade"),
        ("propriedade_logradouro", "o logradouro da propriedade"),
        ("propriedade_numero", "o numero da propriedade"),
        ("propriedade_bairro", "o bairro da propriedade"),
        ("propriedade_cidade", "a cidade da propriedade"),
        ("propriedade_uf", "a UF da propriedade"),
        ("descricao_servico", "a descricao do servico"),
        ("prazo_inicio_dias", "o prazo de inicio"),
        ("prazo_pagamento_dias", "o prazo de pagamento"),
        ("cidade_assinatura", "a cidade da assinatura"),
        ("foro_cidade", "a cidade do foro"),
        ("data_assinatura", "a data da assinatura"),
    ):
        if not form[field]:
            errors[field] = f"Informe {label}."

    doc_digits = ""
    if form["contratante_documento"]:
        doc_ok, _doc_tipo, doc_digits, _doc_fmt, doc_error = validate_documento(form["contratante_documento"])
        if not doc_ok:
            errors["contratante_documento"] = doc_error

    contratante_cep_digits = only_digits(form["contratante_cep"])
    if len(contratante_cep_digits) != 8:
        errors["contratante_cep"] = "Informe um CEP valido com 8 digitos para o contratante."

    propriedade_cep_digits = only_digits(form["propriedade_cep"])
    if len(propriedade_cep_digits) != 8:
        errors["propriedade_cep"] = "Informe um CEP valido com 8 digitos para a propriedade."

    if form["contratante_uf"] and len(form["contratante_uf"]) != 2:
        errors["contratante_uf"] = "UF do contratante deve ter 2 letras."

    if form["propriedade_uf"] and len(form["propriedade_uf"]) != 2:
        errors["propriedade_uf"] = "UF da propriedade deve ter 2 letras."

    if form["status"] not in AGRO_CONTRATO_STATUS_OPTIONS:
        errors["status"] = "Selecione um status valido para o contrato."

    area_contratada_decimal = _parse_area_contratada_decimal(form["area_contratada"])
    valor_total = parse_currency_br(form["valor_total"])
    valor_mapeamento_ha = parse_currency_br(form["valor_mapeamento_ha"]) if form["valor_mapeamento_ha"] else 0
    valor_pulverizacao_ha = parse_currency_br(form["valor_pulverizacao_ha"]) if form["valor_pulverizacao_ha"] else 0
    valor_pulverizacao_adicional_ha = (
        parse_currency_br(form["valor_pulverizacao_adicional_ha"]) if form["valor_pulverizacao_adicional_ha"] else 0
    )

    if form["area_contratada"] and area_contratada_decimal is None:
        errors["area_contratada"] = "Informe uma area contratada valida. Ex.: 59,27 ha"

    valores_por_ha = (
        (valor_mapeamento_ha or 0)
        + (valor_pulverizacao_ha or 0)
        + (valor_pulverizacao_adicional_ha or 0)
    )
    if valor_total is None and area_contratada_decimal is not None and valores_por_ha > 0:
        valor_total = area_contratada_decimal * valores_por_ha

    if form["valor_total"] and valor_total is None:
        errors["valor_total"] = "Informe um valor monetario valido. Ex.: 1500,00"
    elif not form["valor_total"] and valor_total is None:
        errors["valor_total"] = "Informe o valor total ou preencha area contratada e os valores por ha para calcular automaticamente."
    elif valor_total is not None and valor_total < 0:
        errors["valor_total"] = "O valor total nao pode ser negativo."

    if form["valor_mapeamento_ha"] and valor_mapeamento_ha is None:
        errors["valor_mapeamento_ha"] = "Informe um valor monetario valido. Ex.: 1500,00"
    elif valor_mapeamento_ha is not None and valor_mapeamento_ha < 0:
        errors["valor_mapeamento_ha"] = "O valor do mapeamento nao pode ser negativo."

    if form["valor_pulverizacao_ha"] and valor_pulverizacao_ha is None:
        errors["valor_pulverizacao_ha"] = "Informe um valor monetario valido. Ex.: 1500,00"
    elif valor_pulverizacao_ha is not None and valor_pulverizacao_ha < 0:
        errors["valor_pulverizacao_ha"] = "O valor da pulverizacao nao pode ser negativo."

    if len(form["cultura"]) > 100:
        errors["cultura"] = "Cultura deve ter no maximo 100 caracteres."

    if len(form["cultura_alternativa"]) > 100:
        errors["cultura_alternativa"] = "Cultura adicional deve ter no maximo 100 caracteres."

    if form["cultura_alternativa"]:
        if not form["valor_pulverizacao_adicional_ha"]:
            errors["valor_pulverizacao_adicional_ha"] = "Informe o valor da pulverizacao adicional por ha."
        elif valor_pulverizacao_adicional_ha is None:
            errors["valor_pulverizacao_adicional_ha"] = "Informe um valor monetario valido. Ex.: 1500,00"
        elif valor_pulverizacao_adicional_ha < 0:
            errors["valor_pulverizacao_adicional_ha"] = "O valor da pulverizacao adicional nao pode ser negativo."
    elif form["valor_pulverizacao_adicional_ha"]:
        if valor_pulverizacao_adicional_ha is None:
            errors["valor_pulverizacao_adicional_ha"] = "Informe um valor monetario valido. Ex.: 1500,00"
        elif valor_pulverizacao_adicional_ha < 0:
            errors["valor_pulverizacao_adicional_ha"] = "O valor da pulverizacao adicional nao pode ser negativo."
        else:
            errors["cultura_alternativa"] = "Informe a cultura adicional para usar a pulverizacao adicional."

    try:
        prazo_inicio_dias = int(form["prazo_inicio_dias"])
        if prazo_inicio_dias <= 0:
            raise ValueError
    except (TypeError, ValueError):
        prazo_inicio_dias = None
        errors["prazo_inicio_dias"] = "Informe um prazo de inicio valido em dias."

    try:
        prazo_pagamento_dias = int(form["prazo_pagamento_dias"])
        if prazo_pagamento_dias <= 0:
            raise ValueError
    except (TypeError, ValueError):
        prazo_pagamento_dias = None
        errors["prazo_pagamento_dias"] = "Informe um prazo de pagamento valido em dias."

    data_assinatura = None
    if form["data_assinatura"]:
        try:
            data_assinatura = datetime.strptime(form["data_assinatura"], "%Y-%m-%d").date()
        except ValueError:
            errors["data_assinatura"] = "Informe uma data de assinatura valida."

    return (
        errors,
        doc_digits,
        contratante_cep_digits,
        propriedade_cep_digits,
        valor_total,
        valor_mapeamento_ha or 0,
        valor_pulverizacao_ha or 0,
        valor_pulverizacao_adicional_ha or 0,
        prazo_inicio_dias,
        prazo_pagamento_dias,
        data_assinatura,
    )


def _normalize_contrato_template_form(form_source):
    status = (form_source.get("status") or ContratoAgro.STATUS_APROVADO).strip().upper()
    return {
        "status": status if status in AGRO_CONTRATO_STATUS_OPTIONS else ContratoAgro.STATUS_APROVADO,
        "equipe_agro_id": (form_source.get("equipe_agro_id") or "").strip(),
    }


def _validate_contrato_template_form(form, equipes):
    errors = {}
    equipe = None

    if form["status"] not in AGRO_CONTRATO_STATUS_OPTIONS:
        errors["status"] = "Selecione um status valido."

    equipe_id = _normalize_optional_int(form["equipe_agro_id"])
    if form["equipe_agro_id"] and equipe_id is None:
        errors["equipe_agro_id"] = "Selecione uma equipe valida."
    elif equipe_id:
        equipe = next((item for item in equipes if item.id == equipe_id), None)
        if not equipe:
            errors["equipe_agro_id"] = "A equipe selecionada nao foi encontrada."

    if form["status"] == ContratoAgro.STATUS_APROVADO and equipe_id is None:
        errors["equipe_agro_id"] = "Para manter o contrato aprovado, selecione a equipe responsavel."

    return errors, equipe_id, equipe


def _build_contrato_agro_draft(orcamento):
    cliente = orcamento.cliente
    return ContratoAgro(
        prefeitura_id=orcamento.prefeitura_id,
        orcamento=orcamento,
        contratante_nome=(cliente.nome if cliente else orcamento.cliente_nome) or "",
        contratante_documento=(cliente.documento if cliente else orcamento.cliente_documento) or "",
        contratante_rg="",
        contratante_cep=(cliente.cep if cliente else "") or "",
        contratante_logradouro=(cliente.logradouro if cliente else "") or "",
        contratante_numero=(cliente.numero if cliente else "") or "",
        contratante_complemento=(cliente.complemento if cliente else "") or None,
        contratante_bairro=(cliente.bairro if cliente else "") or "",
        contratante_cidade=(cliente.cidade if cliente else "") or "",
        contratante_uf=(cliente.uf if cliente else "") or "",
        propriedade_nome=orcamento.nome_fazenda or "",
        propriedade_cep=orcamento.cep or "",
        propriedade_logradouro=orcamento.logradouro or "",
        propriedade_numero=orcamento.numero or "",
        propriedade_complemento=orcamento.complemento or None,
        propriedade_bairro=orcamento.bairro or "",
        propriedade_cidade=orcamento.cidade or "",
        propriedade_uf=orcamento.uf or "",
        descricao_servico=(
            f"{orcamento.servico} na cultura de {orcamento.culturas_formatadas}"
            if orcamento.culturas_formatadas
            else (orcamento.servico or "Prestacao de servicos agro")
        ),
        cultura=orcamento.cultura or None,
        cultura_alternativa=orcamento.cultura_alternativa or None,
        area_contratada=orcamento.area_ha_formatada or None,
        valor_total=orcamento.valor_total_calculado or 0,
        valor_mapeamento_ha=orcamento.preco_mapeamento or 0,
        valor_pulverizacao_ha=orcamento.preco_pulverizacao or 0,
        valor_pulverizacao_adicional_ha=orcamento.preco_pulverizacao_adicional or 0,
        prazo_inicio_dias=10,
        prazo_pagamento_dias=10,
        cidade_assinatura="São Paulo",
        foro_cidade="São Paulo",
        data_assinatura=datetime.now().date(),
        observacoes_adicionais=None,
        status=ContratoAgro.STATUS_EM_ELABORACAO,
    )


def _build_os_agro_identificador():
    return f"AGRO-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def _build_os_agro_area_total_from_contrato(contrato):
    area_contratada = _parse_area_contratada_decimal(getattr(contrato, "area_contratada", None))
    return _format_decimal_br_value(area_contratada) if area_contratada is not None else ""


def _build_equipamento_agro_meta(equipamento):
    if equipamento is None:
        return {}

    return {
        "id": equipamento.id,
        "identificacao": equipamento.identificacao or "",
        "modelo": equipamento.modelo or "",
        "tipo": equipamento.tipo or "",
        "registro_anatel": equipamento.registro_anatel or "",
        "registro_anac": equipamento.registro_anac or "",
        "capacidade_tanque_l": str(equipamento.capacidade_tanque_l or ""),
        "largura_faixa_m": str(equipamento.largura_faixa_m or ""),
        "altura_voo_padrao_m": str(equipamento.altura_voo_padrao_m or ""),
        "ponta_pulverizacao": equipamento.ponta_pulverizacao or "",
        "funcao_operacional": equipamento.funcao_operacional or "",
    }


def _apply_os_agro_drone_snapshot(ordem_servico, equipamento, *, prefix):
    setattr(ordem_servico, f"{prefix}_identificacao", getattr(equipamento, "identificacao", None) if equipamento else None)
    setattr(ordem_servico, f"{prefix}_modelo", getattr(equipamento, "modelo", None) if equipamento else None)
    setattr(ordem_servico, f"{prefix}_tipo", getattr(equipamento, "tipo", None) if equipamento else None)
    setattr(ordem_servico, f"{prefix}_registro_anatel", getattr(equipamento, "registro_anatel", None) if equipamento else None)
    setattr(ordem_servico, f"{prefix}_registro_anac", getattr(equipamento, "registro_anac", None) if equipamento else None)


def _build_os_agro_defaults(contrato):
    orcamento = contrato.orcamento
    return {
        "identificador_os": _build_os_agro_identificador(),
        "status": OrdemServicoAgro.STATUS_PLANEJADA,
        "data_aplicacao": "",
        "periodo_aplicacao": "",
        "equipe_agro_id": str(contrato.equipe_agro_id or ""),
        "drone_pulverizacao_id": "",
        "drone_mapeamento_id": "",
        "cliente_nome": (orcamento.cliente_nome or contrato.contratante_nome or "").strip(),
        "propriedade_nome": (contrato.propriedade_nome or orcamento.nome_fazenda or "").strip(),
        "cultura": (contrato.culturas_formatadas or orcamento.culturas_formatadas or "").strip(),
        "servico": (orcamento.servico or "").strip(),
        "protocolo": (orcamento.protocolo or "").strip(),
        "cidade_operacao": (contrato.propriedade_cidade or orcamento.cidade or "").strip(),
        "uf_operacao": (contrato.propriedade_uf or orcamento.uf or "").strip(),
        "altura_voo_m": "",
        "largura_faixa_m": "",
        "ponta_pulverizacao": "",
        "mapeamento_descricao": "",
        "temperatura_min_c": "",
        "temperatura_max_c": "",
        "umidade_min_pct": "",
        "umidade_max_pct": "",
        "vento_min_kmh": "",
        "vento_max_kmh": "",
        "area_total_ha": _build_os_agro_area_total_from_contrato(contrato),
        "total_calda_l": "",
        "media_aplicada_l_ha": "",
        "taxa_aplicacao_l_ha": "",
        "tipo_aplicacao": "Area Total",
        "produto_aplicado": "",
        "formulacao_produto": "",
        "dosagem": "",
        "classe_toxica": "",
        "observacoes": "",
    }


def _serialize_os_agro_form(ordem_servico):
    return {
        "identificador_os": ordem_servico.identificador_os or "",
        "status": ordem_servico.status or OrdemServicoAgro.STATUS_PLANEJADA,
        "data_aplicacao": ordem_servico.data_aplicacao.isoformat() if ordem_servico.data_aplicacao else "",
        "periodo_aplicacao": ordem_servico.periodo_aplicacao or "",
        "equipe_agro_id": str(ordem_servico.equipe_agro_id or ""),
        "drone_pulverizacao_id": str(ordem_servico.drone_pulverizacao_id or ""),
        "drone_mapeamento_id": str(ordem_servico.drone_mapeamento_id or ""),
        "cliente_nome": ordem_servico.cliente_nome or "",
        "propriedade_nome": ordem_servico.propriedade_nome or "",
        "cultura": ordem_servico.cultura or "",
        "servico": ordem_servico.servico or "",
        "protocolo": ordem_servico.protocolo or "",
        "cidade_operacao": ordem_servico.cidade_operacao or "",
        "uf_operacao": ordem_servico.uf_operacao or "",
        "altura_voo_m": _format_decimal_br_value(ordem_servico.altura_voo_m),
        "largura_faixa_m": _format_decimal_br_value(ordem_servico.largura_faixa_m),
        "ponta_pulverizacao": ordem_servico.ponta_pulverizacao or "",
        "mapeamento_descricao": ordem_servico.mapeamento_descricao or "",
        "temperatura_min_c": _format_decimal_br_value(ordem_servico.temperatura_min_c),
        "temperatura_max_c": _format_decimal_br_value(ordem_servico.temperatura_max_c),
        "umidade_min_pct": _format_decimal_br_value(ordem_servico.umidade_min_pct),
        "umidade_max_pct": _format_decimal_br_value(ordem_servico.umidade_max_pct),
        "vento_min_kmh": _format_decimal_br_value(ordem_servico.vento_min_kmh),
        "vento_max_kmh": _format_decimal_br_value(ordem_servico.vento_max_kmh),
        "area_total_ha": _format_decimal_br_value(ordem_servico.area_total_ha),
        "total_calda_l": _format_decimal_br_value(ordem_servico.total_calda_l),
        "media_aplicada_l_ha": _format_decimal_br_value(ordem_servico.media_aplicada_l_ha),
        "taxa_aplicacao_l_ha": _format_decimal_br_value(ordem_servico.taxa_aplicacao_l_ha),
        "tipo_aplicacao": ordem_servico.tipo_aplicacao or "",
        "produto_aplicado": ordem_servico.produto_aplicado or "",
        "formulacao_produto": ordem_servico.formulacao_produto or "",
        "dosagem": ordem_servico.dosagem or "",
        "classe_toxica": ordem_servico.classe_toxica or "",
        "observacoes": ordem_servico.observacoes or "",
    }


def _normalize_os_agro_form(form_source):
    status = (form_source.get("status") or OrdemServicoAgro.STATUS_PLANEJADA).strip().upper()
    if status not in AGRO_OS_STATUS_OPTIONS:
        status = OrdemServicoAgro.STATUS_PLANEJADA

    return {
        "identificador_os": (form_source.get("identificador_os") or "").strip(),
        "status": status,
        "data_aplicacao": (form_source.get("data_aplicacao") or "").strip(),
        "periodo_aplicacao": (form_source.get("periodo_aplicacao") or "").strip(),
        "equipe_agro_id": (form_source.get("equipe_agro_id") or "").strip(),
        "drone_pulverizacao_id": (form_source.get("drone_pulverizacao_id") or "").strip(),
        "drone_mapeamento_id": (form_source.get("drone_mapeamento_id") or "").strip(),
        "cliente_nome": (form_source.get("cliente_nome") or "").strip(),
        "propriedade_nome": (form_source.get("propriedade_nome") or "").strip(),
        "cultura": (form_source.get("cultura") or "").strip(),
        "servico": (form_source.get("servico") or "").strip(),
        "protocolo": (form_source.get("protocolo") or "").strip(),
        "cidade_operacao": (form_source.get("cidade_operacao") or "").strip(),
        "uf_operacao": (form_source.get("uf_operacao") or "").strip().upper(),
        "altura_voo_m": (form_source.get("altura_voo_m") or "").strip(),
        "largura_faixa_m": (form_source.get("largura_faixa_m") or "").strip(),
        "ponta_pulverizacao": (form_source.get("ponta_pulverizacao") or "").strip(),
        "mapeamento_descricao": (form_source.get("mapeamento_descricao") or "").strip(),
        "temperatura_min_c": (form_source.get("temperatura_min_c") or "").strip(),
        "temperatura_max_c": (form_source.get("temperatura_max_c") or "").strip(),
        "umidade_min_pct": (form_source.get("umidade_min_pct") or "").strip(),
        "umidade_max_pct": (form_source.get("umidade_max_pct") or "").strip(),
        "vento_min_kmh": (form_source.get("vento_min_kmh") or "").strip(),
        "vento_max_kmh": (form_source.get("vento_max_kmh") or "").strip(),
        "area_total_ha": (form_source.get("area_total_ha") or "").strip(),
        "total_calda_l": (form_source.get("total_calda_l") or "").strip(),
        "media_aplicada_l_ha": (form_source.get("media_aplicada_l_ha") or "").strip(),
        "taxa_aplicacao_l_ha": (form_source.get("taxa_aplicacao_l_ha") or "").strip(),
        "tipo_aplicacao": (form_source.get("tipo_aplicacao") or "").strip(),
        "produto_aplicado": (form_source.get("produto_aplicado") or "").strip(),
        "formulacao_produto": (form_source.get("formulacao_produto") or "").strip(),
        "dosagem": (form_source.get("dosagem") or "").strip(),
        "classe_toxica": (form_source.get("classe_toxica") or "").strip(),
        "observacoes": (form_source.get("observacoes") or "").strip(),
    }


def _validate_os_agro_form(form, equipes, equipamentos, *, ordem_atual=None):
    errors = {}

    if form["status"] not in AGRO_OS_STATUS_OPTIONS:
        errors["status"] = "Selecione um status valido."

    if not form["identificador_os"]:
        errors["identificador_os"] = "Informe o identificador da OS Agro."
    else:
        query = OrdemServicoAgro.query.filter(db.func.lower(OrdemServicoAgro.identificador_os) == form["identificador_os"].lower())
        query = apply_prefeitura_scope(query, current_user, OrdemServicoAgro.prefeitura_id)
        if ordem_atual is not None:
            query = query.filter(OrdemServicoAgro.id != ordem_atual.id)
        if query.first():
            errors["identificador_os"] = "Ja existe uma OS Agro com esse identificador."

    if not form["cliente_nome"]:
        errors["cliente_nome"] = "Informe o nome do cliente."
    if not form["propriedade_nome"]:
        errors["propriedade_nome"] = "Informe o nome da propriedade."
    if not form["data_aplicacao"]:
        errors["data_aplicacao"] = "Informe a data da aplicacao."

    data_aplicacao = None
    if form["data_aplicacao"]:
        try:
            data_aplicacao = datetime.strptime(form["data_aplicacao"], "%Y-%m-%d").date()
        except ValueError:
            errors["data_aplicacao"] = "Informe uma data valida."

    equipe_id = _normalize_optional_int(form["equipe_agro_id"])
    equipe = None
    if equipe_id is None:
        errors["equipe_agro_id"] = "Selecione a equipe responsavel."
    else:
        equipe = next((item for item in equipes if item.id == equipe_id), None)
        if not equipe:
            errors["equipe_agro_id"] = "A equipe selecionada nao foi encontrada."

    drone_pulverizacao_id = _normalize_optional_int(form["drone_pulverizacao_id"])
    drone_pulverizacao = None
    if drone_pulverizacao_id:
        drone_pulverizacao = next((item for item in equipamentos if item.id == drone_pulverizacao_id), None)
        if not drone_pulverizacao:
            errors["drone_pulverizacao_id"] = "Selecione um drone de pulverizacao valido."
        elif equipe_id and drone_pulverizacao.equipe_agro_id not in (None, equipe_id):
            errors["drone_pulverizacao_id"] = "O drone de pulverizacao precisa pertencer a equipe selecionada."

    drone_mapeamento_id = _normalize_optional_int(form["drone_mapeamento_id"])
    drone_mapeamento = None
    if drone_mapeamento_id:
        drone_mapeamento = next((item for item in equipamentos if item.id == drone_mapeamento_id), None)
        if not drone_mapeamento:
            errors["drone_mapeamento_id"] = "Selecione um drone de mapeamento valido."
        elif equipe_id and drone_mapeamento.equipe_agro_id not in (None, equipe_id):
            errors["drone_mapeamento_id"] = "O drone de mapeamento precisa pertencer a equipe selecionada."

    numeric_fields = {}
    for field_name in (
        "altura_voo_m",
        "largura_faixa_m",
        "temperatura_min_c",
        "temperatura_max_c",
        "umidade_min_pct",
        "umidade_max_pct",
        "vento_min_kmh",
        "vento_max_kmh",
        "area_total_ha",
        "total_calda_l",
        "media_aplicada_l_ha",
        "taxa_aplicacao_l_ha",
    ):
        value = _parse_decimal_input(form[field_name])
        if form[field_name] and value is None:
            errors[field_name] = "Informe um valor numerico valido."
        numeric_fields[field_name] = value

    if form["uf_operacao"] and len(form["uf_operacao"]) != 2:
        errors["uf_operacao"] = "UF deve ter 2 letras."

    return errors, data_aplicacao, equipe_id, equipe, drone_pulverizacao_id, drone_pulverizacao, drone_mapeamento_id, drone_mapeamento, numeric_fields


def _save_os_agro_attachment(ordem_servico, uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None

    original_filename = secure_filename(uploaded_file.filename)
    if "." not in original_filename or original_filename.rsplit(".", 1)[1].lower() != "pdf":
        raise ValueError("O relatorio final da OS Agro deve ser um arquivo PDF.")

    folder = get_os_agro_attachment_folder()
    stored_filename = f"os_agro_{ordem_servico.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    absolute_path = os.path.join(folder, stored_filename)

    previous_relative_path = (ordem_servico.relatorio_pdf_path or "").strip()
    uploaded_file.save(absolute_path)

    ordem_servico.relatorio_pdf_path = os.path.join("agro", "os", stored_filename).replace("\\", "/")
    ordem_servico.relatorio_pdf_nome = original_filename
    _remove_os_agro_uploaded_file(previous_relative_path, keep_relative_path=ordem_servico.relatorio_pdf_path)
    return original_filename


def _remove_os_agro_uploaded_file(relative_path, *, keep_relative_path=None):
    relative_path = (relative_path or "").strip().replace("\\", "/")
    keep_relative_path = (keep_relative_path or "").strip().replace("\\", "/")
    if not relative_path or relative_path == keep_relative_path:
        return

    absolute_path = os.path.join(get_os_agro_attachment_folder(), os.path.basename(relative_path))
    if os.path.exists(absolute_path):
        try:
            os.remove(absolute_path)
        except OSError:
            pass


def _remove_os_agro_attachments(ordem_servico):
    _remove_os_agro_uploaded_file(getattr(ordem_servico, "relatorio_pdf_path", None))
    _remove_os_agro_uploaded_file(getattr(ordem_servico, "mapa_aplicacao_path", None))
    ordem_servico.relatorio_pdf_path = None
    ordem_servico.relatorio_pdf_nome = None
    ordem_servico.mapa_aplicacao_path = None
    ordem_servico.mapa_aplicacao_nome = None


def _save_os_agro_map_image(ordem_servico, uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None

    original_filename = secure_filename(uploaded_file.filename)
    if "." not in original_filename:
        raise ValueError("A imagem do mapa da OS Agro precisa ser PNG ou JPG.")

    extension = original_filename.rsplit(".", 1)[1].lower()
    if extension not in AGRO_OS_MAP_IMAGE_EXTENSIONS:
        raise ValueError("A imagem do mapa da OS Agro precisa ser PNG ou JPG.")

    folder = get_os_agro_attachment_folder()
    stored_filename = f"os_agro_mapa_{ordem_servico.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{extension}"
    absolute_path = os.path.join(folder, stored_filename)

    previous_relative_path = (ordem_servico.mapa_aplicacao_path or "").strip()
    uploaded_file.save(absolute_path)

    ordem_servico.mapa_aplicacao_path = os.path.join("agro", "os", stored_filename).replace("\\", "/")
    ordem_servico.mapa_aplicacao_nome = original_filename
    _remove_os_agro_uploaded_file(previous_relative_path, keep_relative_path=ordem_servico.mapa_aplicacao_path)
    return original_filename


def _apply_ordem_servico_agro_form(ordem_servico, contrato, form, *, data_aplicacao, equipe_id, drone_pulverizacao_id, drone_pulverizacao, drone_mapeamento_id, drone_mapeamento, numeric_fields):
    orcamento = contrato.orcamento

    ordem_servico.prefeitura_id = contrato.prefeitura_id
    ordem_servico.contrato_agro_id = contrato.id
    ordem_servico.orcamento_agro_id = orcamento.id
    ordem_servico.equipe_agro_id = equipe_id
    ordem_servico.piloto_agro_id = None
    ordem_servico.drone_pulverizacao_id = drone_pulverizacao_id
    ordem_servico.drone_mapeamento_id = drone_mapeamento_id
    ordem_servico.identificador_os = form["identificador_os"]
    ordem_servico.status = form["status"]
    ordem_servico.data_aplicacao = data_aplicacao
    ordem_servico.periodo_aplicacao = form["periodo_aplicacao"] or None
    ordem_servico.cliente_nome = form["cliente_nome"]
    ordem_servico.propriedade_nome = form["propriedade_nome"]
    ordem_servico.cultura = form["cultura"] or None
    ordem_servico.servico = form["servico"] or None
    ordem_servico.protocolo = form["protocolo"] or None
    ordem_servico.cidade_operacao = form["cidade_operacao"] or None
    ordem_servico.uf_operacao = form["uf_operacao"] or None
    ordem_servico.altura_voo_m = numeric_fields["altura_voo_m"]
    ordem_servico.largura_faixa_m = numeric_fields["largura_faixa_m"]
    ordem_servico.ponta_pulverizacao = form["ponta_pulverizacao"] or None
    ordem_servico.mapeamento_descricao = form["mapeamento_descricao"] or None
    ordem_servico.temperatura_min_c = numeric_fields["temperatura_min_c"]
    ordem_servico.temperatura_max_c = numeric_fields["temperatura_max_c"]
    ordem_servico.umidade_min_pct = numeric_fields["umidade_min_pct"]
    ordem_servico.umidade_max_pct = numeric_fields["umidade_max_pct"]
    ordem_servico.vento_min_kmh = numeric_fields["vento_min_kmh"]
    ordem_servico.vento_max_kmh = numeric_fields["vento_max_kmh"]
    ordem_servico.area_total_ha = numeric_fields["area_total_ha"]
    ordem_servico.total_calda_l = numeric_fields["total_calda_l"]
    ordem_servico.media_aplicada_l_ha = numeric_fields["media_aplicada_l_ha"]
    ordem_servico.taxa_aplicacao_l_ha = numeric_fields["taxa_aplicacao_l_ha"]
    ordem_servico.tipo_aplicacao = form["tipo_aplicacao"] or None
    ordem_servico.produto_aplicado = form["produto_aplicado"] or None
    ordem_servico.formulacao_produto = form["formulacao_produto"] or None
    ordem_servico.dosagem = form["dosagem"] or None
    ordem_servico.classe_toxica = form["classe_toxica"] or None
    ordem_servico.observacoes = form["observacoes"] or None
    ordem_servico.finalizado_em = datetime.now() if form["status"] == OrdemServicoAgro.STATUS_CONCLUIDA else None

    _apply_os_agro_drone_snapshot(ordem_servico, drone_pulverizacao, prefix="drone_pulverizacao")
    _apply_os_agro_drone_snapshot(ordem_servico, drone_mapeamento, prefix="drone_mapeamento")


def register_routes(bp):
    @bp.route("/agro", endpoint="agro_root")
    @login_required
    def agro_root():
        if getattr(current_user, "tipo_usuario", None) == "piloto_agro":
            return redirect(url_for("main.agro_piloto_dashboard"))

        _require_agro_access()
        return redirect(url_for("main.admin_agro"))

    @bp.route("/agro/piloto", endpoint="agro_piloto_dashboard")
    @login_required
    def agro_piloto_dashboard():
        _require_piloto_agro()

        piloto = _get_logged_piloto_agro()
        if piloto is None:
            flash("Seu usuario nao esta vinculado a um piloto agro.", "danger")
            return redirect(url_for("auth.logout"))

        equipe = piloto.equipe
        equipamentos = []
        contratos = []
        ordens_servico = []
        if equipe is not None:
            equipamentos = (
                apply_prefeitura_scope(EquipamentoAgro.query, current_user, EquipamentoAgro.prefeitura_id)
                .filter(EquipamentoAgro.equipe_agro_id == equipe.id)
                .order_by(EquipamentoAgro.identificacao.asc(), EquipamentoAgro.id.asc())
                .all()
            )
            contratos = build_contratos_agro_aprovados_query(current_user, equipe_id=equipe.id).all()
            ordens_servico = (
                apply_prefeitura_scope(OrdemServicoAgro.query, current_user, OrdemServicoAgro.prefeitura_id)
                .filter(OrdemServicoAgro.equipe_agro_id == equipe.id)
                .order_by(OrdemServicoAgro.data_aplicacao.desc().nullslast(), OrdemServicoAgro.id.desc())
                .all()
            )

        contratos_sem_os = [contrato for contrato in contratos if not contrato.ordens_servico]
        ordens_ativas = [
            item
            for item in ordens_servico
            if item.status in (OrdemServicoAgro.STATUS_PLANEJADA, OrdemServicoAgro.STATUS_EM_EXECUCAO)
        ]
        ordens_concluidas = [
            item
            for item in ordens_servico
            if item.status == OrdemServicoAgro.STATUS_CONCLUIDA
        ]

        return render_template(
            "piloto_agro_dashboard.html",
            piloto=piloto,
            equipe=equipe,
            equipamentos=equipamentos,
            contratos=contratos,
            contratos_sem_os=contratos_sem_os,
            latest_os_por_contrato=_build_latest_os_by_contrato(contratos),
            ordens_servico=ordens_servico,
            ordens_ativas=ordens_ativas,
            ordens_concluidas=ordens_concluidas,
            total_demandas_prioritarias=len(contratos_sem_os) + len(ordens_ativas),
        )

    @bp.route("/agro/admin", endpoint="admin_agro")
    @login_required
    def admin_agro():
        _require_agro_access()
        context = get_agro_dashboard_context(current_user)
        return render_template("admin_agro.html", **context)

    @bp.route("/agro/clientes", methods=["GET"], endpoint="agro_clientes_listar")
    @login_required
    def agro_clientes_listar():
        _require_agro_access()

        q = (request.args.get("q") or "").strip()
        page = request.args.get("page", 1, type=int)
        per_page = 12

        query = build_clientes_agro_query(current_user, q=q)
        total = query.count()
        total_pages = max(1, math.ceil(total / per_page))
        page = min(max(1, page), total_pages)

        clientes = query.offset((page - 1) * per_page).limit(per_page).all()

        return render_template(
            "agro_clientes_listar.html",
            clientes=clientes,
            clientes_serializados=[serialize_cliente_agro(cliente) for cliente in clientes],
            filters={"q": q, "page": page, "total": total, "total_pages": total_pages},
            pagination_args=_query_args_without_page(),
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/clientes/cadastrar", methods=["GET", "POST"], endpoint="agro_cliente_novo")
    @login_required
    def agro_cliente_novo():
        _require_agro_edit()

        errors = {}
        form = _normalize_cliente_form(request.form if request.method == "POST" else {})

        if request.method == "POST":
            errors, doc_digits, doc_fmt, cep_digits = _validate_cliente_agro_form(form)
            if errors:
                flash("Corrija os campos destacados do cliente agro.", "warning")
                return render_template("agro_cliente_form.html", form=form, errors=errors, modo="novo")

            cliente = ClienteAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                documento=doc_digits,
                nome=form["nome"],
                cep=cep_digits,
                logradouro=form["logradouro"],
                numero=form["numero"],
                complemento=form["complemento"] or None,
                bairro=form["bairro"],
                cidade=form["cidade"],
                uf=form["uf"],
            )
            db.session.add(cliente)
            db.session.commit()

            flash(f"Cliente agro cadastrado com sucesso. Documento salvo como {doc_fmt}.", "success")
            return redirect(url_for("main.agro_clientes_listar"))

        return render_template("agro_cliente_form.html", form=form, errors=errors, modo="novo")

    @bp.route("/agro/clientes/<int:cliente_id>/editar", methods=["GET", "POST"], endpoint="agro_cliente_editar")
    @login_required
    def agro_cliente_editar(cliente_id):
        _require_agro_edit()
        cliente = _get_cliente_agro_or_404(cliente_id)

        errors = {}
        if request.method == "POST":
            form = _normalize_cliente_form(request.form)
            errors, doc_digits, doc_fmt, cep_digits = _validate_cliente_agro_form(form, cliente_atual=cliente)
            if errors:
                flash("Corrija os campos destacados do cliente agro.", "warning")
                return render_template(
                    "agro_cliente_form.html",
                    form=form,
                    errors=errors,
                    modo="editar",
                    cliente=cliente,
                )

            cliente.documento = doc_digits
            cliente.nome = form["nome"]
            cliente.cep = cep_digits
            cliente.logradouro = form["logradouro"]
            cliente.numero = form["numero"]
            cliente.complemento = form["complemento"] or None
            cliente.bairro = form["bairro"]
            cliente.cidade = form["cidade"]
            cliente.uf = form["uf"]
            db.session.commit()

            flash(f"Cliente agro atualizado com sucesso. Documento: {doc_fmt}", "success")
            return redirect(url_for("main.agro_clientes_listar"))

        form = {
            "nome": cliente.nome,
            "documento": format_documento(cliente.documento),
            "cep": format_cep(cliente.cep or ""),
            "logradouro": cliente.logradouro or "",
            "numero": cliente.numero or "",
            "complemento": cliente.complemento or "",
            "bairro": cliente.bairro or "",
            "cidade": cliente.cidade or "",
            "uf": cliente.uf or "",
        }
        return render_template("agro_cliente_form.html", form=form, errors=errors, modo="editar", cliente=cliente)

    @bp.route("/agro/clientes/<int:cliente_id>/deletar", methods=["POST"], endpoint="agro_cliente_deletar")
    @login_required
    def agro_cliente_deletar(cliente_id):
        _require_agro_edit()
        cliente = _get_cliente_agro_or_404(cliente_id)

        if cliente.orcamentos:
            flash("Não é possível excluir este cliente porque ele já possui orçamentos vinculados.", "warning")
            return redirect(url_for("main.agro_clientes_listar"))

        db.session.delete(cliente)
        db.session.commit()
        flash("Cliente agro removido com sucesso.", "success")
        return redirect(url_for("main.agro_clientes_listar"))

    @bp.route("/agro/orcamentos", methods=["GET"], endpoint="agro_orcamentos_listar")
    @login_required
    def agro_orcamentos_listar():
        _require_agro_access()

        q = (request.args.get("q") or "").strip()
        cliente_id = request.args.get("cliente_id", type=int)
        mapeamento = (request.args.get("mapeamento") or "").strip().upper()
        page = request.args.get("page", 1, type=int)
        per_page = 12

        query = build_orcamentos_agro_query(current_user, q=q, cliente_id=cliente_id, mapeamento=mapeamento)
        total = query.count()
        total_pages = max(1, math.ceil(total / per_page))
        page = min(max(1, page), total_pages)
        orcamentos = query.offset((page - 1) * per_page).limit(per_page).all()

        clientes = build_clientes_agro_query(current_user).all()
        return render_template(
            "agro_orcamentos_listar.html",
            orcamentos=orcamentos,
            clientes=clientes,
            agro_bool_label=agro_bool_label,
            filters={
                "q": q,
                "cliente_id": cliente_id,
                "mapeamento": mapeamento,
                "page": page,
                "total": total,
                "total_pages": total_pages,
            },
            pagination_args=_query_args_without_page(),
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/orcamentos/cadastrar", methods=["GET", "POST"], endpoint="agro_orcamento_novo")
    @login_required
    def agro_orcamento_novo():
        _require_agro_edit()
        clientes = build_clientes_agro_query(current_user).all()
        drones_agro = _build_orcamento_agro_drone_options()
        drones_mapeamento_agro = _build_orcamento_agro_drone_options(funcao_operacional="Mapeamento")
        errors = {}
        form = _normalize_orcamento_form(request.form if request.method == "POST" else {})

        if request.method == "POST":
            (
                errors,
                cliente,
                drone_agro,
                drone_mapeamento_agro,
                cliente_documento_digits,
                cep_digits,
                area_ha,
                valor_total_calculado,
                preco_mapeamento,
                preco_pulverizacao,
                preco_pulverizacao_adicional,
                mapeamento_ativo,
                possui_produto_aplicado,
                inicio_aplicacao_prevista,
                fim_aplicacao_prevista,
            ) = _validate_orcamento_form(form)
            form["elaborado_por_nome"] = form.get("elaborado_por_nome") or _current_user_display_name()
            form["valor_total_calculado"] = format_currency_br(valor_total_calculado)
            estimativa_dias = _calculate_application_days(inicio_aplicacao_prevista, fim_aplicacao_prevista)
            form["estimativa_aplicacao_dias"] = str(estimativa_dias or "")
            if errors:
                flash("Corrija os campos destacados do orçamento agro.", "warning")
                return render_template(
                    "agro_orcamento_form.html",
                    **_build_orcamento_agro_form_context(
                        modo="novo",
                        form=form,
                        errors=errors,
                        clientes=clientes,
                        drones_agro=drones_agro,
                        drones_mapeamento_agro=drones_mapeamento_agro,
                    ),
                )

            orcamento = OrcamentoAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                cliente_agro_id=cliente.id if cliente else None,
                cliente_nome=form["cliente_nome"],
                cliente_documento=cliente_documento_digits or None,
                elaborado_por_nome=_current_user_display_name(),
                nome_fazenda=form["nome_fazenda"],
                servico=form["servico"],
                mapeamento=mapeamento_ativo,
                risco_operacional=form["risco_operacional"] or None,
                cultura=form["cultura"] or None,
                cultura_alternativa=form["cultura_alternativa"] or None,
                protocolo=form["protocolo"] or None,
                area_ha=area_ha,
                preco_base=valor_total_calculado,
                preco_mapeamento=preco_mapeamento,
                preco_pulverizacao=preco_pulverizacao,
                preco_pulverizacao_adicional=preco_pulverizacao_adicional,
                possui_produto_aplicado=possui_produto_aplicado,
                produto_aplicado_receituario=form["produto_aplicado_receituario"] or None,
                inicio_aplicacao_prevista=inicio_aplicacao_prevista,
                fim_aplicacao_prevista=fim_aplicacao_prevista,
            )
            orcamento.cep = cep_digits
            orcamento.logradouro = form["logradouro"]
            orcamento.numero = form["numero"]
            orcamento.complemento = form["complemento"] or None
            orcamento.bairro = form["bairro"]
            orcamento.cidade = form["cidade"]
            orcamento.uf = form["uf"]
            _apply_orcamento_agro_drone_snapshot(orcamento, drone_agro)
            _apply_orcamento_agro_drone_mapeamento_snapshot(orcamento, drone_mapeamento_agro)

            db.session.add(orcamento)
            db.session.flush()

            uploaded_file = request.files.get("anexo")
            if uploaded_file and uploaded_file.filename:
                try:
                    save_orcamento_attachment(orcamento, uploaded_file)
                except ValueError as exc:
                    db.session.rollback()
                    errors["anexo"] = str(exc)
                    flash(str(exc), "warning")
                    return render_template(
                        "agro_orcamento_form.html",
                        **_build_orcamento_agro_form_context(
                            modo="novo",
                            form=form,
                            errors=errors,
                            clientes=clientes,
                            drones_agro=drones_agro,
                            drones_mapeamento_agro=drones_mapeamento_agro,
                        ),
                    )

            db.session.commit()
            flash("Orçamento agro cadastrado com sucesso.", "success")
            return redirect(url_for("main.agro_orcamentos_listar"))

        form["elaborado_por_nome"] = form.get("elaborado_por_nome") or _current_user_display_name()
        form["estimativa_aplicacao_dias"] = form.get("estimativa_aplicacao_dias") or ""
        return render_template(
            "agro_orcamento_form.html",
            **_build_orcamento_agro_form_context(
                modo="novo",
                form=form,
                errors=errors,
                clientes=clientes,
                drones_agro=drones_agro,
                drones_mapeamento_agro=drones_mapeamento_agro,
            ),
        )

    @bp.route("/agro/orcamentos/<int:orcamento_id>/editar", methods=["GET", "POST"], endpoint="agro_orcamento_editar")
    @login_required
    def agro_orcamento_editar(orcamento_id):
        _require_agro_edit()
        orcamento = _get_orcamento_agro_or_404(orcamento_id)
        clientes = build_clientes_agro_query(current_user).all()
        drones_agro = _build_orcamento_agro_drone_options()
        drones_mapeamento_agro = _build_orcamento_agro_drone_options(funcao_operacional="Mapeamento")
        errors = {}

        if request.method == "POST":
            form = _normalize_orcamento_form(request.form)
            (
                errors,
                cliente,
                drone_agro,
                drone_mapeamento_agro,
                cliente_documento_digits,
                cep_digits,
                area_ha,
                valor_total_calculado,
                preco_mapeamento,
                preco_pulverizacao,
                preco_pulverizacao_adicional,
                mapeamento_ativo,
                possui_produto_aplicado,
                inicio_aplicacao_prevista,
                fim_aplicacao_prevista,
            ) = _validate_orcamento_form(form)
            form["elaborado_por_nome"] = (
                (orcamento.elaborado_por_nome or "").strip() or _current_user_display_name()
            )
            form["valor_total_calculado"] = format_currency_br(valor_total_calculado)
            estimativa_dias = _calculate_application_days(inicio_aplicacao_prevista, fim_aplicacao_prevista)
            form["estimativa_aplicacao_dias"] = str(estimativa_dias or "")
            if errors:
                flash("Corrija os campos destacados do orçamento agro.", "warning")
                return render_template(
                    "agro_orcamento_form.html",
                    **_build_orcamento_agro_form_context(
                        modo="editar",
                        form=form,
                        errors=errors,
                        clientes=clientes,
                        drones_agro=drones_agro,
                        drones_mapeamento_agro=drones_mapeamento_agro,
                        orcamento=orcamento,
                    ),
                )

            orcamento.cliente_agro_id = cliente.id if cliente else None
            orcamento.cliente_nome = form["cliente_nome"]
            orcamento.cliente_documento = cliente_documento_digits or None
            if not (orcamento.elaborado_por_nome or "").strip():
                orcamento.elaborado_por_nome = _current_user_display_name()
            orcamento.nome_fazenda = form["nome_fazenda"]
            orcamento.servico = form["servico"]
            orcamento.mapeamento = mapeamento_ativo
            orcamento.risco_operacional = form["risco_operacional"] or None
            orcamento.cultura = form["cultura"] or None
            orcamento.cultura_alternativa = form["cultura_alternativa"] or None
            orcamento.protocolo = form["protocolo"] or None
            orcamento.area_ha = area_ha
            orcamento.preco_base = valor_total_calculado
            orcamento.preco_mapeamento = preco_mapeamento
            orcamento.preco_pulverizacao = preco_pulverizacao
            orcamento.preco_pulverizacao_adicional = preco_pulverizacao_adicional
            orcamento.possui_produto_aplicado = possui_produto_aplicado
            orcamento.produto_aplicado_receituario = form["produto_aplicado_receituario"] or None
            orcamento.inicio_aplicacao_prevista = inicio_aplicacao_prevista
            orcamento.fim_aplicacao_prevista = fim_aplicacao_prevista
            orcamento.cep = cep_digits
            orcamento.logradouro = form["logradouro"]
            orcamento.numero = form["numero"]
            orcamento.complemento = form["complemento"] or None
            orcamento.bairro = form["bairro"]
            orcamento.cidade = form["cidade"]
            orcamento.uf = form["uf"]
            _apply_orcamento_agro_drone_snapshot(orcamento, drone_agro)
            _apply_orcamento_agro_drone_mapeamento_snapshot(orcamento, drone_mapeamento_agro)

            uploaded_file = request.files.get("anexo")
            if uploaded_file and uploaded_file.filename:
                try:
                    save_orcamento_attachment(orcamento, uploaded_file)
                except ValueError as exc:
                    db.session.rollback()
                    errors["anexo"] = str(exc)
                    flash(str(exc), "warning")
                    return render_template(
                        "agro_orcamento_form.html",
                        **_build_orcamento_agro_form_context(
                            modo="editar",
                            form=form,
                            errors=errors,
                            clientes=clientes,
                            drones_agro=drones_agro,
                            drones_mapeamento_agro=drones_mapeamento_agro,
                            orcamento=orcamento,
                        ),
                    )

            db.session.commit()
            flash("Orçamento agro atualizado com sucesso.", "success")
            return redirect(url_for("main.agro_orcamentos_listar"))

        form = {
            "cliente_agro_id": str(orcamento.cliente_agro_id or ""),
            "cliente_nome": orcamento.cliente_nome or "",
            "cliente_documento": format_documento(orcamento.cliente_documento or ""),
            "elaborado_por_nome": orcamento.elaborado_por_nome or _current_user_display_name(),
            "nome_fazenda": orcamento.nome_fazenda or "",
            "servico": orcamento.servico or OrcamentoAgro.SERVICO_MAPEAMENTO,
            "mapeamento": "SIM" if orcamento.inclui_mapeamento else "NAO",
            "drone_agro_id": str(orcamento.drone_agro_id or ""),
            "drone_mapeamento_agro_id": str(orcamento.drone_mapeamento_agro_id or ""),
            "possui_produto_aplicado": "SIM" if orcamento.possui_produto_aplicado else "NAO",
            "produto_aplicado_receituario": orcamento.produto_aplicado_receituario or "",
            "inicio_aplicacao_prevista": orcamento.inicio_aplicacao_prevista.isoformat() if orcamento.inicio_aplicacao_prevista else "",
            "fim_aplicacao_prevista": orcamento.fim_aplicacao_prevista.isoformat() if orcamento.fim_aplicacao_prevista else "",
            "estimativa_aplicacao_dias": str(orcamento.estimativa_aplicacao_dias or ""),
            "risco_operacional": orcamento.risco_operacional or "",
            "cultura": orcamento.cultura or "",
            "cultura_alternativa": orcamento.cultura_alternativa or "",
            "protocolo": orcamento.protocolo or "",
            "area_ha": orcamento.area_ha_formatada,
            "preco_mapeamento": format_currency_br(orcamento.preco_mapeamento),
            "preco_pulverizacao": format_currency_br(orcamento.preco_pulverizacao),
            "preco_pulverizacao_adicional": format_currency_br(orcamento.preco_pulverizacao_adicional),
            "valor_total_calculado": format_currency_br(orcamento.valor_total_calculado),
            "cep": format_cep(orcamento.cep or ""),
            "logradouro": orcamento.logradouro or "",
            "numero": orcamento.numero or "",
            "complemento": orcamento.complemento or "",
            "bairro": orcamento.bairro or "",
            "cidade": orcamento.cidade or "",
            "uf": orcamento.uf or "",
        }
        form["elaborado_por_nome"] = form.get("elaborado_por_nome") or _current_user_display_name()
        return render_template(
            "agro_orcamento_form.html",
            **_build_orcamento_agro_form_context(
                modo="editar",
                form=form,
                errors=errors,
                clientes=clientes,
                drones_agro=drones_agro,
                drones_mapeamento_agro=drones_mapeamento_agro,
                orcamento=orcamento,
            ),
        )

    @bp.route("/agro/orcamentos/<int:orcamento_id>/contrato", methods=["GET", "POST"], endpoint="agro_contrato_editar")
    @login_required
    def agro_contrato_editar(orcamento_id):
        _require_agro_edit()
        orcamento = _get_orcamento_agro_or_404(orcamento_id)
        contrato = orcamento.contrato
        equipes_ativas = _build_agro_equipes_ativas()
        errors = {}

        if request.method == "POST":
            form = _normalize_contrato_form(request.form)
            (
                errors,
                doc_digits,
                contratante_cep_digits,
                propriedade_cep_digits,
                valor_total,
                valor_mapeamento_ha,
                valor_pulverizacao_ha,
                valor_pulverizacao_adicional_ha,
                prazo_inicio_dias,
                prazo_pagamento_dias,
                data_assinatura,
            ) = _validate_contrato_form(form)

            if errors:
                flash("Corrija os campos destacados do contrato agro.", "warning")
                return render_template(
                    "agro_contrato_form.html",
                    form=form,
                    errors=errors,
                    orcamento=orcamento,
                    contrato=contrato,
                    equipes_ativas=equipes_ativas,
                    status_options=AGRO_CONTRATO_STATUS_OPTIONS,
                )

            if contrato is None:
                contrato = ContratoAgro(
                    prefeitura_id=getattr(current_user, "prefeitura_id", None),
                    orcamento=orcamento,
                )
                db.session.add(contrato)

            contrato.contratante_nome = form["contratante_nome"]
            contrato.contratante_documento = doc_digits
            contrato.contratante_rg = form["contratante_rg"] or None
            contrato.contratante_cep = contratante_cep_digits
            contrato.contratante_logradouro = form["contratante_logradouro"]
            contrato.contratante_numero = form["contratante_numero"]
            contrato.contratante_complemento = form["contratante_complemento"] or None
            contrato.contratante_bairro = form["contratante_bairro"]
            contrato.contratante_cidade = form["contratante_cidade"]
            contrato.contratante_uf = form["contratante_uf"]
            contrato.propriedade_nome = form["propriedade_nome"]
            contrato.propriedade_cep = propriedade_cep_digits
            contrato.propriedade_logradouro = form["propriedade_logradouro"]
            contrato.propriedade_numero = form["propriedade_numero"]
            contrato.propriedade_complemento = form["propriedade_complemento"] or None
            contrato.propriedade_bairro = form["propriedade_bairro"]
            contrato.propriedade_cidade = form["propriedade_cidade"]
            contrato.propriedade_uf = form["propriedade_uf"]
            contrato.descricao_servico = form["descricao_servico"]
            contrato.cultura = form["cultura"] or None
            contrato.cultura_alternativa = form["cultura_alternativa"] or None
            contrato.area_contratada = form["area_contratada"] or None
            contrato.valor_total = valor_total
            contrato.valor_mapeamento_ha = valor_mapeamento_ha
            contrato.valor_pulverizacao_ha = valor_pulverizacao_ha
            contrato.valor_pulverizacao_adicional_ha = valor_pulverizacao_adicional_ha
            contrato.prazo_inicio_dias = prazo_inicio_dias
            contrato.prazo_pagamento_dias = prazo_pagamento_dias
            contrato.cidade_assinatura = form["cidade_assinatura"]
            contrato.foro_cidade = form["foro_cidade"]
            contrato.data_assinatura = data_assinatura
            contrato.observacoes_adicionais = form["observacoes_adicionais"] or None
            contrato.status = form["status"]

            db.session.commit()
            if contrato.status == ContratoAgro.STATUS_APROVADO:
                if getattr(current_user, "tipo_usuario", None) == "admin":
                    flash(
                        "Contrato agro aprovado e enviado para o template operacional. Agora defina a equipe responsavel.",
                        "success",
                    )
                    return redirect(url_for("main.agro_contratos_template"))

                flash(
                    "Contrato agro aprovado com sucesso. A definicao do template operacional fica disponivel apenas para o admin Agro.",
                    "success",
                )
                return redirect(url_for("main.admin_agro"))

            flash("Contrato agro salvo com sucesso.", "success")
            return redirect(url_for("main.agro_contrato_editar", orcamento_id=orcamento.id))

        form = serialize_contrato_agro_form(contrato) if contrato else build_contrato_agro_defaults(orcamento)
        return render_template(
            "agro_contrato_form.html",
            form=form,
            errors=errors,
            orcamento=orcamento,
            contrato=contrato,
            equipes_ativas=equipes_ativas,
            status_options=AGRO_CONTRATO_STATUS_OPTIONS,
        )

    @bp.route("/agro/contratos", methods=["GET"], endpoint="agro_contratos_listar")
    @login_required
    def agro_contratos_listar():
        _require_agro_access()

        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip().upper()
        if status and status not in AGRO_CONTRATO_STATUS_OPTIONS:
            status = ""

        equipe_id = request.args.get("equipe_id", type=int)
        page = request.args.get("page", 1, type=int)
        per_page = 12

        query = build_contratos_agro_query(current_user, q=q, status=status, equipe_id=equipe_id)
        total = query.count()
        total_pages = max(1, math.ceil(total / per_page))
        page = min(max(1, page), total_pages)
        contratos = query.offset((page - 1) * per_page).limit(per_page).all()
        equipes_ativas = _build_agro_equipes_ativas()

        return render_template(
            "agro_contratos_listar.html",
            contratos=contratos,
            equipes_ativas=equipes_ativas,
            latest_os_by_contrato=_build_latest_os_by_contrato(contratos),
            filters={
                "q": q,
                "status": status,
                "equipe_id": equipe_id,
                "page": page,
                "total": total,
                "total_pages": total_pages,
            },
            pagination_args=_query_args_without_page(),
            status_options=AGRO_CONTRATO_STATUS_OPTIONS,
            is_editable=can_edit_agro_panel(current_user),
            is_admin_agro=getattr(current_user, "tipo_usuario", None) == "admin",
            build_endereco_agro=build_endereco_agro,
        )

    @bp.route("/agro/financeiro", methods=["GET"], endpoint="agro_financeiro_listar")
    @login_required
    def agro_financeiro_listar():
        _require_agro_access()

        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip().upper()
        mes = request.args.get("mes", type=int)
        ano = request.args.get("ano", type=int)
        contrato_id = request.args.get("contrato_id", type=int)

        if status and status not in AGRO_FINANCEIRO_STATUS_OPTIONS:
            status = ""

        lancamentos = build_financeiro_agro_query(
            current_user,
            q=q,
            status=status,
            mes=mes,
            ano=ano,
            contrato_id=contrato_id,
        ).all()
        contratos = build_contratos_agro_query(current_user).all()
        resumo = _build_financeiro_agro_summary(lancamentos)

        return render_template(
            "agro_financeiro_listar.html",
            lancamentos=lancamentos,
            contratos=contratos,
            resumo=resumo,
            filters={
                "q": q,
                "status": status,
                "mes": mes,
                "ano": ano,
                "contrato_id": contrato_id,
                "total": len(lancamentos),
            },
            status_options=AGRO_FINANCEIRO_STATUS_OPTIONS,
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/financeiro/cadastrar", methods=["GET", "POST"], endpoint="agro_financeiro_novo")
    @login_required
    def agro_financeiro_novo():
        _require_agro_edit()

        contratos = build_contratos_agro_query(current_user).all()
        errors = {}

        if request.method == "POST":
            form = _normalize_financeiro_agro_form(request.form)
            (
                errors,
                contrato,
                ordem_servico,
                data_elaboracao_contrato,
                data_servico_executado,
                data_vencimento,
                data_recebimento,
                numeric_fields,
                resolved_status,
            ) = _validate_financeiro_agro_form(form, contratos)
            _sync_financeiro_agro_form_numbers(form, numeric_fields, resolved_status)

            if errors:
                flash("Corrija os campos destacados do financeiro agro.", "warning")
                return render_template(
                    "agro_financeiro_form.html",
                    **_build_financeiro_agro_form_context(
                        modo="novo",
                        form=form,
                        errors=errors,
                        contratos=contratos,
                    ),
                )

            orcamento = contrato.orcamento if contrato else None
            competencia = data_servico_executado or data_vencimento
            lancamento = FinanceiroAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                cliente_agro_id=getattr(orcamento, "cliente_agro_id", None),
                orcamento_agro_id=getattr(orcamento, "id", None),
                contrato_agro_id=contrato.id,
                ordem_servico_agro_id=getattr(ordem_servico, "id", None),
                cliente_nome=form["cliente_nome"],
                cultura=form["cultura"] or None,
                forma_recebimento=form["forma_recebimento"] or None,
                status=resolved_status,
                observacoes=form["observacoes"] or None,
                competencia_mes=getattr(competencia, "month", None),
                competencia_ano=getattr(competencia, "year", None),
                data_elaboracao_contrato=data_elaboracao_contrato,
                data_servico_executado=data_servico_executado,
                data_vencimento=data_vencimento,
                data_recebimento=data_recebimento,
                area_mapeamento_ha=numeric_fields["area_mapeamento_ha"],
                valor_mapeamento_ha=numeric_fields["valor_mapeamento_ha"],
                total_mapeamento=numeric_fields["total_mapeamento"],
                area_pulverizacao_ha=numeric_fields["area_pulverizacao_ha"],
                area_pulverizada_real_ha=numeric_fields["area_pulverizada_real_ha"],
                valor_pulverizacao_ha=numeric_fields["valor_pulverizacao_ha"],
                total_pulverizacao=numeric_fields["total_pulverizacao"],
                valor_total_contrato=numeric_fields["valor_total_contrato"],
                comissao_por_ha=numeric_fields["comissao_por_ha"],
                valor_comissao=numeric_fields["valor_comissao"],
                comissao_cooperativa_por_ha=numeric_fields["comissao_cooperativa_por_ha"],
                valor_comissao_cooperativa=numeric_fields["valor_comissao_cooperativa"],
            )
            db.session.add(lancamento)
            db.session.commit()

            flash("Lancamento financeiro agro cadastrado com sucesso.", "success")
            return redirect(url_for("main.agro_financeiro_listar"))

        contrato_id = request.args.get("contrato_id", type=int)
        contrato = next((item for item in contratos if item.id == contrato_id), None) if contrato_id else None
        if contrato is not None:
            form = build_financeiro_agro_defaults(contrato)
        else:
            form = _normalize_financeiro_agro_form({})
            form["comissao_por_ha"] = format_currency_br(8)
            form["comissao_cooperativa_por_ha"] = format_currency_br(10)
            form["status"] = FinanceiroAgro.STATUS_PENDENTE

        return render_template(
            "agro_financeiro_form.html",
            **_build_financeiro_agro_form_context(
                modo="novo",
                form=form,
                errors=errors,
                contratos=contratos,
            ),
        )

    @bp.route("/agro/financeiro/<int:lancamento_id>/editar", methods=["GET", "POST"], endpoint="agro_financeiro_editar")
    @login_required
    def agro_financeiro_editar(lancamento_id):
        _require_agro_edit()

        lancamento = _get_financeiro_agro_or_404(lancamento_id)
        contratos = build_contratos_agro_query(current_user).all()
        errors = {}

        if request.method == "POST":
            form = _normalize_financeiro_agro_form(request.form)
            (
                errors,
                contrato,
                ordem_servico,
                data_elaboracao_contrato,
                data_servico_executado,
                data_vencimento,
                data_recebimento,
                numeric_fields,
                resolved_status,
            ) = _validate_financeiro_agro_form(form, contratos)
            _sync_financeiro_agro_form_numbers(form, numeric_fields, resolved_status)

            if errors:
                flash("Corrija os campos destacados do financeiro agro.", "warning")
                return render_template(
                    "agro_financeiro_form.html",
                    **_build_financeiro_agro_form_context(
                        modo="editar",
                        form=form,
                        errors=errors,
                        contratos=contratos,
                        lancamento=lancamento,
                    ),
                )

            orcamento = contrato.orcamento if contrato else None
            competencia = data_servico_executado or data_vencimento
            lancamento.cliente_agro_id = getattr(orcamento, "cliente_agro_id", None)
            lancamento.orcamento_agro_id = getattr(orcamento, "id", None)
            lancamento.contrato_agro_id = contrato.id
            lancamento.ordem_servico_agro_id = getattr(ordem_servico, "id", None)
            lancamento.cliente_nome = form["cliente_nome"]
            lancamento.cultura = form["cultura"] or None
            lancamento.forma_recebimento = form["forma_recebimento"] or None
            lancamento.status = resolved_status
            lancamento.observacoes = form["observacoes"] or None
            lancamento.competencia_mes = getattr(competencia, "month", None)
            lancamento.competencia_ano = getattr(competencia, "year", None)
            lancamento.data_elaboracao_contrato = data_elaboracao_contrato
            lancamento.data_servico_executado = data_servico_executado
            lancamento.data_vencimento = data_vencimento
            lancamento.data_recebimento = data_recebimento
            lancamento.area_mapeamento_ha = numeric_fields["area_mapeamento_ha"]
            lancamento.valor_mapeamento_ha = numeric_fields["valor_mapeamento_ha"]
            lancamento.total_mapeamento = numeric_fields["total_mapeamento"]
            lancamento.area_pulverizacao_ha = numeric_fields["area_pulverizacao_ha"]
            lancamento.area_pulverizada_real_ha = numeric_fields["area_pulverizada_real_ha"]
            lancamento.valor_pulverizacao_ha = numeric_fields["valor_pulverizacao_ha"]
            lancamento.total_pulverizacao = numeric_fields["total_pulverizacao"]
            lancamento.valor_total_contrato = numeric_fields["valor_total_contrato"]
            lancamento.comissao_por_ha = numeric_fields["comissao_por_ha"]
            lancamento.valor_comissao = numeric_fields["valor_comissao"]
            lancamento.comissao_cooperativa_por_ha = numeric_fields["comissao_cooperativa_por_ha"]
            lancamento.valor_comissao_cooperativa = numeric_fields["valor_comissao_cooperativa"]
            db.session.commit()

            flash("Lancamento financeiro agro atualizado com sucesso.", "success")
            return redirect(url_for("main.agro_financeiro_listar"))

        form = serialize_financeiro_agro_form(lancamento)
        return render_template(
            "agro_financeiro_form.html",
            **_build_financeiro_agro_form_context(
                modo="editar",
                form=form,
                errors=errors,
                contratos=contratos,
                lancamento=lancamento,
            ),
        )

    @bp.route("/agro/financeiro/<int:lancamento_id>/deletar", methods=["POST"], endpoint="agro_financeiro_deletar")
    @login_required
    def agro_financeiro_deletar(lancamento_id):
        _require_agro_edit()

        lancamento = _get_financeiro_agro_or_404(lancamento_id)
        db.session.delete(lancamento)
        db.session.commit()

        flash("Lancamento financeiro agro excluido com sucesso.", "success")
        return _redirect_back_to_agro("main.agro_financeiro_listar")

    @bp.route("/agro/contratos/template", methods=["GET"], endpoint="agro_contratos_template")
    @login_required
    def agro_contratos_template():
        _require_agro_admin()

        q = (request.args.get("q") or "").strip()
        equipe_id = request.args.get("equipe_id", type=int)
        contratos = build_contratos_agro_aprovados_query(current_user, q=q, equipe_id=equipe_id).all()
        equipes_ativas = _build_agro_equipes_ativas()

        return render_template(
            "agro_contratos_template.html",
            contratos=contratos,
            equipes_ativas=equipes_ativas,
            filters={"q": q, "equipe_id": equipe_id, "total": len(contratos)},
            status_options=AGRO_CONTRATO_STATUS_OPTIONS,
        )

    @bp.route("/agro/contratos/<int:contrato_id>/template", methods=["POST"], endpoint="agro_contrato_template_salvar")
    @login_required
    def agro_contrato_template_salvar(contrato_id):
        _require_agro_admin()

        contrato = _get_contrato_agro_or_404(contrato_id)
        equipes_ativas = _build_agro_equipes_ativas()
        form = _normalize_contrato_template_form(request.form)
        errors, equipe_id, _equipe = _validate_contrato_template_form(form, equipes_ativas)

        if errors:
            for message in errors.values():
                flash(message, "warning")
            return _redirect_back_to_agro("main.agro_contratos_template")

        contrato.status = form["status"]
        contrato.equipe_agro_id = equipe_id
        db.session.commit()

        flash("Template operacional do contrato atualizado com sucesso.", "success")
        return _redirect_back_to_agro("main.agro_contratos_template")

    @bp.route("/agro/contratos/<int:contrato_id>/deletar", methods=["POST"], endpoint="agro_contrato_deletar")
    @login_required
    def agro_contrato_deletar(contrato_id):
        _require_agro_admin()
        contrato = _get_contrato_agro_or_404(contrato_id)
        if contrato.ordens_servico:
            flash("Este contrato possui OS Agro vinculada(s). Exclua primeiro as OS para remover o contrato.", "warning")
            return _redirect_back_to_agro("main.agro_contratos_template")

        db.session.delete(contrato)
        db.session.commit()
        flash("Contrato agro removido com sucesso.", "success")
        return _redirect_back_to_agro("main.agro_contratos_template")

    @bp.route("/agro/orcamentos/<int:orcamento_id>/anexo", endpoint="agro_orcamento_anexo")
    @login_required
    def agro_orcamento_anexo(orcamento_id):
        _require_agro_access()
        orcamento = _get_orcamento_agro_or_404(orcamento_id)
        try:
            upload_folder, rel, download_name = resolve_orcamento_attachment(orcamento)
        except FileNotFoundError:
            abort(404)
        return send_from_directory(upload_folder, rel, as_attachment=False, download_name=download_name)

    @bp.route("/agro/orcamentos/<int:orcamento_id>/pdf", endpoint="agro_orcamento_pdf")
    @login_required
    def agro_orcamento_pdf(orcamento_id):
        _require_agro_access()
        orcamento = _get_orcamento_agro_or_404(orcamento_id)
        pdf = build_orcamento_agro_pdf(orcamento)
        if orcamento.anexo_path:
            try:
                upload_folder, rel, _download_name = resolve_orcamento_attachment(orcamento)
                attachment_absolute_path = os.path.join(upload_folder, rel.replace("/", os.sep))
                pdf = merge_orcamento_agro_with_attachment(pdf, attachment_absolute_path)
            except FileNotFoundError:
                pass
        filename = f"orcamento_agro_{orcamento.id}.pdf"
        return send_file(pdf, mimetype="application/pdf", as_attachment=False, download_name=filename)

    @bp.route("/agro/orcamentos/<int:orcamento_id>/contrato/pdf", endpoint="agro_contrato_pdf")
    @login_required
    def agro_contrato_pdf(orcamento_id):
        _require_agro_access()
        orcamento = _get_orcamento_agro_or_404(orcamento_id)
        contrato = orcamento.contrato or _build_contrato_agro_draft(orcamento)
        pdf = build_contrato_agro_pdf(contrato)
        filename = f"contrato_agro_{orcamento.id}.pdf"
        return send_file(pdf, mimetype="application/pdf", as_attachment=False, download_name=filename)

    @bp.route("/agro/os/<int:os_id>/relatorio/pdf", methods=["GET"], endpoint="agro_os_relatorio_pdf")
    @login_required
    def agro_os_relatorio_pdf(os_id):
        _require_agro_edit()
        ordem_servico = _get_os_agro_or_404(os_id)

        if ordem_servico.status != OrdemServicoAgro.STATUS_CONCLUIDA:
            flash("O relatorio da OS Agro so pode ser gerado quando a OS estiver concluida.", "warning")
            return redirect(url_for("main.agro_os_listar"))

        pdf = build_ordem_servico_agro_pdf(ordem_servico)
        filename = f"os_agro_{ordem_servico.identificador_os or ordem_servico.id}_relatorio.pdf"
        return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)

    @bp.route("/agro/os/<int:os_id>/deletar", methods=["POST"], endpoint="agro_os_deletar")
    @login_required
    def agro_os_deletar(os_id):
        _require_agro_admin()
        ordem_servico = _get_os_agro_or_404(os_id)
        _remove_os_agro_attachments(ordem_servico)
        db.session.delete(ordem_servico)
        db.session.commit()
        flash("OS Agro removida com sucesso.", "success")
        return redirect(url_for("main.agro_os_listar"))

    @bp.route("/agro/os", methods=["GET"], endpoint="agro_os_listar")
    @login_required
    def agro_os_listar():
        _require_agro_access()

        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip().upper()
        equipe_id = request.args.get("equipe_id", type=int)

        ordens_servico = build_ordens_servico_agro_query(
            current_user,
            q=q,
            status=status if status in AGRO_OS_STATUS_OPTIONS else "",
            equipe_id=equipe_id,
        ).all()

        return render_template(
            "agro_os_listar.html",
            ordens_servico=ordens_servico,
            equipes_ativas=_build_agro_equipes_ativas(),
            status_options=AGRO_OS_STATUS_OPTIONS,
            filters={"q": q, "status": status, "equipe_id": equipe_id, "total": len(ordens_servico)},
            is_editable=can_edit_agro_panel(current_user),
            is_admin_agro=getattr(current_user, "tipo_usuario", None) == "admin",
        )

    @bp.route("/agro/contratos/<int:contrato_id>/os/cadastrar", methods=["GET", "POST"], endpoint="agro_os_nova")
    @login_required
    def agro_os_nova(contrato_id):
        pilot_form_mode = getattr(current_user, "tipo_usuario", None) == "piloto_agro"
        piloto_logado = None
        if pilot_form_mode:
            piloto_logado = _get_logged_piloto_agro()
            if piloto_logado is None:
                flash("Seu usuario nao esta vinculado a um piloto agro.", "danger")
                return redirect(url_for("auth.logout"))
        else:
            _require_agro_access()
            flash("A criacao da OS Agro agora deve ser feita pelo piloto no painel Agro.", "info")
            return redirect(url_for("main.agro_contratos_template"))

        contrato = _get_contrato_agro_or_404(contrato_id)
        if contrato.status != ContratoAgro.STATUS_APROVADO:
            flash("A OS Agro so pode ser criada a partir de um contrato aprovado.", "warning")
            if pilot_form_mode:
                return redirect(url_for("main.agro_piloto_dashboard"))
            return redirect(url_for("main.agro_contrato_editar", orcamento_id=contrato.orcamento.id))

        if not contrato.equipe_agro_id:
            flash("Defina a equipe responsavel no template operacional antes de criar a OS Agro.", "warning")
            return redirect(url_for("main.agro_piloto_dashboard" if pilot_form_mode else "main.agro_contratos_template"))

        if pilot_form_mode and piloto_logado.equipe_agro_id != contrato.equipe_agro_id:
            flash("Este contrato aprovado esta vinculado a outra equipe.", "warning")
            return redirect(url_for("main.agro_piloto_dashboard"))

        ordem_existente = (
            apply_prefeitura_scope(OrdemServicoAgro.query, current_user, OrdemServicoAgro.prefeitura_id)
            .filter(OrdemServicoAgro.contrato_agro_id == contrato.id)
            .order_by(OrdemServicoAgro.criado_em.desc(), OrdemServicoAgro.id.desc())
            .first()
        )
        if ordem_existente is not None:
            flash("Este contrato ja possui OS cadastrada. Voce pode atualiza-la no formulario.", "info")
            return redirect(url_for("main.agro_os_editar", os_id=ordem_existente.id))

        equipes, pilotos, equipamentos = _build_os_agro_form_options(piloto_logado=piloto_logado if pilot_form_mode else None)

        errors = {}
        form = _normalize_os_agro_form(request.form if request.method == "POST" else _build_os_agro_defaults(contrato))
        if pilot_form_mode:
            form["equipe_agro_id"] = str(contrato.equipe_agro_id or "")
        if not form.get("area_total_ha"):
            form["area_total_ha"] = _build_os_agro_area_total_from_contrato(contrato)

        if request.method == "POST":
            (
                errors,
                data_aplicacao,
                equipe_id,
                _equipe,
                drone_pulverizacao_id,
                drone_pulverizacao,
                drone_mapeamento_id,
                drone_mapeamento,
                numeric_fields,
            ) = _validate_os_agro_form(form, equipes, equipamentos)

            if equipe_id and contrato.equipe_agro_id and equipe_id != contrato.equipe_agro_id:
                errors["equipe_agro_id"] = "A equipe da OS precisa seguir a equipe definida no contrato aprovado."

            if errors:
                flash("Corrija os campos destacados da OS Agro.", "warning")
                return render_template(
                    "agro_os_form.html",
                    **_build_os_agro_form_context(
                        modo="novo",
                        contrato=contrato,
                        form=form,
                        errors=errors,
                        equipes=equipes,
                        pilotos=pilotos,
                        equipamentos=equipamentos,
                        pilot_form_mode=pilot_form_mode,
                        piloto_logado=piloto_logado,
                    ),
                )

            ordem_servico = OrdemServicoAgro()
            _apply_ordem_servico_agro_form(
                ordem_servico,
                contrato,
                form,
                data_aplicacao=data_aplicacao,
                equipe_id=equipe_id,
                drone_pulverizacao_id=drone_pulverizacao_id,
                drone_pulverizacao=drone_pulverizacao,
                drone_mapeamento_id=drone_mapeamento_id,
                drone_mapeamento=drone_mapeamento,
                numeric_fields=numeric_fields,
            )
            db.session.add(ordem_servico)
            db.session.flush()

            uploaded_report = request.files.get("relatorio_pdf")
            if uploaded_report and uploaded_report.filename:
                try:
                    _save_os_agro_attachment(ordem_servico, uploaded_report)
                except ValueError as exc:
                    db.session.rollback()
                    flash(str(exc), "warning")
                    return render_template(
                        "agro_os_form.html",
                        **_build_os_agro_form_context(
                            modo="novo",
                            contrato=contrato,
                            form=form,
                            errors=errors,
                            equipes=equipes,
                            pilotos=pilotos,
                            equipamentos=equipamentos,
                            pilot_form_mode=pilot_form_mode,
                            piloto_logado=piloto_logado,
                        ),
                    )

            if not pilot_form_mode:
                uploaded_map = request.files.get("mapa_aplicacao")
                if uploaded_map and uploaded_map.filename:
                    try:
                        _save_os_agro_map_image(ordem_servico, uploaded_map)
                    except ValueError as exc:
                        db.session.rollback()
                        flash(str(exc), "warning")
                        return render_template(
                            "agro_os_form.html",
                            **_build_os_agro_form_context(
                                modo="novo",
                                contrato=contrato,
                                form=form,
                                errors=errors,
                                equipes=equipes,
                                pilotos=pilotos,
                                equipamentos=equipamentos,
                                pilot_form_mode=pilot_form_mode,
                                piloto_logado=piloto_logado,
                            ),
                        )

            db.session.commit()
            flash("OS Agro criada com sucesso.", "success")
            return redirect(url_for("main.agro_piloto_dashboard" if pilot_form_mode else "main.agro_os_listar"))

        return render_template(
            "agro_os_form.html",
            **_build_os_agro_form_context(
                modo="novo",
                contrato=contrato,
                form=form,
                errors=errors,
                equipes=equipes,
                pilotos=pilotos,
                equipamentos=equipamentos,
                pilot_form_mode=pilot_form_mode,
                piloto_logado=piloto_logado,
            ),
        )

    @bp.route("/agro/os/<int:os_id>/editar", methods=["GET", "POST"], endpoint="agro_os_editar")
    @login_required
    def agro_os_editar(os_id):
        ordem_servico = _get_os_agro_or_404(os_id)
        contrato = ordem_servico.contrato
        pilot_form_mode = getattr(current_user, "tipo_usuario", None) == "piloto_agro"
        piloto_logado = None
        if pilot_form_mode:
            piloto_logado = _get_logged_piloto_agro()
            if piloto_logado is None:
                flash("Seu usuario nao esta vinculado a um piloto agro.", "danger")
                return redirect(url_for("auth.logout"))
            if piloto_logado.equipe_agro_id != ordem_servico.equipe_agro_id:
                flash("Esta OS Agro pertence a outra equipe.", "warning")
                return redirect(url_for("main.agro_piloto_dashboard"))
        else:
            _require_agro_edit()

        equipes, pilotos, equipamentos = _build_os_agro_form_options(piloto_logado=piloto_logado if pilot_form_mode else None)

        errors = {}
        if request.method == "POST":
            form = _normalize_os_agro_form(request.form)
            if pilot_form_mode:
                form["equipe_agro_id"] = str(ordem_servico.equipe_agro_id or "")
            if not form.get("area_total_ha"):
                form["area_total_ha"] = _build_os_agro_area_total_from_contrato(contrato)

            (
                errors,
                data_aplicacao,
                equipe_id,
                _equipe,
                drone_pulverizacao_id,
                drone_pulverizacao,
                drone_mapeamento_id,
                drone_mapeamento,
                numeric_fields,
            ) = _validate_os_agro_form(form, equipes, equipamentos, ordem_atual=ordem_servico)

            if equipe_id and contrato.equipe_agro_id and equipe_id != contrato.equipe_agro_id:
                errors["equipe_agro_id"] = "A equipe da OS precisa seguir a equipe definida no contrato aprovado."

            if errors:
                flash("Corrija os campos destacados da OS Agro.", "warning")
                return render_template(
                    "agro_os_form.html",
                    **_build_os_agro_form_context(
                        modo="editar",
                        contrato=contrato,
                        ordem_servico=ordem_servico,
                        form=form,
                        errors=errors,
                        equipes=equipes,
                        pilotos=pilotos,
                        equipamentos=equipamentos,
                        pilot_form_mode=pilot_form_mode,
                        piloto_logado=piloto_logado,
                    ),
                )

            _apply_ordem_servico_agro_form(
                ordem_servico,
                contrato,
                form,
                data_aplicacao=data_aplicacao,
                equipe_id=equipe_id,
                drone_pulverizacao_id=drone_pulverizacao_id,
                drone_pulverizacao=drone_pulverizacao,
                drone_mapeamento_id=drone_mapeamento_id,
                drone_mapeamento=drone_mapeamento,
                numeric_fields=numeric_fields,
            )

            uploaded_report = request.files.get("relatorio_pdf")
            if uploaded_report and uploaded_report.filename:
                try:
                    _save_os_agro_attachment(ordem_servico, uploaded_report)
                except ValueError as exc:
                    db.session.rollback()
                    flash(str(exc), "warning")
                    return render_template(
                        "agro_os_form.html",
                        **_build_os_agro_form_context(
                            modo="editar",
                            contrato=contrato,
                            ordem_servico=ordem_servico,
                            form=form,
                            errors=errors,
                            equipes=equipes,
                            pilotos=pilotos,
                            equipamentos=equipamentos,
                            pilot_form_mode=pilot_form_mode,
                            piloto_logado=piloto_logado,
                        ),
                    )

            if not pilot_form_mode:
                uploaded_map = request.files.get("mapa_aplicacao")
                if uploaded_map and uploaded_map.filename:
                    try:
                        _save_os_agro_map_image(ordem_servico, uploaded_map)
                    except ValueError as exc:
                        db.session.rollback()
                        flash(str(exc), "warning")
                        return render_template(
                            "agro_os_form.html",
                            **_build_os_agro_form_context(
                                modo="editar",
                                contrato=contrato,
                                ordem_servico=ordem_servico,
                                form=form,
                                errors=errors,
                                equipes=equipes,
                                pilotos=pilotos,
                                equipamentos=equipamentos,
                                pilot_form_mode=pilot_form_mode,
                                piloto_logado=piloto_logado,
                            ),
                        )

            db.session.commit()
            flash("OS Agro atualizada com sucesso.", "success")
            return redirect(url_for("main.agro_piloto_dashboard" if pilot_form_mode else "main.agro_os_listar"))

        form = _serialize_os_agro_form(ordem_servico)
        if not form.get("area_total_ha"):
            form["area_total_ha"] = _build_os_agro_area_total_from_contrato(contrato)
        if pilot_form_mode:
            form["equipe_agro_id"] = str(ordem_servico.equipe_agro_id or "")
        return render_template(
            "agro_os_form.html",
            **_build_os_agro_form_context(
                modo="editar",
                contrato=contrato,
                ordem_servico=ordem_servico,
                form=form,
                errors=errors,
                equipes=equipes,
                pilotos=pilotos,
                equipamentos=equipamentos,
                pilot_form_mode=pilot_form_mode,
                piloto_logado=piloto_logado,
            ),
        )

    @bp.route("/agro/orcamentos/<int:orcamento_id>/deletar", methods=["POST"], endpoint="agro_orcamento_deletar")
    @login_required
    def agro_orcamento_deletar(orcamento_id):
        _require_agro_edit()
        orcamento = _get_orcamento_agro_or_404(orcamento_id)
        if orcamento.ordens_servico:
            flash("Este orçamento possui OS Agro vinculada(s). Exclua primeiro as OS para remover o orçamento.", "warning")
            return redirect(url_for("main.agro_orcamentos_listar"))
        if orcamento.contrato is not None:
            flash("Este orçamento possui contrato vinculado. Exclua primeiro o contrato para remover o orçamento.", "warning")
            return redirect(url_for("main.agro_orcamentos_listar"))
        remove_orcamento_attachment(orcamento)
        db.session.delete(orcamento)
        db.session.commit()
        flash("Orçamento agro removido com sucesso.", "success")
        return redirect(url_for("main.agro_orcamentos_listar"))

    @bp.route("/agro/equipes", methods=["GET"], endpoint="agro_equipes_listar")
    @login_required
    def agro_equipes_listar():
        _require_agro_access()
        q = (request.args.get("q") or "").strip()
        query = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id)
        if q:
            query = query.filter(
                db.or_(
                    EquipeAgro.nome.ilike(f"%{q}%"),
                    EquipeAgro.descricao.ilike(f"%{q}%"),
                )
            )
        equipes = query.order_by(EquipeAgro.nome.asc(), EquipeAgro.id.desc()).all()
        return render_template(
            "agro_equipes_listar.html",
            equipes=equipes,
            filters={"q": q, "total": len(equipes)},
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/equipes/cadastrar", methods=["GET", "POST"], endpoint="agro_equipe_nova")
    @login_required
    def agro_equipe_nova():
        _require_agro_edit()
        errors = {}
        form = _normalize_equipe_form(request.form if request.method == "POST" else {})
        if request.method == "POST":
            errors, ativa = _validate_equipe_agro_form(form)
            if errors:
                flash("Corrija os campos destacados da equipe agro.", "warning")
                return render_template("agro_equipe_form.html", form=form, errors=errors, modo="novo")

            equipe = EquipeAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                nome=form["nome"],
                descricao=form["descricao"] or None,
                ativa=ativa,
            )
            db.session.add(equipe)
            db.session.commit()
            flash("Equipe agro cadastrada com sucesso.", "success")
            return redirect(url_for("main.agro_equipes_listar"))

        return render_template("agro_equipe_form.html", form=form, errors=errors, modo="novo")

    @bp.route("/agro/equipes/<int:equipe_id>/editar", methods=["GET", "POST"], endpoint="agro_equipe_editar")
    @login_required
    def agro_equipe_editar(equipe_id):
        _require_agro_edit()
        equipe = _get_equipe_agro_or_404(equipe_id)
        errors = {}
        if request.method == "POST":
            form = _normalize_equipe_form(request.form)
            errors, ativa = _validate_equipe_agro_form(form, equipe_atual=equipe)
            if errors:
                flash("Corrija os campos destacados da equipe agro.", "warning")
                return render_template("agro_equipe_form.html", form=form, errors=errors, modo="editar", equipe=equipe)

            equipe.nome = form["nome"]
            equipe.descricao = form["descricao"] or None
            equipe.ativa = ativa
            db.session.commit()
            flash("Equipe agro atualizada com sucesso.", "success")
            return redirect(url_for("main.agro_equipes_listar"))

        form = {
            "nome": equipe.nome or "",
            "descricao": equipe.descricao or "",
            "ativa": "SIM" if equipe.ativa else "NAO",
        }
        return render_template("agro_equipe_form.html", form=form, errors=errors, modo="editar", equipe=equipe)

    @bp.route("/agro/equipes/<int:equipe_id>/deletar", methods=["POST"], endpoint="agro_equipe_deletar")
    @login_required
    def agro_equipe_deletar(equipe_id):
        _require_agro_edit()
        equipe = _get_equipe_agro_or_404(equipe_id)
        if equipe.pilotos or equipe.equipamentos:
            flash("Não é possível excluir a equipe porque ela possui pilotos ou equipamentos vinculados.", "warning")
            return redirect(url_for("main.agro_equipes_listar"))
        db.session.delete(equipe)
        db.session.commit()
        flash("Equipe agro removida com sucesso.", "success")
        return redirect(url_for("main.agro_equipes_listar"))

    @bp.route("/agro/pilotos", methods=["GET"], endpoint="agro_pilotos_listar")
    @login_required
    def agro_pilotos_listar():
        _require_agro_access()
        q = (request.args.get("q") or "").strip()
        query = apply_prefeitura_scope(PilotoAgro.query, current_user, PilotoAgro.prefeitura_id)
        if q:
            query = query.filter(
                db.or_(
                    PilotoAgro.nome.ilike(f"%{q}%"),
                    PilotoAgro.telefone.ilike(f"%{only_digits(q)}%") if only_digits(q) else db.false(),
                    PilotoAgro.usuario.has(Usuario.login.ilike(f"%{q}%")),
                )
            )
        pilotos = query.order_by(PilotoAgro.nome.asc(), PilotoAgro.id.desc()).all()
        return render_template(
            "agro_pilotos_listar.html",
            pilotos=pilotos,
            filters={"q": q, "total": len(pilotos)},
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/pilotos/cadastrar", methods=["GET", "POST"], endpoint="agro_piloto_novo")
    @login_required
    def agro_piloto_novo():
        _require_agro_edit()
        equipes = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id).order_by(EquipeAgro.nome.asc()).all()
        errors = {}
        form = _normalize_piloto_form(request.form if request.method == "POST" else {})
        if request.method == "POST":
            errors, telefone_digits, equipe_id, _equipe, ativo = _validate_piloto_agro_form(form, equipes)
            if errors:
                flash("Corrija os campos destacados do piloto agro.", "warning")
                return render_template("agro_piloto_form.html", form=form, errors=errors, modo="novo", equipes=equipes)

            piloto = PilotoAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                equipe_agro_id=equipe_id,
                nome=form["nome"],
                telefone=telefone_digits or None,
                ativo=ativo,
            )
            db.session.add(piloto)
            db.session.flush()

            usuario = Usuario(
                prefeitura_id=piloto.prefeitura_id,
                nome_uvis=piloto.nome,
                login=form["login"],
                tipo_usuario="piloto_agro",
                piloto_agro_id=piloto.id,
            )
            usuario.set_senha(form["senha"])
            db.session.add(usuario)
            db.session.commit()
            flash("Piloto agro cadastrado com sucesso.", "success")
            return redirect(url_for("main.agro_pilotos_listar"))

        return render_template("agro_piloto_form.html", form=form, errors=errors, modo="novo", equipes=equipes)

    @bp.route("/agro/pilotos/<int:piloto_id>/editar", methods=["GET", "POST"], endpoint="agro_piloto_editar")
    @login_required
    def agro_piloto_editar(piloto_id):
        _require_agro_edit()
        piloto = _get_piloto_agro_or_404(piloto_id)
        equipes = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id).order_by(EquipeAgro.nome.asc()).all()
        errors = {}
        if request.method == "POST":
            form = _normalize_piloto_form(request.form)
            errors, telefone_digits, equipe_id, _equipe, ativo = _validate_piloto_agro_form(form, equipes, piloto_atual=piloto)
            if errors:
                flash("Corrija os campos destacados do piloto agro.", "warning")
                return render_template("agro_piloto_form.html", form=form, errors=errors, modo="editar", piloto=piloto, equipes=equipes)

            piloto.nome = form["nome"]
            piloto.telefone = telefone_digits or None
            piloto.equipe_agro_id = equipe_id
            piloto.ativo = ativo
            usuario = piloto.usuario
            if usuario is None:
                usuario = Usuario(
                    prefeitura_id=piloto.prefeitura_id,
                    nome_uvis=piloto.nome,
                    login=form["login"],
                    tipo_usuario="piloto_agro",
                    piloto_agro_id=piloto.id,
                )
                db.session.add(usuario)

            usuario.prefeitura_id = piloto.prefeitura_id
            usuario.nome_uvis = piloto.nome
            usuario.login = form["login"]
            usuario.tipo_usuario = "piloto_agro"
            usuario.piloto_agro_id = piloto.id
            if form["senha"]:
                usuario.set_senha(form["senha"])
            db.session.commit()
            flash("Piloto agro atualizado com sucesso.", "success")
            return redirect(url_for("main.agro_pilotos_listar"))

        form = {
            "nome": piloto.nome or "",
            "telefone": format_phone_br(piloto.telefone or ""),
            "equipe_agro_id": str(piloto.equipe_agro_id or ""),
            "login": piloto.usuario.login if piloto.usuario else "",
            "senha": "",
            "confirmar_senha": "",
            "ativo": "SIM" if piloto.ativo else "NAO",
        }
        return render_template("agro_piloto_form.html", form=form, errors=errors, modo="editar", piloto=piloto, equipes=equipes)

    @bp.route("/agro/pilotos/<int:piloto_id>/deletar", methods=["POST"], endpoint="agro_piloto_deletar")
    @login_required
    def agro_piloto_deletar(piloto_id):
        _require_agro_edit()
        piloto = _get_piloto_agro_or_404(piloto_id)
        if piloto.usuario is not None:
            db.session.delete(piloto.usuario)
        db.session.delete(piloto)
        db.session.commit()
        flash("Piloto agro removido com sucesso.", "success")
        return redirect(url_for("main.agro_pilotos_listar"))

    @bp.route("/agro/equipamentos", methods=["GET"], endpoint="agro_equipamentos_listar")
    @login_required
    def agro_equipamentos_listar():
        _require_agro_access()
        q = (request.args.get("q") or "").strip()
        query = apply_prefeitura_scope(EquipamentoAgro.query, current_user, EquipamentoAgro.prefeitura_id)
        if q:
            query = query.filter(
                db.or_(
                    EquipamentoAgro.tipo.ilike(f"%{q}%"),
                    EquipamentoAgro.funcao_operacional.ilike(f"%{q}%"),
                    EquipamentoAgro.modelo.ilike(f"%{q}%"),
                    EquipamentoAgro.identificacao.ilike(f"%{q}%"),
                    EquipamentoAgro.numero_serie.ilike(f"%{q}%"),
                    EquipamentoAgro.registro_anatel.ilike(f"%{q}%"),
                    EquipamentoAgro.registro_anac.ilike(f"%{q}%"),
                )
            )
        equipamentos = query.order_by(EquipamentoAgro.identificacao.asc(), EquipamentoAgro.id.desc()).all()
        return render_template(
            "agro_equipamentos_listar.html",
            equipamentos=equipamentos,
            filters={"q": q, "total": len(equipamentos)},
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/equipamentos/cadastrar", methods=["GET", "POST"], endpoint="agro_equipamento_novo")
    @login_required
    def agro_equipamento_novo():
        _require_agro_edit()
        equipes = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id).order_by(EquipeAgro.nome.asc()).all()
        errors = {}
        form = _normalize_equipamento_form(request.form if request.method == "POST" else {})
        if request.method == "POST":
            errors, numero_serie, equipe_id, _equipe, capacidade_tanque_l, largura_faixa_m, altura_voo_padrao_m = _validate_equipamento_agro_form(form, equipes)
            if errors:
                flash("Corrija os campos destacados do equipamento agro.", "warning")
                return render_template("agro_equipamento_form.html", form=form, errors=errors, modo="novo", equipes=equipes)

            equipamento = EquipamentoAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                equipe_agro_id=equipe_id,
                tipo=form["tipo"],
                modelo=form["modelo"],
                identificacao=form["identificacao"],
                numero_serie=numero_serie,
                status=form["status"],
                funcao_operacional=form["funcao_operacional"] or None,
                registro_anatel=form["registro_anatel"] or None,
                registro_anac=form["registro_anac"] or None,
                capacidade_tanque_l=capacidade_tanque_l,
                largura_faixa_m=largura_faixa_m,
                altura_voo_padrao_m=altura_voo_padrao_m,
                ponta_pulverizacao=form["ponta_pulverizacao"] or None,
            )
            db.session.add(equipamento)
            db.session.commit()
            flash("Equipamento agro cadastrado com sucesso.", "success")
            return redirect(url_for("main.agro_equipamentos_listar"))

        return render_template("agro_equipamento_form.html", form=form, errors=errors, modo="novo", equipes=equipes)

    @bp.route("/agro/equipamentos/<int:equipamento_id>/editar", methods=["GET", "POST"], endpoint="agro_equipamento_editar")
    @login_required
    def agro_equipamento_editar(equipamento_id):
        _require_agro_edit()
        equipamento = _get_equipamento_agro_or_404(equipamento_id)
        equipes = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id).order_by(EquipeAgro.nome.asc()).all()
        errors = {}
        if request.method == "POST":
            form = _normalize_equipamento_form(request.form)
            errors, numero_serie, equipe_id, _equipe, capacidade_tanque_l, largura_faixa_m, altura_voo_padrao_m = _validate_equipamento_agro_form(form, equipes, equipamento_atual=equipamento)
            if errors:
                flash("Corrija os campos destacados do equipamento agro.", "warning")
                return render_template(
                    "agro_equipamento_form.html",
                    form=form,
                    errors=errors,
                    modo="editar",
                    equipamento=equipamento,
                    equipes=equipes,
                )

            equipamento.tipo = form["tipo"]
            equipamento.modelo = form["modelo"]
            equipamento.identificacao = form["identificacao"]
            equipamento.numero_serie = numero_serie
            equipamento.status = form["status"]
            equipamento.funcao_operacional = form["funcao_operacional"] or None
            equipamento.registro_anatel = form["registro_anatel"] or None
            equipamento.registro_anac = form["registro_anac"] or None
            equipamento.capacidade_tanque_l = capacidade_tanque_l
            equipamento.largura_faixa_m = largura_faixa_m
            equipamento.altura_voo_padrao_m = altura_voo_padrao_m
            equipamento.ponta_pulverizacao = form["ponta_pulverizacao"] or None
            equipamento.equipe_agro_id = equipe_id
            db.session.commit()
            flash("Equipamento agro atualizado com sucesso.", "success")
            return redirect(url_for("main.agro_equipamentos_listar"))

        form = {
            "tipo": equipamento.tipo or "",
            "modelo": equipamento.modelo or "",
            "identificacao": equipamento.identificacao or "",
            "numero_serie": equipamento.numero_serie or "",
            "status": equipamento.status or "Ativo",
            "funcao_operacional": equipamento.funcao_operacional or "",
            "registro_anatel": equipamento.registro_anatel or "",
            "registro_anac": equipamento.registro_anac or "",
            "capacidade_tanque_l": _format_decimal_br_value(equipamento.capacidade_tanque_l),
            "largura_faixa_m": _format_decimal_br_value(equipamento.largura_faixa_m),
            "altura_voo_padrao_m": _format_decimal_br_value(equipamento.altura_voo_padrao_m),
            "ponta_pulverizacao": equipamento.ponta_pulverizacao or "",
            "equipe_agro_id": str(equipamento.equipe_agro_id or ""),
        }
        return render_template(
            "agro_equipamento_form.html",
            form=form,
            errors=errors,
            modo="editar",
            equipamento=equipamento,
            equipes=equipes,
        )

    @bp.route("/agro/equipamentos/<int:equipamento_id>/deletar", methods=["POST"], endpoint="agro_equipamento_deletar")
    @login_required
    def agro_equipamento_deletar(equipamento_id):
        _require_agro_edit()
        equipamento = _get_equipamento_agro_or_404(equipamento_id)
        db.session.delete(equipamento)
        db.session.commit()
        flash("Equipamento agro removido com sucesso.", "success")
        return redirect(url_for("main.agro_equipamentos_listar"))

    @bp.app_template_filter("agro_endereco")
    def agro_endereco_filter(obj):
        if obj is None:
            return ""
        return build_endereco_agro(
            getattr(obj, "cep", None),
            getattr(obj, "logradouro", None),
            getattr(obj, "numero", None),
            getattr(obj, "complemento", None),
            getattr(obj, "bairro", None),
            getattr(obj, "cidade", None),
            getattr(obj, "uf", None),
        )
