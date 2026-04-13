from datetime import date, datetime
from io import BytesIO
import os
import uuid

from flask import current_app
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy import case
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Equipe, Solicitacao, Usuario
from app.shared.access import (
    ADMIN_PANEL_EDIT_TYPES,
    ADMIN_PANEL_VIEW_TYPES,
    apply_prefeitura_scope,
    apply_regiao_scope,
    apply_solicitacao_prefeitura_scope,
)
from app.shared.uploads import allowed_file, get_upload_folder
APPROVAL_STATUSES = {"APROVADO", "APROVADO COM RECOMENDAÇÕES"}


def can_access_admin_panel(user) -> bool:
    return getattr(user, "tipo_usuario", None) in ADMIN_PANEL_VIEW_TYPES


def can_edit_admin_panel(user) -> bool:
    return getattr(user, "tipo_usuario", None) in ADMIN_PANEL_EDIT_TYPES


def get_google_maps_key():
    return current_app.config.get("KEY_API_GOOGLE_MAPS") or os.getenv("KEY_API_GOOGLE_MAPS")


def build_uvis_select(user=None):
    query = Usuario.query.filter_by(tipo_usuario="uvis")
    if user is not None:
        query = apply_prefeitura_scope(query, user, Usuario.prefeitura_id)
        query = apply_regiao_scope(query, user, Usuario.regiao)
    return query.order_by(Usuario.nome_uvis.asc()).all()


def build_active_teams(user=None):
    query = Equipe.query.filter(Equipe.ativa.is_(True))
    if user is not None:
        query = apply_prefeitura_scope(query, user, Equipe.prefeitura_id)
        query = apply_regiao_scope(query, user, Equipe.regiao)
    return query.order_by(Equipe.regiao.asc(), Equipe.nome_equipe.asc()).all()


def build_status_order():
    return case(
        {
            "PENDENTE": 1,
            "EM ANALISE": 2,
            "EM ANÁLISE": 2,
            "APROVADO COM RECOMENDACOES": 3,
            "APROVADO COM RECOMENDAÇÕES": 3,
            "APROVADO": 4,
            "NEGADO": 5,
            "CONCLUIDO": 6,
            "CONCLUÍDO": 6,
        },
        value=Solicitacao.status,
        else_=99,
    )


def build_admin_dashboard_query(
    user,
    filtro_status: str,
    filtro_unidade: str,
    filtro_regiao: str,
    filtro_apoio_cet: str,
    filtro_protocolo: str,
    filtro_tipo_visita: str = "",
    filtro_tipo_imovel: str = "",
    filtro_foco: str = "",
):
    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .join(Usuario)
        .filter(Solicitacao.status != "CANCELADO")
    )
    query = apply_solicitacao_prefeitura_scope(query, user)
    query = apply_regiao_scope(query, user, Usuario.regiao)

    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    if filtro_unidade:
        query = query.filter(Usuario.nome_uvis.ilike(f"%{filtro_unidade}%"))

    if filtro_regiao:
        query = query.filter(Usuario.regiao.ilike(f"%{filtro_regiao}%"))

    if filtro_apoio_cet == "SIM":
        query = query.filter(Solicitacao.apoio_cet.is_(True))
    elif filtro_apoio_cet == "NAO":
        query = query.filter(Solicitacao.apoio_cet.is_(False))

    if filtro_protocolo:
        query = query.filter(Solicitacao.protocolo.ilike(f"%{filtro_protocolo}%"))

    if filtro_tipo_visita:
        query = query.filter(Solicitacao.tipo_visita == filtro_tipo_visita)

    if filtro_tipo_imovel:
        query = query.filter(Solicitacao.tipo_imovel == filtro_tipo_imovel)

    if filtro_foco:
        query = query.filter(Solicitacao.foco == filtro_foco)

    return query


