from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
ROOT=Path('/Users/joaopedro/Documents/Ija-System');D=ROOT/'tmp/pdfs/guia-contatos';OUT=ROOT/'output/pdf/guia-contatos-prefeituras-azul-ija-system-2026-10-17.pdf'
for n,f in [('Arial','Arial.ttf'),('ArialB','Arial Bold.ttf')]: pdfmetrics.registerFont(TTFont(n,'/System/Library/Fonts/Supplemental/'+f))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='ArialB',italic='Arial',boldItalic='ArialB')
W,H=landscape(A4);NAVY='#173D50';TEAL='#008F98';INK='#304754';MUTED='#667987';LIGHT='#E9F5F5'
c=canvas.Canvas(str(OUT),pagesize=(W,H));c.setTitle('Contatos das prefeituras e Azul | Guia ilustrado IJA System');c.setAuthor('Time de Desenvolvimento da IJA DRONES')
def tx(s,x,y,w,size=12,color=INK,bold=False):
 p=Paragraph(s,ParagraphStyle('p',fontName='ArialB' if bold else 'Arial',fontSize=size,leading=size*1.38,textColor=HexColor(color)))
 _,h=p.wrap(w,1000);assert y+h<543,(s[:60],y,h);p.drawOn(c,x,H-y-h);return y+h

def box(x,y,w,h,color=LIGHT):
 c.setFillColor(HexColor(color));c.roundRect(x,H-y-h,w,h,8,fill=1,stroke=0)
def head(n,k,title,sub):
 c.setFillColor(HexColor('#FFFFFF'));c.rect(0,0,W,H,fill=1,stroke=0)
 c.setFillColor(HexColor(TEAL));c.rect(0,H-7,W,7,fill=1,stroke=0)
 tx('IJA SYSTEM  /  '+k.upper(),38,25,760,9,TEAL,True);tx(title,38,46,770,27,NAVY,True);tx(sub,38,88,760,11,MUTED)
 c.setStrokeColor(HexColor('#DCE6EB'));c.line(38,52,W-38,52)
 c.setFillColor(HexColor(NAVY));c.setFont('ArialB',10);c.drawCentredString(W/2,32,'IJA DRONES')
 c.setFont('Arial',9);c.drawCentredString(W/2,17,'Documento elaborado pelo time de desenvolvimento da IJA DRONES')
 c.setFont('Arial',8);c.drawRightString(W-38,32,f'{n:02d} / 08');c.setFillColor(HexColor(MUTED));c.drawString(38,32,'Guia ilustrado | 17/10/2026')
def shot(name,x,y,w,h,crop=None):
 im=Image.open(D/name)
 if crop: im=im.crop(crop)
 iw,ih=im.size;s=min(w/iw,h/ih);dw,dh=iw*s,ih*s;xx=x+(w-dw)/2;yy=y+(h-dh)/2
 box(xx-3,yy-3,dw+6,dh+6,'#EDF2F5');c.drawImage(ImageReader(im),xx,H-yy-dh,dw,dh);return yy+dh

def blocks(items,x,y,w,size=12):
 for title,body in items:
  y=tx(title,x,y,w,size,TEAL,True)+5;y=tx(body,x,y,w,size)+15
 return y

def note(s,x,y,w,h=58):
 box(x,y,w,h);tx(s,x+12,y+10,w-24,10,NAVY)

head(1,'Visão geral','Contatos municipais e assistente Azul','Um cadastro por prefeitura para orientar a população pelos canais corretos.')
tx('A gestão atualiza.<br/>O cidadão encontra.<br/>A Azul orienta.',38,137,325,25,NAVY,True)
tx('Telefone, WhatsApp, Instagram, e-mail, horários e serviços ficam reunidos no Portal do Cidadão. A assistente consulta essa mesma base publicada ao responder às perguntas.',38,258,325,13)
shot('05-canais.png',416,128,386,288,crop=(180,140,755,700))
for i,(a,b) in enumerate([('01  COVISA','Cadastra e publica os canais'),('02  Portal','Exibe os dados ao cidadão'),('03  Azul','Responde com a base municipal')]):
 x=38+i*260;box(x,437,246,65);tx(a,x+12,447,220,12,TEAL,True);tx(b,x+12,469,220,11)
