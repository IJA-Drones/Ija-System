from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import os
from xml.sax.saxutils import escape

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.agro.service import agro_bool_label
from app.shared.formatters import format_cep, format_currency_br, format_documento
from app.shared.uploads import get_upload_folder


IJA_GREEN = colors.HexColor("#6FD11A")
IJA_GREEN_DARK = colors.HexColor("#2E8B57")
TEXT_MAIN = colors.HexColor("#142033")
TEXT_MUTED = colors.HexColor("#5C6A80")
BORDER = colors.HexColor("#DCE5EC")
SURFACE = colors.HexColor("#F7FBF8")
SURFACE_SOFT = colors.HexColor("#EFFAEC")
CONTRACT_BLUE = colors.HexColor("#0F4761")

CONTRATADA_NOME = "IJA Drones Brasil LTDA"
CONTRATADA_DOCUMENTO = "59.826.603/0001-90"
CONTRATADA_ENDERECO = "AV BPS, 1303, SALA 04 PREDIO PCE- PINHEIRINHO - ITAJUBA - MG - CEP: 37500-903"
CONTRATADA_REPRESENTANTE = "Maria Fernanda Mota Gorgulho Chaves"
CONTRATADA_RG = "55.620.345-8"
CONTRATADA_CPF = "430.902.638-90"


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


def _resolve_agro_os_upload_absolute_path(relative_path):
    relative_path = (relative_path or "").strip().replace("\\", "/")
    if not relative_path:
        return None

    absolute_path = os.path.join(get_upload_folder(), relative_path.replace("/", os.sep))
    if not os.path.exists(absolute_path):
        return None
    return absolute_path


def _try_make_agro_os_map_image(relative_path, *, max_width_mm=165, max_height_mm=205):
    absolute_path = _resolve_agro_os_upload_absolute_path(relative_path)
    if not absolute_path:
        return None

    try:
        image = RLImage(absolute_path)
        img_width = float(getattr(image, "imageWidth", 0) or 1)
        img_height = float(getattr(image, "imageHeight", 0) or 1)
        max_width = max_width_mm * mm
        max_height = max_height_mm * mm
        scale = min(max_width / img_width, max_height / img_height)
        image.drawWidth = img_width * scale
        image.drawHeight = img_height * scale
        image.hAlign = "CENTER"
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

    footer_text = "IJA Drones | Tecnologia e Inovação"
    page_text = f"Página {canvas.getPageNumber()}"

    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(margin_left, 11 * mm, footer_text)
    page_width_text = stringWidth(page_text, "Helvetica", 8.5)
    canvas.drawString(page_width - margin_right - page_width_text, 11 * mm, page_text)
    canvas.restoreState()


def _build_os_report_page_frame(canvas, doc):
    canvas.saveState()

    page_width, page_height = A4
    margin_left = doc.leftMargin
    margin_right = doc.rightMargin
    usable_width = page_width - margin_left - margin_right

    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    canvas.setFillColor(SURFACE)
    canvas.roundRect(margin_left, page_height - 44 * mm, usable_width, 24 * mm, 10, fill=1, stroke=0)

    footer_y = 7.5 * mm
    footer_h = 9 * mm

    canvas.setFillColor(colors.white)
    canvas.roundRect(margin_left, footer_y, usable_width, footer_h, 6, fill=1, stroke=0)

    canvas.setFillColor(IJA_GREEN)
    canvas.roundRect(margin_left, footer_y, usable_width, 1.6 * mm, 6, fill=1, stroke=0)

    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.7)
    canvas.roundRect(margin_left, footer_y, usable_width, footer_h, 6, fill=0, stroke=1)

    footer_text = "+55 35 99239-4222 | Av. Bps 1303, Prédio J3 Sala 28 | Itajubá-MG | CEP 37500-903"
    page_text = f"Página {canvas.getPageNumber()}"

    canvas.setFont("Helvetica-Bold", 8.1)
    canvas.setFillColor(CONTRACT_BLUE)
    canvas.drawCentredString(page_width / 2, footer_y + 2.65 * mm, footer_text)

    page_width_text = stringWidth(page_text, "Helvetica-Bold", 8.1)
    canvas.setFillColor(IJA_GREEN_DARK)
    canvas.drawString(page_width - margin_right - page_width_text - 2, footer_y + footer_h + 1.8 * mm, page_text)

    canvas.restoreState()


def _ensure_contract_fonts():
    fonts_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    font_specs = {
        "AgroArial": "arial.ttf",
        "AgroArialBold": "arialbd.ttf",
        "AgroArialItalic": "ariali.ttf",
        "AgroArialBoldItalic": "arialbi.ttf",
    }
    for font_name, file_name in font_specs.items():
        if font_name in pdfmetrics.getRegisteredFontNames():
            continue
        font_path = os.path.join(fonts_dir, file_name)
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont(font_name, font_path))
    pdfmetrics.registerFontFamily(
        "AgroArial",
        normal="AgroArial",
        bold="AgroArialBold",
        italic="AgroArialItalic",
        boldItalic="AgroArialBoldItalic",
    )


