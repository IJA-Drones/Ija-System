from pathlib import Path
from xml.sax.saxutils import escape
import json

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.utils import ImageReader
from PIL import Image

ROOT = Path('/Users/pedrohenriquevb/Projetos/Empresa/Ija-System')
TMP = ROOT/'tmp/pdfs/novas-funcionalidades'
OUTPUT = ROOT/'output/pdf/IJA-System-Novas-Funcionalidades.pdf'
FONTDIR = Path('/System/Library/Fonts/Supplemental')
for name, file in [('Body','Arial.ttf'),('Bold','Arial Bold.ttf'),('Italic','Arial Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONTDIR/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Italic',boldItalic='Bold')
W, H = 595.2756, 841.8898
M = 46
CW = W-2*M
NAVY = HexColor('#183B56')
BLUE = HexColor('#1A4A7C')
TEAL = HexColor('#087B8C')
TEXT = HexColor('#263747')
MUTED = HexColor('#5A6D7D')
LIGHT = HexColor('#F0F5F8')
LINE = HexColor('#D8E4EA')
AMBER = HexColor('#FFF3DB')
GOLD = HexColor('#805315')
PALE = HexColor('#E5F3F5')
TOTAL = 12
C = canvas.Canvas(str(OUTPUT), pagesize=(W,H), pageCompression=1)
C.setTitle('IJA System | Novas funcionalidades de vigilância')
C.setSubject('Guia funcional: SINAN, LIRAa/focal e Ações realizadas. Revisão de 20/10/2026.')
C.setAuthor('')
C.setKeywords('IJA System, SINAN, LIRAa, focal, ações realizadas, guia funcional, demonstração')
positions = []


def p(text, x, y, width=CW, size=10.5, leading=15.4, color=TEXT, bold=False, align=TA_LEFT):
    style = ParagraphStyle('p',fontName='Bold' if bold else 'Body',fontSize=size,leading=leading,textColor=color,alignment=align,spaceAfter=0)
    para = Paragraph(text,style)
    _, height = para.wrap(width,10000)
    para.drawOn(C,x,y-height)
    positions.append((C.getPageNumber(),round(y-height,2),text[:75]))
    return y-height


def label(text,x,y,color=TEAL):
    C.setFillColor(color);C.setFont('Bold',8)
    C.drawString(x,y,text.upper())


def box(x,y,w,h,fill=LIGHT,stroke=None,r=10):
    C.setFillColor(fill)
    C.setStrokeColor(stroke or fill)
    C.roundRect(x,y-h,w,h,r,fill=1,stroke=bool(stroke))


def note(title,body,y,fill=PALE,color=TEAL):
    ph=Paragraph(body,ParagraphStyle('note',fontName='Body',fontSize=9.6,leading=13.7,textColor=TEXT))
    _,bh=ph.wrap(CW-32,10000)
    h=bh+47
    box(M,y,CW,h,fill)
    p(title,M+16,y-13,CW-32,size=10.2,leading=13,color=color,bold=True)
    p(body,M+16,y-33,CW-32,size=9.6,leading=13.7)
    return y-h-16


def bullet(title,body,y,num=None,x=M,width=CW):
    if num is not None:
        C.setFillColor(TEAL);C.circle(x+10,y-10,10,fill=1,stroke=0)
        C.setFillColor(white);C.setFont('Bold',9);C.drawCentredString(x+10,y-13,str(num))
        tx=x+30;tw=width-30
    else:
        C.setFillColor(TEAL);C.roundRect(x,y-7,4,4,1,fill=1,stroke=0)
        tx=x+15;tw=width-15
    y=p(title,tx,y,tw,size=10.7,leading=14.4,bold=True)
    y=p(body,tx,y-4,tw,size=10.1,leading=14.8)
    return y-17


def heading(kicker,title,subtitle='',source=''):
    key='p'+str(C.getPageNumber())
    C.bookmarkPage(key)
    C.addOutlineEntry(title,key,level=0)
    C.setFillColor(white);C.rect(0,0,W,H,fill=1,stroke=0)
    C.setFillColor(TEAL);C.rect(0,H-8,W,8,fill=1,stroke=0)
    label('IJA SYSTEM / GUIA FUNCIONAL',M,H-38)
    C.setFillColor(MUTED);C.setFont('Body',8)
    C.drawRightString(W-M,H-38,'20 OUT 2026  |  VERSÃO 1.0')
    label(kicker,M,H-80)
    y=p(title,M,H-96,CW,size=25,leading=29,color=NAVY,bold=True)
    if subtitle:y=p(subtitle,M,y-12,CW,size=10.6,leading=15.5,color=MUTED)
    y-=24
    C.setStrokeColor(LINE);C.line(M,52,W-M,52)
    C.setFillColor(MUTED);C.setFont('Body',7.7)
    C.drawString(M,36,'Vigilância municipal  |  Funcionalidades e exemplos de uso')
    C.drawRightString(W-M,36,f'{C.getPageNumber():02d} / {TOTAL}')
    if source:
        C.setFont('Body',6.8);C.drawString(M,22,f'Base funcional: {source}. Referências na página 12.')
    return y


def end():
    C.showPage()


def table(headers,rows,y,widths=None,fs=9.5):
    widths=widths or [CW/len(headers)]*len(headers)
    header_style=ParagraphStyle('header',fontName='Bold',fontSize=9,leading=12)
    head_height=max(30,max(Paragraph(text,header_style).wrap(w-24,10000)[1] for text,w in zip(headers,widths))+16)
    box(M,y,CW,head_height,NAVY,r=5)
    x=M
    for name,w in zip(headers,widths):
        p(name,x+12,y-8,w-24,size=9,leading=12,color=white,bold=True)
        x+=w
    y-=head_height
    for i,row in enumerate(rows):
        content=[];rh=0
        for text,w in zip(row,widths):
            para=Paragraph(text,ParagraphStyle('cell',fontName='Body',fontSize=fs,leading=fs*1.45,textColor=TEXT))
            _,h=para.wrap(w-24,10000);content.append((para,h));rh=max(rh,h)
        rh+=22
        C.setFillColor(LIGHT if i%2==0 else white);C.rect(M,y-rh,CW,rh,fill=1,stroke=0)
        x=M
        for (para,h),w in zip(content,widths):
            para.drawOn(C,x+12,y-11-h);x+=w
        C.setStrokeColor(LINE);C.line(M,y-rh,W-M,y-rh)
        y-=rh
    return y-18


def flow(items,y,colors=None):
    gap=14;w=(CW-gap*(len(items)-1))/len(items);h=77
    for i,(title,body) in enumerate(items):
        x=M+i*(w+gap)
        box(x,y,w,h,fill=LIGHT)
        label(str(i+1).zfill(2),x+12,y-17,(colors or [TEAL]*len(items))[i])
        p(title,x+12,y-25,w-24,size=10.2,leading=13,bold=True,color=NAVY)
        p(body,x+12,y-44,w-24,size=8.3,leading=11,color=MUTED)
        if i<len(items)-1:
            C.setStrokeColor(TEAL);C.line(x+w+3,y-h/2,x+w+gap-4,y-h/2)
            path=C.beginPath();path.moveTo(x+w+gap-3,y-h/2);path.lineTo(x+w+gap-7,y-h/2+3);path.lineTo(x+w+gap-7,y-h/2-3);path.close()
            C.setFillColor(TEAL);C.drawPath(path,fill=1,stroke=0)
    return y-h-22


def picture(file,x,y,width,maxheight=None):
    with Image.open(file) as im: iw,ih=im.size
    height=width*ih/iw
    if maxheight and height>maxheight:
        width*=maxheight/height;height=maxheight
    C.setStrokeColor(LINE);C.setFillColor(white);C.roundRect(x-3,y-height-3,width+6,height+6,6,fill=1,stroke=1)
    C.drawImage(ImageReader(str(file)),x,y-height,width=width,height=height,mask='auto')
    return y-height,width,height

# 01 - cover
C.bookmarkPage('p1')
C.addOutlineEntry('Capa','p1',level=0)
C.setFillColor(LIGHT);C.rect(0,0,W,H,fill=1,stroke=0)
C.setFillColor(white);C.rect(0,H-100,W,100,fill=1,stroke=0)
label('IJA SYSTEM',M,H-46,BLUE)
C.setFillColor(MUTED);C.setFont('Body',9);C.drawString(M,H-66,'DOCUMENTAÇÃO FUNCIONAL')
C.drawImage(str(ROOT/'app/static/img/logo_oceano_azul_light.png'),W-M-155,H-78,width=155,height=43,preserveAspectRatio=True,mask='auto')
label('VIGILÂNCIA MUNICIPAL',M,H-158)
y=p('Novas<br/>funcionalidades',M,H-184,CW,size=39,leading=44,color=NAVY,bold=True)
y=p('SINAN, LIRAa/focal e<br/>Ações realizadas',M,y-24,CW,size=22,leading=28,color=BLUE)
y=p('Guia explicativo dos recursos, dos fluxos de trabalho e dos cuidados para interpretar e divulgar as informações do sistema.',M,y-25,430,size=12,leading=18,color=MUTED)
start=y-34
for i,(code,title,body) in enumerate([
    ('01','Consultar','Notificações e recortes do SINAN'),
    ('02','Registrar e analisar','Planejamento, visitas e resultados de campo'),
    ('03','Divulgar','Publicações aprovadas no Portal do Cidadão')]):
    w=(CW-24)/3;x=M+i*(w+12)
    box(x,start,w,116,white,LINE)
    label(code,x+14,start-22)
    p(title,x+14,start-36,w-28,size=12,leading=16,bold=True,color=NAVY)
    p(body,x+14,start-73,w-28,size=9.5,leading=13.5,color=MUTED)
C.setFillColor(NAVY);C.rect(0,0,W,150,fill=1,stroke=0)
p('VERSÃO EXPLICATIVA / 20 DE OUTUBRO DE 2026',M,116,CW,size=9,leading=13,color=white,bold=True)
p('As capturas usam dados fictícios da demonstração local. O design de SINAN e LIRAa está em finalização; os fluxos são descritos a partir do código e da documentação atual.',M,89,CW,size=10.1,leading=15,color=HexColor('#D4E4ED'))
C.setFillColor(white);C.setFont('Body',8);C.drawRightString(W-M,27,'01 / 12')
end()

# 02 - overview
Y=heading('VISÃO GERAL','Três frentes, um fluxo de trabalho','Cada módulo responde a uma pergunta diferente e conserva a origem da informação.','S1 a S6')
Y=table(['Frente','Para que serve','O que entrega'],[
    ('<b>SINAN</b>','Consultar notificações de arboviroses e guardar recortes para consulta.','Tabela, indicadores do recorte, lotes salvos, CSV e visualização geográfica quando há coordenadas.'),
    ('<b>LIRAa e focal</b>','Planejar e registrar o trabalho de campo da prefeitura.','Território, amostra informada, visitas, indicadores preliminares e comparação de camadas.'),
    ('<b>Ações realizadas</b>','Divulgar à população uma atividade já realizada e autorizada.','Rascunho revisado, página pública, mídias selecionadas e links de compartilhamento.')],Y,[95,194,CW-289],9.1)
Y=note('A origem faz diferença','Notificação SINAN não é automaticamente um caso confirmado. Uma OS não substitui uma inspeção LIRAa. Uma publicação no portal é comunicação da atividade, e não um registro epidemiológico.',Y)
Y=p('Como navegar neste guia',M,Y,CW,size=16,leading=20,bold=True,color=NAVY)-15
for title,pages in [('Consulta e dados salvos do SINAN','03-04'),('Planejamento, visitas e resultados de campo','05-07'),('Preparação, publicação e acesso da população','08-10'),('Permissões e condições de uso','11'),('Roteiro de demonstração e referências','12')]:
    C.setStrokeColor(LINE);C.line(M,Y-25,W-M,Y-25)
    p(title,M,Y,CW-65,size=10.2,leading=14)
    C.setFillColor(TEAL);C.setFont('Bold',10);C.drawRightString(W-M,Y-11,pages)
    destination=int(pages.split('-')[0])
    C.linkRect('',f'p{destination}',(M,Y-25,W-M,Y+3),relative=0,thickness=0)
    Y-=39
end()

# 03 - SINAN query
Y=heading('01 / SINAN','Consultar notificações','Entrada: Vigilância > SINAN - Arboviroses > Consulta pública.','S1')
Y=flow([('Filtrar','Doença, município e ano'),('Consultar','Leitura paginada da fonte'),('Interpretar','Página atual e contexto')],Y)
Y=bullet('Selecione o recorte','Escolha dengue, zika ou chikungunya, o município de notificação e o ano. O catálogo contempla São Paulo capital e os 15 municípios do CONDOMAR.',Y,1)
Y=bullet('Leia a tabela e navegue','Cada página apresenta até 10 notificações, com semana epidemiológica, classificação e informação de residência no mesmo município, em outro município ou não informada. Use Anterior e Próxima para navegar.',Y,2)
Y=bullet('Consulte os detalhes do recorte','Indicadores desta página reúne os dados das linhas exibidas. Sobre os dados informa a fonte e os limites. As contagens da página não representam, por si só, o total municipal.',Y,3)
Y=bullet('Refaça a consulta quando necessário','Alterar filtros ou usar Limpar busca limpa o recorte anterior. Em falhas, Tentar novamente preserva a leitura anterior; Interromper cancela a consulta pendente.',Y,4)
Y=note('Como interpretar uma resposta vazia','O retorno sem registros descreve a consulta à fonte naquele momento. Ele não comprova ausência de casos. O município selecionado é o da notificação e pode incluir moradores de outras cidades.',Y,AMBER,GOLD)
end()

# 04 - saved SINAN
Y=heading('01 / SINAN','Guardar, exportar e comparar','A aba Dados salvos reúne os lotes importados e as opções de consulta posterior.','S1, S4')
Y=table(['Origem do lote','Como funciona','Uso no mapa'],[
    ('<b>Importar da API</b>','Importação em segundo plano, com até 100 registros. O lote pode ser parcial; não representa o total do município.','A fonte consumida não oferece coordenadas individuais. Os agregados não viram pontos de casos.'),
    ('<b>Importar CSV</b>','Modelo próprio com até 100 casos e coordenadas fornecidas pela equipe. O arquivo inteiro é validado antes da publicação.','Os pontos usam as coordenadas do arquivo e a classificação informada. Não há geolocalização automática a partir da API.')],Y,[105,216,CW-321],9.2)
Y=bullet('Acompanhe a importação','Consulte andamento, situação e origem do lote. Uma carga parcial ou com falha não substitui a última importação completa da API. Não há continuação automática entre lotes.',Y,1)
Y=bullet('Exporte o recorte selecionado','O CSV exportado lê o lote salvo, sem consultar novamente a fonte. Origem, situação, filtros e horário de importação ajudam a contextualizar o arquivo.',Y,2)
Y=bullet('Compare somente os dados compatíveis','A integração com os resultados de campo exige o vínculo correto entre a prefeitura e o IBGE, além de doença, ano, modo e conta compatíveis. Os períodos de campo e SINAN mantêm suas referências próprias.',Y,3)
Y=note('Regras práticas para os arquivos','O CSV usa referências sem identificação pessoal. A autorização é exigida para conteúdo real; os modelos de demonstração são identificados como fictícios. O limite de 100 registros é por importação, sem consolidação automática de todos os lotes.',Y)
end()

# 05 - planning
Y=heading('02 / LIRAa E FOCAL','Planejar o levantamento','A coordenação municipal organiza o território, a amostra informada e as atribuições dos agentes.','S2')
Y=flow([('Território','Quarteirões e contornos'),('Plano','Estratos, metas e agentes'),('Liberação','Conferir e iniciar visitas')],Y)
Y=bullet('Cadastre o território','Informe código estável do quarteirão, bairro, área, número de imóveis e referência da fonte. Quando disponível, o mapa permite desenhar ou ajustar um contorno e confirmar antes de salvar.',Y,1)
Y=bullet('Defina o levantamento e os estratos','Cadastre código, período, responsável técnico e fonte do plano amostral. Informe a população de imóveis e a meta de cada estrato.',Y,2)
Y=bullet('Selecione os quarteirões da amostra','Vincule os quarteirões já cadastrados ao estrato, defina suas metas e atribua, quando necessário, uma conta individual de agente da mesma prefeitura.',Y,3)
Y=bullet('Revise e libere o plano','As metas dos quarteirões precisam fechar a meta do estrato e respeitar sua população de imóveis. Após a liberação, o plano fica protegido contra edição direta. Encerrar o plano interrompe novas confirmações.',Y,4)
Y=note('O que a coordenação continua definindo','O sistema registra a amostra informada. Ele não executa sorteio nem calcula automaticamente o tamanho da amostra. O contorno desenhado também não conta imóveis nem valida o planejamento amostral.',Y,AMBER,GOLD)
end()

# 06 - field
Y=heading('02 / LIRAa E FOCAL','Registrar e confirmar uma visita','Os registros só entram na base confirmada depois da revisão e da confirmação do lote.','S2, S3')
Y=bullet('O agente acessa a própria área','No login principal, a conta Agente de Endemias entra em Meus levantamentos. São mostrados seus quarteirões de planos liberados, dentro da prefeitura da conta e com separação entre demonstração e dados autorizados.',Y,1)
Y=bullet('Informe os dados efetivos do campo','Registre códigos estáveis de imóvel e inspeção, data e situação da visita. No LIRAa, o contexto de levantamento, estrato, bairro e área vem do plano; a participação na amostra precisa ser declarada.',Y,2)
Y=bullet('Registre somente o resultado identificado','Imóvel inspecionado recebe positividade identificada para Aedes aegypti. Quando fornecidas, as sete contagens de recipientes positivos devem ser completas e coerentes com o resultado. Fechado, recusado e não inspecionado ficam sem positividade.',Y,3)
Y=bullet('Revise antes de gravar','O sistema prepara uma prévia e valida conflitos, vínculo e período. A confirmação efetiva a gravação da visita na base de campo. Reenvios idênticos são reaproveitados para evitar duplicidade.',Y,4)
Y=note('Como uma OS pode ajudar','Na área da coordenação, uma OS acessível pode fornecer uma referência para conferência. O imóvel, a data da inspeção, a amostra e o resultado precisam ser confirmados. O registro não deduz uma inspeção LIRAa apenas porque existe uma OS.',Y)
Y=p('Responsabilidade individual',M,Y,CW,size=14,leading=19,bold=True,color=NAVY)-7
p('Cada confirmação conserva a autoria da conta. O agente não recebe acesso geral ao planejamento, ao SINAN, às OS ou aos registros de outra conta.',M,Y,CW,size=10.1,leading=15)
end()

# 07 - results
Y=heading('02 / LIRAa E FOCAL','Entender os resultados e os mapas','Os painéis preservam as fontes: inspeção de campo, tratamento focal, notificações e histórico agregado.','S3, S4, S5')
Y=table(['Indicador do painel','O que expressa','Dependência'],[
    ('<b>IIP</b>','Proporção de imóveis positivos entre os imóveis efetivamente inspecionados.','Conta imóveis únicos no grupo. Fechados, recusados e não inspecionados não entram no denominador.'),
    ('<b>Breteau</b>','Recipientes positivos para cada 100 imóveis inspecionados.','Exige contagens completas de recipientes. Pode ser maior que 100.'),
    ('<b>ITR</b>','Participação de cada categoria no total de recipientes positivos.','Depende de recipientes positivos e de contagens completas. Informação ausente não é tratada como zero.')],Y,[90,198,CW-288],9.2)
Y=note('Exemplo fictício de leitura','Dois imóveis inspecionados, um positivo e dois recipientes positivos da categoria B resultam em IIP de 50%, Breteau de 100 e ITR B de 100%. Uma visita fechada e uma ação focal não alteram esses denominadores.',Y)
Y=p('Duas leituras territoriais diferentes',M,Y,CW,size=15,leading=20,bold=True,color=NAVY)-12
Y=bullet('Levantamento LIRAa','Consulta visitas e IIP do levantamento selecionado, com tabelas, gráficos e contornos disponíveis. CSV, GeoJSON e impressão/salvar PDF apoiam a consulta do recorte. Os índices permanecem preliminares.',Y)
Y=bullet('Histórico de casos - área avançada','Analisa concentrações e recorrência a partir de contornos territoriais e contagens anuais de casos fornecidas. A classificação depende de histórico completo de ao menos cinco anos e é exploratória. Não prevê a data de um surto.',Y)
end()

# 08 - preparation with screenshot
Y=heading('03 / AÇÕES REALIZADAS','Preparar a divulgação','Entrada: Vigilância > Ações realizadas > Preparar divulgação.','S6')
Y=p('Prepare título, tipo de ação, prefeitura, bairro ou área, período e descrição pública. A divulgação pode começar manualmente ou pelo atalho Preparar divulgação de uma OS concluída e acessível. Fotos e vídeos são escolhidos no editor.',M,Y,CW,size=10.5,leading=15.5)-18
bottom,iw,ih=picture(TMP/'editor.png',M+49,Y,405,maxheight=415)
Y=p('Captura real do editor local. Conteúdo e prefeitura fictícios; dados preenchidos apenas para demonstração.',M,bottom-12,CW,size=8.6,leading=12.3,color=MUTED)-16
Y=note('A OS é uma referência interna','Endereço completo, observações operacionais e mídias não são copiados automaticamente para o portal. O editor prepara cópias próprias dos arquivos escolhidos e exige revisão antes de publicar.',Y)
end()

# 09 - approval
Y=heading('03 / AÇÕES REALIZADAS','Revisar, publicar e retirar','A versão aprovada fica separada das alterações ainda em preparação.','S6')
Y=flow([('Rascunho','Preparar texto e arquivos'),('Em revisão','Conferir e autorizar'),('Publicado','Disponível à população'),('Retirado','Bloquear o acesso público')],Y)
Y=bullet('Confira a prévia','Conferir prévia permite visualizar o texto e as mídias antes da divulgação. Enviar para revisão bloqueia a edição; para corrigir, devolva ao rascunho.',Y,1)
Y=bullet('Confirme a autorização','A conta com permissão para publicar confirma a autorização do texto e de todas as mídias selecionadas. Só então a página fica disponível no portal.',Y,2)
Y=p('O que acontece quando a ação é editada?',M,Y,CW,size=15,leading=20,bold=True,color=NAVY)-14
box(M,Y,CW,123,LIGHT)
p('VERSÃO JÁ APROVADA',M+16,Y-17,200,size=8.5,leading=12,color=TEAL,bold=True)
p('Continua visível no portal.',M+16,Y-40,200,size=12,leading=17,bold=True,color=NAVY)
p('A população consulta o último conteúdo que recebeu autorização.',M+16,Y-67,200,size=9.5,leading=14,color=MUTED)
C.setStrokeColor(LINE);C.line(M+CW/2,Y-17,M+CW/2,Y-107)
p('NOVO RASCUNHO',M+CW/2+16,Y-17,200,size=8.5,leading=12,color=TEAL,bold=True)
p('Permanece no editor.',M+CW/2+16,Y-40,200,size=12,leading=17,bold=True,color=NAVY)
p('Só substitui a versão pública depois de nova revisão e publicação.',M+CW/2+16,Y-67,200,size=9.5,leading=14,color=MUTED)
Y-=145
Y=bullet('Retire a publicação quando necessário','Retirar do portal bloqueia novas consultas públicas à página e às mídias. O conteúdo e os eventos permanecem no histórico interno da ação.',Y,3)
Y=note('Limite do compartilhamento externo','A retirada impede novos acessos pelo sistema. Ela não apaga arquivos já baixados nem prévias eventualmente conservadas por aplicativos e redes sociais.',Y,AMBER,GOLD)
end()

# 10 - public
Y=heading('03 / AÇÕES REALIZADAS','O que a população acessa','As páginas públicas dispensam login e mostram somente o conteúdo aprovado.','S6')
Y=p('O visitante pode filtrar prefeitura e período, abrir a ação e consultar texto, local resumido, datas e mídias autorizadas. Demonstrações aparecem separadas do conteúdo autorizado e são identificadas como fictícias.',M,Y,CW,size=10.5,leading=15.5)-16
# Two real captures; different roles are identified in captions.
leftw=315;rightx=M+leftw+22;rightw=CW-leftw-22
bottom,lw,lh=picture(TMP/'publicacao.png',M,Y,leftw,maxheight=310)
b2,rw,rh=picture(TMP/'cartao-publico.png',rightx,Y,rightw,maxheight=310)
Y=min(bottom,b2)-12
Y=p('Capturas reais da demonstração: detalhe público (esquerda) e cartão na lista de ações (direita). Nenhuma atividade municipal real está representada.',M,Y,CW,size=8.6,leading=12.3,color=MUTED)-20
Y=p('Compartilhamento iniciado pelo visitante',M,Y,CW,size=15,leading=20,bold=True,color=NAVY)-12
Y=table(['Opção','Como funciona'],[
    ('<b>Copiar link</b>','Copia o endereço público para que o visitante o use onde preferir.'),
    ('<b>Compartilhar</b>','Abre o compartilhamento nativo quando o navegador oferece esse recurso.'),
    ('<b>WhatsApp e Facebook</b>','Abrem o aplicativo ou a página de compartilhamento. O visitante escolhe o destino e confirma o envio.')],Y,[140,CW-140],9.5)
Y=p('O sistema não envia mensagens nem publica automaticamente em contas de redes sociais.',M,Y,CW,size=9.6,leading=14,color=MUTED)
end()

# 11 - access/readiness
Y=heading('USO E ATIVAÇÃO','Acesso, arquivos e condições de uso','A existência do recurso no código não confirma sua ativação em cada ambiente.','S1 a S6')
Y=table(['Perfil / acesso','Papel no fluxo'],[
    ('<b>COVISA e coordenação</b>','Coordenar planejamento e consultar os módulos, respeitando prefeitura, habilitação e permissões configuradas.'),
    ('<b>Agente de Endemias</b>','Registrar visitas nos quarteirões atribuídos a sua conta, sem acesso geral aos demais módulos.'),
    ('<b>Editor / publicador</b>','A Central de TI pode separar quem prepara a divulgação de quem autoriza a publicação. As ações permanecem no alcance municipal da conta.'),
    ('<b>População</b>','Consultar somente publicações aprovadas e mídias selecionadas para acesso público.')],Y,[145,CW-145],9.2)
Y=p('Condições para colocar em uso',M,Y,CW,size=15,leading=20,bold=True,color=NAVY)-12
Y=bullet('Ações realizadas','Implementado e demonstrado localmente. O ambiente real ainda precisa receber a migração preparada e a ativação do módulo, com revisão dos acessos. Para vídeo, o servidor precisa do FFmpeg configurado.',Y)
Y=bullet('Campo, mapas e SINAN','Conferir a estrutura do banco, a configuração dos módulos e vínculo prefeitura/IBGE do ambiente. O Google Maps precisa de chave e domínio autorizados. Arquivos municipais devem seguir os modelos e ser validados pela equipe.',Y)
Y=bullet('Volume e arquivos','SINAN: até 100 registros por importação. Publicações: até cinco mídias selecionadas; imagens até 10 MiB e MP4 até 50 MiB. O fluxo atual de campo tem limites próprios de lotes e tamanho da base, que exigem revisão antes de campanhas de grande volume.',Y)
Y=note('Interface em evolução','O design de SINAN e LIRAa está em finalização. Ações realizadas foi conferido no Chrome em larguras de 320, 390, 430 e 1440 px, nos temas claro e escuro. Isso não equivale a um aceite final de todos os módulos em aparelhos físicos.',Y,AMBER,GOLD)
end()

# 12 - demonstration and sources
Y=heading('ROTEIRO E REFERÊNCIAS','Como apresentar as funcionalidades','Use dados fictícios identificados e mostre os resultados de cada etapa.','')
for num,title,body in [
    (1,'Consultar o SINAN','Escolha doença, município e ano; mostre a paginação e o alcance dos indicadores da página.'),
    (2,'Abrir um lote salvo','Mostre origem, situação, limites e exportação do lote. Explique a diferença entre a API e um CSV com coordenadas.'),
    (3,'Percorrer o planejamento e o campo','Mostre território, estratos, metas e atribuições. Registre uma visita fictícia, revise e confirme; confira o resultado preliminar.'),
    (4,'Preparar e publicar uma ação','Escolha texto e mídias, confira a prévia, envie para revisão e publique com a confirmação de autorização.'),
    (5,'Acessar como visitante e retirar','Abra o portal sem login, mostre a página e copie o link. Depois retire a publicação e confirme o bloqueio da página e das mídias.')]:
    Y=bullet(title,body,Y,num)
Y=p('Base técnica consultada',M,Y,CW,size=14,leading=18,bold=True,color=NAVY)-10
sources=[
    ('S1','Consulta pública e importações SINAN','docs/sinan-consulta-publica.md'),
    ('S2','Território e planejamento LIRAa','docs/vigilancia-planejamento.md'),
    ('S3','Registro e indicadores de campo','docs/vigilancia-registro-campo.md'),
    ('S4','Resultados e comparação de camadas','docs/vigilancia-resultados-poc.md'),
    ('S5','Mapa LIRAa e histórico agregado','app/modules/vigilancia/risk_routes.py e risk.py'),
    ('S6','Editor e publicação de ações','docs/acoes-publicas.md e app/modules/acoes_publicas/')]
for code,title,path in sources:
    Y=p(f'<b>{code} - {title}</b><br/><font color="#5A6D7D">{escape(path)}</font>',M,Y,CW,size=8.3,leading=11.4)-7
Y=p('Revisão do código e da documentação em 20/10/2026. Este guia explica o produto e a demonstração; não certifica atendimento integral ao edital nem homologação epidemiológica.',M,Y-2,CW,size=8.4,leading=12,color=MUTED)
end()

bad=[r for r in positions if r[1]<62 and r[0]!=1]
if bad:
    raise RuntimeError('Conteúdo abaixo da área útil: '+repr(bad))
C.save()
(TMP/'layout-positions.json').write_text(json.dumps(positions,ensure_ascii=False,indent=2))
print(OUTPUT)
print('Páginas:',TOTAL,'| Menor posição de texto:',min(y for page,y,text in positions if page!=1))
