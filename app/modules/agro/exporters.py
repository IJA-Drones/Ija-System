from __future__ import annotations

from io import BytesIO
import os

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.agro.service import agro_bool_label, build_endereco_agro
from app.shared.formatters import format_currency_br


IJA_GREEN = colors.HexColor("#6FD11A")
IJA_GREEN_DARK = colors.HexColor("#2E8B57")
IJA_BLUE = colors.HexColor("#1E90FF")
TEXT_MAIN = colors.HexColor("#142033")
TEXT_MUTED = colors.HexColor("#5C6A80")
BORDER = colors.HexColor("#DCE5EC")
SURFACE = colors.HexColor("#F7FBF8")


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

    footer_text = "IJA Drones | Tecnologia e Inovação"
    page_text = f"Página {canvas.getPageNumber()}"

    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(margin_left, 11 * mm, footer_text)
    page_width_text = stringWidth(page_text, "Helvetica", 8.5)
    canvas.drawString(page_width - margin_right - page_width_text, 11 * mm, page_text)
    canvas.restoreState()


def _label_value_table(rows):
    table = Table(rows, colWidths=[43 * mm, 122 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF8E2")),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_MAIN),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("GRID", (0, 0), (-1, -1), 0.65, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
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
        spaceBefore=4,
        spaceAfter=6,
    )
    text_style = ParagraphStyle(
        "AgroPdfBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.6,
        leading=13,
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
    price_style = ParagraphStyle(
        "AgroPdfPrice",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=IJA_GREEN_DARK,
        alignment=1,
    )

    logo = _try_make_agro_logo()
    company_lines = [
        Paragraph("Proposta Comercial Agro", title_style),
        Paragraph("IJA Drones | Tecnologia e Inovação", subtitle_style),
        Paragraph(f"Documento gerado para apresentação ao cliente | Orçamento #{orcamento.id}", subtitle_style),
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

    price_card = Table(
        [[Paragraph("Preço base da proposta", subtitle_style)], [Paragraph(format_currency_br(orcamento.preco_base) or "Não informado", price_style)]],
        colWidths=[56 * mm],
    )
    price_card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFFAEC")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CDEFC4")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )

    summary = Table(
        [[
            Paragraph(
                f"<b>Cliente:</b> {orcamento.cliente_nome}<br/><b>Fazenda:</b> {orcamento.nome_fazenda}<br/><b>Cultura:</b> {orcamento.cultura or 'Não informada'}",
                text_style,
            ),
            price_card,
        ]],
        colWidths=[109 * mm, 56 * mm],
    )
    summary.setStyle(
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

    endereco = build_endereco_agro(
        orcamento.cep,
        orcamento.logradouro,
        orcamento.numero,
        orcamento.complemento,
        orcamento.bairro,
        orcamento.cidade,
        orcamento.uf,
    )

    dados_principais = _label_value_table(
        [
            ["Cliente", orcamento.cliente_nome],
            ["Fazenda", orcamento.nome_fazenda],
            ["Cultura", orcamento.cultura or "Não informada"],
            ["Mapeamento", agro_bool_label(orcamento.mapeamento)],
            ["Protocolo DECEA", orcamento.protocolo or "Não informado"],
            ["Data de emissão", orcamento.data_criacao.strftime("%d/%m/%Y às %H:%M") if orcamento.data_criacao else "—"],
            ["Preço base", format_currency_br(orcamento.preco_base) or "—"],
        ]
    )

    dados_operacionais = _label_value_table(
        [
            ["Endereço da operação", endereco or "Não informado"],
            ["Risco operacional", orcamento.risco_operacional or "Não informado"],
        ]
    )

    next_steps = Table(
        [[Paragraph(
            "Este PDF apresenta o valor-base inicial e os principais dados da operação para validação comercial com o cliente. Caso a proposta avance, ele pode ser complementado com escopo técnico, prazo, condições de pagamento e observações contratuais.",
            note_style,
        )]],
        colWidths=[165 * mm],
    )
    next_steps.setStyle(
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
        Spacer(1, 7 * mm),
        summary,
        Spacer(1, 8 * mm),
        Paragraph("Dados da proposta", section_style),
        dados_principais,
        Spacer(1, 6 * mm),
        Paragraph("Detalhes operacionais", section_style),
        dados_operacionais,
        Spacer(1, 7 * mm),
        Paragraph("Observação comercial", section_style),
        next_steps,
    ]

    doc.build(story, onFirstPage=_build_page_frame, onLaterPages=_build_page_frame)
    buffer.seek(0)
    return buffer