def _build_contract_page_frame(canvas, doc):
    canvas.saveState()

    page_width, page_height = A4
    margin_left = doc.leftMargin

    logo = _try_make_agro_logo(width_mm=26)
    if logo:
        logo.drawOn(canvas, margin_left, page_height - 40 * mm)

    canvas.setFillColor(CONTRACT_BLUE)
    canvas.setFont("AgroArialBoldItalic", 12)
    canvas.drawString(
        margin_left + 34 * mm,
        page_height - 34.6 * mm,
        "IJA DRONES Tecnologia a Serviço do Campo",
    )

    canvas.setFillColor(colors.black)
    canvas.setFont("AgroArial", 9)
    canvas.drawCentredString(page_width / 2, 9 * mm, str(canvas.getPageNumber()))

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
        line_items.append(("Serviço de mapeamento", f"{_money(orcamento.preco_mapeamento)} por ha"))

    if include_spraying:
        line_items.append(("Serviço de pulverização", f"{_money(orcamento.preco_pulverizacao)} por ha"))

    if not line_items:
        line_items.append(("Serviço contratado", orcamento.servico or "Não informado"))

    return line_items


def _build_service_line_items(orcamento):
    line_items = []
    area_label = f"{orcamento.area_ha_formatada} ha" if getattr(orcamento, "area_ha_formatada", "") else "area nao informada"

    if orcamento.inclui_mapeamento:
        line_items.append(
            (
                "Servico de mapeamento",
                f"{_money(orcamento.preco_mapeamento)} por ha x {area_label} = {_money(orcamento.valor_mapeamento_total)}",
            )
        )

    if orcamento.inclui_pulverizacao:
        line_items.append(
            (
                "Servico de pulverizacao",
                f"{_money(orcamento.preco_pulverizacao)} por ha x {area_label} = {_money(orcamento.valor_pulverizacao_total)}",
            )
        )

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
        title=f"Orçamento Agro #{orcamento.id}",
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
    signature_date_style = ParagraphStyle(
        "AgroPdfSignatureDate",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=12,
        textColor=TEXT_MUTED,
        alignment=1,
    )
    signature_name_style = ParagraphStyle(
        "AgroPdfSignatureName",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9.4,
        leading=11.5,
        textColor=TEXT_MAIN,
        alignment=1,
    )

    logo = _try_make_agro_logo()
    company_lines = [
        Paragraph("Proposta Comercial Agro", title_style),
        Paragraph("IJA Drones | Tecnologia e Inovação", subtitle_style),
        Paragraph(f"Documento gerado para apresentação ao cliente. Orçamento #{orcamento.id}.", subtitle_style),
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
        orcamento.valor_total_calculado,
        service_label_style,
        service_value_style,
        total_label_style,
        total_value_style,
    )

    proposal_left = _label_value_table(
        [
            ["Cliente", orcamento.cliente_nome],
            ["Fazenda", orcamento.nome_fazenda],
            ["Serviço", orcamento.servico or "Não informado"],
            ["Cultura", orcamento.cultura or "Não informada"],
        ],
        label_style,
        value_style,
        label_width=30 * mm,
        value_width=51 * mm,
    )
    proposal_right = _label_value_table(
        [
            ["Mapeamento", agro_bool_label(orcamento.inclui_mapeamento)],
            ["Area total", f"{orcamento.area_ha_formatada} ha" if orcamento.area_ha_formatada else "Nao informada"],
            ["Protocolo DECEA", orcamento.protocolo or "Não informado"],
            ["Emissão", orcamento.data_criacao.strftime("%d/%m/%Y às %H:%M") if orcamento.data_criacao else "-"],
            ["Orçamento", f"#{orcamento.id}"],
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

    address_html = _format_operation_address(orcamento) or "Endereço não informado"
    if orcamento.nome_fazenda:
        address_html = f"<b>{escape(orcamento.nome_fazenda)}</b><br/>{address_html}"

    address_box = _info_box(
        "Endereço da operação",
        Paragraph(address_html, card_body_style),
        card_title_style,
        card_body_style,
        107 * mm,
    )
    risk_box = _info_box(
        "Risco operacional",
        orcamento.risco_operacional or "Não informado",
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
                "Este PDF apresenta os principais dados da proposta e a composição financeira inicial para validação comercial com o cliente. Caso a proposta avance, poderá ser complementado com escopo técnico, prazo, condições de pagamento e observações contratuais.",
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

    assinatura_elaborador = _signature_name_block(
        "Elaborado por: {nome}".format(
            nome=escape(orcamento.elaborado_por_nome or "Responsavel comercial")
        ),
        signature_name_style,
        width=78 * mm,
    )
    assinatura_wrapper = Table([[assinatura_elaborador]], colWidths=[165 * mm])
    assinatura_wrapper.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    emissao_orcamento = orcamento.data_criacao.strftime("%d/%m/%Y Ã s %H:%M") if orcamento.data_criacao else "-"

    story = [
        header,
        Spacer(1, 8 * mm),
        Paragraph("Composição financeira", section_style),
        service_breakdown,
        Spacer(1, 7 * mm),
        Paragraph("Dados da proposta", section_style),
        proposal_grid,
        Spacer(1, 7 * mm),
        Paragraph("Detalhes operacionais", section_style),
        operational_grid,
        Spacer(1, 7 * mm),
        Paragraph("Observação comercial", section_style),
        commercial_note,
        Spacer(1, 10 * mm),
        Paragraph(f"Emitido em {emissao_orcamento}", signature_date_style),
        Spacer(1, 8 * mm),
        assinatura_wrapper,
    ]

    doc.build(story, onFirstPage=_build_page_frame, onLaterPages=_build_page_frame)
    buffer.seek(0)
    return buffer


def merge_orcamento_agro_with_attachment(orcamento_pdf, attachment_absolute_path):
    if not attachment_absolute_path or not os.path.exists(attachment_absolute_path):
        return orcamento_pdf

    try:
        from pypdf import PdfReader, PdfWriter
    except ModuleNotFoundError:
        current_app.logger.warning(
            "pypdf não está instalado; retornando apenas o PDF base do orçamento agro."
        )
        return orcamento_pdf

    try:
        writer = PdfWriter()
        orcamento_pdf.seek(0)

        for page in PdfReader(orcamento_pdf).pages:
            writer.add_page(page)

        with open(attachment_absolute_path, "rb") as attachment_stream:
            for page in PdfReader(attachment_stream).pages:
                writer.add_page(page)

        merged = BytesIO()
        writer.write(merged)
        merged.seek(0)
        return merged
    except Exception:
        current_app.logger.exception(
            "Falha ao anexar relatório técnico ao PDF do orçamento agro."
        )
        orcamento_pdf.seek(0)
        return orcamento_pdf


def _format_short_date(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "-"
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.strftime("%d/%m/%Y")
            except ValueError:
                continue
        return text
    return str(value)


def _format_short_datetime(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "-"
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.strftime("%d/%m/%Y %H:%M")
            except ValueError:
                continue
        short_date = _format_short_date(text)
        if short_date != text:
            return short_date
        return text
    return str(value)


def _format_decimal_report(value, unit=""):
    if value in (None, ""):
        return "-"
    try:
        amount = Decimal(str(value))
        text = f"{amount:.2f}".replace(".", ",").rstrip("0").rstrip(",")
        if "," not in text:
            text = f"{text},0"
    except Exception:
        text = str(value)
    return f"{text} {unit}".strip()


def _format_range_report(min_value, max_value, unit=""):
    if min_value in (None, "") and max_value in (None, ""):
        return "-"
    if min_value not in (None, "") and max_value not in (None, ""):
        if str(min_value) == str(max_value):
            return _format_decimal_report(min_value, unit)
        return f"{_format_decimal_report(min_value)} a {_format_decimal_report(max_value)} {unit}".strip()
    return _format_decimal_report(min_value if min_value not in (None, "") else max_value, unit)


def build_ordem_servico_agro_pdf(ordem_servico):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=f"Relatório de OS {ordem_servico.identificador_os or ordem_servico.id}",
        author="IJA Drones",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AgroOsPdfTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=TEXT_MAIN,
        spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "AgroOsPdfSubtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.3,
        leading=12.2,
        textColor=TEXT_MUTED,
    )
    section_style = ParagraphStyle(
        "AgroOsPdfSection",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=12,
        textColor=IJA_GREEN_DARK,
        spaceBefore=1,
        spaceAfter=3,
    )
    label_style = ParagraphStyle(
        "AgroOsPdfLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9.1,
        leading=12,
        textColor=TEXT_MAIN,
    )
    value_style = ParagraphStyle(
        "AgroOsPdfValue",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.3,
        leading=11.2,
        textColor=TEXT_MAIN,
    )
    note_style = ParagraphStyle(
        "AgroOsPdfNote",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.8,
        leading=12,
        textColor=TEXT_MUTED,
    )
    table_head_style = ParagraphStyle(
        "AgroOsPdfTableHead",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8.3,
        leading=9.4,
        textColor=TEXT_MAIN,
        alignment=1,
    )
    table_cell_style = ParagraphStyle(
        "AgroOsPdfTableCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.4,
        leading=9.5,
        textColor=TEXT_MAIN,
        alignment=1,
    )

    logo = _try_make_agro_logo()
    cidade_uf = "/".join([part for part in [ordem_servico.cidade_operacao or "", ordem_servico.uf_operacao or ""] if part]) or "-"
    header_lines = [
        Paragraph("Relatório de Aplicação", title_style),
        Paragraph(ordem_servico.cliente_nome or "-", subtitle_style),
        Paragraph(cidade_uf, subtitle_style),
        Paragraph(
            f"OS {ordem_servico.identificador_os or '-'} | Contrato #{getattr(ordem_servico, 'contrato_agro_id', '-')}",
            subtitle_style,
        ),
        Paragraph(
            f"Período de Aplicação: {_format_short_date(ordem_servico.periodo_aplicacao) if ordem_servico.periodo_aplicacao else _format_short_date(ordem_servico.data_aplicacao)}",
            subtitle_style,
        ),
    ]

    if logo:
        header = Table([[logo, header_lines]], colWidths=[46 * mm, 119 * mm])
    else:
        header = Table([[header_lines]], colWidths=[165 * mm])
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

    drone = _label_value_table(
        [
            ("Drone de pulverização", ordem_servico.drone_pulverizacao_identificacao or "-"),
            ("Modelo", ordem_servico.drone_pulverizacao_modelo or ordem_servico.drone_mapeamento_modelo or "-"),
            ("Tipo", ordem_servico.drone_pulverizacao_tipo or ordem_servico.drone_mapeamento_tipo or "-"),
            ("Drone de mapeamento", ordem_servico.drone_mapeamento_identificacao or "-"),
            ("Mapeamento", ordem_servico.mapeamento_descricao or "-"),
            ("Altura de voo", _format_decimal_report(ordem_servico.altura_voo_m, "metros")),
            ("Largura das faixas", _format_decimal_report(ordem_servico.largura_faixa_m, "metros")),
            ("Ponta de pulv.", ordem_servico.ponta_pulverizacao or "-"),
        ],
        label_style,
        value_style,
    )

    climate_table = Table(
        [
            [
                _paragraph("Data", table_head_style),
                _paragraph("Temp. Min", table_head_style),
                _paragraph("Temp. Max", table_head_style),
                _paragraph("Umid. Min", table_head_style),
                _paragraph("Umid. Max", table_head_style),
                _paragraph("Vento Min", table_head_style),
                _paragraph("Vento Max", table_head_style),
            ],
            [
                _paragraph(_format_short_date(ordem_servico.data_aplicacao), table_cell_style),
                _paragraph(_format_decimal_report(ordem_servico.temperatura_min_c, "C"), table_cell_style),
                _paragraph(_format_decimal_report(ordem_servico.temperatura_max_c, "C"), table_cell_style),
                _paragraph(_format_decimal_report(ordem_servico.umidade_min_pct, "%"), table_cell_style),
                _paragraph(_format_decimal_report(ordem_servico.umidade_max_pct, "%"), table_cell_style),
                _paragraph(_format_decimal_report(ordem_servico.vento_min_kmh, "km/h"), table_cell_style),
                _paragraph(_format_decimal_report(ordem_servico.vento_max_kmh, "km/h"), table_cell_style),
            ],
        ],
        colWidths=[24 * mm, 23.5 * mm, 23.5 * mm, 23.5 * mm, 23.5 * mm, 23.5 * mm, 23.5 * mm],
    )
    climate_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF8E2")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.65, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    resultado = _label_value_table(
        [
            ("Área total de aplicação", _format_decimal_report(ordem_servico.area_total_ha, "ha")),
            ("Total de calda aplicada", _format_decimal_report(ordem_servico.total_calda_l, "litros")),
            ("Média aplicada por hectare", _format_decimal_report(ordem_servico.media_aplicada_l_ha, "l/ha")),
            ("Taxa de aplicação", _format_decimal_report(ordem_servico.taxa_aplicacao_l_ha, "l/ha")),
            ("Tipo de aplicação", ordem_servico.tipo_aplicacao or "-"),
        ],
        label_style,
        value_style,
    )

    insumo_table = Table(
        [
            [
                _paragraph("Produto aplicado", table_head_style),
                _paragraph("Formulação", table_head_style),
                _paragraph("Dosagem", table_head_style),
                _paragraph("Classe tóxica", table_head_style),
            ],
            [
                _paragraph(ordem_servico.produto_aplicado or "-", table_cell_style),
                _paragraph(ordem_servico.formulacao_produto or "-", table_cell_style),
                _paragraph(ordem_servico.dosagem or "-", table_cell_style),
                _paragraph(ordem_servico.classe_toxica or "-", table_cell_style),
            ],
        ],
        colWidths=[41.25 * mm, 41.25 * mm, 41.25 * mm, 41.25 * mm],
    )
    insumo_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF8E2")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.65, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    observacoes = Table(
        [[Paragraph(ordem_servico.observacoes or "Sem observações registradas.", value_style)]],
        colWidths=[165 * mm],
    )
    observacoes.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.85, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    note = Table(
        [[
            Paragraph(
                "Documento gerado automaticamente a partir dos dados preenchidos na OS Agro concluída. "
                "A imagem do mapa, quando anexada pelo admin, é incluída na página final do relatório.",
                note_style,
            )
        ]],
        colWidths=[165 * mm],
    )
    note.setStyle(
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

    mapa_aplicacao = _try_make_agro_os_map_image(getattr(ordem_servico, "mapa_aplicacao_path", None))
    has_map_page = bool(mapa_aplicacao or getattr(ordem_servico, "mapa_aplicacao_nome", None))

    story = [
        header,
        Spacer(1, 3 * mm),
        Paragraph("Especificações do drone", section_style),
        drone,
        Spacer(1, 2.5 * mm),
        Paragraph("Condições climáticas", section_style),
        climate_table,
        Spacer(1, 2.5 * mm),
        Paragraph("Resultado da Aplicação", section_style),
        resultado,
        Spacer(1, 2.5 * mm),
        Paragraph("Especificações do insumo aplicado", section_style),
        insumo_table,
        Spacer(1, 2.5 * mm),
        Paragraph("Observações", section_style),
        observacoes,
    ]
    if not has_map_page:
        story.extend(
            [
                Spacer(1, 2.5 * mm),
                note,
            ]
        )

    if has_map_page:
        story.extend(
            [
                PageBreak(),
                Paragraph("Mapas de Aplicação", title_style),
                Spacer(1, 3 * mm),
            ]
        )

        if getattr(ordem_servico, "mapa_aplicacao_nome", None):
            story.append(Paragraph(ordem_servico.mapa_aplicacao_nome, subtitle_style))
            story.append(Spacer(1, 5 * mm))

        if mapa_aplicacao:
            mapa_wrapper = Table([[mapa_aplicacao]], colWidths=[165 * mm])
            mapa_wrapper.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("BOX", (0, 0), (-1, -1), 0.85, BORDER),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ]
                )
            )
            story.append(mapa_wrapper)
        else:
            story.append(
                _info_box(
                    "Mapa não encontrado",
                    "A imagem cadastrada para esta OS não foi localizada no armazenamento do sistema.",
                    label_style,
                    value_style,
                    165 * mm,
                )
            )
        story.extend(
            [
                Spacer(1, 3 * mm),
                note,
            ]
        )

    doc.build(story, onFirstPage=_build_os_report_page_frame, onLaterPages=_build_os_report_page_frame)
    buffer.seek(0)
    return buffer


