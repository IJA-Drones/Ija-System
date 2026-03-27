import tempfile
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.extensions import db
from app.models import Solicitacao, Usuario
from app.modules.piloto_os.exporters import _fmt_date, _try_make_local_rlimage, _try_make_logo
from app.modules.relatorios.service import build_relatorio_coleta_imagens_export_data, build_relatorio_os_export_data
from app.shared.access import apply_regiao_scope, apply_solicitacao_regiao_scope
from app.shared.query_filters import aplicar_filtros_base

try:
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def _resolve_filters(user, args):
    mes = args.get("mes", datetime.now().month, type=int)
    ano = args.get("ano", datetime.now().year, type=int)
    filtro_data = f"{ano}-{mes:02d}"

    if getattr(user, "tipo_usuario", None) == "uvis":
        uvis_id = user.id
    else:
        uvis_id = args.get("uvis_id", type=int)

    return mes, ano, filtro_data, uvis_id


def _build_pdf_export_data(user, args):
    mes, ano, filtro_data, uvis_id = _resolve_filters(user, args)
    orient = args.get("orient", default="portrait")

    base_query = aplicar_filtros_base(
        db.session.query(Solicitacao),
        filtro_data,
        uvis_id,
    )
    base_query = apply_solicitacao_regiao_scope(base_query, user)

    query_detalhe = aplicar_filtros_base(
        db.session.query(Solicitacao, Usuario).join(Usuario, Usuario.id == Solicitacao.usuario_id),
        filtro_data,
        uvis_id,
    )
    query_detalhe = apply_regiao_scope(query_detalhe, user, Usuario.regiao)

    query_results = query_detalhe.order_by(Solicitacao.data_criacao.desc()).all()

    total_solicitacoes = base_query.count()
    total_aprovadas = base_query.filter(Solicitacao.status == "APROVADO").count()
    total_aprovadas_com_recomendacoes = base_query.filter(
        Solicitacao.status == "APROVADO COM RECOMENDAÇÕES"
    ).count()
    total_recusadas = base_query.filter(Solicitacao.status == "NEGADO").count()
    total_analise = base_query.filter(Solicitacao.status == "EM ANÁLISE").count()
    total_pendentes = base_query.filter(Solicitacao.status == "PENDENTE").count()

    dados_regiao = [
        (regiao or "Não informado", total)
        for regiao, total in (
            apply_regiao_scope(
                aplicar_filtros_base(
                    db.session.query(Usuario.regiao, db.func.count(Solicitacao.id)).join(Usuario),
                    filtro_data,
                    uvis_id,
                ),
                user,
                Usuario.regiao,
            )
            .group_by(Usuario.regiao)
            .all()
        )
    ]

    dados_status = [
        (status or "Não informado", total)
        for status, total in (
            base_query
            .with_entities(Solicitacao.status, db.func.count(Solicitacao.id))
            .group_by(Solicitacao.status)
            .all()
        )
    ]

    dados_foco = [
        (foco or "Não informado", total)
        for foco, total in (
            base_query
            .with_entities(Solicitacao.foco, db.func.count(Solicitacao.id))
            .group_by(Solicitacao.foco)
            .all()
        )
    ]

    dados_tipo_visita = [
        (tipo or "Não informado", total)
        for tipo, total in (
            base_query
            .with_entities(Solicitacao.tipo_visita, db.func.count(Solicitacao.id))
            .group_by(Solicitacao.tipo_visita)
            .all()
        )
    ]

    dados_altura_voo = [
        (altura or "Não informado", total)
        for altura, total in (
            base_query
            .with_entities(Solicitacao.altura_voo, db.func.count(Solicitacao.id))
            .group_by(Solicitacao.altura_voo)
            .all()
        )
    ]

    dados_unidade = [
        (uvis_nome or "Não informado", total)
        for uvis_nome, total in (
            apply_regiao_scope(
                aplicar_filtros_base(
                    db.session.query(Usuario.nome_uvis, db.func.count(Solicitacao.id))
                    .join(Usuario)
                    .filter(Usuario.tipo_usuario == "uvis"),
                    filtro_data,
                    uvis_id,
                ),
                user,
                Usuario.regiao,
            )
            .group_by(Usuario.nome_uvis)
            .all()
        )
    ]

    if db.engine.name == "postgresql":
        func_mes = db.func.to_char(Solicitacao.data_agendamento, "YYYY-MM")
    else:
        func_mes = db.func.strftime("%Y-%m", Solicitacao.data_agendamento)

    dados_mensais = [
        tuple(row)
        for row in (
            apply_solicitacao_regiao_scope(
                db.session.query(func_mes.label("mes"), db.func.count(Solicitacao.id)).filter(
                    Solicitacao.data_agendamento.isnot(None)
                ),
                user,
            )
            .group_by("mes")
            .order_by("mes")
            .all()
        )
    ]

    return {
        "mes": mes,
        "ano": ano,
        "orient": orient,
        "filtro_data": filtro_data,
        "uvis_id": uvis_id,
        "query_results": query_results,
        "total_solicitacoes": total_solicitacoes,
        "total_aprovadas": total_aprovadas,
        "total_aprovadas_com_recomendacoes": total_aprovadas_com_recomendacoes,
        "total_recusadas": total_recusadas,
        "total_analise": total_analise,
        "total_pendentes": total_pendentes,
        "dados_regiao": dados_regiao,
        "dados_status": dados_status,
        "dados_foco": dados_foco,
        "dados_tipo_visita": dados_tipo_visita,
        "dados_altura_voo": dados_altura_voo,
        "dados_unidade": dados_unidade,
        "dados_mensais": dados_mensais,
    }