def build_admin_canceladas_query(
    user,
    filtro_unidade: str,
    filtro_regiao: str,
    filtro_foco: str,
    filtro_protocolo: str,
    filtro_tipo_visita: str = "",
    filtro_tipo_imovel: str = "",
):
    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .join(Usuario)
        .filter(Solicitacao.status == "CANCELADO")
    )
    query = apply_solicitacao_prefeitura_scope(query, user)
    query = apply_regiao_scope(query, user, Usuario.regiao)

    if filtro_unidade:
        query = query.filter(Usuario.nome_uvis.ilike(f"%{filtro_unidade}%"))

    if filtro_regiao:
        query = query.filter(Usuario.regiao.ilike(f"%{filtro_regiao}%"))

    if filtro_foco:
        query = query.filter(Solicitacao.foco == filtro_foco)

    if filtro_tipo_visita:
        query = query.filter(Solicitacao.tipo_visita == filtro_tipo_visita)

    if filtro_tipo_imovel:
        query = query.filter(Solicitacao.tipo_imovel == filtro_tipo_imovel)

    if filtro_protocolo:
        query = query.filter(Solicitacao.protocolo.ilike(f"%{filtro_protocolo}%"))

    return query


def build_admin_historico_os_query(user, filtro_unidade: str, filtro_regiao: str):
    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .join(Usuario)
        .filter(Solicitacao.status.in_(["CONCLUÍDO", "CONCLUIDO"]))
    )
    query = apply_solicitacao_prefeitura_scope(query, user)
    query = apply_regiao_scope(query, user, Usuario.regiao)

    if filtro_unidade:
        query = query.filter(Usuario.nome_uvis.ilike(f"%{filtro_unidade}%"))

    if filtro_regiao:
        query = query.filter(Usuario.regiao.ilike(f"%{filtro_regiao}%"))

    return query


def build_admin_export_query(
    user,
    filtro_status: str,
    filtro_unidade: str,
    filtro_regiao: str,
    filtro_apoio_cet: str,
    filtro_protocolo: str,
    filtro_tipo_visita: str = "",
    filtro_tipo_imovel: str = "",
    filtro_foco: str = "",
):
    query = (
        Solicitacao.query
        .join(Usuario)
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
    )
    query = apply_solicitacao_prefeitura_scope(query, user)
    query = apply_regiao_scope(query, user, Usuario.regiao)

    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    if filtro_unidade:
        query = query.filter(Usuario.nome_uvis.ilike(f"%{filtro_unidade}%"))

    if filtro_regiao:
        query = query.filter(Usuario.regiao.ilike(f"%{filtro_regiao}%"))

    if filtro_apoio_cet == "SIM":
        query = query.filter(Solicitacao.apoio_cet.is_(True))
    elif filtro_apoio_cet == "NAO":
        query = query.filter(Solicitacao.apoio_cet.is_(False))

    if filtro_protocolo:
        query = query.filter(Solicitacao.protocolo.ilike(f"%{filtro_protocolo}%"))

    if filtro_tipo_visita:
        query = query.filter(Solicitacao.tipo_visita == filtro_tipo_visita)

    if filtro_tipo_imovel:
        query = query.filter(Solicitacao.tipo_imovel == filtro_tipo_imovel)

    if filtro_foco:
        query = query.filter(Solicitacao.foco == filtro_foco)

    return query.order_by(Solicitacao.data_criacao.desc())


