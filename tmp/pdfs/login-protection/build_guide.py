from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path('/Users/joaopedro/Documents/Ija-System')
FONT=Path('/Users/joaopedro/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype')
for name,file in [('Body','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Body',boldItalic='Bold')
OUT=ROOT/'output/pdf/guia-protecao-login-ija.pdf'
W,H=A4
C=canvas.Canvas(str(OUT),pagesize=A4)
C.setTitle('Proteção de login | Guia da funcionalidade | IJA SYSTEM')
C.setAuthor('Time de desenvolvimento da IJA DRONES')
NAVY='#12344A'; INK='#233D4D'; CYAN='#008EA4'; MUTED='#526776'; LIGHT='#EFF6F9'; GOLD='#8B500A'

def rect(x,top,w,h,fill,r=10,stroke=None):
    C.setFillColor(colors.HexColor(fill))
    if stroke:C.setStrokeColor(colors.HexColor(stroke))
    C.roundRect(x,H-top-h,w,h,r,fill=1,stroke=bool(stroke))

def text(s,x,top,w,size=10.5,color=INK,bold=False,leading=None):
    st=ParagraphStyle('p',fontName='Bold' if bold else 'Body',fontSize=size,leading=leading or size*1.48,textColor=colors.HexColor(color))
    p=Paragraph(s,st); _,h=p.wrap(w,H)
    p.drawOn(C,x,H-top-h)
    return top+h

def base(n,tag,title,subtitle):
    rect(0,0,W,8,CYAN,0)
    text('IJA SYSTEM  /  GUIA DA FUNCIONALIDADE',38,25,450,8,CYAN,True)
    text('15 OUT 2026',W-125,25,90,8,MUTED)
    text(tag.upper(),38,61,510,8.5,CYAN,True)
    y=text(title,38,80,520,26,NAVY,True,31)
    text(subtitle,38,y+12,510,10.5,MUTED)
    C.setStrokeColor(colors.HexColor('#D6E4EB'));C.line(38,68,W-38,68)
    text('IJA DRONES',38,H-55,430,10,NAVY,True)
    text('Documento elaborado pelo time de desenvolvimento da IJA DRONES',38,H-38,490,7.7,MUTED)
    text(f'{n} / 3',W-72,H-55,40,8,MUTED)

def step(num,title,body,x,top,w):
    rect(x,top,25,25,CYAN,7)
    text(str(num),x+7,top+4,17,10,'#FFFFFF',True)
    y=text(title,x+37,top,w-37,11,NAVY,True)
    y=text(body,x+37,y+6,w-37,10,INK)
    return y+20

base(1,'Visão geral','Proteção de login','Mais clareza para o usuário e controle sobre tentativas de acesso sem sucesso.')
y=text('O que mudou',38,177,510,15,NAVY,True)
text('Quando o limite de tentativas é atingido, o sistema interrompe temporariamente novas tentativas de login. Um aviso permanece junto ao formulário, explica o motivo e mostra o tempo de espera.',38,y+10,510,11)
for x,value,label in [(38,'5 falhas','por conta'),(215,'15 minutos','de espera'),(392,'3 acessos','com proteção compartilhada')]:
    rect(x,284,165,94,LIGHT)
    text(value,x+14,300,140,20,CYAN,True)
    text(label,x+14,336,140,9.5,INK)
text('Valores padrão: 5 falhas por conta em uma janela de 15 minutos; bloqueio por 15 minutos. Os limites podem variar conforme a configuração do ambiente.',38,390,510,9,MUTED)
text('Como acontece',38,449,510,15,NAVY,True)
y=step(1,'Tentativas sem sucesso','As falhas são contadas. O controle acompanha tanto o login informado quanto a origem da conexão (endereço IP).',38,484,510)
y=step(2,'Limite atingido','O bloqueio começa na tentativa que atinge o limite. Durante esse período, informar a senha correta também não libera o acesso.',38,y,510)
y=step(3,'Nova tentativa após a espera','Ao vencer o prazo, a pessoa pode tentar novamente. O sistema continua verificando os dados e os bloqueios aplicáveis.',38,y,510)
rect(38,701,519,52,'#E6F5F6')
text('<b>Onde vale:</b> login principal, acesso operacional UVIS e login do piloto Agro. Trocar de tela de login não reinicia os limites.',51,711,490,9.4)
C.showPage()

base(2,'Orientação ao usuário','Entenda o aviso de bloqueio','O alerta fica visível na página; não desaparece após poucos segundos.')
img=ROOT/'tmp/pdfs/login-protection/login.png'
C.drawImage(str(img),38,H-186-517,width=240,height=517,mask='auto')
text('Tela real da funcionalidade, com usuário fictício.',38,715,240,8,MUTED)
y=step(1,'Leia o motivo','O aviso informa que o limite de tentativas sem sucesso foi atingido e que o bloqueio é temporário.',302,190,255)
y=step(2,'Acompanhe a espera','A contagem regressiva indica quando tentar novamente. Sem JavaScript, o aviso ainda exibe o tempo aproximado.',302,y+3,255)
y=step(3,'Confira os dados','Após a espera, verifique usuário e senha e clique para entrar. O formulário não é enviado automaticamente.',302,y+3,255)
y=step(4,'Peça ajuda, se necessário','Se esqueceu a senha ou não reconhece as tentativas, procure o suporte do sistema.',302,y+3,255)
rect(302,y+4,255,95,'#FFF6E5')
text('<b>Não precisa insistir.</b><br/>Tentar durante o bloqueio não encurta a espera nem prolonga o prazo desse bloqueio. As tentativas continuam registradas.',315,y+17,229,9.4,GOLD)
text('O contador é informativo. A liberação é confirmada pelo sistema em uma nova tentativa; outro bloqueio ativo ainda pode impedir a entrada.',38,744,519,8.5,MUTED)
C.showPage()

base(3,'Consulta e suporte','Gestão pelo perfil DEV','Caminho: Painel Dev → Proteção de login')
y=step(1,'Consulte os bloqueios ativos','A tela apresenta o tipo de bloqueio (conta ou origem/IP), identificação, número de falhas e horário previsto para liberação.',38,177,519)
y=step(2,'Valide o pedido antes de liberar','Se houver necessidade de antecipar a liberação, confira a solicitação do usuário. A operação exige perfil DEV e as permissões aplicáveis da Central de TI.',38,y,519)
y=step(3,'Informe o motivo e desbloqueie','Preencha a justificativa e clique em Desbloquear. A liberação afeta o bloqueio selecionado, e o histórico registra o responsável e o motivo.',38,y,519)
text('O que aparece no histórico',38,439,519,14,NAVY,True)
rows=[('Login realizado','O acesso foi autenticado com sucesso.'),('Acesso recusado','A tentativa não foi autenticada.'),('Limite atingido','Uma tentativa acionou o bloqueio.'),('Tentativa durante bloqueio','Houve nova tentativa enquanto o bloqueio estava ativo.'),('Desbloqueio manual','O DEV antecipou a liberação e registrou uma justificativa.')]
for i,(a,b) in enumerate(rows):
    top=472+i*33
    rect(38,top,519,33,LIGHT if i%2==0 else '#FFFFFF',0)
    text(a,49,top+8,172,8.7,NAVY,True)
    text(b,231,top+8,314,8.7,INK)
text('São exibidos até 100 bloqueios ativos e os últimos 100 eventos, com horários de Brasília. Senhas e tokens não são registrados nesse histórico.',38,650,519,9,MUTED)
rect(38,700,519,59,'#E6F5F6')
text('<b>Conta e origem são independentes.</b> O padrão também prevê bloqueio após 50 falhas por IP em 15 minutos, somando contas. Se ambos estiverem bloqueados, liberar apenas um pode não restabelecer o acesso.',51,710,493,9.1)
C.showPage()
C.save()
print(OUT)
