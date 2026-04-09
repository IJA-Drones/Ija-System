from __future__ import annotations

from decimal import Decimal
from io import BytesIO
import os
from xml.sax.saxutils import escape

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.agro.service import agro_bool_label
from app.shared.formatters import format_currency_br


IJA_GREEN = colors.HexColor("#6FD11A")
IJA_GREEN_DARK = colors.HexColor("#2E8B57")
TEXT_MAIN = colors.HexColor("#142033")
TEXT_MUTED = colors.HexColor("#5C6A80")
BORDER = colors.HexColor("#DCE5EC")
SURFACE = colors.HexColor("#F7FBF8")
SURFACE_SOFT = colors.HexColor("#EFFAEC")


def _logo_path():
    return os.path.join(current_app.root_path, "static", "img", "logo ija.jpg")


def _try_make_agro_logo(width_mm=42):
    path = _logo_path()
    if not os.path.exists(path):
        return None

    try:
        image = RLImage(path)
        width_pt = width_mm * mm
        img_width = float(getattr(image, "imageWidth", 0) or 1)
        img_height = float(getattr(image, "imageHeight", 0) or 1)
        image.drawWidth = width_pt
        image.drawHeight = width_pt * (img_height / img_width)
        return image
    except Exception:
        return None


def _build_page_frame(canvas, doc):
    canvas.saveState()

    page_width, page_height = A4
    margin_left = doc.leftMargin
    margin_right = doc.rightMargin
    usable_width = page_width - margin_left - margin_right

    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    canvas.setFillColor(SURFACE)
    canvas.roundRect(margin_left, page_height - 44 * mm, usable_width, 24 * mm, 10, fill=1, stroke=0)

    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.7)
    canvas.line(margin_left, 18 * mm, page_width - margin_right, 18 * mm)

    footer_text = "IJA Drones | Tecnologia e Inovacao"
    page_text = f"Pagina {canvas.getPageNumber()}"

    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(margin_left, 11 * mm, footer_text)
    page_width_text = stringWidth(page_text, "Helvetica", 8.5)
    canvas.drawString(page_width - margin_right - page_width_text, 11 * mm, page_text)
    canvas.restoreState()


def _paragraph(value, style, fallback="-"):
    if isinstance(value, Paragraph):
        return value

    text = fallback if value in (None, "") else str(value)
    text = escape(text).replace("\n", "<br/>")
    return Paragraph(text, style)


def _money(value, fallback="R$ 0,00"):
    formatted = format_currency_br(value)
    return formatted or fallback


def _decimal(value):
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _format_operation_address(orcamento):
    line_1_parts = [part for part in [orcamento.logradouro, f"No {orcamento.numero}" if orcamento.numero else ""] if part]
    city_region = f"{orcamento.cidade}/{orcamento.uf}" if orcamento.cidade and orcamento.uf else (orcamento.cidade or orcamento.uf or "")
    line_2_parts = [part for part in [orcamento.bairro, city_region] if part]
    line_3_parts = [part for part in [f"CEP {orcamento.cep}" if orcamento.cep else "", orcamento.complemento] if part]

    lines = []
    if line_1_parts:
        lines.append(escape(", ".join(line_1_parts)))
    if line_2_parts:
        lines.append(escape(" - ".join(line_2_parts)))
    if line_3_parts:
        lines.append(escape(" | ".join(line_3_parts)))
    return "<br/>".join(lines)


