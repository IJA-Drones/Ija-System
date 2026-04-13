from __future__ import annotations

from datetime import datetime
import os
import uuid

from flask import current_app
from sqlalchemy import false, or_
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.utils import secure_filename

from app.models import (
    ClienteAgro,
    ContratoAgro,
    EquipamentoAgro,
    EquipeAgro,
    FinanceiroAgro,
    OrcamentoAgro,
    OrdemServicoAgro,
    PilotoAgro,
)
from app.shared.access import ADMIN_PANEL_EDIT_TYPES, ADMIN_PANEL_VIEW_TYPES, apply_prefeitura_scope, normalize_role
from app.shared.formatters import format_cep, format_currency_br, format_documento, only_digits
from app.shared.uploads import get_upload_folder


def can_access_agro_panel(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in ADMIN_PANEL_VIEW_TYPES


def can_edit_agro_panel(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in ADMIN_PANEL_EDIT_TYPES


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
    )
    query = apply_prefeitura_scope(query, user, FinanceiroAgro.prefeitura_id)

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                FinanceiroAgro.cliente_nome.ilike(like),
                FinanceiroAgro.cultura.ilike(like),
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
