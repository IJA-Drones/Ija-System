from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path('/Users/joaopedro/Documents/Ija-System')
D=ROOT/'tmp/pdfs/guia-saude'
OUT=ROOT/'output/pdf/guia-suspeitas-adoecimento-ija-system-2026-10-17.pdf'
for name,file in [('Arial','Arial.ttf'),('ArialB','Arial Bold.ttf')]:
 pdfmetrics.registerFont(TTFont(name,'/System/Library/Fonts/Supplemental/'+file))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='ArialB',italic='Arial',boldItalic='ArialB')
W,H=landscape(A4)
NAVY='#173D50'; TEAL='#008F98'; INK='#304754'; MUTED='#667987'; LIGHT='#E9F5F5'
c=canvas.Canvas(str(OUT),pagesize=(W,H))
c.setTitle('Guia de uso | Suspeitas de adoecimento | IJA System')
c.setAuthor('Time de Desenvolvimento da IJA DRONES')

def text(s,x,y,w,size=12,color=INK,bold=False,leading=None):
 st=ParagraphStyle('p',fontName='ArialB' if bold else 'Arial',fontSize=size,leading=leading or size*1.38,textColor=HexColor(color))
 p=Paragraph(s,st);ww,hh=p.wrap(w,1000)
 assert y+hh<548, (s[:80],y,hh)
 p.drawOn(c,x,H-y-hh)
 return y+hh

def rect(x,y,w,h,fill,stroke=None):
 c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke or fill));c.roundRect(x,H-y-h,w,h,8,stroke=bool(stroke),fill=1)

def header(n,section,title,subtitle):
 c.setFillColor(HexColor('#FFFFFF'));c.rect(0,0,W,H,fill=1,stroke=0)
 c.setFillColor(HexColor(TEAL));c.rect(0,H-7,W,7,fill=1,stroke=0)
 text(f'IJA SYSTEM  /  {section.upper()}',38,25,730,9,TEAL,True)
 text(title,38,46,770,27,NAVY,True,31)
 text(subtitle,38,85,760,11,MUTED)
 c.setStrokeColor(HexColor('#DCE6EB'));c.line(38,52,W-38,52)
 c.setFillColor(HexColor(NAVY));c.setFont('ArialB',10);c.drawCentredString(W/2,32,'IJA DRONES')
 c.setFont('Arial',9);c.drawCentredString(W/2,17,'Documento elaborado pelo time de desenvolvimento da IJA DRONES')
 c.setFont('Arial',8);c.drawRightString(W-38,32,f'{n:02d} / 10')
 c.setFillColor(HexColor(MUTED));c.drawString(38,32,'Guia ilustrado • 17/10/2026')

def shot(name,x,y,w,h,crop=None):
 src=D/name
 im=Image.open(src)
 if crop: im=im.crop(crop)
 dest=D/('crop-'+name);im.save(dest)
 iw,ih=im.size;scale=min(w/iw,h/ih);dw,dh=iw*scale,ih*scale
 xx=x+(w-dw)/2;yy=y+(h-dh)/2
 rect(xx-3,yy-3,dw+6,dh+6,'#F5F8FA','#DCE6EB')
 c.drawImage(str(dest),xx,H-yy-dh,dw,dh)
 return yy+dh

def blocks(items,x,y,w,size=12):
 for title,body in items:
  y=text(title,x,y,w,size,TEAL,True)+5
  y=text(body,x,y,w,size,INK)+16
 return y

def note(s,x,y,w,h=56):
 rect(x,y,w,h,LIGHT);text(s,x+12,y+10,w-24,10,NAVY)

header(1,'Visão geral','Suspeitas de adoecimento','Do relato da população ao acompanhamento municipal, com protocolo e histórico.')
text('Um canal para ouvir a população e organizar o atendimento.',38,132,360,21,NAVY,True)
text('O cidadão informa onde mora e descreve sua suspeita. A COVISA da prefeitura escolhida recebe o relato, faz a triagem e direciona à UVIS quando necessário.',38,205,350,13)
shot('04-caixa-covisa.png',420,132,382,226,crop=(230,180,2010,880))
text('Tela real da caixa de entrada no ambiente de testes.',420,366,382,9,MUTED)
for i,(title,body) in enumerate([('1. Cidadão','Preenche e recebe protocolo'),('2. COVISA','Registra ciência e direciona'),('3. UVIS','Acompanha e registra ações'),('4. Relatório','Consulta e exporta o recorte')]):
 x=38+i*194;rect(x,414,182,79,LIGHT);text(title,x+12,427,158,13,TEAL,True);text(body,x+12,451,158,11)