def _format_full_address(logradouro, numero, complemento, bairro, cidade, uf, cep):
    line_1 = ", ".join([part for part in [logradouro, numero] if part])
    if complemento:
        line_1 = f"{line_1} ({complemento})" if line_1 else complemento
    city_region = f"{cidade}/{uf}" if cidade and uf else (cidade or uf or "")
    line_2 = " - ".join([part for part in [bairro, city_region] if part])
    line_3 = f"CEP {format_cep(cep or '')}" if cep else ""
    return "<br/>".join([escape(part) for part in [line_1, line_2, line_3] if part])


def _format_partes_address(logradouro, numero, complemento, bairro, cidade, uf):
    partes = []

    linha_1 = ", ".join([part for part in [logradouro, numero] if part])
    if linha_1:
        partes.append(linha_1)

    if complemento:
        partes.append(complemento)
    if bairro:
        partes.append(bairro)
    if cidade:
        partes.append(cidade)
    if uf:
        partes.append(uf)

    return " - ".join([escape(part) for part in partes if part])


def _format_date_extenso(value):
    if not value:
        return "-"

    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        return str(value)

    meses = [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ]
    return f"{value.day:02d} de {meses[value.month - 1]} de {value.year}"


_UNIDADES_PT = {
    0: "zero",
    1: "um",
    2: "dois",
    3: "três",
    4: "quatro",
    5: "cinco",
    6: "seis",
    7: "sete",
    8: "oito",
    9: "nove",
    10: "dez",
    11: "onze",
    12: "doze",
    13: "treze",
    14: "quatorze",
    15: "quinze",
    16: "dezesseis",
    17: "dezessete",
    18: "dezoito",
    19: "dezenove",
}
_DEZENAS_PT = {
    20: "vinte",
    30: "trinta",
    40: "quarenta",
    50: "cinquenta",
    60: "sessenta",
    70: "setenta",
    80: "oitenta",
    90: "noventa",
}
_CENTENAS_PT = {
    100: "cem",
    200: "duzentos",
    300: "trezentos",
    400: "quatrocentos",
    500: "quinhentos",
    600: "seiscentos",
    700: "setecentos",
    800: "oitocentos",
    900: "novecentos",
}


