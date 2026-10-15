from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

ROOT = Path('/Users/joaopedro/Documents/Ija-System')
FONT = Path('/Users/joaopedro/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype')
pdfmetrics.registerFont(TTFont('Body', str(FONT / 'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('Bold', str(FONT / 'DejaVuSans-Bold.ttf')))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold')
OUT = ROOT / 'output/pdf/guia-edicao-protegida-ija.pdf'
C = canvas.Canvas(str(OUT), pagesize=A4)
C.setTitle('Edição protegida | IJA System')
C.setAuthor('Time de Desenvolvimento da IJA Drones')
W, H = A4
NAVY, INK, TEAL, MUTED = '#12344A', '#233D4D', '#008EA4', '#526776'
CW = W - 76

def box(x, top, w, h, color='#EFF6F9', radius=10):
    C.setFillColor(HexColor(color))
    C.roundRect(x, H-top-h, w, h, radius, fill=1, stroke=0)

def txt(s, x, top, w, size=10, color=INK, bold=False, leading=None):
    style = ParagraphStyle('p', fontName='Bold' if bold else 'Body', fontSize=size,
                           leading=leading or size*1.45, textColor=HexColor(color))
    p = Paragraph(s, style)
    _, height = p.wrap(w, H)
    p.drawOn(C, x, H-top-height)
    return top+height

def page(n, tag, title, subtitle):
    C.setFillColor(HexColor(TEAL)); C.rect(0,H-8,W,8,fill=1,stroke=0)
    txt('IJA SYSTEM  /  GUIA DA FUNCIONALIDADE',38,25,390,8,TEAL,True)
    txt('15 OUT 2026',W-125,25,90,8,MUTED)
    txt(tag.upper(),38,61,CW,8.5,TEAL,True)
    y = txt(title,38,80,CW,26,NAVY,True,31)
    txt(subtitle,38,y+12,CW,10.5,MUTED)
    C.setStrokeColor(HexColor('#D9E5EA')); C.line(38,68,W-38,68)
    txt('IJA DRONES',38,H-55,430,10,NAVY,True)
    txt('Documento elaborado pelo time de desenvolvimento da IJA DRONES',38,H-38,475,7.7,MUTED)
    txt(f'{n} / 3',W-72,H-55,40,8,MUTED)

def step(n,title,body,top):
    box(38,top,25,25,TEAL,7)
    txt(str(n),46,top+4,18,11,'#FFFFFF',True)
    y=txt(title,75,top,CW-37,11,NAVY,True)
    return txt(body,75,y+5,CW-37,10)+18

def arrow(x,y):
    C.setStrokeColor(HexColor(TEAL)); C.setLineWidth(1.7)
    C.line(x,H-y,x+24,H-y)
    C.line(x+18,H-y+4,x+24,H-y); C.line(x+18,H-y-4,x+24,H-y)

page(1,'Visão geral','Edição protegida','Mais segurança quando duas pessoas trabalham no mesmo registro.')
txt('Uma alteração por vez, sem perder o controle',38,160,CW,15,NAVY,True)
txt('A funcionalidade evita que uma pessoa sobrescreva o trabalho de outra. Nos fluxos protegidos, o registro abre para consulta e a edição começa após uma reserva temporária.',38,190,CW,10.5)

txt('COMO A PROTEÇÃO FUNCIONA',38,257,CW,8.5,TEAL,True)
cardw=(CW-60)/3
cards=[('01  RESERVAR','Maria inicia a edição','O sistema reserva o registro para ela.'),('02  CONSULTAR','João abre o mesmo registro','Ele vê quem está editando e pode consultar os dados.'),('03  LIBERAR','Maria salva ou cancela','A reserva é liberada para uma nova edição.')]
for i,(tag,title,body) in enumerate(cards):
    x=38+i*(cardw+30)
    box(x,280,cardw,155)
    txt(tag,x+13,294,cardw-26,8,TEAL,True)
    y=txt(title,x+13,321,cardw-26,11,NAVY,True)
    txt(body,x+13,y+12,cardw-26,9.2)
    if i<2: arrow(x+cardw+3,358)
txt('Representação ilustrativa de duas pessoas acessando o mesmo registro.',38,445,CW,8,MUTED)

txt('Duas camadas de proteção',38,487,CW,15,NAVY,True)
box(38,520,CW,83,'#EAF7F5')
txt('Reserva temporária',53,534,CW-30,11,TEAL,True)
txt('Enquanto uma pessoa edita, os demais consultam. Isso também vale para outra aba aberta pelo mesmo usuário.',53,558,CW-30,10)
box(38,616,CW,99)
txt('Conferência da versão',53,630,CW-30,11,TEAL,True)
txt('Antes de salvar, o sistema confere se o registro mudou desde a abertura da página. Uma aba desatualizada não pode substituir informações mais recentes: é preciso recarregar e revisar.',53,654,CW-30,10)
C.showPage()

page(2,'Uso no dia a dia','Como editar com segurança','Os avisos explicam o estado do registro e orientam a próxima ação.')
y=step(1,'Abra o registro e clique em “Iniciar edição”','A página começa em modo de consulta. A edição só é habilitada quando a reserva é obtida.',161)
y=step(2,'Faça as alterações e salve','Ao salvar com sucesso, a reserva é liberada. Para desistir, use “Cancelar edição e liberar” e confirme; a página será recarregada e as alterações não salvas serão descartadas.',y)

box(38,342,CW,91,'#FFF4DF')
txt('OUTRA PESSOA ESTÁ EDITANDO',53,355,CW-30,8.5,'#8B500A',True)
txt('“Maria está editando este registro.”',53,376,CW-30,11,NAVY,True)
txt('Você pode consultar os dados. Aguarde a liberação e use “Tentar novamente”.',53,401,CW-30,9.5)

box(38,445,CW,108,'#FFF0EF')
txt('O REGISTRO MUDOU DESDE A ABERTURA',53,458,CW-30,8.5,'#A13E36',True)
txt('Suas alterações não foram salvas.',53,479,CW-30,11,NAVY,True)
txt('Copie o que precisar, use “Recarregar dados” e revise a versão atual antes de editar novamente.',53,504,CW-30,9.5)
txt('Avisos acima: exemplos ilustrativos do comportamento da interface.',38,562,CW,8,MUTED)

txt('E se eu fechar a aba ou perder a conexão?',38,598,CW,13,NAVY,True)
txt('A reserva tem duração padrão de <b>5 minutos a partir da última renovação</b>. Ela é renovada enquanto a aba está visível e há atividade recente. Ao fechar ou abandonar a aba, a liberação ocorre pelo vencimento da reserva.',38,624,CW,9.8)
txt('Se a renovação falhar ou a reserva vencer, a edição é pausada. Os campos permanecem na tela para consulta e cópia. <b>Não há recuperação automática de rascunho:</b> copie o necessário antes de recarregar.',38,689,CW,9.8)
C.showPage()

page(3,'Administração e rastreabilidade','Onde a proteção atua','A reserva respeita os acessos já definidos para cada perfil e prefeitura.')
txt('Fluxos contemplados nesta entrega',38,160,CW,14,NAVY,True)
rows=[('Solicitações','Edição completa e decisões administrativas rápidas.'),('Ordens de serviço','Formulários operacionais de piloto, equipe Oceano Azul e administração; retornos automáticos da UVIS.'),('Denúncias','Triagem, encaminhamento, designação, arquivamento e conversão em solicitação.')]
top=190
for i,(label,body) in enumerate(rows):
    height=69 if i else 53
    box(38,top,CW,height,'#EFF6F9' if i%2==0 else '#F7FAFC',4)
    txt(label,50,top+12,130,10,NAVY,True)
    txt(body,190,top+12,CW-165,9.5)
    top+=height+5
txt('A solicitação e seus formulários de OS compartilham a reserva. Esta entrega não estende a reserva a todos os demais módulos do sistema.',38,top+8,CW,9.2,MUTED)

txt('Liberação excepcional pelo DEV',38,449,CW,14,NAVY,True)
txt('Quando houver outro editor, o DEV pode abrir <b>“DEV: liberar a reserva de outro editor”</b>, informar um motivo de 10 a 300 caracteres e clicar em <b>“Liberar e registrar na auditoria”</b>.',38,477,CW,10)
txt('A autorização de edição anterior é invalidada. Depois, é necessário recarregar e iniciar uma nova reserva para editar normalmente.',38,533,CW,10)

box(38,585,CW,142,'#EAF7F5')
txt('O que fica registrado',53,599,CW-30,12,TEAL,True)
txt('A auditoria registra reservas, liberações e conflitos de edição. Na liberação pelo DEV, também registra o motivo e o editor anterior. As alterações nos dados continuam seguindo o histórico de auditoria.',53,627,CW-30,9.7)
txt('O arquivamento segue o processo de auditoria já existente no Skybox. A reserva não concede acesso a dados de outra prefeitura.',53,686,CW-30,9.7)
C.showPage()
C.save()
print(OUT)
