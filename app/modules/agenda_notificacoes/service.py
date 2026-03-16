import json
import os
from datetime import date, datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from flask import current_app, url_for
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Notificacao, Solicitacao, Usuario


ADMIN_VIEW_TYPES = {"admin", "operario", "visualizar"}
AGENDA_ROUTE_STATUSES = (
    "APROVADO",
    "APROVADO COM RECOMENDACOES",
    "APROVADO COM RECOMENDAÇÕES",
)
TZ_BR = ZoneInfo("America/Sao_Paulo")


def agenda_status_color(status):
    if status == "APROVADO":
        return "#198754"
    if status == "APROVADO COM RECOMENDAÇÕES":
        return "#ffa023"
    if status == "NEGADO":
        return "#dc3545"
    if status == "EM ANÁLISE":
        return "#e9fa05"
    return "#0d6efd"


def agora_brasilia_naive():
    return datetime.now(TZ_BR).replace(tzinfo=None)


def can_view_all_agenda(user):
    return getattr(user, "tipo_usuario", None) in ADMIN_VIEW_TYPES


def get_agenda_google_maps_key():
    return current_app.config.get("Maps_KEY_FRONT") or os.getenv("KEY_API_GOOGLE_MAPS") or ""


def build_agenda_query(user, *, filtro_status=None, filtro_uvis_id=None, mes=None, ano=None):
    query = (
        Solicitacao.query
        .options(joinedload(Solicitacao.usuario))
        .filter(Solicitacao.status != "CANCELADO")
    )

    if not can_view_all_agenda(user):
        query = query.filter(Solicitacao.usuario_id == user.id)
        filtro_uvis_id = None
    elif filtro_uvis_id:
        query = query.filter(Solicitacao.usuario_id == filtro_uvis_id)

    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    if mes and ano:
        filtro_mesano = f"{ano}-{mes:02d}"
        if db.engine.name == "postgresql":
            query = query.filter(db.func.to_char(Solicitacao.data_agendamento, "YYYY-MM") == filtro_mesano)
        else:
            query = query.filter(db.func.strftime("%Y-%m", Solicitacao.data_agendamento) == filtro_mesano)

    return query


def build_agenda_eventos(solicitacoes):
    agenda_eventos = []

    for solicitacao in solicitacoes:
        if not solicitacao.data_agendamento:
            continue

        data = solicitacao.data_agendamento.strftime("%Y-%m-%d")
        hora = solicitacao.hora_agendamento.strftime("%H:%M") if solicitacao.hora_agendamento else "00:00"
        uvis_nome = (solicitacao.usuario.nome_uvis if solicitacao.usuario else "UVIS") or "UVIS"

        lat = None
        lng = None
        try:
            if solicitacao.latitude is not None and str(solicitacao.latitude).strip() != "":
                lat = float(str(solicitacao.latitude).replace(",", "."))
            if solicitacao.longitude is not None and str(solicitacao.longitude).strip() != "":
                lng = float(str(solicitacao.longitude).replace(",", "."))
        except Exception:
            lat = None
            lng = None

        logradouro = (solicitacao.logradouro or "").strip()
        numero = solicitacao.numero or "S/N"
        bairro = (solicitacao.bairro or "").strip()
        cidade = (getattr(solicitacao, "cidade", "") or "").strip()
        uf = (getattr(solicitacao, "uf", "") or "").strip()
        cep = (solicitacao.cep or "").strip()

        partes = []
        if logradouro:
            partes.append(f"{logradouro}, {numero}")
        elif numero:
            partes.append(str(numero))

        if bairro:
            partes.append(bairro)

        if cidade or uf:
            partes.append(f"{cidade}/{uf}".strip("/"))

        endereco_txt = " - ".join([parte for parte in partes if parte and parte != "S/N"])
        if cep:
            endereco_txt = (endereco_txt + f" (CEP {cep})").strip()

        agenda_eventos.append(
            {
                "id": str(solicitacao.id),
                "title": f"{solicitacao.foco} - {uvis_nome}",
                "start": f"{data}T{hora}",
                "color": agenda_status_color(solicitacao.status),
                "extendedProps": {
                    "foco": solicitacao.foco,
                    "uvis": uvis_nome,
                    "hora": hora,
                    "status": solicitacao.status,
                    "lat": lat,
                    "lng": lng,
                    "endereco": endereco_txt,
                },
            }
        )

    return agenda_eventos


def build_agenda_uvis_disponiveis(user):
    if not can_view_all_agenda(user):
        return []

    return (
        db.session.query(Usuario.id, Usuario.nome_uvis)
        .filter(Usuario.tipo_usuario == "uvis")
        .order_by(Usuario.nome_uvis)
        .all()
    )


def build_agenda_anos_disponiveis():
    if db.engine.name == "postgresql":
        func_ano = db.func.to_char(Solicitacao.data_agendamento, "YYYY")
    else:
        func_ano = db.func.strftime("%Y", Solicitacao.data_agendamento)

    anos_raw = (
        db.session.query(func_ano)
        .filter(Solicitacao.data_agendamento.isnot(None))
        .distinct()
        .order_by(func_ano.desc())
        .all()
    )
    return [int(item[0]) for item in anos_raw if item and item[0]] or [datetime.now().year]