def build_admin_dashboard_export(
    user,
    filtro_status: str,
    filtro_unidade: str,
    filtro_regiao: str,
    filtro_apoio_cet: str,
    filtro_protocolo: str,
    filtro_tipo_visita: str = "",
    filtro_tipo_imovel: str = "",
    filtro_foco: str = "",
):
    pedidos = build_admin_export_query(
        user=user,
        filtro_status=filtro_status,
        filtro_unidade=filtro_unidade,
        filtro_regiao=filtro_regiao,
        filtro_apoio_cet=filtro_apoio_cet,
        filtro_protocolo=filtro_protocolo,
        filtro_tipo_visita=filtro_tipo_visita,
        filtro_tipo_imovel=filtro_tipo_imovel,
        filtro_foco=filtro_foco,
    ).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Relatorio de Solicitacoes"

    headers = [
        "ID",
        "Unidade",
        "Regiao",
        "Equipe Responsavel",
        "Data Agendada",
        "Hora",
        "Endereco Completo",
        "Latitude",
        "Longitude",
        "Foco",
        "Tipo Operacao",
        "Tipo Visita",
        "Tipo Imovel",
        "Altura",
        "Apoio CET?",
        "Observacao",
        "Status",
        "Protocolo",
        "Justificativa",
    ]

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for column, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=column, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    for row_number, pedido in enumerate(pedidos, start=2):
        uvis_nome = pedido.usuario.nome_uvis if pedido.usuario else "Nao informado"
        uvis_regiao = pedido.usuario.regiao if pedido.usuario else "Nao informado"

        equipe_nome = ""
        if getattr(pedido, "equipe", None):
            equipe_nome = pedido.equipe.nome_equipe or ""
        elif getattr(pedido, "equipe_id", None):
            equipe_nome = f"ID #{pedido.equipe_id}"

        endereco_completo = (
            f"{pedido.logradouro or ''}, {pedido.numero or ''} - "
            f"{pedido.bairro or ''} - "
            f"{(pedido.cidade or '')}/{(pedido.uf or '')} - {pedido.cep or ''}"
        )
        if pedido.complemento:
            endereco_completo += f" - {pedido.complemento}"

        data_formatada = ""
        if pedido.data_agendamento:
            if isinstance(pedido.data_agendamento, (date, datetime)):
                data_formatada = pedido.data_agendamento.strftime("%d/%m/%Y")
            else:
                data_formatada = str(pedido.data_agendamento)

        row = [
            pedido.id,
            uvis_nome,
            uvis_regiao,
            equipe_nome,
            data_formatada,
            str(pedido.hora_agendamento or ""),
            endereco_completo,
            pedido.latitude or "",
            pedido.longitude or "",
            pedido.foco,
            pedido.tipo_operacao or "",
            pedido.tipo_visita or "",
            pedido.tipo_imovel or "",
            pedido.altura_voo or "",
            "SIM" if pedido.apoio_cet else "NAO",
            pedido.observacao or "",
            pedido.status,
            pedido.protocolo or "",
            pedido.justificativa or "",
        ]

        for column, value in enumerate(row, start=1):
            cell = ws.cell(row=row_number, column=column, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    ws.freeze_panes = "A2"

    for column_cells in ws.columns:
        max_length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 50)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def apply_admin_update_fields(pedido, form, *, user=None):
    pedido.protocolo = form.get("protocolo")
    pedido.status = form.get("status")
    pedido.justificativa = form.get("justificativa")
    pedido.latitude = form.get("latitude")
    pedido.longitude = form.get("longitude")

    equipe_id = form.get("equipe_id")
    if equipe_id in (None, "", "null", "undefined"):
        pedido.equipe_id = None
        equipe_nome = None
    else:
        try:
            equipe_id_int = int(equipe_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Equipe invalida.") from exc

        equipe_query = Equipe.query.filter(Equipe.id == equipe_id_int)
        if user is not None:
            equipe_query = apply_prefeitura_scope(equipe_query, user, Equipe.prefeitura_id)
            equipe_query = apply_regiao_scope(equipe_query, user, Equipe.regiao)
        equipe = equipe_query.first()
        if not equipe:
            raise ValueError("Equipe selecionada nao existe.")

        pedido.equipe_id = equipe_id_int
        equipe_nome = equipe.nome_equipe

    if pedido.status in APPROVAL_STATUSES and not pedido.equipe_id:
        raise ValueError("Para aprovar, selecione uma equipe responsavel.")

    return equipe_nome


def save_admin_attachment(pedido, uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None

    if not allowed_file(uploaded_file.filename):
        raise ValueError("Formato de arquivo nao permitido.")

    original_filename = secure_filename(uploaded_file.filename)
    ext = original_filename.rsplit(".", 1)[1].lower()
    unique_name = f"sol_{pedido.id}_{uuid.uuid4().hex}.{ext}"
    upload_folder = get_upload_folder()
    file_path = os.path.join(upload_folder, unique_name)

    uploaded_file.save(file_path)

    pedido.anexo_path = f"upload-files/{unique_name}"
    pedido.anexo_nome = original_filename
    return original_filename