text('Demonstração realizada em 17/10/2026 no banco de testes, com dados e contas fictícios. Não corresponde a um caso real.',38,508,760,9,MUTED)
c.showPage()

header(2,'Cidadão • localização','O cidadão escolhe a prefeitura','Não é necessário conhecer a UVIS responsável pelo endereço.')
blocks([('Onde acessar','No Portal do Cidadão, abra a opção de relato de suspeita de adoecimento.'),('Preenchimento inicial','Selecione a prefeitura onde mora e informe rua, número ou S/N e bairro.'),('Encaminhamento municipal','A prefeitura selecionada define qual COVISA receberá o relato. O endereço ajuda a equipe a direcionar o atendimento à UVIS adequada.'),('Exemplo deste guia','Foi utilizada a Prefeitura Teste, com endereço e cidadão de demonstração.')],38,139,305)
shot('01-formulario.png',382,123,420,397,crop=(593,172,1424,935))
c.showPage()

header(3,'Cidadão • informações e envio','Descrever, conferir e enviar','O formulário reúne os dados necessários ao contato e à avaliação inicial.')
blocks([('Contato','Nome e telefone com DDD são obrigatórios. A data de início dos sintomas é opcional.'),('Descrição','O cidadão escreve o que está acontecendo, em até 2.000 caracteres. A orientação na tela pede que não sejam incluídos CPF, exames ou dados de outras pessoas.'),('Ciência sobre o uso dos dados','Leia o aviso de uso das informações e marque a concordância. Depois, clique em “Enviar relato à COVISA”.')],38,136,300)
note('O formulário não confirma diagnóstico e não funciona como serviço de emergência.',38,449,305,62)
shot('02-envio.png',380,123,422,397,crop=(593,245,1424,1055))
c.showPage()

header(4,'Protocolo e destino','Cada envio recebe um protocolo','O comprovante identifica o relato e informa a prefeitura destinatária.')
shot('03-protocolo.png',38,141,454,350,crop=(646,113,1370,673))
blocks([('Guarde o número','O protocolo pode ser informado ao entrar em contato com a vigilância. O recibo fica disponível na sessão do navegador após o envio.'),('O que acontece depois','A COVISA recebe a notificação interna e pode iniciar a triagem. O contato ocorre pelo telefone informado, conforme a avaliação da equipe.'),('Acesso reservado','Não existe consulta pública dos dados de saúde pelo protocolo. Enviar o formulário não confirma diagnóstico nem agendamento.')],526,140,276,11.5)
c.showPage()

header(5,'COVISA • caixa de entrada','Uma tela para acompanhar os relatos','A opção “Suspeitas de adoecimento” fica disponível no menu dos perfis autorizados.')
shot('04-caixa-covisa.png',38,130,764,300,crop=(0,190,2016,940))
blocks([('Filtrar e localizar','Use situação e período de recebimento; a seleção de prefeitura respeita o acesso do usuário. O contador de abertos corresponde ao recorte aplicado.')],38,453,365,11)
blocks([('Abrir o atendimento','A listagem exibe protocolo, data, prefeitura, bairro, situação e UVIS. Clique em “Abrir relato” para consultar os detalhes restritos.')],437,453,365,11)
c.showPage()

