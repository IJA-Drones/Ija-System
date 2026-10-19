"""Operational report: no names, phones, home street addresses or symptoms."""
from io import BytesIO
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
from app.shared.pdf_watermark import municipal_canvas, report_prefeitura_id
from .service import STATUS


def pdf(rows, filters, user):
    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles['BodyText'].fontSize = 8
    styles['BodyText'].leading = 11
    def p(value):
        return Paragraph(escape(str(value)), styles['BodyText'])
    stamp = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M')
    counts = Counter(row.status for row in rows)
    criteria = [f"Recebido a partir de: {filters.get('inicio') or 'sem limite'}",
                f"Recebido até: {filters.get('fim') or 'sem limite'}",
                f"Situação: {STATUS.get(filters.get('status'), 'Todas')}",
                f"Prefeitura: {rows[0].prefeitura.nome if rows and filters.get('prefeitura_id') else ('ID ' + filters['prefeitura_id'] if filters.get('prefeitura_id') else 'Todas no acesso do emissor')}"]
    story = [Paragraph('Suspeitas de adoecimento', styles['Title']),
             p('Relatório de acompanhamento - relatos da população, não casos confirmados no SINAN.'),
             p(f'Gerado em {stamp} (Brasília) | Total: {len(rows)}'), p(' | '.join(criteria)),
             p(' | '.join(f'{STATUS[key]}: {counts[key]}' for key in STATUS)), Spacer(1,12)]
    data = [[p(x) for x in ['Protocolo','Recebido (Brasília)','Prefeitura','Bairro','Situação','UVIS']]]
    for row in rows:
        values = [row.protocolo, row.criado_em.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M'),
                  row.prefeitura.nome, row.bairro, STATUS[row.status], row.uvis.nome_uvis if row.uvis else 'Aguardando direcionamento']
        data.append([p(x) for x in values])
    table = LongTable(data, repeatRows=1, colWidths=[125,100,145,105,130,160])
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#deedf4')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#ccd7dc'))]))
    story += [table, Spacer(1,12), p('Uso interno. Dados de contato e descrição de saúde permanecem no atendimento restrito.'),
              p('IJA DRONES - Documento elaborado pelo time de desenvolvimento da IJA DRONES')]
    SimpleDocTemplate(stream, pagesize=landscape(A4),leftMargin=35,rightMargin=35,topMargin=35,bottomMargin=35).build(
        story, canvasmaker=municipal_canvas(report_prefeitura_id([r.prefeitura_id for r in rows], user),user=user))
    stream.seek(0)
    return stream
