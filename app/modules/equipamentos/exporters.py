import os
import tempfile
from datetime import datetime

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OCEANO_BLUE = colors.HexColor("#1f4f82")
OCEANO_BLUE_LIGHT = colors.HexColor("#eaf2fb")
TEXT_DARK = colors.HexColor("#263247")
TEXT_MUTED = colors.HexColor("#6b778d")
BORDER = colors.HexColor("#d9e2ef")


def _fmt_dt(value):
    if not value:
        return "-"
    try:
        return value.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


def _fmt_date(value):
    if not value:
        return "-"
    try:
        return value.strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def _safe(value):
    text = "" if value is None else str(value)
    return text if text.strip() else "-"


def _logo_path():
    return os.path.join(current_app.root_path, "static", "img", "logo_oceano_azul_light.png")


def _try_make_logo(width_mm=36):
    try:
        path = _logo_path()
        if not os.path.exists(path):
            return None
        logo = RLImage(path)
        logo.drawWidth = width_mm * mm
        logo.drawHeight = (width_mm * 0.55) * mm
        return logo
    except Exception:
        return None


def _header_footer(canvas, doc):
    canvas.saveState()
    page_width, page_height = A4

    logo = _try_make_logo(width_mm=30)
    if logo:
        logo.drawOn(canvas, doc.leftMargin, page_height - 14 * mm - logo.drawHeight)

    canvas.setFillColor(OCEANO_BLUE)
    canvas.roundRect(doc.leftMargin, page_height - 31 * mm, doc.width, 2.2 * mm, 2, fill=1, stroke=0)

    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(doc.leftMargin + doc.width, page_height - 15 * mm, f"Página {canvas.getPageNumber()}")

    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.7)
    canvas.line(doc.leftMargin, 22 * mm, doc.leftMargin + doc.width, 22 * mm)

    canvas.setFillColor(OCEANO_BLUE)
    canvas.setFont("Helvetica-Bold", 7.4)
    canvas.drawCentredString(page_width / 2, 16.5 * mm, "OCEANO AZUL COMERCIO INTERNACIONAL LTDA")
    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 6.2)
    canvas.drawCentredString(page_width / 2, 12.8 * mm, "Alameda Rio Negro, 503 - sala 2401")
    canvas.drawCentredString(page_width / 2, 9.8 * mm, "Alphaville Centro Industrial e Empresarial - Barueri SP")
    canvas.restoreState()


def _info_table(rows):
    table = Table(rows, colWidths=[38 * mm, 55 * mm, 32 * mm, 55 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), OCEANO_BLUE_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _pecas_table(usos):
    rows = [["Peça", "Nº de série", "Qtd.", "Data", "Responsável", "Observações"]]
    for uso in usos:
        peca = uso.peca
        usuario = uso.usuario
        rows.append([
            _safe(getattr(peca, "modelo_peca", None)),
            _safe(getattr(peca, "numero_serie", None)),
            str(uso.quantidade_usada or 0),
            _fmt_dt(uso.criado_em),
            _safe(getattr(usuario, "nome_uvis", None)),
            _safe(uso.observacoes),
        ])

    if len(rows) == 1:
        rows.append(["Nenhuma peça registrada.", "-", "-", "-", "-", "-"])

    table = Table(rows, colWidths=[33 * mm, 28 * mm, 14 * mm, 27 * mm, 30 * mm, 38 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), OCEANO_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("TEXTCOLOR", (0, 1), (-1, -1), TEXT_DARK),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def build_manutencao_pdf(drone, usos, manutencao=None):
    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    path = tmp_pdf.name
    tmp_pdf.close()

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=38 * mm,
        bottomMargin=28 * mm,
        title=f"Manutenção {drone.renomacao}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "maintenance_title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=OCEANO_BLUE,
        alignment=0,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "maintenance_subtitle",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        textColor=TEXT_MUTED,
        spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "maintenance_section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=OCEANO_BLUE,
        spaceBefore=12,
        spaceAfter=8,
    )

    total_pecas = sum((uso.quantidade_usada or 0) for uso in usos)
    aberta_em = _fmt_dt(getattr(manutencao, "aberta_em", None)) if manutencao else "-"
    encerrada_em = _fmt_dt(getattr(manutencao, "encerrada_em", None)) if manutencao else "-"
    status_manutencao = _safe(getattr(manutencao, "status", None)).capitalize() if manutencao else "Aberta"
    story = [
        Paragraph("Relatório de manutenção", title_style),
        Paragraph(
            f"Peças usadas na manutenção do drone {drone.renomacao}. Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')}.",
            subtitle_style,
        ),
        _info_table([
            ["Drone", _safe(drone.renomacao), "Modelo", _safe(drone.modelo)],
            ["Nº de série", _safe(drone.numero_serie), "Status atual", _safe(drone.status)],
            ["Equipe", _safe(getattr(getattr(drone, "equipe", None), "nome_equipe", None)), "Status manutenção", status_manutencao],
            ["Abertura", aberta_em, "Encerramento", encerrada_em],
            ["Total de itens usados", str(total_pecas), "Registros", str(len(usos))],
        ]),
        Spacer(1, 8 * mm),
        Paragraph("Peças utilizadas", section_style),
        _pecas_table(usos),
    ]

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return path