header(6,'COVISA • triagem','Registrar ciência e encaminhar','A COVISA organiza o destino do relato dentro da mesma prefeitura.')
shot('06-encaminhar.png',38,135,494,360,crop=(468,215,1770,965))
blocks([('1. Registrar ciência','Abra o relato e registre que a COVISA tomou conhecimento. A situação passa para “Em análise pela COVISA”.'),('2. Selecionar a UVIS','Escolha “Encaminhar / redirecionar à UVIS” e selecione a unidade responsável. A lista apresenta unidades vinculadas à mesma prefeitura.'),('3. Registrar a orientação','Informe a observação e clique em “Registrar ação”. A UVIS recebe uma notificação interna e o encaminhamento entra no histórico.')],558,140,244,11.5)
c.showPage()

header(7,'UVIS • acompanhamento','Atender o relato encaminhado','A UVIS visualiza os relatos destinados à sua unidade.')
shot('07-acompanhamento-uvis.png',38,134,494,360,crop=(468,215,1770,935))
blocks([('Ciência da UVIS','Ao receber o relato, a UVIS registra sua própria ciência. O status passa para “Em atendimento pela UVIS”.'),('Acompanhamento','Escolha “Registrar acompanhamento” e descreva a providência adotada. Cada registro fica associado ao responsável e ao horário.'),('Redirecionamento ou conclusão','Se precisar de outro destino, devolva à COVISA com justificativa. Para encerrar, registre a conclusão e a providência final. Conclusão administrativa não confirma uma doença.')],558,139,244,11.5)
c.showPage()

header(8,'Rastreabilidade','O histórico preserva o caminho do relato','Recebimento, ciência, encaminhamento, acompanhamento e conclusão ficam registrados.')
shot('08-historico.png',38,135,495,370,crop=(468,287,1772,970))
blocks([('Quem fez e quando','O histórico mostra ação, situação, responsável, unidade quando aplicável e data/hora de Brasília.'),('Após concluir','O atendimento permanece disponível para consulta, com a conclusão e as observações. A tela deixa de oferecer novas ações sobre o relato concluído.'),('Evitar sobrescrita','Se outra pessoa atualizar o relato enquanto a tela está aberta, o sistema pede a conferência do histórico antes de uma nova tentativa.')],558,142,244,11.5)
c.showPage()

header(9,'Relatórios','Filtrar na tela e gerar o PDF','O relatório usa o mesmo recorte e as mesmas restrições de acesso da consulta.')
shot('09-relatorio.png',38,132,470,170,crop=(240,190,2010,825))
shot('10-exportado.png',38,324,470,185,crop=(55,40,1750,620))
blocks([('Como gerar','Aplique os filtros desejados e clique em “Baixar relatório PDF”. O período considera a data de recebimento; a situação corresponde ao estado atual do atendimento.'),('O que aparece','Protocolo, recebimento, prefeitura, bairro, situação e UVIS, com total e contagem por situação. A configuração municipal de marca d’água é reutilizada quando aplicável.'),('Informações protegidas','Nome, telefone, rua e descrição de saúde não entram nesse relatório. Eles permanecem no detalhe restrito. Para mais de 2.000 relatos, reduza o período.')],538,138,264,11.5)
c.showPage()

header(10,'Acesso e operação','Um fluxo municipal com responsabilidades claras','O módulo organiza relatos de suspeita sem criar automaticamente OS ou caso confirmado no SINAN.')
rows=[('Cidadão','Envia o relato pelo formulário público e recebe o protocolo.'),('COVISA / gestão municipal','Consulta os relatos da sua prefeitura, registra ciência, encaminha e acompanha.'),('UVIS responsável','Consulta e atende os relatos atribuídos à sua unidade.'),('ADM, DIRETOR e DEV','Acesso gerencial, condicionado às permissões configuradas no sistema.')]
y=133
for label,body in rows:
 rect(38,y,764,57,'#F3F7F9');text(label,52,y+13,220,12,NAVY,True);text(body,292,y+11,493,12);y+=66
note('Perfis personalizados na Central de TI precisam ter as permissões do módulo habilitadas. A vinculação correta de usuários e UVIS à prefeitura define o alcance municipal.',38,414,764,60)
text('As notificações deste fluxo são internas ao sistema. Este guia não descreve envio automático por e-mail ou WhatsApp. Demonstração com dados fictícios; a publicação em produção depende da versão implantada.',38,491,764,10,MUTED)
c.showPage();c.save()
print(OUT)