def _label_value_table(rows, label_style, value_style, *, label_width=42 * mm, value_width=122 * mm):
    normalized_rows = [[_paragraph(label, label_style), _paragraph(value, value_style)] for label, value in rows]
    table = Table(normalized_rows, colWidths=[label_width, value_width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF8E2")),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_MAIN),
                ("GRID", (0, 0), (-1, -1), 0.65, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("WORDWRAP", (0, 0), (-1, -1), "CJK"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _info_box(title, body, title_style, body_style, width):
    table = Table([[ _paragraph(title, title_style) ], [ _paragraph(body, body_style) ]], colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.85, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _build_service_line_items(orcamento):
    service_name = (orcamento.servico or "").lower()
    line_items = []

    include_mapping = bool(orcamento.mapeamento or "mapeamento" in service_name or _decimal(orcamento.preco_mapeamento) > 0)
    include_spraying = bool("pulver" in service_name or _decimal(orcamento.preco_pulverizacao) > 0)

    if include_mapping:
        line_items.append(("Servico de mapeamento", f"{_money(orcamento.preco_mapeamento)} por Ha"))

    if include_spraying:
        line_items.append(("Servico de pulverizacao", f"{_money(orcamento.preco_pulverizacao)} por Ha"))

    if not line_items:
        line_items.append(("Servico contratado", orcamento.servico or "Nao informado"))

    return line_items


def _service_breakdown_table(line_items, total_value, item_label_style, item_value_style, total_label_style, total_value_style):
    rows = [[_paragraph(label, item_label_style), _paragraph(value, item_value_style)] for label, value in line_items]
    rows.append([_paragraph("Total da proposta", total_label_style), _paragraph(_money(total_value), total_value_style)])

    table = Table(rows, colWidths=[112 * mm, 53 * mm])
    total_row = len(rows) - 1
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -2), colors.white),
                ("BACKGROUND", (0, total_row), (-1, total_row), SURFACE_SOFT),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_MAIN),
                ("LINEABOVE", (0, 0), (-1, 0), 0.85, BORDER),
                ("LINEBELOW", (0, -1), (-1, -1), 0.85, BORDER),
                ("LINEBELOW", (0, 0), (-1, -2), 0.55, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    return table


def build_orcamento_agro_pdf(orcamento):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=f"Orcamento Agro #{orcamento.id}",
        author="IJA Drones",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AgroPdfTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=TEXT_MAIN,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "AgroPdfSubtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=12,
        textColor=TEXT_MUTED,
    )
    section_style = ParagraphStyle(
        "AgroPdfSection",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        textColor=IJA_GREEN_DARK,
        spaceBefore=2,
        spaceAfter=6,
    )
    label_style = ParagraphStyle(
        "AgroPdfLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9.1,
        leading=12,
        textColor=TEXT_MAIN,
    )
    value_style = ParagraphStyle(
        "AgroPdfValue",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.3,
        leading=12.8,
        textColor=TEXT_MAIN,
    )
    note_style = ParagraphStyle(
        "AgroPdfNote",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.9,
        leading=12,
        textColor=TEXT_MUTED,
    )
    service_label_style = ParagraphStyle(
        "AgroPdfServiceLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12.5,
        textColor=TEXT_MAIN,
    )
    service_value_style = ParagraphStyle(
        "AgroPdfServiceValue",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12.5,
        textColor=TEXT_MAIN,
        alignment=2,
    )
    total_label_style = ParagraphStyle(
        "AgroPdfTotalLabel",
        parent=service_label_style,
        fontSize=11,
        leading=13.5,
        textColor=IJA_GREEN_DARK,
    )
    total_value_style = ParagraphStyle(
        "AgroPdfTotalValue",
        parent=service_value_style,
        fontSize=14,
        leading=17,
        textColor=IJA_GREEN_DARK,
    )
    card_title_style = ParagraphStyle(
        "AgroPdfCardTitle",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=IJA_GREEN_DARK,
        spaceAfter=4,
    )
    card_body_style = ParagraphStyle(
        "AgroPdfCardBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.3,
        leading=13,
        textColor=TEXT_MAIN,
    )

    logo = _try_make_agro_logo()
    company_lines = [
        Paragraph("Proposta Comercial Agro", title_style),
        Paragraph("IJA Drones | Tecnologia e Inovacao", subtitle_style),
        Paragraph(f"Documento gerado para apresentacao ao cliente | Orcamento #{orcamento.id}", subtitle_style),
    ]

    if logo:
        header = Table([[logo, company_lines]], colWidths=[46 * mm, 119 * mm])
    else:
        header = Table([[company_lines]], colWidths=[165 * mm])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    service_breakdown = _service_breakdown_table(
        _build_service_line_items(orcamento),
        orcamento.preco_base,
        service_label_style,
        service_value_style,
        total_label_style,
        total_value_style,
    )

    proposal_left = _label_value_table(
        [
            ["Cliente", orcamento.cliente_nome],
            ["Fazenda", orcamento.nome_fazenda],
            ["Servico", orcamento.servico or "Nao informado"],
            ["Cultura", orcamento.cultura or "Nao informada"],
        ],
        label_style,
        value_style,
        label_width=30 * mm,
        value_width=51 * mm,
    )
    proposal_right = _label_value_table(
        [
            ["Mapeamento", agro_bool_label(orcamento.mapeamento)],
            ["Protocolo DECEA", orcamento.protocolo or "Nao informado"],
            ["Emissao", orcamento.data_criacao.strftime("%d/%m/%Y as %H:%M") if orcamento.data_criacao else "-"],
            ["Orcamento", f"#{orcamento.id}"],
        ],
        label_style,
        value_style,
        label_width=31 * mm,
        value_width=53 * mm,
    )
    proposal_grid = Table([[proposal_left, proposal_right]], colWidths=[81 * mm, 84 * mm])
    proposal_grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    address_html = _format_operation_address(orcamento) or "Endereco nao informado"
    if orcamento.nome_fazenda:
        address_html = f"<b>{escape(orcamento.nome_fazenda)}</b><br/>{address_html}"

    address_box = _info_box(
        "Endereco da operacao",
        Paragraph(address_html, card_body_style),
        card_title_style,
        card_body_style,
        107 * mm,
    )
    risk_box = _info_box(
        "Risco operacional",
        orcamento.risco_operacional or "Nao informado",
        card_title_style,
        card_body_style,
        58 * mm,
    )
    operational_grid = Table([[address_box, risk_box]], colWidths=[107 * mm, 58 * mm])
    operational_grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    commercial_note = Table(
        [[
            Paragraph(
                "Este PDF apresenta os principais dados da proposta e a composicao financeira inicial para validacao comercial com o cliente. Caso a proposta avance, ele pode ser complementado com escopo tecnico, prazo, condicoes de pagamento e observacoes contratuais.",
                note_style,
            )
        ]],
        colWidths=[165 * mm],
    )
    commercial_note.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    story = [
        header,
        Spacer(1, 8 * mm),
        Paragraph("Composicao financeira", section_style),
        service_breakdown,
        Spacer(1, 7 * mm),
        Paragraph("Dados da proposta", section_style),
        proposal_grid,
        Spacer(1, 7 * mm),
        Paragraph("Detalhes operacionais", section_style),
        operational_grid,
        Spacer(1, 7 * mm),
        Paragraph("Observacao comercial", section_style),
        commercial_note,
    ]

    doc.build(story, onFirstPage=_build_page_frame, onLaterPages=_build_page_frame)
    buffer.seek(0)
    return buffer