def build_agenda_context(user, args):
    filtro_status = (args.get("status") or "").strip() or None
    filtro_uvis_id = args.get("uvis_id", type=int)
    mes = args.get("mes", datetime.now().month, type=int)
    ano = args.get("ano", datetime.now().year, type=int)
    d = (args.get("d") or "").strip()
    initial_date = d or datetime.now().strftime("%Y-%m-%d")

    solicitacoes = build_agenda_query(
        user,
        filtro_status=filtro_status,
        filtro_uvis_id=filtro_uvis_id,
        mes=mes,
        ano=ano,
    ).all()

    return {
        "eventos_json": json.dumps(build_agenda_eventos(solicitacoes), ensure_ascii=False),
        "filtros": {
            "uvis_id": filtro_uvis_id if can_view_all_agenda(user) else None,
            "status": filtro_status,
            "mes": mes,
            "ano": ano,
        },
        "status_opcoes": [
            "PENDENTE",
            "EM ANÁLISE",
            "APROVADO",
            "APROVADO COM RECOMENDAÇÕES",
            "NEGADO",
        ],
        "uvis_disponiveis": build_agenda_uvis_disponiveis(user),
        "anos_disponiveis": build_agenda_anos_disponiveis(),
        "initial_date": initial_date,
        "pode_filtrar_uvis": can_view_all_agenda(user),
        "google_maps_key": get_agenda_google_maps_key(),
    }


def build_agenda_rotas_payload(user, args):
    dia = (args.get("dia") or "").strip()
    if not dia:
        raise ValueError("Par\u00e2metro 'dia' \u00e9 obrigat\u00f3rio (YYYY-MM-DD).")

    try:
        dia_date = datetime.strptime(dia, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Formato inv\u00e1lido para 'dia'. Use YYYY-MM-DD.") from exc

    filtro_uvis_id = args.get("uvis_id", type=int)

    query = Solicitacao.query.options(joinedload(Solicitacao.usuario))
    if not can_view_all_agenda(user):
        query = query.filter(Solicitacao.usuario_id == user.id)
    elif filtro_uvis_id:
        query = query.filter(Solicitacao.usuario_id == filtro_uvis_id)

    query = query.filter(Solicitacao.status.in_(AGENDA_ROUTE_STATUSES))
    query = query.filter(Solicitacao.data_agendamento == dia_date)

    eventos = query.order_by(Solicitacao.hora_agendamento.asc()).all()

    pontos = []
    total_com_coords = 0
    for evento in eventos:
        lat = evento.latitude
        lng = evento.longitude

        try:
            if isinstance(lat, str):
                lat = float(lat.replace(",", "."))
            else:
                lat = float(lat) if lat is not None else None

            if isinstance(lng, str):
                lng = float(lng.replace(",", "."))
            else:
                lng = float(lng) if lng is not None else None
        except Exception:
            lat = None
            lng = None

        if lat is None or lng is None:
            continue

        total_com_coords += 1
        pontos.append(
            {
                "id": evento.id,
                "lat": lat,
                "lng": lng,
                "hora": evento.hora_agendamento.strftime("%H:%M") if evento.hora_agendamento else "00:00",
                "uvis": evento.usuario.nome_uvis if evento.usuario else "",
                "foco": evento.foco or "",
                "status": evento.status,
                "endereco": f"{evento.logradouro or ''}, {evento.numero or 'S/N'} - {evento.bairro or ''}".strip(),
            }
        )

    return {
        "ok": True,
        "dia": dia,
        "total_eventos": len(eventos),
        "total_com_coordenadas": total_com_coords,
        "pontos": pontos,
    }


def build_agenda_export(args):
    export_all = args.get("all") == "1"

    filtro_status = None if export_all else (args.get("status") or None)
    filtro_uvis_id = None if export_all else args.get("uvis_id", type=int)
    mes = None if export_all else args.get("mes", type=int)
    ano = None if export_all else args.get("ano", type=int)

    query = Solicitacao.query.options(joinedload(Solicitacao.usuario))

    if filtro_uvis_id:
        query = query.filter(Solicitacao.usuario_id == filtro_uvis_id)
    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)
    if mes and ano:
        filtro_mesano = f"{ano}-{mes:02d}"
        if db.engine.name == "postgresql":
            query = query.filter(db.func.to_char(Solicitacao.data_agendamento, "YYYY-MM") == filtro_mesano)
        else:
            query = query.filter(db.func.strftime("%Y-%m", Solicitacao.data_agendamento) == filtro_mesano)

    eventos = query.order_by(
        Solicitacao.data_agendamento.desc(),
        Solicitacao.hora_agendamento.desc(),
    ).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Agenda"

    headers = [
        "DATA",
        "HORÁRIO",
        "REGIÃO",
        "UVIS",
        "CET",
        "ENDEREÇO DA AÇÃO",
        "CEP",
        "FOCO DA AÇÃO",
        "COORDENADA GEOGRÁFICA",
        "Altura dos Voos",
        "Protocolo DECA",
        "Status",
    ]
    ws.append(headers)

    for evento in eventos:
        endereco_completo = (
            f"{evento.logradouro or ''}, {getattr(evento, 'numero', '')} - "
            f"{evento.bairro or ''} - "
            f"{(evento.cidade or '')}/{(evento.uf or '')} - "
            f"{evento.cep or ''}"
        )
        if getattr(evento, "complemento", None):
            endereco_completo += f" - {evento.complemento}"

        cet_txt = "SIM" if getattr(evento, "apoio_cet", None) else "NÃO"
        data_str = evento.data_agendamento.strftime("%d/%m/%Y") if evento.data_agendamento else ""
        hora_str = evento.hora_agendamento.strftime("%H:%M") if evento.hora_agendamento else ""
        uvis_nome = evento.usuario.nome_uvis if getattr(evento, "usuario", None) else ""
        regiao = evento.usuario.regiao if getattr(evento, "usuario", None) else ""
        lat = getattr(evento, "latitude", "") or ""
        lon = getattr(evento, "longitude", "") or ""
        coordenada = f"{lat},{lon}" if (lat or lon) else ""
        protocolo_deca = getattr(evento, "protocolo_deca", None) or getattr(evento, "protocolo", "") or ""

        ws.append(
            [
                data_str,
                hora_str,
                regiao,
                uvis_nome,
                cet_txt,
                endereco_completo,
                getattr(evento, "cep", "") or "",
                getattr(evento, "foco", "") or "",
                coordenada,
                getattr(evento, "altura_voo", "") or "",
                protocolo_deca,
                getattr(evento, "status", "") or "",
            ]
        )

    header_fill = PatternFill("solid", fgColor="0D6EFD")
    header_font = Font(bold=True, color="FFFFFF")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    wrap = Alignment(vertical="top", wrap_text=True)

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center

    thin = Side(style="thin", color="D0D7DE")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            cell.border = border
            cell.alignment = wrap if cell.row > 1 else center

    for col in range(1, ws.max_column + 1):
        max_len = max(len(str(cell.value)) if cell.value else 0 for cell in ws[get_column_letter(col)])
        ws.column_dimensions[get_column_letter(col)].width = min(max(12, max_len + 2), 60)

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    return bio, ("agenda_tudo.xlsx" if export_all else "agenda_exportada.xlsx")