tx('Prints reais do banco de testes. Perfil Covisa / Prefeitura Padrão, com informações oficiais de São Paulo para demonstração. O nome do cadastro de teste foi mantido.',38,514,764,9,MUTED)
c.showPage()

head(2,'Acesso e responsabilidades','Onde a COVISA configura os contatos','Menu lateral: Configurações > Contatos públicos da prefeitura > Configurar contatos públicos.')
shot('08-perfil-acesso.png',38,130,764,290,crop=(0,0,2016,766))
blocks([('COVISA','Consulta e altera os contatos da prefeitura à qual está vinculada. A configuração é compartilhada pelos usuários dessa prefeitura.')],38,442,360,11)
blocks([('DEV e DIRETOR','DEV administra todas as prefeituras. DIRETOR tem acesso de consulta. Permissões personalizadas da Central de TI também são respeitadas.')],437,442,365,11)
c.showPage()

head(3,'Preenchimento','Quais informações cadastrar','Informe os canais institucionais autorizados para divulgação pública.')
shot('01-configuracao.png',38,133,470,385,crop=(578,282,1668,985))
blocks([('Telefone e WhatsApp','Preencha com DDD. O sistema padroniza o número para montar os atalhos de ligação e conversa.'),('Instagram e e-mail','Use @perfil ou a URL do perfil no Instagram. O e-mail deve ser o canal público de atendimento.'),('Horários e serviços','Explique o horário de cada canal e o tipo de demanda atendida. Serviços e orientações aceita até 1.500 caracteres.')],538,140,264,11.5)
note('O e-mail público é independente do destinatário privado dos relatórios. Alterar um não modifica o outro.',538,431,264,76)
c.showPage()

head(4,'Publicação e histórico','Salvar, publicar e manter atualizado','Os contatos só são divulgados quando a publicação está ativada e o cadastro é salvo.')
shot('02-publicacao-historico.png',38,135,476,380,crop=(580,440,1666,981))
blocks([('1. Publicar','Ative “Publicar no Portal do Cidadão e disponibilizar para a Azul” e clique em “Salvar contatos”. Pelo menos um canal deve estar preenchido.'),('2. Conferir','Use “Ver página pública” para revisar os dados que a população verá.'),('3. Retirar da divulgação','Desative a publicação e salve. Os dados deixam a página e as próximas consultas da Azul. Mensagens antigas já respondidas permanecem.'),('Histórico e conflito de edição','A tela mostra as últimas 10 alterações, com responsável e horário em UTC. Se outra pessoa salvar antes, o sistema pede que você recarregue.')],542,135,260,10.8)
c.showPage()

head(5,'Experiência do cidadão','Encontrar a prefeitura e abrir um canal','A página pública funciona sem login e permite filtrar a prefeitura desejada.')
shot('05-canais.png',38,132,424,386,crop=(180,140,750,695))
blocks([('Acesso pelo portal','Abra “Contatos das prefeituras”, escolha o município e clique em “Buscar”. A página informa a última atualização dos dados.'),('Telefone','Abre a opção de ligação disponível no dispositivo.'),('WhatsApp e Instagram','Abrem a conversa com o número cadastrado e o perfil institucional. O cidadão continua o atendimento no canal escolhido.'),('E-mail','Abre o aplicativo de e-mail com o destinatário preenchido. A pessoa redige e envia a mensagem.'),('Sem dados publicados','A prefeitura pode aparecer com a indicação de que ainda não publicou seus canais. Dados de rascunho não são exibidos.')],496,133,306,10.8)
c.showPage()

