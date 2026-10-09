from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from PIL import Image

ROOT=Path('/Users/joaopedro/Documents/Ija-System')
ASSETS=ROOT/'tmp/pdfs/triagem/assets'
OUT=ROOT/'output/pdf/guia-chatbot-portal-cidadao.pdf'
FONT=Path('/Users/joaopedro/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype')
for name,file in [('Sans','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf'),('BoldItalic','DejaVuSans-BoldOblique.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
pdfmetrics.registerFontFamily('Sans',normal='Sans',bold='Bold',italic='Sans',boldItalic='BoldItalic')
W,H=landscape(A4)
NAVY=colors.HexColor('#123C57'); BLUE=colors.HexColor('#215B87'); TEAL=colors.HexColor('#009CB5')
INK=colors.HexColor('#233748'); MUTED=colors.HexColor('#5C7280'); LIGHT=colors.HexColor('#EFF6F8'); BORDER=colors.HexColor('#D9E5EA'); WHITE=colors.white
c=canvas.Canvas(str(OUT),pagesize=(W,H),pageCompression=1)
c.setTitle('Portal do Cidadão | Guia do chatbot com IA')
c.setAuthor('Time de desenvolvimento da IJA DRONES')
c.setSubject('Funcionalidades, uso e limites do Assistente do cidadão')
PAGE=0

def rect(x,y,w,h,fill,r=0,stroke=None):
    c.setFillColor(fill); c.setStrokeColor(stroke or fill)
    if r:c.roundRect(x,H-y-h,w,h,r,fill=1,stroke=bool(stroke))
    else:c.rect(x,H-y-h,w,h,fill=1,stroke=bool(stroke))

def text(s,x,y,w,size=11,color=INK,bold=False,leading=None):
    style=ParagraphStyle('t',fontName='Bold' if bold else 'Sans',fontSize=size,leading=leading or size*1.4,textColor=color)
    p=Paragraph(s,style); aw,ah=p.wrap(w,1000)
    p.drawOn(c,x,H-y-ah)
    if y < H-28 and y+ah>H-28: raise ValueError(f'Text overflow page {PAGE}: {s[:65]}')
    return ah

def tag(s,x,y,w=135):
    rect(x,y,w,24,LIGHT,12);text(s,x+10,y+5,w-20,8.5,BLUE,True)

def header(section,title,subtitle=''):
    global PAGE
    PAGE+=1
    rect(0,0,W,H,WHITE)
    rect(0,0,W,7,TEAL)
    text('IJA DRONES  /  ASSISTENTE DO CIDADÃO',34,21,500,8,BLUE,True)
    text(section.upper(),610,21,198,8,MUTED,True)
    text(title,34,45,W-68,24,NAVY,True,28)
    if subtitle:text(subtitle,34,80,W-68,10,MUTED)
    c.bookmarkPage(f'p{PAGE}');c.addOutlineEntry(title,f'p{PAGE}',0)

def footer():
    c.setStrokeColor(BORDER);c.line(34,30,W-34,30)
    text('IJA DRONES',34,H-44,600,8.5,BLUE,True)
    text('<b><i>Documento elaborado pelo time de desenvolvimento da IJA DRONES</i></b>',34,H-23,690,7.3,MUTED)
    text(f'{PAGE:02d} / 06',W-83,H-23,55,8,BLUE,True)
    c.showPage()

def image(name,x,y,w,h):
    p=ASSETS/name
    iw,ih=Image.open(p).size
    scale=min(w/iw,h/ih);dw,dh=iw*scale,ih*scale
    xx=x+(w-dw)/2; yy=y+(h-dh)/2
    c.drawImage(str(p),xx,H-yy-dh,width=dw,height=dh,mask='auto')
    return xx,yy,dw,dh

def callout(title,body,x,y,w,h=90):
    rect(x,y,w,h,LIGHT,10)
    text(title,x+15,y+12,w-30,11,BLUE,True)
    text(body,x+15,y+33,w-30,10,INK,leading=14)

def steps(items,x,y,w,size=11,gap=17):
    for i,(title,body) in enumerate(items,1):
        rect(x,y,23,23,TEAL,11)
        text(str(i),x+7,y+4,16,10,WHITE,True)
        th=text(title,x+35,y,w-35,size,BLUE,True)
        bh=text(body,x+35,y+th+4,w-35,size-0.4)
        y+=max(25,th+bh+4)+gap
    return y

def table(rows,widths,x,y,font=10,rowpad=11):
    sty=ParagraphStyle('cell',fontName='Sans',fontSize=font,leading=font*1.4,textColor=INK)
    head=ParagraphStyle('head',parent=sty,fontName='Bold',textColor=WHITE)
    data=[[Paragraph(v,head if i==0 else sty) for v in row] for i,row in enumerate(rows)]
    t=Table(data,colWidths=widths,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BLUE),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),rowpad),('BOTTOMPADDING',(0,0),(-1,-1),rowpad),('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,LIGHT]),('LINEBELOW',(0,1),(-1,-1),0.5,BORDER)]))
    tw,th=t.wrap(1000,1000)
    if y+th>H-38:raise ValueError(f'Table overflow {PAGE} {th}')
    t.drawOn(c,x,H-y-th)
    return th

def screenshot_page(section,title,subtitle,filename,caption,notes):
    header(section,title,subtitle)
    image(filename,34,105,W-68,391)
    text(caption,34,499,W-68,8.3,MUTED)
    text(notes,34,517,W-68,10,INK,leading=13)
    footer()

header('Guia de uso','Chatbot com IA do Portal do Cidadão')
text('ORIENTAÇÃO E REGISTRO ASSISTIDO',34,110,480,11,TEAL,True)
text('Ajuda para entender o portal e registrar um relato.',34,144,405,27,NAVY,True,34)
text('O Assistente do cidadão conversa em português, explica como usar o portal e pode consultar fontes oficiais para apoiar dúvidas sobre vigilância e prevenção.',34,263,396,13,MUTED,leading=19)
callout('Onde encontrar','No portal, clique em Ajuda com IA. Dentro da janela, é possível enviar perguntas, acessar o boletim e iniciar um relato guiado.',34,382,396,105)
image('portal-chat.jpg',458,106,347,399)
text('Tela real: formulário de relato aberto dentro do assistente.',458,515,347,8.5,MUTED)
footer()

header('Funcionalidades','O que é possível fazer no chatbot','O assistente reúne orientação por conversa e um formulário de registro dentro da mesma janela.')
table([
 ['Recurso','Como ajuda o cidadão','Como usar'],
 ['<b>Tirar dúvidas sobre o portal</b>','Explica os campos, o registro de ocorrências e as etapas gerais do atendimento.','Digite uma pergunta em Como posso ajudar? e clique em Enviar mensagem.'],
 ['<b>Buscar orientação em fontes oficiais</b>','Pode pesquisar informações externas sobre vigilância, prevenção e serviços públicos relacionados.','Faça uma pergunta objetiva e confira os links apresentados, quando houver pesquisa.'],
 ['<b>Acessar o boletim de saúde</b>','Direciona para a página do boletim, que apresenta fonte, período, município e filtros.','Use o atalho Boletim de saúde dentro da janela.'],
 ['<b>Registrar um relato</b>','Abre um formulário guiado em cinco etapas, com identificação, anexos opcionais e revisão.','Clique em Registrar relato e avance pelos campos até confirmar o envio.'],
 ['<b>Limpar a conversa</b>','Remove as mensagens exibidas e reinicia o contexto da conversa na interface.','Use Limpar conversa. Isso não exclui denúncias já cadastradas.'],
 ],[176,304,294],34,118,10.5,12)
text('<b>Dois usos diferentes:</b> a conversa oferece orientação; o formulário guiado realiza o cadastro após confirmação.',34,523,773,10,MUTED)
footer()

header('Conversa e fontes','Como fazer perguntas e avaliar as respostas','Exemplos de perguntas que o cidadão pode enviar. Não são transcrições de respostas da IA.')
steps([
 ('Dúvidas sobre o funcionamento','“Como registro um foco de água parada?”<br/>“Preciso informar o RG?”<br/>“Posso anexar fotos ao relato?”'),
 ('Orientações de prevenção','“Onde encontro orientações oficiais para evitar criadouros?”<br/>“Quais cuidados gerais ajudam a prevenir água parada?”'),
 ('Informações sobre o boletim','“Como vejo o boletim de dengue?”<br/>“Onde encontro dados oficiais de dengue em São Paulo?”'),
],34,122,427,11,22)
callout('Informações do próprio portal','Para explicar como usar o sistema, o assistente utiliza o contexto público do portal: campos, categorias, páginas disponíveis e regras do registro.',491,118,317,113)
callout('Informações externas','Quando necessário e disponível, a pesquisa consulta fontes oficiais, como órgãos de governo, Prefeitura de São Paulo, Secretaria de Saúde e Fiocruz.',491,248,317,120)
callout('Confira antes de utilizar','Ao receber números ou dados atuais, confira município, período e fonte. Sem pesquisa disponível ou evidência suficiente, a resposta não deve ser tratada como confirmação de dados atuais.',491,385,317,142)
footer()

header('Relato dentro do chat','Cinco etapas para registrar uma ocorrência','Abra Ajuda com IA e clique em Registrar relato. Use os campos do formulário guiado.')
steps([
 ('Ocorrência','Selecione o tipo de situação e o foco. Para Aedes, informe também o tipo de local.'),
 ('Endereço','Informe logradouro, número, bairro e cidade. O CEP é opcional; confira os dados obtidos por CEP ou localização.'),
 ('Identificação','Preencha nome completo, CPF e telefone com DDD. O RG é opcional. Informe esses dados nos campos próprios, não na conversa.'),
 ('Detalhes','Descreva o problema. Se desejar, anexe até cinco fotos ou vídeos para ajudar a equipe a entender a situação.'),
 ('Revisão e envio','Confira os dados, confirme o consentimento e clique em Confirmar e enviar. Aguarde o resultado e guarde o protocolo exibido.'),
],34,118,454,11,15)
image('portal-chat.jpg',519,112,288,304)
callout('Continuar e voltar','Use Continuar para avançar e Voltar para revisar a etapa anterior. Voltar à conversa permite retornar às perguntas. O formulário também pode ser retomado na página.',519,427,288,111)
footer()

header('Confirmação e cuidado com os dados','Quando o relato está realmente registrado','Uma resposta da IA ou uma conversa sobre a ocorrência não comprova o cadastro de uma denúncia.')
callout('Orientação na conversa','A IA pode explicar como registrar, quais campos preencher e onde encontrar informações. Ela não gera protocolos nem confirma registros apenas por uma mensagem.',34,118,375,129)
callout('Confirmação do formulário','O cadastro ocorre após Confirmar e enviar. Somente a confirmação de sucesso do sistema, com o protocolo real, comprova o registro do relato.',433,118,375,129)
text('DADOS PESSOAIS',34,280,375,10,TEAL,True)
text('Nome, CPF e telefone devem ser informados apenas no formulário de identificação. Esses campos são enviados diretamente ao sistema, sem passar pelo modelo de IA.',34,304,375,12)
text('Evite escrever documentos, telefone, endereço residencial completo ou dados de saúde na conversa livre.',34,398,375,12)
text('SE HOUVER ERRO OU DEMORA',433,280,375,10,TEAL,True)
steps([
 ('Erro em um campo','Leia a mensagem, corrija o dado e confira novamente.'),
 ('Envio sem confirmação','Não considere o registro concluído. Confira o resultado antes de repetir para reduzir duplicidades.'),
 ('Assistente indisponível','Use o formulário da própria página do portal para registrar o relato.'),
],433,306,375,10.7,14)
footer()

header('Limites e consulta rápida','O que esperar da assistente virtual','A IA apoia o uso do portal. As decisões e o atendimento continuam sob responsabilidade das equipes.')
table([
 ['O chatbot ajuda a…','O chatbot não realiza pela conversa…'],
 ['Entender o portal e os campos do relato.','Consultar, editar ou confirmar denúncias existentes.'],
 ['Encontrar orientações e fontes oficiais.','Garantir que todas as respostas estejam corretas ou atualizadas.'],
 ['Abrir o formulário guiado e orientar seu preenchimento.','Cadastrar uma denúncia apenas porque o cidadão descreveu o problema em uma mensagem.'],
 ['Direcionar para o boletim de saúde.','Consultar publicamente o andamento de um protocolo.'],
 ['Explicar, em termos gerais, o que acontece após o envio.','Agendar visitas, prometer prazos ou decidir o atendimento.'],
 ['Fornecer orientações gerais de prevenção.','Realizar diagnóstico ou prescrever tratamento.'],
 ],[387,387],34,116,10.2,10)
callout('Para usar bem','Faça perguntas objetivas. Confira as fontes. Preencha dados pessoais somente no formulário. Guarde o protocolo após o envio confirmado.',34,428,375,107)
callout('Sobre a assistente de IA','O aviso da própria janela informa que as respostas podem conter erros e não substituem as orientações da equipe responsável. Confirme informações importantes nos canais oficiais.',433,428,375,107)
footer()
assert PAGE==6
c.save()
print(OUT)