def criar_notificacao(usuario_id, titulo, mensagem="", link=None, commit=True):
    notificacao = Notificacao(
        usuario_id=usuario_id,
        titulo=titulo,
        mensagem=mensagem or "",
        link=link,
        criada_em=agora_brasilia_naive(),
    )
    db.session.add(notificacao)
    if commit:
        db.session.commit()
    return notificacao


def garantir_notificacoes_do_dia(usuario_id):
    hoje = date.today()

    agendamentos = (
        Solicitacao.query
        .options(joinedload(Solicitacao.usuario))
        .filter_by(usuario_id=usuario_id)
        .filter(Solicitacao.data_agendamento == hoje)
        .all()
    )

    for solicitacao in agendamentos:
        hora_fmt = solicitacao.hora_agendamento.strftime("%H:%M") if solicitacao.hora_agendamento else "00:00"
        link = url_for("main.agenda", sid=solicitacao.id, d=hoje.isoformat())

        ja_existe = (
            Notificacao.query
            .filter_by(usuario_id=usuario_id, link=link)
            .first()
        )
        if ja_existe:
            continue

        criar_notificacao(
            usuario_id=usuario_id,
            titulo="Agendamento para hoje",
            mensagem=f"Você tem um agendamento hoje às {hora_fmt} (Foco: {solicitacao.foco}).",
            link=link,
        )


def get_notificacao_or_404(user, notif_id):
    if can_view_all_agenda(user):
        return Notificacao.query.get_or_404(notif_id)

    return (
        Notificacao.query
        .filter_by(id=notif_id, usuario_id=user.id)
        .first_or_404()
    )


def list_notificacoes(user):
    if not can_view_all_agenda(user):
        garantir_notificacoes_do_dia(user.id)

    base = Notificacao.query.filter(Notificacao.apagada_em.is_(None))
    if can_view_all_agenda(user):
        return base.order_by(Notificacao.criada_em.desc()).all()

    return (
        base
        .filter_by(usuario_id=user.id)
        .order_by(Notificacao.criada_em.desc())
        .all()
    )


def mark_notificacao_as_read(notificacao):
    if notificacao.lida_em is None:
        notificacao.lida_em = agora_brasilia_naive()
        db.session.commit()


def soft_delete_notificacao(notificacao):
    notificacao.apagada_em = agora_brasilia_naive()
    db.session.commit()


def clear_notificacoes(user):
    agora = agora_brasilia_naive()
    query = Notificacao.query.filter(Notificacao.apagada_em.is_(None))

    if not can_view_all_agenda(user):
        query = query.filter_by(usuario_id=user.id)

    query.update({"apagada_em": agora}, synchronize_session=False)
    db.session.commit()