def _int_to_pt_br(value):
    value = int(value or 0)
    if value < 20:
        return _UNIDADES_PT[value]
    if value < 100:
        dezena = (value // 10) * 10
        resto = value % 10
        return _DEZENAS_PT[dezena] if resto == 0 else f"{_DEZENAS_PT[dezena]} e {_int_to_pt_br(resto)}"
    if value < 1000:
        if value in _CENTENAS_PT:
            return _CENTENAS_PT[value]
        centena = (value // 100) * 100
        resto = value % 100
        prefixo = "cento" if centena == 100 else _CENTENAS_PT[centena]
        return prefixo if resto == 0 else f"{prefixo} e {_int_to_pt_br(resto)}"

    grupos = (
        (1_000_000_000, "bilhão", "bilhões"),
        (1_000_000, "milhão", "milhões"),
        (1_000, "mil", "mil"),
    )
    for divisor, singular, plural in grupos:
        if value >= divisor:
            quantidade = value // divisor
            resto = value % divisor
            if divisor == 1_000:
                prefixo = "mil" if quantidade == 1 else f"{_int_to_pt_br(quantidade)} mil"
            else:
                nome = singular if quantidade == 1 else plural
                prefixo = f"um {nome}" if quantidade == 1 else f"{_int_to_pt_br(quantidade)} {nome}"
            if resto == 0:
                return prefixo
            conector = " e " if resto < 100 else ", "
            return f"{prefixo}{conector}{_int_to_pt_br(resto)}"
    return str(value)


def _currency_extenso(value):
    amount = _decimal(value).quantize(Decimal("0.01"))
    inteiro = int(amount)
    centavos = int((amount - Decimal(inteiro)) * 100)

    if inteiro == 0:
        reais = "zero real"
    elif inteiro == 1:
        reais = "um real"
    else:
        reais = f"{_int_to_pt_br(inteiro)} reais"

    if centavos == 0:
        return reais
    if centavos == 1:
        centavos_txt = "um centavo"
    else:
        centavos_txt = f"{_int_to_pt_br(centavos)} centavos"
    return f"{reais} e {centavos_txt}"


def _normalize_contract_service_label(contrato, orcamento):
    origem = ((getattr(orcamento, "servico", "") or contrato.descricao_servico or "")).lower()
    if "mapeamento" in origem and "pulver" in origem:
        return "Mapeamento e Pulverização"
    if "pulver" in origem:
        return "Pulverização"
    if "mapeamento" in origem:
        return "Mapeamento"
    return "Prestação de serviços"


def _build_contract_service_item(contrato, orcamento):
    label = _normalize_contract_service_label(contrato, orcamento)
    cultura = (contrato.cultura or "").strip().lower()
    area = (contrato.area_contratada or "").strip()
    texto = f"Serviço 01 {label}"
    if cultura:
        texto += f" de {cultura}"
    if area:
        area_lower = area.lower()
        if area_lower.endswith((" ha", " ha.", "ha", "ha.", " hectare", " hectares", "hectare", "hectares")):
            texto += f": {area}"
        else:
            texto += f": {area} ha"
    return f"{texto}."


def _build_financial_items(contrato, orcamento):
    servico_base = _normalize_contract_service_label(contrato, orcamento)
    itens = []
    if _decimal(contrato.valor_mapeamento_ha) > 0:
        itens.append(("Serviço de Mapeamento", contrato.valor_mapeamento_ha))
    if _decimal(contrato.valor_pulverizacao_ha) > 0:
        itens.append(("Serviço de Pulverização", contrato.valor_pulverizacao_ha))
    if not itens:
        valor_referencia = contrato.valor_total
        itens.append((f"Serviço de {servico_base}", valor_referencia))
    return itens


def _contract_party_qualificacao(contrato):
    documento_digits = "".join(ch for ch in (contrato.contratante_documento or "") if ch.isdigit())
    residencia = _format_partes_address(
        contrato.contratante_logradouro,
        contrato.contratante_numero,
        contrato.contratante_complemento,
        contrato.contratante_bairro,
        contrato.contratante_cidade,
        contrato.contratante_uf,
    )
    propriedade = _format_partes_address(
        contrato.propriedade_logradouro,
        contrato.propriedade_numero,
        contrato.propriedade_complemento,
        contrato.propriedade_bairro,
        contrato.propriedade_cidade,
        contrato.propriedade_uf,
    )
    nome = escape(contrato.contratante_nome or "")
    rg = escape(contrato.contratante_rg or "Não informado")
    documento = format_documento(contrato.contratante_documento or "")

    if len(documento_digits) == 14:
        return (
            f"<b>CONTRATANTE: {nome}</b>, pessoa jurídica de direito privado, inscrita no CNPJ nº {documento}, "
            f"com sede em {residencia} e fazenda localizada em {propriedade}, doravante denominada CONTRATANTE, "
            "neste ato representada na forma de seus atos constitutivos."
        )

    return (
        f"<b>CONTRATANTE: {nome}</b>, pessoa física, inscrita no CPF nº {documento} e no RG nº {rg}, "
        f"residente em {residencia} e proprietária da fazenda localizada em {propriedade}, "
        "doravante denominada CONTRATANTE."
    )


def _contract_spacer(height_mm):
    return Spacer(1, height_mm * mm)


def _signature_name_block(text, style, width=92 * mm):
    table = Table([[Paragraph(text, style)]], colWidths=[width], hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black),
                ("TOPPADDING", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
                ("LEFTPADDING", (0, 0), (-1, 0), 0),
                ("RIGHTPADDING", (0, 0), (-1, 0), 0),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ]
        )
    )
    return table


