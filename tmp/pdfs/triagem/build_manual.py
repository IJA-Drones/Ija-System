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
OUT=ROOT/'output/pdf/manual-administrativo-triagem-denuncias.pdf'
FONT=Path('/Users/joaopedro/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype')
for name,file in [('Sans','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf'),('BoldItalic','DejaVuSans-BoldOblique.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
pdfmetrics.registerFontFamily('Sans',normal='Sans',bold='Bold',italic='Sans',boldItalic='BoldItalic')
W,H=landscape(A4)
NAVY=colors.HexColor('#123C57'); BLUE=colors.HexColor('#215B87'); TEAL=colors.HexColor('#009CB5')
INK=colors.HexColor('#233748'); MUTED=colors.HexColor('#5C7280'); LIGHT=colors.HexColor('#EFF6F8'); BORDER=colors.HexColor('#D9E5EA'); WHITE=colors.white
c=canvas.Canvas(str(OUT),pagesize=(W,H),pageCompression=1)
c.setTitle('Portal do Cidadão | Manual administrativo da triagem de denúncias')
c.setAuthor('Time de desenvolvimento da IJA DRONES')
c.setSubject('Registro pelo cidadão, triagem COVISA, encaminhamento à coordenadoria e atuação da UVIS')
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
    text('OCEANO AZUL  /  PORTAL DO CIDADÃO',34,21,500,8,BLUE,True)
    text(section.upper(),610,21,198,8,MUTED,True)
    text(title,34,45,W-68,24,NAVY,True,28)
    if subtitle:text(subtitle,34,80,W-68,10,MUTED)
    c.bookmarkPage(f'p{PAGE}');c.addOutlineEntry(title,f'p{PAGE}',0)

def footer():
    c.setStrokeColor(BORDER);c.line(34,30,W-34,30)
    text('IJA DRONES',34,H-44,600,8.5,BLUE,True)
    text('<b><i>Documento elaborado pelo time de desenvolvimento da IJA DRONES</i></b>',34,H-23,690,7.3,MUTED)
    text(f'{PAGE:02d} / 15',W-83,H-23,55,8,BLUE,True)
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

# 01
header('Manual administrativo','Do relato do cidadão à solicitação operacional')
text('TRIAGEM DE DENÚNCIAS',36,103,700,11,TEAL,True)
text('Um fluxo, quatro responsáveis.',36,130,750,29,NAVY,True)
text('Guia visual para orientar a recepção, a análise e o encaminhamento das ocorrências no Portal do Cidadão.',36,179,705,14,MUTED,leading=20)
labels=[('01','CIDADÃO','Relata a situação e recebe um protocolo.'),('02','COVISA','Confere as informações e define a coordenadoria.'),('03','COORDENADORIA','Escolhe a UVIS responsável da sua região.'),('04','UVIS','Avalia o relato e cria a solicitação operacional.')]
for i,(num,title,body) in enumerate(labels):
    x=36+i*195
    rect(x,250,183,151,LIGHT,12)
    text(num,x+15,264,140,23,TEAL,True)
    text(title,x+15,302,156,10.4,BLUE,True)
    text(body,x+15,329,153,11,INK)
text('PARA QUEM É ESTE MATERIAL',36,433,365,9,TEAL,True)
text('Equipes administrativas da COVISA, coordenadorias e UVIS; apoio ao atendimento e treinamento de novos usuários.',36,454,367,11)
text('COMO USAR',438,433,365,9,TEAL,True)
text('Siga as etapas na ordem ou consulte as páginas do seu perfil. As telas administrativas usam registros fictícios de teste.',438,454,365,11)
footer()

# 02
header('Visão geral','Quem faz o quê no atendimento','Cada encaminhamento mantém o protocolo da denúncia e muda o responsável pela próxima etapa.')
table([
 ['Responsável','Recebe e confere','Ação no sistema','Resultado esperado'],
 ['<b>Cidadão</b><br/>Páginas 3 a 5','Tipo de ocorrência, local, identificação, descrição e anexos.','Envia o relato após revisão e consentimento.','Protocolo e status <b>Recebida</b>.'],
 ['<b>COVISA</b><br/>Páginas 6 a 8','Relato, endereço, evidências e possíveis duplicidades.','Encaminha à coordenadoria ou arquiva com justificativa.','<b>Encaminhada à coordenadoria</b> ou <b>Arquivada</b>.'],
 ['<b>Coordenadoria</b><br/>Páginas 9 e 10','Denúncias da sua região e unidade adequada ao local.','Seleciona a UVIS e confirma o encaminhamento.','<b>Encaminhada à UVIS</b>.'],
 ['<b>UVIS</b><br/>Páginas 11 a 13','Ocorrência atribuída à unidade e dados para atendimento.','Completa o formulário e cria a solicitação.','<b>Convertida em solicitação</b>; solicitação operacional pendente.'],
], [125,218,215,216],34,119,10,12)
callout('O que o protocolo confirma','Confirma o registro do relato. Não significa que já existe uma visita agendada, uma ação concluída ou uma operação aprovada.',34,440,774,88)
footer()

#03
header('01 • Cidadão','Registrar a ocorrência e localizar o problema','O portal público pode ser acessado sem login; o formulário orienta o preenchimento.')
image('portal-formulario.jpg',34,109,460,410)
steps([
 ('Escolher a situação','Selecione água parada ou criadouro, mosquitos em área alagada ou outro problema.'),
 ('Detalhar o foco','Para Aedes, informe também o tipo de local. Depois escolha a opção que melhor descreve o que foi encontrado.'),
 ('Informar o endereço','Preencha logradouro, número, bairro e cidade. O CEP é opcional no relato inicial.'),
 ('Conferir a localização','CEP ou localização podem ajudar. Revise o endereço antes de seguir; dados imprecisos dificultam a triagem.'),
],515,116,288,10.6,15)
text('Tela do portal capturada para este manual. Campos pessoais não preenchidos.',34,529,760,8,MUTED)
footer()

#04
header('01 • Cidadão','Identificação, detalhes e confirmação','A qualidade das informações facilita o trabalho de todas as equipes que receberão a denúncia.')
image('portal-identificacao.jpg',34,109,460,410)
steps([
 ('Preencher a identificação','Nome completo, CPF e telefone com DDD são obrigatórios. O RG é opcional; o relato não é anônimo.'),
 ('Descrever o que foi observado','Explique a situação, o local e referências úteis. Prefira descrições objetivas que ajudem a equipe a localizar o problema.'),
 ('Anexar evidências, se houver','É possível enviar até cinco fotos ou vídeos. Anexos são opcionais e ficam disponíveis na análise interna.'),
 ('Revisar e confirmar','Marque o consentimento, revise o envio e aguarde a confirmação. Guarde o protocolo exibido pelo sistema.'),
],515,115,288,10.5,12)
text('Se houver erro em um campo, corrija-o e confira novamente. Sem confirmação do servidor, o registro não está comprovado.',34,529,774,8.5,MUTED)
footer()

#05
header('01 • Cidadão','Também é possível registrar pelo chatbot','O assistente abre um formulário guiado; a triagem administrativa segue o mesmo fluxo.')
image('portal-chat.jpg',34,108,464,410)
text('Ajuda com IA → Registrar relato',520,118,280,15,BLUE,True)
text('O cidadão percorre cinco etapas:',520,160,278,11)
steps([
 ('Ocorrência','Tipo de situação, local e foco.'),
 ('Endereço','Local onde o problema foi observado.'),
 ('Identificação','Nome, CPF e telefone; RG opcional.'),
 ('Detalhes','Descrição e anexos opcionais.'),
 ('Revisão e envio','Confirmação dos dados e do consentimento; clique em <b>Confirmar e enviar</b>.'),
],520,190,284,10,10)
text('Conversar com a IA não cria uma denúncia. O cadastro ocorre pelo formulário e termina com a confirmação e o protocolo.',34,530,773,9,MUTED)
footer()

#06
screenshot_page('02 • COVISA','Receber e localizar as denúncias','Acesse Denúncias na sidebar e use Visualizar para abrir o registro.',
 'tela-5.png','Figura 1 • COVISA: lista de denúncias com protocolo, ocorrência, endereço, cidadão e status.',
 '<b>Leitura da tela:</b> há 3 registros na lista e 2 pendências no menu. O terceiro já está encaminhado à UVIS. O contador do menu representa a fila pendente do perfil, não o total de registros.')

#07
screenshot_page('02 • COVISA','Conferir o relato antes de decidir','No detalhe, revise ocorrência, endereço, identificação e eventuais fotos ou vídeos.',
 'tela-6.png','Figura 2 • COVISA: detalhe do registro e painel de encaminhamento ou arquivamento.',
 '<b>Ação:</b> selecione a coordenadoria responsável pelo local e clique em <b>Encaminhar</b>. Para arquivar, preencha uma justificativa e use <b>Arquivar denúncia</b>. Veja os critérios na próxima página.')

#08
header('02 • COVISA','Decidir com base no relato e no território','Abrir o detalhe permite consultar o registro; o encaminhamento depende da confirmação da equipe.')
steps([
 ('Conferir o conteúdo','Compare a descrição com o foco informado. Consulte anexos disponíveis e verifique se o relato contém informação suficiente para análise.'),
 ('Conferir o endereço','Revise município, bairro, logradouro, número e referências. A coordenadoria deve corresponder ao local real da ocorrência.'),
 ('Consultar possíveis duplicidades','Use os filtros e a busca por protocolo, endereço ou cidadão. Compare os registros antes de concluir que se trata da mesma ocorrência.'),
 ('Escolher e confirmar o destino','Selecione a coordenadoria no painel de ações e clique em Encaminhar. Confira a mensagem de sucesso e o novo status.'),
],34,120,457,11,18)
callout('Quando arquivar','Registre o motivo da decisão, por exemplo duplicidade confirmada ou informação que inviabilize o tratamento. O sistema exige pelo menos 10 caracteres.',518,119,290,142)
callout('Exemplo de justificativa','“Duplicidade confirmada com o protocolo DEN-...; mesmo local e mesma ocorrência.” Inclua o protocolo relacionado quando houver.',518,278,290,116)
callout('Se precisar corrigir o destino','Enquanto a denúncia estiver ativa, a COVISA pode reencaminhar. Isso remove a atribuição anterior à UVIS. Registros arquivados ou convertidos ficam encerrados para estas ações.',518,410,290,128)
footer()

#09
screenshot_page('03 • Coordenadoria','Designar a UVIS responsável','A coordenadoria consulta os relatos da própria região e define a unidade que fará a avaliação.',
 'tela-3.png','Figura 3 • Coordenadoria: ocorrência, endereço, identificação e seleção da UVIS.',
 '<b>Passo principal:</b> escolha a unidade em <b>UVIS responsável</b> e clique em <b>Encaminhar para UVIS</b>. O print já mostra o estado posterior ao encaminhamento: <b>Encaminhada à UVIS</b>.')

#10
header('03 • Coordenadoria','Confirmar o perfil e revisar o encaminhamento','Use a conta da coordenadoria responsável e escolha uma UVIS compatível com o território.')
image('tela-4.png',34,119,477,291)
text('Figura 4 • O menu de usuário identifica a conta “Coordenador Sul”.',34,419,477,8.4,MUTED)
callout('As telas são exemplos de teste','Os dados, bairros e encaminhamentos mostrados são fictícios. Não use a combinação de bairro e UVIS destes prints como referência de divisão territorial.',34,448,477,86)
steps([
 ('Validar a conta','Confira a identificação do usuário no canto superior direito e o perfil da tela.'),
 ('Revisar o relato','Leia endereço, descrição e evidências antes de selecionar a unidade.'),
 ('Selecionar a UVIS','A lista oferece unidades cadastradas na região da denúncia. Se não houver opções, solicite conferência do cadastro administrativo.'),
 ('Conferir o resultado','Após confirmar, verifique o status e a UVIS escolhida. O relato passa a compor a fila da unidade.'),
],536,120,273,10.7,17)
footer()

#11
screenshot_page('04 • UVIS','Receber a denúncia atribuída à unidade','A UVIS acessa Denúncias e consulta os registros encaminhados à sua conta.',
 'tela-1.png','Figura 5 • UVIS: endereço, relato do cidadão, contato e área de fotos e vídeos.',
 '<b>Conferência:</b> valide local, tipo de ocorrência e descrição. “Nenhuma foto ou vídeo” significa ausência de anexos, não falha no cadastro. Na sequência da página está o formulário para gerar a solicitação.')

#12
screenshot_page('04 • UVIS','Completar a solicitação operacional','Revise os dados trazidos da denúncia e preencha o planejamento necessário ao atendimento.',
 'tela-2.png','Figura 6 • UVIS: agendamento, detalhes da operação, observações e botão Criar solicitação.',
 '<b>Antes de criar:</b> confira data, horário, CEP, tipo de visita, altura do voo, distrito, foco, tipo de imóvel e operação. Preserve o protocolo de origem nas observações. O envio segue as validações do cadastro operacional.')

#13
header('04 • UVIS','Da denúncia à solicitação: o que conferir','Criar a solicitação encerra esta etapa de triagem e inicia o fluxo operacional correspondente.')
table([
 ['Grupo de informações','Orientação para preenchimento'],
 ['<b>Agendamento</b>','Informe data da visita e horário previsto. Não use data retroativa. Complete o CEP exigido no formulário operacional, mesmo quando ausente no relato inicial.'],
 ['<b>Classificação e local</b>','Revise tipo de visita e foco. Para Aedes, confira o tipo de imóvel. Informe o distrito administrativo e verifique a coerência com o endereço recebido.'],
 ['<b>Planejamento da operação</b>','Preencha a altura do voo e escolha o tipo de operação conforme a avaliação técnica responsável. Informe se há necessidade de apoio CET.'],
 ['<b>Observações</b>','O campo já traz o protocolo e a descrição do relato. Preserve a origem e complemente com informações administrativas úteis ao atendimento.'],
 ],[180,594],34,117,10.6,12)
callout('Após clicar em Criar solicitação','A denúncia recebe o vínculo com a solicitação e passa para Convertida em solicitação. A nova solicitação entra como pendente no fluxo operacional; isso não confirma execução nem aprovação da operação.',34,427,375,105)
callout('Se o envio não for concluído','Leia a mensagem e corrija os campos indicados. Se houver dúvida sobre a gravação, reabra a denúncia e verifique o vínculo antes de repetir. Uma denúncia já convertida não gera uma segunda solicitação.',432,427,376,105)
footer()

#14
header('Acompanhamento','Como interpretar os status','O status informa em qual etapa o relato está e qual providência administrativa é esperada.')
table([
 ['Status na denúncia','Significado','Providência'],
 ['<b>Recebida</b>','Relato registrado e disponível para análise.','COVISA confere e define o encaminhamento.'],
 ['<b>Em triagem COVISA</b>','Estado previsto para a fila de análise central. Abrir a tela não altera automaticamente o status.','COVISA conclui a análise e decide.'],
 ['<b>Encaminhada à coordenadoria</b>','A COVISA definiu a coordenadoria responsável.','Coordenadoria seleciona uma UVIS da região.'],
 ['<b>Encaminhada à UVIS</b>','A coordenadoria designou a unidade.','UVIS avalia e preenche a solicitação operacional.'],
 ['<b>Convertida em solicitação</b>','Existe uma solicitação vinculada à denúncia.','Acompanhar a solicitação no fluxo operacional.'],
 ['<b>Arquivada</b>','A triagem central registrou uma justificativa de arquivamento.','Consultar motivo; a denúncia não segue para conversão.'],
 ],[198,309,267],34,115,10,10)
text('<b>Atenção:</b> o painel “Fluxo do atendimento” explica as etapas. Para saber a situação atual, confira o status, a unidade atribuída e o vínculo com a solicitação.',34,514,774,10,MUTED)
footer()

#15
header('Consulta rápida','Checklist para a rotina administrativa','Use esta página para conferir a passagem de responsabilidade entre as equipes.')
cols=[(34,'COVISA',[('Identificar','Localizar o protocolo e conferir a situação atual.'),('Analisar','Revisar endereço, descrição e evidências.'),('Decidir','Encaminhar ao território correto ou arquivar com motivo.'),('Confirmar','Verificar mensagem de sucesso e novo status.')]),
      (295,'COORDENADORIA',[('Conferir','Confirmar que o relato pertence à sua região.'),('Revisar','Comparar endereço e informações da ocorrência.'),('Designar','Escolher uma UVIS da região e encaminhar.'),('Confirmar','Verificar unidade atribuída e status atualizado.')]),
      (556,'UVIS',[('Receber','Abrir a denúncia atribuída à unidade.'),('Avaliar','Conferir o relato e os dados necessários.'),('Completar','Preencher agendamento e dados da operação.'),('Concluir','Criar a solicitação e confirmar o vínculo.')])]
for x,title,items in cols:
    tag(title,x,117,248)
    steps(items,x+2,156,244,10.3,11)
rect(34,428,774,111,LIGHT,10)
text('SE ALGO NÃO APARECER OU NÃO AVANÇAR',49,440,744,10,BLUE,True)
text('<b>Lista vazia:</b> confira o perfil, a região/unidade e os filtros. <b>Sem UVIS na seleção:</b> solicite revisão do cadastro da região. <b>Ação indisponível:</b> confira se a denúncia já foi arquivada ou convertida. <b>Sem protocolo de sucesso:</b> confirme o registro antes de considerar o envio concluído.',49,461,744,10)
text('Referência: telas do sistema e comportamento implementado em 09/10/2026. Não há consulta pública de andamento por protocolo neste fluxo nem promessa automática de prazo ou atendimento. Dados pessoais devem ser usados apenas na finalidade administrativa do atendimento.',49,505,744,8.1,MUTED,leading=11)
footer()
assert PAGE==15
c.save()
print(OUT)