head(6,'Assistente com contexto municipal','A Azul usa os contatos publicados','Exemplo real: “Quais são os contatos publicados da Prefeitura Padrão?”')
shot('07-azul-contatos.png',38,129,288,388,crop=(1068,65,1497,731))
blocks([('Mesma informação em dois lugares','A resposta apresentada no teste trouxe o telefone e o e-mail da COVISA, o WhatsApp SP156 e o Instagram @prefsp cadastrados pela gestão.'),('Atualização a cada consulta','A base municipal é carregada no momento da pergunta. Salvar novos dados publicados atualiza a fonte usada nas próximas respostas, sem precisar treinar novamente a assistente.'),('Município identificado','Quando não estiver claro qual prefeitura o cidadão procura, a Azul é orientada a pedir essa informação. O atalho “Contatos das prefeituras” permite consultar a lista diretamente.'),('Contexto disponível','Horário, serviços e data da atualização ajudam a explicar qual canal usar. A resposta pode variar na redação; os contatos devem corresponder ao cadastro publicado.')],365,140,437,12)
c.showPage()

head(7,'Operação diária','Como manter o serviço confiável','Uma rotina simples para a prefeitura e informação clara para a população.')
rows=[('Cadastrar','A COVISA confere o vínculo municipal e informa somente canais institucionais autorizados.'),('Publicar e revisar','Salva a configuração, abre a página pública e confere números, perfil, e-mail e descrição.'),('Atualizar','Quando um contato mudar, atualiza o mesmo cadastro e salva novamente. A alteração entra no histórico.'),('Orientar','O cidadão escolhe o canal; a Azul ajuda a localizar os contatos e a entender os serviços informados.')]
y=132
for title,body in rows:
 box(38,y,764,58,'#F3F7F9');tx(title,52,y+15,150,12,NAVY,True);tx(body,220,y+12,565,11.5);y+=67
note('Esta entrega oferece o diretório municipal e a base de contatos para a Azul. Conversas de WhatsApp e Instagram acontecem nos respectivos canais; não há caixa de entrada social integrada neste módulo.',38,414,764,60)
tx('No contexto do edital, esta base contribui para o assistente com contexto local. Compartilhamento de ações públicas e atendimento social integrado exigem seus próprios fluxos e comprovações.',38,492,764,10,MUTED)
c.showPage()

head(8,'Demonstração e referências','São Paulo como exemplo de preenchimento','Contatos verificados em fontes oficiais e cadastrados apenas no ambiente de testes.')
rows=[('Telefone COVISA','(11) 5461-9321'),('E-mail COVISA','smscovisa@prefeitura.sp.gov.br'),('WhatsApp SP156','(11) 3230-5156'),('Instagram da Prefeitura','@prefsp')]
y=130
for a,b in rows:
 box(38,y,460,42,'#F3F7F9');tx(a,50,y+11,210,11,NAVY,True);tx(b,264,y+11,225,11);y+=49
blocks([('Identificação do exemplo','O perfil “Covisa” está vinculado à “Prefeitura Padrão”. Esse nome foi preservado nos prints; os contatos usados no exemplo são de São Paulo.'),('Horários','A disponibilidade de 24 horas foi atribuída à central telefônica 156. Para COVISA e demais canais, o cidadão deve consultar o órgão responsável.')],526,135,276,11.5)
tx('FONTES OFICIAIS CONSULTADAS',38,345,760,10,TEAL,True)
refs=[('COVISA - Quem é Quem: telefone e e-mail','https://prefeitura.sp.gov.br/web/saude/w/vigilancia_em_saude/acesso_a_informacao/281520'),('Atendimento ao Cidadão - SP156: WhatsApp e serviços','https://prefeitura.sp.gov.br/web/inovacao/w/atendimento_ao_cidadao/246617'),('Canal SP156: horário da central telefônica','https://prefeitura.sp.gov.br/web/mooca/w/canalsp156-sub-mo-1'),('Documento municipal: redes sociais institucionais / @prefsp','https://prefeitura.sp.gov.br/documents/d/meio_ambiente/produto-4-1-plano-de-comunicacao-e-advocacy-pdf')]
y=367
for label,url in refs:
 tx(f'<link href="{url}" color="{TEAL}"><u>{label}</u></link>',38,y,764,10);y+=24
tx('Os títulos acima são links clicáveis para as referências. Verificação e demonstração em 17/10/2026.',38,474,764,9,MUTED)
c.setFillColor(HexColor(NAVY));c.setFont('ArialB',19);c.drawCentredString(W/2,H-521,'IJA DRONES')
c.showPage();c.save();print(OUT)