def _build_clause_block(title, linhas, title_style, numbered_style, continuation_style, bullet_style):
    blocos = [Paragraph(title, title_style), _contract_spacer(1.9)]
    for linha in linhas:
        texto = (linha or "").strip()
        if not texto:
            continue
        style = continuation_style
        if texto.startswith("•"):
            style = bullet_style
        elif texto.startswith("<b>"):
            style = numbered_style
        blocos.append(Paragraph(texto, style))
        blocos.append(_contract_spacer(1.2))
    if len(blocos) > 1:
        blocos.pop()
    return blocos


def build_contrato_agro_pdf(contrato):
    _ensure_contract_fonts()
    orcamento = contrato.orcamento
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=35 * mm,
        bottomMargin=24 * mm,
        title=f"Contrato Agro #{getattr(orcamento, 'id', contrato.id)}",
        author="IJA Drones",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AgroContractTitle",
        parent=styles["BodyText"],
        fontName="AgroArialBold",
        fontSize=16,
        leading=18.5,
        textColor=CONTRACT_BLUE,
        alignment=1,
        spaceAfter=0,
    )
    section_style = ParagraphStyle(
        "AgroContractSection",
        parent=styles["BodyText"],
        fontName="AgroArialBold",
        fontSize=16,
        leading=18,
        textColor=CONTRACT_BLUE,
        alignment=0,
        spaceBefore=0,
        spaceAfter=0,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "AgroContractBodyReal",
        parent=styles["BodyText"],
        fontName="AgroArial",
        fontSize=11.04,
        leading=15.2,
        textColor=colors.black,
        alignment=4,
        spaceAfter=0,
    )
    body_no_indent_style = ParagraphStyle(
        "AgroContractBodyNoIndent",
        parent=body_style,
        firstLineIndent=0,
    )
    parties_body_style = ParagraphStyle(
        "AgroContractPartiesBody",
        parent=body_style,
        leftIndent=20 * mm,
        firstLineIndent=0,
    )
    clause_body_style = ParagraphStyle(
        "AgroContractClauseBody",
        parent=body_style,
        leftIndent=7.6 * mm,
        firstLineIndent=-7.6 * mm,
    )
    clause_continuation_style = ParagraphStyle(
        "AgroContractClauseContinuation",
        parent=body_style,
        leftIndent=7.6 * mm,
        firstLineIndent=0,
    )
    bullet_style = ParagraphStyle(
        "AgroContractBullet",
        parent=body_style,
        leftIndent=10.8 * mm,
        firstLineIndent=0,
    )
    note_style = ParagraphStyle(
        "AgroContractNoteReal",
        parent=styles["BodyText"],
        fontName="AgroArialItalic",
        fontSize=10,
        leading=13.2,
        textColor=colors.black,
        alignment=4,
    )
    signature_style = ParagraphStyle(
        "AgroContractSignatureReal",
        parent=styles["BodyText"],
        fontName="AgroArial",
        fontSize=11,
        leading=13.4,
        textColor=colors.black,
        alignment=1,
    )
    signature_date_style = ParagraphStyle(
        "AgroContractSignatureDate",
        parent=body_no_indent_style,
        alignment=0,
        fontSize=11,
        leading=14.2,
    )
    signature_name_style = ParagraphStyle(
        "AgroContractSignatureName",
        parent=signature_style,
        spaceAfter=0,
    )
    intro_blocks = [
        Paragraph("DAS PARTES:", section_style),
        _contract_spacer(2.4),
        Paragraph(
            (
                f"<b>CONTRATADA: {escape(CONTRATADA_NOME)}</b>, pessoa jurídica de direito privado, inscrita no CNPJ n° "
                f"{escape(CONTRATADA_DOCUMENTO)}, com sede em {escape(CONTRATADA_ENDERECO)}, doravante denominada CONTRATADA, "
                f"neste ato representada, na forma de seus atos constitutivos, por sua representante legal "
                f"<b>{escape(CONTRATADA_REPRESENTANTE)}</b>, portadora do Documento de Identidade RG nº {escape(CONTRATADA_RG)} "
                f"e inscrita no CPF sob o nº {escape(CONTRATADA_CPF)};"
            ),
            parties_body_style,
        ),
        _contract_spacer(1.2),
        Paragraph(_contract_party_qualificacao(contrato), parties_body_style),
        _contract_spacer(1.2),
        Paragraph(
            (
                "Decidem as partes, na melhor forma de direito, celebrar o presente CONTRATO DE PRESTAÇÃO "
                "DE SERVIÇOS, que se regerá pelas cláusulas e condições a seguir estipuladas."
            ),
            body_no_indent_style,
        ),
    ]

    service_item = _build_contract_service_item(contrato, orcamento)
    clausula_primeira = _build_clause_block(
        "CLÁUSULA PRIMEIRA - DO OBJETO",
        [
            "<b>1.1</b> O presente contrato tem por objeto a prestação de serviços profissionais especializados em mapeamento e pulverização via drones, por parte da CONTRATADA, de acordo com os termos e condições aqui estabelecidos.",
            service_item,
        ],
        section_style,
        clause_body_style,
        clause_continuation_style,
        bullet_style,
    )
    clausula_segunda = _build_clause_block(
        "CLÁUSULA SEGUNDA - OBRIGAÇÕES DA CONTRATANTE",
        [
            "<b>2.1</b> A CONTRATANTE deverá fornecer à CONTRATADA todas as informações necessárias à realização do serviço, especificando os detalhes indispensáveis à sua perfeita execução.",
            "<b>2.2</b> A CONTRATANTE é obrigada ainda a disponibilizar: insumos a serem pulverizados.",
            "<b>2.3</b> A CONTRATANTE deverá efetuar o pagamento na forma e nas condições estabelecidas na Cláusula Quinta.",
        ],
        section_style,
        clause_body_style,
        clause_continuation_style,
        bullet_style,
    )
    clausula_terceira = _build_clause_block(
        "CLÁUSULA TERCEIRA - OBRIGAÇÕES DA CONTRATADA",
        [
            "<b>3.1</b> A CONTRATADA deverá prestar os serviços de mapeamento e pulverização agrícola com drones, equipamentos e EPI 100% higienizados para evitar transmissão de eventuais doenças de outras lavouras, conforme mencionado neste contrato.",
            "<b>3.2</b> A CONTRATADA se obriga a manter absoluto sigilo sobre as operações, dados, estratégias, materiais, informações e documentos da CONTRATANTE, mesmo após a conclusão dos serviços ou do término da relação contratual.",
            "<b>3.3</b> Os contratos, informações, dados, materiais e documentos inerentes a CONTRATANTE ou a seus clientes deverão ser utilizados, pela CONTRATADA, por seus funcionários ou contratados, estritamente para cumprimento dos serviços solicitados pela CONTRATANTE, sendo vedado a comercialização ou utilização para outros fins.",
            "<b>3.4</b> Será de responsabilidade da CONTRATADA todo o ônus trabalhista ou tributário referente aos funcionários utilizados para a prestação do serviço objeto deste instrumento, ficando a CONTRATANTE isenta de qualquer obrigação em relação a eles.",
            "<b>3.5</b> A CONTRATADA deverá fornecer a respectiva Nota Fiscal referente ao(s) pagamento(s) do presente instrumento e aos serviços efetuados.",
        ],
        section_style,
        clause_body_style,
        clause_continuation_style,
        bullet_style,
    )
    clausula_quarta = _build_clause_block(
        "CLÁUSULA QUARTA - DOS SERVIÇOS",
        [
            "<b>4.1</b> A CONTRATADA prestará os serviços contratados para fins de mapeamento e pulverização.",
            f"<b>4.2</b> Os serviços terão início em até {contrato.prazo_inicio_dias or 10} dias corridos da assinatura do presente contrato.",
            "<b>4.3</b> A agenda de realização dos serviços será combinada entre as partes para evitar prejuízos/cancelamentos por situações climáticas ou demais interferências.",
        ],
        section_style,
        clause_body_style,
        clause_continuation_style,
        bullet_style,
    )

    itens_financeiros = _build_financial_items(contrato, orcamento)
    clausula_quinta_linhas = []
    if len(itens_financeiros) == 1:
        descricao, valor = itens_financeiros[0]
        clausula_quinta_linhas.append(
            f"<b>5.1</b> {descricao} a ser executado por hectare no valor de {_money(valor)} ({_currency_extenso(valor)}), "
            f"totalizando {_money(contrato.valor_total)} ({_currency_extenso(contrato.valor_total)})."
        )
    else:
        for index, (descricao, valor) in enumerate(itens_financeiros, start=1):
            clausula_quinta_linhas.append(
                f"<b>5.{index}</b> {descricao} a ser executado por hectare no valor de {_money(valor)} ({_currency_extenso(valor)})."
            )
    clausula_quinta_linhas.extend(
        [
            f"TOTAL DO CONTRATO: {_money(contrato.valor_total)} ({_currency_extenso(contrato.valor_total)})",
            "Condições de pagamento:",
            f"• O pagamento deverá ser efetuado em até {contrato.prazo_pagamento_dias or 10} dias após a finalização dos serviços.",
            "• O pagamento deverá ser efetuado na conta abaixo:",
            "IJA DRONES BRASIL LTDA",
            "ITAU UNIBANCO (341)",
            "Ag: 4807",
            "C/C: 96651-2",
            "Chave pix: 59826603000190 (CNPJ)",
            "<b>5.2</b> Em caso de atraso de pagamento, será cobrada multa moratória de 10% sobre o valor inadimplido mais correção monetária pelo índice IPCA.",
            "<b>5.3</b> Considera-se o cumprimento integral do contrato o momento em que todos os serviços especificados na Cláusula Primeira tenham sido concluídos, mediante aprovação da CONTRATANTE, via relatório de serviços.",
        ]
    )
    clausula_quinta = _build_clause_block(
        "CLÁUSULA QUINTA - DO PREÇO E DAS CONDIÇÕES DE PAGAMENTO",
        clausula_quinta_linhas,
        section_style,
        clause_body_style,
        clause_continuation_style,
        bullet_style,
    )
    clausula_sexta = _build_clause_block(
        "CLÁUSULA SEXTA - DO PRAZO E VALIDADE",
        [
            "<b>6.1</b> A CONTRATADA deverá realizar os serviços dentro dos prazos determinados no cronograma, comunicando eventual impossibilidade de cumprimento, seus motivos e o novo prazo previsto.",
            "<b>6.2</b> Este instrumento é válido por prazo indeterminado, vigorando até a finalização do serviço ora contratado ou até o encerramento do contrato, não ficando as partes isentas de seus compromissos éticos após sua invalidação.",
        ],
        section_style,
        clause_body_style,
        clause_continuation_style,
        bullet_style,
    )
    clausula_setima = _build_clause_block(
        "CLÁUSULA SÉTIMA - DA OBSERVÂNCIA À LGPD",
        [
            "<b>7.1</b> O CONTRATANTE declara expresso consentimento que a CONTRATADA irá coletar, tratar e compartilhar os dados necessários ao cumprimento do contrato, nos termos do Art. 7º, inc. V da LGPD, os dados necessários para cumprimento de obrigações legais, nos termos do Art. 7º, inc. II da LGPD, bem como os dados, se necessários para proteção ao crédito, conforme autorizado pelo Art. 7º, inc. V da LGPD.",
            "<b>7.2</b> Outros dados poderão ser coletados, conforme termo de consentimento específico.",
        ],
        section_style,
        clause_body_style,
        clause_continuation_style,
        bullet_style,
    )
    clausula_oitava = _build_clause_block(
        "CLÁUSULA OITAVA - DAS DISPOSIÇÕES GERAIS",
        [
            "<b>8.1</b> Fica pactuada a total inexistência de vínculo trabalhista entre as partes, não havendo entre CONTRATADA e CONTRATANTE qualquer tipo de relação de subordinação.",
            "<b>8.2</b> A tolerância, por qualquer das partes, com relação ao descumprimento de qualquer termo ou condição aqui ajustado, não será considerada como desistência em exigir o cumprimento de disposição nele contida, nem representará novação com relação à obrigação passada, presente ou futura, no tocante ao termo ou condição cujo descumprimento foi tolerado.",
        ],
        section_style,
        clause_body_style,
        clause_continuation_style,
        bullet_style,
    )
    clausula_nona = _build_clause_block(
        "CLÁUSULA NONA - DO FORO",
        [
            f"<b>9.1</b> Para dirimir quaisquer controvérsias oriundas do presente contrato, as partes elegem o foro da Comarca de {contrato.foro_cidade or 'São Paulo'}.",
            "Por estarem justas e acordadas, as partes firmam o presente instrumento em duas vias de igual teor.",
        ],
        section_style,
        clause_body_style,
        clause_continuation_style,
        bullet_style,
    )

    signature_date = "{cidade}, {data}".format(
        cidade=contrato.cidade_assinatura or "São Paulo",
        data=_format_date_extenso(contrato.data_assinatura),
    )
    assinatura_contratada = _signature_name_block("IJA DRONES BRASIL LTDA", signature_name_style)
    assinatura_contratante = _signature_name_block(
        escape(contrato.contratante_nome or "Contratante"),
        signature_name_style,
    )

    story = [
        _contract_spacer(22),
        Paragraph("CONTRATO DE PRESTAÇÃO DE SERVIÇOS", title_style),
        _contract_spacer(10),
    ]
    story.extend(intro_blocks)
    story.append(_contract_spacer(10))
    story.extend(clausula_primeira)
    story.extend(
        [
            PageBreak(),
            _contract_spacer(12),
        ]
    )
    story.extend(clausula_segunda)
    story.append(_contract_spacer(6))
    story.extend(clausula_terceira)
    story.extend(
        [
            PageBreak(),
            _contract_spacer(12),
        ]
    )
    story.extend(clausula_quarta)
    story.append(_contract_spacer(6))
    story.extend(clausula_quinta)
    story.extend(
        [
            PageBreak(),
            _contract_spacer(12),
        ]
    )
    story.extend(clausula_sexta)
    story.append(_contract_spacer(6))
    story.extend(clausula_setima)
    story.append(_contract_spacer(6))
    story.extend(clausula_oitava)
    story.extend(
        [
            PageBreak(),
            _contract_spacer(12),
        ]
    )
    story.extend(clausula_nona)

    if contrato.observacoes_adicionais:
        story.extend(
            [
                _contract_spacer(6),
                Paragraph("OBSERVAÇÕES COMPLEMENTARES", section_style),
                Paragraph(escape(contrato.observacoes_adicionais), note_style),
                _contract_spacer(4),
            ]
        )

    story.extend(
        [
            _contract_spacer(14),
            Paragraph(signature_date, signature_date_style),
            _contract_spacer(24),
            assinatura_contratada,
            _contract_spacer(28),
            assinatura_contratante,
        ]
    )

    doc.build(story, onFirstPage=_build_contract_page_frame, onLaterPages=_build_contract_page_frame)
    buffer.seek(0)
    return buffer