def build_relatorio_pdf_export(user, args):
    data = _build_pdf_export_data(user, args)

    status_colors = {
        "APROVADO": "#2f855a",
        "APROVADO COM RECOMENDAÇÕES": "#F7630C",
        "EM ANÁLISE": "#f3e526",
        "PENDENTE": "#718096",
        "NEGADO": "#e53e3e",
        "CANCELADO": "#343a40",
        "CONCLUÍDO": "#9B30FF",
        "CONCLUIDO": "#9B30FF",
    }

    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    caminho_pdf = tmp_pdf.name
    tmp_pdf.close()

    pagesize = landscape(A4) if data["orient"] == "landscape" else A4
    doc = SimpleDocTemplate(
        caminho_pdf,
        pagesize=pagesize,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        alignment=1,
        textColor=colors.HexColor("#0d6efd"),
        spaceAfter=10,
    )
    subtitle_style = ParagraphStyle(
        "subtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#555"),
        spaceAfter=12,
    )
    section_h = ParagraphStyle(
        "sec",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0d6efd"),
        spaceBefore=10,
        spaceAfter=6,
    )
    normal = ParagraphStyle(
        "normal",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
    )
    cell_style = ParagraphStyle(
        "cell",
        parent=styles["BodyText"],
        fontSize=8.6,
        leading=11,
        textColor=colors.HexColor("#222"),
        wordWrap="CJK",
        splitLongWords=True,
    )

    story = []
    story.append(Paragraph(f"Relatório Mensal — {data['mes']:02d}/{data['ano']}", title_style))

    filtro_txt = f"Filtro: {data['filtro_data']}"
    if data["uvis_id"]:
        filtro_txt += f" | UVIS ID: {data['uvis_id']}"
    else:
        filtro_txt += " | UVIS: Todas"
    story.append(Paragraph(filtro_txt, subtitle_style))

    def resumo_cards():
        cards = [
            ("Total", data["total_solicitacoes"], "#0d6efd"),
            ("Aprovadas", data["total_aprovadas"], "#198754"),
            ("Aprov. c/ Recom.", data["total_aprovadas_com_recomendacoes"], "#F7630C"),
            ("Negadas", data["total_recusadas"], "#dc3545"),
            ("Em Análise", data["total_analise"], "#ffc107"),
            ("Pendentes", data["total_pendentes"], "#718096"),
        ]

        rows = []
        row = []
        for label, value, hexcolor in cards:
            box = Table(
                [
                    [Paragraph(label, ParagraphStyle("l", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#666")))],
                    [Paragraph(str(value), ParagraphStyle("v", parent=styles["Normal"], fontSize=18, leading=20, textColor=colors.HexColor(hexcolor)))],
                ],
                colWidths=[48 * mm] if data["orient"] == "portrait" else [52 * mm],
            )
            box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e5e7eb")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            row.append(box)
            if len(row) == 3:
                rows.append(row)
                row = []

        if row:
            while len(row) < 3:
                row.append(Spacer(1, 1))
            rows.append(row)

        grid = Table(rows, colWidths=None)
        grid.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return grid

    story.append(resumo_cards())
    story.append(Spacer(1, 10))

    def add_count_table(titulo, dados, col1="Categoria"):
        story.append(Paragraph(titulo, section_h))
        rows = [[
            Paragraph(col1, ParagraphStyle("th", parent=cell_style, textColor=colors.white, fontSize=9)),
            Paragraph("Total", ParagraphStyle("th2", parent=cell_style, textColor=colors.white, fontSize=9)),
        ]]

        for nome, total in (dados or [("Nenhum", 0)]):
            rows.append([Paragraph(str(nome), cell_style), Paragraph(str(total), cell_style)])

        tbl = Table(rows, repeatRows=1, colWidths=[140 * mm, 25 * mm] if data["orient"] == "portrait" else [190 * mm, 30 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9dee7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfdff")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 10))

    story.append(Paragraph("Resumo por Agrupamentos", section_h))
    story.append(Paragraph("Abaixo estão os agrupamentos do mês selecionado, apresentados em formato de tabela.", normal))
    story.append(Spacer(1, 6))

    add_count_table("Agrupamento — Região", data["dados_regiao"])
    add_count_table("Agrupamento — Status", data["dados_status"])
    add_count_table("Agrupamento — Foco", data["dados_foco"])
    add_count_table("Agrupamento — Tipo de Visita", data["dados_tipo_visita"])
    add_count_table("Agrupamento — Altura do Voo", data["dados_altura_voo"])
    add_count_table("Agrupamento — Unidade (UVIS)", data["dados_unidade"])
    add_count_table("Histórico Mensal (tabela)", data["dados_mensais"], col1="Mês")

    story.append(PageBreak())
    story.append(Paragraph("Gráficos", section_h))
    story.append(Paragraph("Os gráficos abaixo representam visualmente os dados apresentados nas tabelas anteriores.", normal))
    story.append(Spacer(1, 8))

    def safe_img_from_plt(fig, width_mm=170):
        bio = BytesIO()
        fig.tight_layout()
        fig.savefig(bio, format="png", dpi=220, bbox_inches="tight")
        plt.close(fig)
        bio.seek(0)
        return RLImage(bio, width=width_mm * mm)

    if MATPLOTLIB_AVAILABLE:
        try:
            labels = [status for status, _ in data["dados_status"]]
            values = [count for _, count in data["dados_status"]]
            colors_status = [status_colors.get(status, "#bdc3c7") for status in labels]

            fig1, ax1 = plt.subplots(figsize=(6.4, 3.0))

            def autopct(percent):
                return f"{percent:.0f}%" if percent >= 6 else ""

            wedges, *_ = ax1.pie(
                values or [1],
                labels=None,
                colors=colors_status,
                autopct=autopct,
                startangle=90,
                pctdistance=0.78,
                textprops={"fontsize": 9},
            )
            centre_circle = plt.Circle((0, 0), 0.58, fc="white")
            ax1.add_artist(centre_circle)
            ax1.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9, frameon=False)
            ax1.set_title("Distribuição por Status", fontsize=11, pad=10)
            ax1.axis("equal")
            story.append(safe_img_from_plt(fig1, width_mm=170))
            story.append(Spacer(1, 10))

            u_names = [uvis for uvis, _ in data["dados_unidade"][:10]]
            u_vals = [count for _, count in data["dados_unidade"][:10]]
            fig2, ax2 = plt.subplots(figsize=(7.2, 3.0))
            ax2.barh(u_names[::-1] or ["Nenhum"], u_vals[::-1] or [0])
            ax2.set_xlabel("Total", fontsize=9)
            ax2.set_title("Top UVIS", fontsize=11, pad=10)
            ax2.tick_params(axis="both", labelsize=9)
            ax2.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6)
            story.append(safe_img_from_plt(fig2, width_mm=180 if data["orient"] == "landscape" else 170))
            story.append(Spacer(1, 10))

            months = [mes for mes, _ in data["dados_mensais"]]
            counts = [count for _, count in data["dados_mensais"]]
            fig3, ax3 = plt.subplots(figsize=(7.2, 3.0))
            if months:
                ax3.plot(range(len(months)), counts, marker="o", linewidth=1.6)
                ax3.set_xticks(range(len(months)))
                ax3.set_xticklabels(months, rotation=45, ha="right", fontsize=9)
            ax3.set_title("Histórico Mensal", fontsize=11, pad=10)
            ax3.tick_params(axis="y", labelsize=9)
            ax3.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
            story.append(safe_img_from_plt(fig3, width_mm=185 if data["orient"] == "landscape" else 170))
            story.append(Spacer(1, 8))
        except Exception:
            story.append(Paragraph("Gráficos indisponíveis (erro ao gerar).", normal))
    else:
        story.append(Paragraph("Matplotlib não disponível — gráficos foram omitidos.", normal))

    story.append(PageBreak())
    story.append(Paragraph("Registros Detalhados", section_h))
    story.append(Paragraph("Listagem completa dos registros retornados pelo filtro selecionado.", normal))
    story.append(Spacer(1, 8))

    registros_header = [
        "Data",
        "Hora",
        "Unidade",
        "Região",
        "Protocolo",
        "Status",
        "Foco",
        "Tipo Visita",
        "Altura Voo",
        "Observação",
    ]
    hdr_style = ParagraphStyle("hdr", parent=cell_style, textColor=colors.white, fontSize=7.8, leading=9.2)
    cell_style_small = ParagraphStyle(
        "cell_small",
        parent=cell_style,
        fontSize=7.6,
        leading=9.2,
        wordWrap="CJK",
        splitLongWords=True,
    )

    registros_rows = [[Paragraph(header, hdr_style) for header in registros_header]]
    for solicitacao, usuario in data["query_results"]:
        data_str = solicitacao.data_criacao.strftime("%d/%m/%Y") if getattr(solicitacao, "data_criacao", None) else ""
        hora_str = getattr(solicitacao, "hora_agendamento", "")
        hora_str = hora_str.strftime("%H:%M") if hasattr(hora_str, "strftime") else str(hora_str or "")

        unidade = getattr(usuario, "nome_uvis", "") or "Não informado"
        regiao = getattr(usuario, "regiao", "") or "Não informado"
        protocolo = getattr(solicitacao, "protocolo", "") or ""
        status = getattr(solicitacao, "status", "") or ""
        foco = getattr(solicitacao, "foco", "") or ""
        tipo_visita = getattr(solicitacao, "tipo_visita", "") or ""
        altura_voo = getattr(solicitacao, "altura_voo", "") or ""
        observacao = getattr(solicitacao, "observacao", "") or ""

        registros_rows.append([
            Paragraph(str(data_str), cell_style_small),
            Paragraph(str(hora_str), cell_style_small),
            Paragraph(str(unidade), cell_style_small),
            Paragraph(str(regiao), cell_style_small),
            Paragraph(str(protocolo), cell_style_small),
            Paragraph(str(status), cell_style_small),
            Paragraph(str(foco), cell_style_small),
            Paragraph(str(tipo_visita), cell_style_small),
            Paragraph(str(altura_voo), cell_style_small),
            Paragraph(str(observacao), cell_style_small),
        ])

    base_col_widths = [18 * mm, 14 * mm, 28 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 26 * mm, 18 * mm, 60 * mm]
    total_w = sum(base_col_widths)
    max_w = doc.width
    col_widths = [w * (max_w / total_w) for w in base_col_widths] if total_w > max_w else base_col_widths
    chunk_size = 28 if data["orient"] == "landscape" else 24

    for index in range(0, len(registros_rows), chunk_size):
        chunk = registros_rows[index:index + chunk_size]
        tbl = Table(chunk, repeatRows=1, colWidths=col_widths, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9dee7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfdff")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("ALIGN", (0, 1), (-1, -1), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("WORDWRAP", (0, 0), (-1, -1), "CJK"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 6))
        if index + chunk_size < len(registros_rows):
            story.append(PageBreak())

    def _header_footer(canvas, doc_):
        canvas.saveState()
        _, height = pagesize
        canvas.setFillColor(colors.HexColor("#0d6efd"))
        canvas.rect(doc_.leftMargin, height - (12 * mm), doc_.width, 3, fill=1, stroke=0)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777"))
        canvas.drawString(doc_.leftMargin, 9 * mm, f"Relatório — {data['mes']:02d}/{data['ano']} — IJASystem")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 9 * mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)

    nome_arquivo = f"relatorio_OceanoAzul_{data['ano']}_{data['mes']:02d}"
    if data["uvis_id"]:
        nome_arquivo += f"_UVIS_{data['uvis_id']}"

    return caminho_pdf, f"{nome_arquivo}.pdf"


def _montar_endereco(row):
    partes_rua = []
    if row.logradouro:
        partes_rua.append(row.logradouro.strip())
    if row.numero is not None and str(row.numero).strip():
        partes_rua.append(str(row.numero).strip())

    rua_numero = ", ".join([parte for parte in partes_rua if parte]).strip()

    cidade_uf = ""
    if row.cidade and row.uf:
        cidade_uf = f"{row.cidade.strip()}/{row.uf.strip()}"
    elif row.cidade:
        cidade_uf = row.cidade.strip()
    elif row.uf:
        cidade_uf = row.uf.strip()

    bairro_cidade = " - ".join([parte for parte in [(row.bairro or "").strip(), cidade_uf] if parte]).strip()
    cep_txt = f"CEP {row.cep.strip()}" if row.cep else ""
    return " | ".join([parte for parte in [rua_numero, bairro_cidade, cep_txt] if parte])


def build_relatorio_excel_export(user, args):
    mes, ano, filtro_data, uvis_id = _resolve_filters(user, args)

    query_dados = db.session.query(
        Solicitacao.id,
        Solicitacao.status,
        Solicitacao.foco,
        Solicitacao.tipo_visita,
        Solicitacao.altura_voo,
        Solicitacao.data_agendamento,
        Solicitacao.hora_agendamento,
        Solicitacao.cep,
        Solicitacao.logradouro,
        Solicitacao.numero,
        Solicitacao.bairro,
        Solicitacao.cidade,
        Solicitacao.uf,
        Solicitacao.latitude,
        Solicitacao.longitude,
        Usuario.nome_uvis,
        Usuario.regiao,
    ).join(Usuario, Usuario.id == Solicitacao.usuario_id)
    query_dados = apply_regiao_scope(query_dados, user, Usuario.regiao)

    if db.engine.name == "postgresql":
        query_dados = query_dados.filter(
            Solicitacao.data_agendamento.isnot(None),
            db.func.to_char(Solicitacao.data_agendamento, "YYYY-MM") == filtro_data,
        )
    else:
        query_dados = query_dados.filter(
            Solicitacao.data_agendamento.isnot(None),
            db.func.strftime("%Y-%m", Solicitacao.data_agendamento) == filtro_data,
        )

    if uvis_id:
        query_dados = query_dados.filter(Solicitacao.usuario_id == uvis_id)

    dados = query_dados.order_by(
        Solicitacao.data_agendamento.desc(),
        Solicitacao.hora_agendamento.desc(),
    ).all()

    nome_uvis_filtro = None
    if uvis_id:
        nome_uvis_filtro = (
            apply_regiao_scope(
                db.session.query(Usuario.nome_uvis).filter(Usuario.id == uvis_id),
                user,
                Usuario.regiao,
            )
            .scalar()
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório"

    colunas = [
        "UVIS",
        "Região",
        "ID",
        "Status",
        "Foco",
        "Tipo Visita",
        "Altura Voo",
        "Data Agendamento",
        "Hora Agendamento",
        "ENDEREÇO DE AÇÃO",
        "Latitude",
        "Longitude",
    ]

    header_fill = PatternFill(start_color="1E90FF", end_color="1E90FF", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    thin = Side(style="thin", color="000000")
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    zebra1 = PatternFill(start_color="FFFFFFFF", end_color="FFFFFFFF", fill_type="solid")
    zebra2 = PatternFill(start_color="FFF7FBFF", end_color="FFF7FBFF", fill_type="solid")
    center = Alignment(horizontal="center", vertical="center")
    left_center = Alignment(horizontal="left", vertical="center")

    for col_num, col_name in enumerate(colunas, 1):
        cell = ws.cell(row=1, column=col_num, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = thin_border

    ws.row_dimensions[1].height = 22

    for row_num, row in enumerate(dados, 2):
        data_agendamento_fmt = row.data_agendamento.strftime("%d/%m/%Y") if row.data_agendamento else ""
        hora_agendamento_fmt = row.hora_agendamento.strftime("%H:%M") if row.hora_agendamento else ""
        endereco_acao = _montar_endereco(row)
        values = [
            row.nome_uvis,
            row.regiao,
            row.id,
            row.status,
            row.foco,
            row.tipo_visita,
            row.altura_voo,
            data_agendamento_fmt,
            hora_agendamento_fmt,
            endereco_acao,
            row.latitude,
            row.longitude,
        ]

        ws.row_dimensions[row_num].height = 20
        for col_index, value in enumerate(values, 1):
            cell = ws.cell(row=row_num, column=col_index, value=value)
            cell.border = thin_border
            cell.fill = zebra1 if row_num % 2 == 0 else zebra2
            cell.alignment = center if col_index in (3, 7, 8, 9, 11, 12) else left_center

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(colunas))}1"

    larguras = {
        "A": 24,
        "B": 12,
        "C": 6,
        "D": 18,
        "E": 22,
        "F": 16,
        "G": 10,
        "H": 14,
        "I": 14,
        "J": 90,
        "K": 14,
        "L": 14,
    }
    for col, width in larguras.items():
        ws.column_dimensions[col].width = width

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    nome_arquivo = f"relatorio_OceanoAzul_{ano}_{mes:02d}"
    if uvis_id:
        safe_nome = (nome_uvis_filtro or f"ID_{uvis_id}").replace(" ", "_")
        nome_arquivo += f"_UVIS_{safe_nome}"

    return output, f"{nome_arquivo}.xlsx"


OS_THIN = Side(style="thin", color="D0D7DE")
OS_BORDER = Border(left=OS_THIN, right=OS_THIN, top=OS_THIN, bottom=OS_THIN)
OS_FILL_HEADER = PatternFill("solid", fgColor="0D6EFD")
OS_FILL_SECTION = PatternFill("solid", fgColor="EAF2FF")
OS_FILL_ZEBRA = PatternFill("solid", fgColor="FBFDFF")
OS_FONT_HEADER = Font(bold=True, color="FFFFFF")
OS_FONT_TITLE = Font(bold=True, size=16, color="0D6EFD")
OS_FONT_SUBTITLE = Font(size=10, color="555555")
OS_FONT_SECTION = Font(bold=True, color="0D6EFD")


def _os_fmt_dt(value):
    if not value:
        return ""
    try:
        return value.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


def _os_safe(value):
    if value is None:
        return ""
    return str(value)


def _os_excel_add_title(ws, title: str, subtitle: str = ""):
    ws.merge_cells("A1:B1")
    ws["A1"] = title
    ws["A1"].font = OS_FONT_TITLE
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:B2")
    ws["A2"] = subtitle
    ws["A2"].font = OS_FONT_SUBTITLE
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 18


def _os_excel_add_section(ws, row: int, title: str):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    cell = ws.cell(row=row, column=1, value=title)
    cell.fill = OS_FILL_SECTION
    cell.font = OS_FONT_SECTION
    cell.alignment = Alignment(vertical="center")
    cell.border = OS_BORDER
    ws.cell(row=row, column=2).border = OS_BORDER
    ws.row_dimensions[row].height = 18


def _os_excel_apply_table_style(ws, header_row: int, end_row: int, col_count: int = 2):
    for col in range(1, col_count + 1):
        cell = ws.cell(row=header_row, column=col)
        cell.fill = OS_FILL_HEADER
        cell.font = OS_FONT_HEADER
        cell.border = OS_BORDER
        cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)

    for row in range(header_row + 1, end_row + 1):
        for col in range(1, col_count + 1):
            cell = ws.cell(row=row, column=col)
            cell.border = OS_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if (row - header_row) % 2 == 0:
                cell.fill = OS_FILL_ZEBRA


def _os_excel_write_kv(ws, start_row: int, items: list[tuple[str, object]]):
    ws.cell(row=start_row, column=1, value="Campo")
    ws.cell(row=start_row, column=2, value="Valor")

    row = start_row + 1
    for key, value in items:
        ws.cell(row=row, column=1, value=str(key))
        ws.cell(row=row, column=2, value=_os_safe(value))
        row += 1

    _os_excel_apply_table_style(ws, start_row, row - 1, col_count=2)
    return row


def _os_excel_write_table(ws, start_row: int, headers: list[str], rows: list[tuple], col_widths=None):
    for index, header in enumerate(headers, start=1):
        ws.cell(row=start_row, column=index, value=header)

    row = start_row + 1
    for values in rows:
        for col, value in enumerate(values, start=1):
            ws.cell(row=row, column=col, value=_os_safe(value))
        row += 1

    _os_excel_apply_table_style(ws, start_row, row - 1, col_count=len(headers))

    if col_widths:
        for index, width in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(index)].width = width

    return row


def _os_excel_auto_width(ws, max_col=2, min_w=12, max_w=60):
    for col in range(1, max_col + 1):
        letter = get_column_letter(col)
        best = 0
        for cell in ws[letter]:
            if cell.value:
                best = max(best, len(str(cell.value)))
        ws.column_dimensions[letter].width = max(min_w, min(max_w, best + 2))


def _os_pdf_header_footer_factory(title: str):
    def _hf(canvas, doc):
        canvas.saveState()
        _, height = doc.pagesize
        canvas.setFillColor(colors.HexColor("#0d6efd"))
        canvas.rect(doc.leftMargin, height - 12 * mm, doc.width, 3, fill=1, stroke=0)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#666"))
        canvas.drawString(doc.leftMargin, 9 * mm, title)
        canvas.drawRightString(doc.leftMargin + doc.width, 9 * mm, f"Pagina {canvas.getPageNumber()}")
        canvas.restoreState()

    return _hf


def _os_pdf_table(title: str, rows: list[list[str]], styles, col_widths=None):
    section = ParagraphStyle(
        "os_sec",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0d6efd"),
        spaceBefore=10,
        spaceAfter=6,
    )
    story = [Paragraph(title, section)]

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9dee7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfdff")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    story.append(Spacer(1, 8))
    return story


def build_relatorio_os_excel_export(user, args):
    data = build_relatorio_os_export_data(user, args)

    workbook = Workbook()
    ws = workbook.active
    ws.title = "Resumo"

    _os_excel_add_title(
        ws,
        "Relatorio Geral de OS",
        f"Filtro: {data['mes']:02d}/{data['ano']} | Unidade: {data['uvis_nome']} | Gerado em {_os_fmt_dt(datetime.now())}",
    )

    row = 4
    _os_excel_add_section(ws, row, "Indicadores")
    row += 1
    row = _os_excel_write_kv(ws, row, [
        ("Total OS", data["total_os"]),
        ("Concluidas", data["total_concluidas"]),
        ("Larva (SIM)", data["total_larva_sim"]),
        ("Tratamento adicional", data["total_tratamento_adicional"]),
        ("Nao realizadas", data["total_nao_realizadas"]),
    ])

    ws.freeze_panes = "A5"
    _os_excel_auto_width(ws, max_col=2, min_w=18, max_w=70)

    ws2 = workbook.create_sheet("Detalhamento")
    _os_excel_add_title(ws2, "Detalhamento do Relatorio", "Agrupamentos por campos")

    row = 4
    _os_excel_add_section(ws2, row, "Situacao da Aplicacao")
    row += 1
    row = _os_excel_write_table(ws2, row, ["Situacao", "Total"], data["dados_situacao_aplicacao"], col_widths=[45, 12])

    row += 1
    _os_excel_add_section(ws2, row, "Tipo de Aplicacao")
    row += 1
    row = _os_excel_write_table(ws2, row, ["Tipo", "Total"], data["dados_tipo_aplicacao"], col_widths=[45, 12])

    row += 1
    _os_excel_add_section(ws2, row, "Larva Visualizada")
    row += 1
    row = _os_excel_write_table(ws2, row, ["Resposta", "Total"], data["dados_larva"], col_widths=[45, 12])

    row += 1
    _os_excel_add_section(ws2, row, "Pilotos (Top 10)")
    row += 1
    row = _os_excel_write_table(ws2, row, ["Piloto", "Total"], data["dados_piloto"][:10], col_widths=[45, 12])

    row += 1
    _os_excel_add_section(ws2, row, "OS por Unidade")
    row += 1
    row = _os_excel_write_table(ws2, row, ["Unidade (UVIS)", "Total"], data["dados_unidade"], col_widths=[45, 12])

    row += 1
    _os_excel_add_section(ws2, row, "Historico Mensal")
    row += 1
    _os_excel_write_table(ws2, row, ["Mes", "Total"], data["dados_mensais"], col_widths=[18, 12])

    ws2.freeze_panes = "A5"

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    nome = f"relatorio_os_{data['ano']}_{data['mes']:02d}"
    if data["uvis_id"]:
        nome += f"_uvis_{data['uvis_id']}"
    nome += ".xlsx"
    return output, nome


def build_relatorio_os_pdf_export(user, args):
    data = build_relatorio_os_export_data(user, args)

    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    path = tmp_pdf.name
    tmp_pdf.close()

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "os_title",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        alignment=1,
        textColor=colors.HexColor("#0d6efd"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "os_sub",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#555"),
        spaceAfter=12,
    )

    story = [
        Paragraph("Relatorio Geral de OS", title_style),
        Paragraph(
            f"Filtro: {data['mes']:02d}/{data['ano']} | Unidade: {data['uvis_nome']} | Gerado em {_os_fmt_dt(datetime.now())}",
            subtitle_style,
        ),
    ]

    story += _os_pdf_table(
        "Indicadores",
        rows=[
            ["Indicador", "Total"],
            ["Total OS", str(data["total_os"])],
            ["Concluidas", str(data["total_concluidas"])],
            ["Larva (SIM)", str(data["total_larva_sim"])],
            ["Tratamento adicional", str(data["total_tratamento_adicional"])],
            ["Nao realizadas", str(data["total_nao_realizadas"])],
        ],
        styles=styles,
        col_widths=[120 * mm, 50 * mm],
    )
    story += _os_pdf_table(
        "Situacao da Aplicacao",
        rows=[["Situacao", "Total"]] + [[a, str(b)] for a, b in data["dados_situacao_aplicacao"]],
        styles=styles,
        col_widths=[120 * mm, 50 * mm],
    )
    story += _os_pdf_table(
        "Tipo de Aplicacao",
        rows=[["Tipo", "Total"]] + [[a, str(b)] for a, b in data["dados_tipo_aplicacao"]],
        styles=styles,
        col_widths=[120 * mm, 50 * mm],
    )
    story += _os_pdf_table(
        "Larva Visualizada",
        rows=[["Resposta", "Total"]] + [[a, str(b)] for a, b in data["dados_larva"]],
        styles=styles,
        col_widths=[120 * mm, 50 * mm],
    )
    story += _os_pdf_table(
        "Pilotos (Top 10)",
        rows=[["Piloto", "Total"]] + [[a, str(b)] for a, b in data["dados_piloto"][:10]],
        styles=styles,
        col_widths=[120 * mm, 50 * mm],
    )
    story += _os_pdf_table(
        "OS por Unidade",
        rows=[["Unidade (UVIS)", "Total"]] + [[a, str(b)] for a, b in data["dados_unidade"]],
        styles=styles,
        col_widths=[120 * mm, 50 * mm],
    )
    story += _os_pdf_table(
        "Historico Mensal",
        rows=[["Mes", "Total"]] + [[a, str(b)] for a, b in data["dados_mensais"]],
        styles=styles,
        col_widths=[60 * mm, 110 * mm],
    )

    header_title = f"Relatorio OS - {data['mes']:02d}/{data['ano']}"
    doc.build(
        story,
        onFirstPage=_os_pdf_header_footer_factory(header_title),
        onLaterPages=_os_pdf_header_footer_factory(header_title),
    )

    nome = f"relatorio_os_{data['ano']}_{data['mes']:02d}"
    if data["uvis_id"]:
        nome += f"_uvis_{data['uvis_id']}"
    nome += ".pdf"
    return path, nome


def build_relatorio_coleta_imagens_pdf_export(user, args):
    data = build_relatorio_coleta_imagens_export_data(user, args)

    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    path = tmp_pdf.name
    tmp_pdf.close()

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=21 * mm,
        rightMargin=21 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()

    page_inner_width = min(doc.width, 162 * mm)
    summary_width = min(doc.width - (20 * mm), 128 * mm)
    detail_label_width = 44 * mm

    title_style = ParagraphStyle(
        "coleta_title",
        parent=styles["Title"],
        fontSize=14.4,
        leading=19,
        alignment=1,
        textColor=colors.HexColor("#111827"),
        spaceAfter=0,
    )
    top_info_style = ParagraphStyle(
        "coleta_top_info",
        parent=styles["BodyText"],
        fontSize=9.2,
        leading=12.2,
        alignment=1,
        textColor=colors.HexColor("#111827"),
    )
    detail_label_style = ParagraphStyle(
        "coleta_detail_label",
        parent=styles["BodyText"],
        fontSize=7.4,
        leading=10.2,
        textColor=colors.HexColor("#111827"),
    )
    detail_value_style = ParagraphStyle(
        "coleta_detail_value",
        parent=styles["BodyText"],
        fontSize=7.4,
        leading=10.2,
        textColor=colors.HexColor("#111827"),
    )
    footer_company_style = ParagraphStyle(
        "coleta_footer_company",
        parent=styles["Normal"],
        fontSize=7.2,
        leading=8.4,
        alignment=1,
        textColor=colors.HexColor("#4f81c7"),
    )
    footer_text_style = ParagraphStyle(
        "coleta_footer_text",
        parent=styles["Normal"],
        fontSize=5.8,
        leading=7,
        alignment=1,
        textColor=colors.HexColor("#a0a7b3"),
    )
    empty_state_style = ParagraphStyle(
        "coleta_empty",
        parent=styles["Normal"],
        fontSize=9.4,
        leading=13,
        alignment=1,
        textColor=colors.HexColor("#4b5563"),
    )

    story = []

    if not data["levantamentos"]:
        logo = _try_make_logo(args, width_mm=30)
        if logo:
            logo_box = Table([[logo]], colWidths=[doc.width])
            logo_box.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(logo_box)
            story.append(Spacer(1, 24))

        story.append(Paragraph("Relatorio de Coleta de Imagens - Operacao Dengue PMSP", title_style))
        story.append(Spacer(1, 24))

        filtro_box = Table([[
            Paragraph(f"<b>UVIS:</b> {_os_safe(data['uvis_nome_selecionado'])}", top_info_style),
            Paragraph(f"<b>REGIAO:</b> {_os_safe(data['regiao_nome_selecionada'])}", top_info_style),
            Paragraph(f"<b>PERIODO:</b> {_os_safe(data['periodo_label'])}", top_info_style),
        ]], colWidths=[summary_width / 3, summary_width / 3, summary_width / 3])
        filtro_box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 5.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
        ]))
        filtro_wrap = Table([[filtro_box]], colWidths=[doc.width])
        filtro_wrap.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(filtro_wrap)
        story.append(Spacer(1, 22))

        vazio = Table(
            [[Paragraph("Nenhum levantamento com foto principal foi encontrado para os filtros selecionados.", empty_state_style)]],
            colWidths=[page_inner_width],
            rowHeights=[102 * mm],
        )
        vazio.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        vazio_wrap = Table([[vazio]], colWidths=[doc.width])
        vazio_wrap.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(vazio_wrap)
        story.append(Spacer(1, 28))
        story.append(Paragraph("OCEANO AZUL COMERCIO INTERNACIONAL LTDA", footer_company_style))
        story.append(Paragraph("Alameda Rio Negro, 503 - sala 2401", footer_text_style))
        story.append(Paragraph("Alphaville Centro Industrial e Empresarial - Barueri SP", footer_text_style))

        doc.build(story)
        return path, "relatorio_coleta_imagens.pdf"

    for index, item in enumerate(data["levantamentos"]):
        if index:
            story.append(PageBreak())

        logo = _try_make_logo(args, width_mm=30)
        if logo:
            logo_box = Table([[logo]], colWidths=[doc.width])
            logo_box.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(logo_box)
            story.append(Spacer(1, 24))

        story.append(Paragraph("Relatorio de Coleta de Imagens - Operacao Dengue PMSP", title_style))
        story.append(Spacer(1, 24))

        resumo_topo = Table([[
            Paragraph(f"<b>UVIS:</b> {_os_safe(item['uvis_nome'])}", top_info_style),
            Paragraph(f"<b>REGIAO:</b> {_os_safe(item['regiao_nome'])}", top_info_style),
            Paragraph(f"<b>PERIODO:</b> {_os_safe(data['periodo_label'])}", top_info_style),
        ]], colWidths=[summary_width / 3, summary_width / 3, summary_width / 3])
        resumo_topo.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 5.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
        ]))
        resumo_wrap = Table([[resumo_topo]], colWidths=[doc.width])
        resumo_wrap.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(resumo_wrap)
        story.append(Spacer(1, 22))

        imagem_principal = _try_make_local_rlimage(
            item["imagem_principal_path"],
            width_mm=148,
            max_height_mm=96,
        )

        if imagem_principal:
            imagem_box = Table([[imagem_principal]], colWidths=[page_inner_width])
            imagem_box.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
        else:
            imagem_box = Table(
                [[Paragraph("Imagem principal indisponivel no momento da exportacao.", empty_state_style)]],
                colWidths=[page_inner_width],
                rowHeights=[96 * mm],
            )
            imagem_box.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))

        detalhes = Table(
            [
                [Paragraph("<b>ENDERECO:</b>", detail_label_style), Paragraph(_os_safe(item["endereco"]), detail_value_style)],
                [Paragraph("<b>CEP:</b>", detail_label_style), Paragraph(_os_safe(item["cep"]), detail_value_style)],
                [Paragraph("<b>COORDENADAS:</b>", detail_label_style), Paragraph(_os_safe(item["coordenadas"]), detail_value_style)],
                [Paragraph("<b>DATA DE COLETA DE IMG:</b>", detail_label_style), Paragraph(_os_safe(item["data_coleta_label"]), detail_value_style)],
                [Paragraph("<b>FOCO:</b>", detail_label_style), Paragraph(_os_safe(item["foco"]), detail_value_style)],
            ],
            colWidths=[detail_label_width, page_inner_width - detail_label_width],
        )
        detalhes.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        bloco_principal = Table(
            [[imagem_box], [detalhes]],
            colWidths=[page_inner_width],
        )
        bloco_principal.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 16),
            ("TOPPADDING", (0, 1), (0, 1), 10),
            ("BOTTOMPADDING", (0, 1), (0, 1), 12),
        ]))
        bloco_wrap = Table([[bloco_principal]], colWidths=[doc.width])
        bloco_wrap.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(bloco_wrap)
        story.append(Spacer(1, 28))
        story.append(Paragraph("OCEANO AZUL COMERCIO INTERNACIONAL LTDA", footer_company_style))
        story.append(Paragraph("Alameda Rio Negro, 503 - sala 2401", footer_text_style))
        story.append(Paragraph("Alphaville Centro Industrial e Empresarial - Barueri SP", footer_text_style))

    doc.build(story)

    nome = "relatorio_coleta_imagens"
    if data["ano_selecionado"]:
        nome += f"_{data['ano_selecionado']}"
    if data["mes_selecionado"]:
        nome += f"_{int(data['mes_selecionado']):02d}"
    if data["regiao_selecionada"]:
        nome += f"_regiao_{data['regiao_selecionada'].replace(' ', '_').lower()}"
    if data["uvis_id_selecionado"]:
        nome += f"_uvis_{data['uvis_id_selecionado']}"
    nome += ".pdf"
    return path, nome
