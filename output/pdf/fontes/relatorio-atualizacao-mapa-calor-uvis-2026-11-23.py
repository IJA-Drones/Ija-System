"""Build the map report with the same identity as the training report.

Run from the repository with .venv/bin/python. Captures are temporary inputs;
only this source, its JSON evidence and the final PDF need to remain.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from scripts.training_pdf_style import (
    WIDTH as W, HEIGHT as H, MARGIN as M, CONTENT as CW, INK, ACCENT,
    MUTED, SOFT, LINE, register_fonts, text, paragraph, panel,
)

HERE = Path(__file__).with_suffix('.json')
EVIDENCE = json.loads(HERE.read_text())
TOTAL = 6


def chrome(c, page):
    c.setFillColor(ACCENT); c.rect(0, H-8, W, 8, fill=1, stroke=0)
    text(c, 'OCEANO AZUL / INTELIGÊNCIA GEOGRÁFICA', M, H-27, 350, 7.7, 11, True, ACCENT)
    c.setFillColor(MUTED); c.setFont('Training', 8); c.drawRightString(W-M, H-35, '23 NOV 2026')
    c.setStrokeColor(LINE); c.line(M, 52, W-M, 52)
    text(c, 'IJA DRONES  |  OCEANO AZUL', M, 40, 350, 8, 11, True)
    text(c, 'Relatório de atualização dos mapas', M, 25, 400, 7.3, 10, color=MUTED)
    c.setFont('Training', 8); c.drawRightString(W-M, 32, f'{page} / {TOTAL}')


def heading(c, number, title, subtitle):
    y = text(c, number, M, H-65, size=8.5, leading=12, bold=True, color=ACCENT)
    y = text(c, title, M, y-12, size=24, leading=30, bold=True)
    y = text(c, subtitle, M, y-10, size=10, leading=15, color=MUTED)
    return y-19


def body(c, value, y, x=M, width=CW, size=9.5, color=INK):
    return text(c, value, x, y, width, size, 14, color=color)


def section(c, title, y, x=M, width=CW):
    return text(c, title, x, y, width, 12, 16, True, ACCENT)-8


def figure(c, path, y, caption, width=CW, max_h=500, x=M):
    iw, ih = Image.open(path).size
    scale = min(width/iw, max_h/ih)
    dw, dh = iw*scale, ih*scale
    left = x+(width-dw)/2
    c.saveState()
    border = c.beginPath(); border.roundRect(left, y-dh, dw, dh, 7)
    c.clipPath(border, stroke=0)
    c.drawImage(ImageReader(str(path)), left, y-dh, dw, dh, mask='auto')
    c.restoreState()
    c.setStrokeColor(LINE); c.setLineWidth(.7); c.roundRect(left, y-dh, dw, dh, 7, fill=0, stroke=1)
    return text(c, caption, x, y-dh-8, width, 8, 11, color=MUTED)-15


def table(c, rows, y, widths, header):
    c.setFillColor(INK); c.roundRect(M, y-28, sum(widths), 28, 6, fill=1, stroke=0)
    x = M
    for value, width in zip(header, widths):
        text(c, value, x+10, y-8, width-20, 8.5, 12, True, colors.white); x += width
    y -= 28
    for index, row in enumerate(rows):
        parts=[paragraph(value, width-20, 8.6, 12) for value,width in zip(row,widths)]
        height=max(p[1] for p in parts)+18
        if index%2==0:
            c.setFillColor(SOFT); c.rect(M,y-height,sum(widths),height,fill=1,stroke=0)
        x=M
        for (p, ph), width in zip(parts,widths): p.drawOn(c,x+10,y-9-ph); x+=width
        y-=height
        c.setStrokeColor(LINE); c.line(M,y,M+sum(widths),y)
    return y-16


def end(c, y):
    if y<64: raise RuntimeError(f'Content overlaps footer: {y:.1f}')
    c.showPage()


def reference(c, label, url, y):
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from xml.sax.saxutils import escape
    style=ParagraphStyle('reference',fontName='Training',fontSize=8.4,leading=12,textColor=ACCENT)
    p=Paragraph(f'<link href="{escape(url, {chr(34): "&quot;"})}"><u>{escape(label)}</u></link>',style)
    _,h=p.wrap(CW,H);p.drawOn(c,M,y-h);return y-h-7


def build(assets, output):
    register_fonts();output.parent.mkdir(parents=True,exist_ok=True)
    tmp=Path('/tmp/ija-maps-report-review');tmp.mkdir(parents=True,exist_ok=True)
    # Recorte editorial da captura existente, incluindo a atribuição cartográfica.
    blank=tmp/'mapa-sem-fundo.jpg'
    Image.open(assets/'07-full.jpg').crop((128,115,1218,596)).save(blank,quality=96)
    c=canvas.Canvas(str(output),pagesize=(W,H),pageCompression=1)
    c.setTitle('Atualização do mapa de calor e territórios das UVIS - Oceano Azul')
    c.setAuthor('Relatório técnico do projeto')
    c.setSubject('Melhorias nos mapas, opções de camadas e evidências locais em 23/11/2026')
    c.setCreator('Gerado a partir do código, de capturas locais existentes e dos testes dos mapas')

    chrome(c,1)
    y=heading(c,'RELATÓRIO DE ATUALIZAÇÃO','Mapa de calor\ne territórios das UVIS','Geolocalização e Inteligência Geográfica. Consulta territorial, concentração de registros e opções de apresentação no mesmo ambiente.')
    y=body(c,'A atualização reúne a demarcação das UVIS de São Paulo, filtros territoriais e controles de camadas. A consulta por territórios e sobreposições segue a experiência visual solicitada como referência no GeoSampa.',y)-16
    y=figure(c,assets/'01-municipio-uvis.jpg',y,'Figura 1. Visão geral dos territórios das UVIS sobre o mapa de São Paulo, com preenchimentos e contornos próprios. Captura local existente de 23/11/2026.',max_h=260)
    gap=10;tw=(CW-gap*2)/3
    for i,(value,label) in enumerate([('28','UVIS na referência'),('96','distritos na referência'),('2','ambientes de consulta')]):
        x=M+i*(tw+gap);c.setFillColor(SOFT);c.roundRect(x,y-61,tw,61,8,fill=1,stroke=0)
        text(c,value,x+12,y-9,tw-24,23,29,True,ACCENT)
        text(c,label,x+12,y-40,tw-24,7.8,11,color=MUTED)
    y-=78
    y=panel(c,'Escopo das imagens','Os limites são da referência municipal importada. Os exemplos operacionais usam 60 registros fictícios em ambiente local descartável; não representam a situação sanitária real.',M,y)
    end(c,y)

    chrome(c,2)
    y=heading(c,'01 / TERRITÓRIOS E BUSCA','Demarcação por UVIS','A consulta permite localizar a unidade, enquadrar seu território e conferir os distritos vinculados à referência importada.')
    y=figure(c,assets/'02-filtros-territoriais.jpg',y,'Figura 2. Geolocalização: a busca de endereço permanece disponível e a aba Consultar áreas das UVIS oferece filtros de coordenadoria e unidade.',max_h=210)
    y=figure(c,assets/'03-consulta-uvis-se.jpg',y,'Figura 3. UVIS Sé selecionada, com contorno, nome, CNES e distritos. O entorno branco destaca a área consultada. Nomes e vínculos de coordenadoria seguem a base importada.',max_h=240)
    y=body(c,'Busque por coordenadoria ou UVIS, selecione a unidade e use Ver São Paulo inteiro para retornar ao enquadramento geral. Os nomes das UVIS aparecem ao aproximar o mapa.',y)
    end(c,y)

    chrome(c,3)
    y=heading(c,'02 / MAPA DE CALOR','Concentração no recorte escolhido','O calor é exibido junto ao território selecionado. A busca de registros operacionais é acionada pelo botão Filtrar.')
    y=figure(c,assets/'04-filtros-do-calor.jpg',y,'Figura 4. Filtros operacionais: UVIS responsável, mês, ano, foco da ação, larva visualizada e visão operacional.',max_h=135)
    y=figure(c,assets/'06-calor-uvis-se.jpg',y,'Figura 5. Exemplo do calor sobre a UVIS Sé. Os 60 registros foram criados para demonstração; as áreas mais intensas mostram a concentração visual desses registros fictícios.',max_h=235)
    y=panel(c,'Leitura das cores','As cores do calor representam concentração de registros. As cores dos territórios identificam as UVIS. Esses elementos não são uma classificação automática de risco epidemiológico ou um índice LIRAa.',M,y)-15
    y=body(c,'Como utilizar: escolha o período e os recortes permitidos, clique em Filtrar e consulte o resultado. Alterações nos campos preparam uma nova consulta; trocar de aba não busca novos registros por si só.',y)
    end(c,y)

    chrome(c,4)
    y=heading(c,'03 / APARÊNCIA DO MAPA','Layouts, nomes e cores','As opções ficam em Camadas do mapa, dentro da própria visualização. Cada camada pode ser ajustada conforme a necessidade de leitura.')
    left=185;right_x=M+205;right_w=CW-205
    ly=figure(c,assets/'07a-controles-de-fundo.jpg',y,'Figura 6. Recorte dos controles de nomes, distritos, fundo e locais.',width=left,max_h=240,x=M)
    ly=body(c,'Mapa e Satélite\nOs botões nativos no canto superior esquerdo alternam a base cartográfica. O controle Mostrar fundo do mapa permite ocultá-la.',ly,width=left)-16
    ly=body(c,'Nome e cor da UVIS\nAtive os nomes e aproxime o mapa para ver os rótulos. O preenchimento usa uma cor estável para identificar cada unidade. Na aba Calor, fica mais discreto para manter a densidade em destaque.',ly,width=left)
    rows=[
        ('Limites das UVIS','Exibe ou oculta os contornos territoriais.'),
        ('Colorir UVIS','Liga ou desliga o preenchimento com cores próprias de cada unidade.'),
        ('Nomes das UVIS','Exibe os rótulos quando o mapa está aproximado.'),
        ('Distritos','Mostra ou oculta a divisão distrital de referência.'),
        ('Mostrar fundo','Mantém a base cartográfica ou apresenta fundo branco.'),
        ('Satélite no entorno','Mostra também a área externa ao território destacado.'),
        ('Locais do Google','Controla nomes e ícones dos locais no mapa de fundo.'),
        ('São Paulo inteiro','Retorna ao enquadramento geral, quando disponível na tela.'),
    ]
    # Compact right-column table in the same visual system.
    from reportlab.platypus import Table,TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    style=ParagraphStyle('cell',fontName='Training',fontSize=8.4,leading=11.5,textColor=INK)
    head=ParagraphStyle('head',fontName='Training-Bold',fontSize=8.4,leading=11.5,textColor=colors.white)
    cells=[[Paragraph('Opção',head),Paragraph('Efeito',head)]]+[[Paragraph(a,style),Paragraph(b,style)] for a,b in rows]
    t=Table(cells,colWidths=[105,right_w-105]);t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),INK),('ROWBACKGROUNDS',(0,1),(-1,-1),[SOFT,colors.white]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    _,th=t.wrap(right_w,H);t.drawOn(c,right_x,y-th)
    y=min(ly,y-th)-18
    y=panel(c,'Foco na área selecionada','Ao selecionar uma UVIS ou coordenadoria, o branco no entorno facilita localizar o território. O usuário pode recuperar o contexto externo com Satélite no entorno ou ocultar todo o fundo mantendo os limites e os registros visíveis.',M,y)
    end(c,y)

    chrome(c,5)
    y=heading(c,'04 / FORMAS DE VISUALIZAÇÃO','Calor e Áreas','As duas abas apresentam leituras complementares do recorte. Os controles de fundo e território permanecem disponíveis no mapa.')
    y=figure(c,blank,y,'Figura 7. Fundo oculto: o contorno e a camada de calor permanecem visíveis. O painel informa a configuração aplicada. Exemplo com registros fictícios.',max_h=210)
    y=figure(c,assets/'08-areas-larvas.jpg',y,'Figura 8. Aba Áreas com os registros individuais. Neste exemplo fictício: 20 com larva observada, 20 sem observação de larva e 20 sem informação.',max_h=210)
    y=panel(c,'Registros individuais e quadras','Em Áreas, a cor dos registros pode seguir larva visualizada ou tipo de foco, e os pontos permitem consultar o histórico autorizado. A consulta de quadras fiscais do GeoSampa pertence a essa aba e depende da aproximação do mapa.',M,y)
    end(c,y)

    chrome(c,6)
    y=heading(c,'05 / ACESSO, FONTES E VERIFICAÇÃO','O que foi conferido','Revisão em 23/11/2026 sobre o código atual, a referência territorial importada e capturas locais existentes com dados fictícios.')
    y=table(c,[
        ('Python','84 testes aprovados','Filtros, geometrias, dados operacionais e acesso entre unidades.'),
        ('Subtestes','147 aprovados','Verificações adicionais das suítes Python selecionadas.'),
        ('JavaScript','30 testes aprovados','Camadas, nomes, cores, fundo, recortes e aplicação explícita de filtros.'),
    ],y,[85,142,CW-227],['Verificação','Resultado','Cobertura selecionada'])
    y=section(c,'Acesso aos registros e carregamento',y)
    y=body(c,'A consulta dos registros continua sujeita ao perfil, à prefeitura, à região e aos vínculos da conta. Visualizar o contorno público de outra UVIS não libera suas solicitações. A opção UVIS responsável usa o vínculo cadastral; o recorte territorial usa a referência geográfica.',y)-12
    y=body(c,'A atualização evita buscar registros antes do clique em Filtrar e adia o desenho dos pontos de Áreas até a abertura da aba. Esses comportamentos foram verificados em testes; não foi realizada uma medição de desempenho da hospedagem de produção.',y)-15
    y=section(c,'Origem da demarcação e referência GeoSampa',y)
    y=body(c,'Os contornos UVIS do sistema vêm da referência municipal/COVISA importada, com versão declarada de 27/07/2026 e limites simplificados para visualização. A semelhança com o GeoSampa tratada neste relatório é a consulta territorial por camadas; a fonte específica usada pelo sistema está identificada abaixo.',y)-11
    y=reference(c,'1. Referência municipal importada: Territórios UVIS / COVISA','https://www.google.com/maps/d/viewer?mid=1ZdzK_HpjS1xBTZbtGzHSq6y1OTzjW1XD',y)
    y=reference(c,'2. GeoSampa: catálogo oficial de metadados de UVIS','https://metadados.geosampa.prefeitura.sp.gov.br/geonetwork/srv/resources/datasets/36e2df68-8549-4795-98db-d2445c9a7241',y)
    y=reference(c,'3. Prefeitura: camadas geográficas e acesso ao GeoSampa','https://prefeitura.sp.gov.br/web/saude/w/epidemiologia_e_informacao/geoprocessamento_e_informacoes_socioambientais/265388',y)-6
    y=panel(c,'Escopo da evidência','As capturas registram o sistema executado localmente com SQLite descartável e 60 registros fictícios, conforme o manifesto preservado das imagens. Publicação, aceite e desempenho em produção permanecem fora desta verificação.',M,y)-13
    y=text(c,'Fontes locais: mapa_relatorio.html; controles de camadas; uvis-territory.js; municipal-satellite.js; mapas-territorio.js; base UVIS e suítes de testes. Imagens de fundo: Google Maps e fornecedores indicados nas capturas.',M,y,CW,7.5,10.5,color=MUTED)
    end(c,y)
    c.save();return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',type=Path,default=ROOT/'output/pdf/fontes/novos-mapas-20261123')
    parser.add_argument('--output',type=Path,default=ROOT/'output/pdf/relatorio-atualizacao-mapa-calor-uvis.pdf')
    args=parser.parse_args();print(build(args.assets,args.output))
