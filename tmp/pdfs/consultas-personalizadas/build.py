from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

ROOT=Path('/Users/joaopedro/Documents/Ija-System')
TMP=ROOT/'tmp/pdfs/consultas-personalizadas'
S=TMP/'screens'; C=TMP/'crops'; C.mkdir(exist_ok=True)
OUT=ROOT/'output/pdf/guia-consultas-personalizadas-ija-system-2026-10-17.pdf'
F=Path('/Users/joaopedro/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/poppler/fonts')
for n,f in [('Ubuntu','Ubuntu-R.ttf'),('Ubuntu-Bold','Ubuntu-B.ttf'),('Ubuntu-Italic','Ubuntu-RI.ttf')]: pdfmetrics.registerFont(TTFont(n,str(F/f)))
pdfmetrics.registerFontFamily('Ubuntu',normal='Ubuntu',bold='Ubuntu-Bold',italic='Ubuntu-Italic',boldItalic='Ubuntu-Bold')
W,H=landscape(A4); navy=HexColor('#173B55'); teal=HexColor('#04A9B9'); gray=HexColor('#526677'); pale=HexColor('#F1F6F9')
c=canvas.Canvas(str(OUT),pagesize=(W,H)); c.setTitle('Consultas personalizadas - Guia de uso | IJA System');c.setAuthor('Time de desenvolvimento da IJA DRONES')
styles={}
for name,size,col in [('body',11,navy),('small',9,gray),('lead',13,gray),('white',11,white)]: styles[name]=ParagraphStyle(name,fontName='Ubuntu',fontSize=size,leading=size*1.38,textColor=col,spaceAfter=0)

def p(text,x,top,w,style='body'):
 a=Paragraph(text,styles[style]); aw,ah=a.wrap(w,1000); a.drawOn(c,x,H-top-ah);return top+ah

def title(n,head,sub):
 c.setFillColor(white);c.rect(0,0,W,H,fill=1,stroke=0)
 c.setFillColor(teal);c.rect(0,H-8,W,8,fill=1,stroke=0)
 c.setFillColor(teal);c.setFont('Ubuntu-Bold',9);c.drawString(36,H-32,'IJA SYSTEM  /  GUIA DE USO')
 c.setFillColor(navy);c.setFont('Ubuntu-Bold',25);c.drawString(36,H-66,head)
 p(sub,36,78,W-72,'small')
 c.setStrokeColor(HexColor('#DFE7EC'));c.line(36,35,W-36,35)
 c.setFillColor(gray);c.setFont('Ubuntu',8);c.drawString(36,22,'IJA DRONES  •  Consultas personalizadas  •  17/10/2026')
 c.drawRightString(W-36,22,f'{n:02d} / 09')

def box(x,top,w,h,color=pale):
 c.setFillColor(color);c.roundRect(x,H-top-h,w,h,9,fill=1,stroke=0)

def crop(name,source,rect):
 im=Image.open(S/source);im.crop(rect).convert('RGB').save(C/(name+'.jpg'),quality=94);return C/(name+'.jpg')

def pic(path,x,top,w,h):
 im=Image.open(path);iw,ih=im.size;scale=min(w/iw,h/ih);dw,dh=iw*scale,ih*scale
 c.drawImage(str(path),x+(w-dw)/2,H-top-dh,width=dw,height=dh,mask='auto')
 return top+dh

def note(head,body,x,top,w):
 y=p('<b>'+head+'</b>',x,top,w);return p(body,x,y+6,w)+12

def end():c.showPage()

central=crop('central','01-central.png',(785,500,2585,1465))
builder=crop('builder','02-construtor.png',(575,710,2795,1610))
formulas=crop('formulas','04-resultado.png',(580,425,2790,810))
filters=crop('filters','04-resultado.png',(580,825,2790,1470))
result=crop('result','06-status.png',(600,515,2780,1850))
bar=crop('bar','06-status.png',(595,320,2780,505))
config=crop('config','09-configuracoes.png',(1260,615,2590,1170))
emailconf=crop('emailconf','10-email-config.png',(945,585,2430,1410))
confirm=crop('confirm','07-email-confirmar.png',(1115,810,1910,1265))
ready=crop('ready','08-email-pronto.png',(1115,700,1910,1375))

# 1
title(1,'Consultas personalizadas','Monte relatórios com os campos e critérios que sua equipe precisa. Salve a definição e compartilhe o resultado.')
pic(central,36,112,770,326)
p('Acesse <b>Relatórios &gt; Consultas personalizadas &gt; Montar consulta</b>. Os relatórios já existentes, incluindo <b>Logs de Voo</b> e <b>SINAN</b>, continuam disponíveis na Central de Relatórios.',36,450,770)
box(36,495,770,48)
p('<b>Fluxo:</b> escolher base e campos &gt; filtrar &gt; executar &gt; conferir &gt; exportar ou preparar e-mail.',49,506,744)
p('Capturas reais do sistema local em 17/10/2026, com banco de testes. Prefeituras, quantidades e resultados ilustram o uso.',36,543,770,'small');end()
# 2
title(2,'Quem acessa e quais dados aparecem','O perfil define as ações disponíveis. Os vínculos municipais e operacionais delimitam os dados consultáveis.')
rows=[['Perfil','Consultas personalizadas','Configurações municipais'],['COVISA','Consulta os dados permitidos da prefeitura\nvinculada ao seu cadastro.','Consulta e altera o destinatário e as\npreferências da própria prefeitura.'],['Diretor','Acesso conforme suas permissões\nde Relatórios e alcance global.','Pode consultar todas as prefeituras.\nNo padrão, não salva alterações.'],['Administrador','Acesso conforme suas permissões\nde Relatórios e alcance global.','O acesso a Relatórios não libera\nConfigurações automaticamente.'],['DEV','Acesso global para administrar\ne verificar o funcionamento.','Consulta e administra as\nconfigurações de todas as prefeituras.']]
rr=[[Paragraph(t.replace('\n','<br/>'),styles['small' if i else 'white']) for t in row] for i,row in enumerate(rows)]
t=Table(rr,colWidths=[115,320,335],rowHeights=[30,58,58,58,58]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('ROWBACKGROUNDS',(0,1),(-1,-1),[pale,white]),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),12),('LINEBELOW',(0,1),(-1,-1),0.5,HexColor('#DFE7EC'))]));t.wrapOn(c,770,300);t.drawOn(c,36,H-121-262)
note('O filtro não concede acesso','Selecionar uma prefeitura apenas restringe o que o usuário já pode consultar. Uma COVISA não passa a visualizar os dados de outra prefeitura por mudar um filtro.',36,405,366)
note('A Central de TI pode ajustar as permissões','Consultar e exportar são permissões separadas. Outros perfis seguem suas regras de Relatórios. A disponibilidade do menu pode variar conforme a configuração do perfil.',438,405,366)
p('O catálogo de consultas é pessoal. Em cada execução, o sistema confere novamente as permissões e os vínculos atuais.',36,525,770,'small');end()
# 3
title(3,'Escolha a base, os campos e o formato','Comece com uma pergunta clara: quais registros você quer analisar e quais informações precisam aparecer?')
pic(builder,36,117,770,313)
note('1. Escolha a base','<b>Solicitações:</b> consulta as solicitações permitidas. <b>Ordens de serviço:</b> considera as solicitações que já possuem OS.',36,446,237)
note('2. Selecione as colunas','Marque até 12 campos. Use as setas para ajustar a ordem e escolha o formato quando disponível, como decimal ou percentual.',302,446,237)
note('3. Reutilize depois','Dê um nome e clique em <b>Salvar consulta</b>. Em <b>Minhas consultas</b>, carregue a definição; use <b>Salvar cópia</b> para criar uma variação.',568,446,237)
end()
# 4
title(4,'Filtros, fórmulas e agrupamentos','Combine os recursos para tornar o relatório útil à análise, sem precisar montar uma planilha do zero.')
pic(formulas,36,117,770,166)
p('<b>Exemplo:</b> a fórmula <b>imagens + videos</b> cria a coluna “Total de mídias”. Use os códigos dos campos numéricos. Dados ausentes e divisões por zero aparecem como “Não informado”.',36,291,770)
pic(filters,36,337,770,191)
p('<b>Condições:</b> todas precisam ser satisfeitas. <b>Exceções:</b> qualquer correspondência exclui o registro. A opção <b>Quebrar o relatório por</b> organiza os resultados em grupos, como Bairro.',36,531,770,'small');end()
# 5
title(5,'Leia os resultados em conjunto','Após Executar consulta, confira a quantidade retornada, o gráfico de status, o mapa e a tabela.')
pic(result,36,116,555,350)
note('Mesmo conjunto de dados','Tabela, gráfico e mapa partem do resultado da mesma execução. No exemplo, 70 registros foram retornados.',613,125,190)
note('Mapa e coordenadas','67 registros têm coordenadas válidas; 3 continuam na tabela e na contagem, embora não apareçam no mapa.',613,236,190)
note('Quebra por bairro','Os grupos ajudam a comparar os registros. Campos numéricos podem apresentar somas por grupo, exceto o identificador.',613,368,190)
box(36,490,770,61)
p('<b>Bairro depende do cadastro.</b> O filtro usa o bairro registrado nos dados. Ele não preenche automaticamente os cadastros antigos. Para investigar valores ausentes, comece sem restringir o bairro.',49,502,744)
end()
# 6
title(6,'Salvar, atualizar e exportar','A consulta salva guarda os critérios. O resultado é obtido novamente quando você executa ou gera um arquivo.')
pic(bar,36,116,770,66)
note('PDF','Use <b>Baixar PDF</b> para gerar o relatório com a definição atual. O limite é de 2.000 registros. Se ultrapassar, restrinja os filtros antes de gerar novamente.',36,207,237)
note('Excel','Use <b>Baixar Excel</b> para trabalhar com os dados em planilha. Consulta e Excel permitem até 10.000 registros por execução.',302,207,237)
note('Impressão','Use <b>Imprimir tabela</b> para abrir a impressão do navegador. Confira a prévia, a orientação da página e o destino antes de concluir.',568,207,237)
box(36,350,770,83)
p('<b>Atualizar a cada 30 segundos</b><br/>Quando habilitado, o sistema repete a consulta enquanto a tela está visível e não há uma execução em andamento. Confira a data e a hora do último resultado para saber quando os dados foram consultados.',50,362,742)
note('Por que o arquivo pode diferir da tela?','PDF e Excel consultam o banco novamente com os mesmos critérios. Alterações feitas por colegas entre a consulta e a exportação podem aparecer no arquivo mais recente.',36,451,365)
note('Período e campos vazios','O período corresponde à <b>data de agendamento</b>. Se o resultado vier vazio ou incompleto, revise datas, status, bairro e condições antes de aumentar o alcance.',438,451,365)
end()
# 7
title(7,'Um destinatário para cada prefeitura','Configure o endereço que receberá os PDFs. A preferência é compartilhada pelas contas daquela prefeitura.')
pic(emailconf,36,116,512,306)
note('Como cadastrar','1. Abra <b>Configurações</b>.<br/>2. Selecione a prefeitura, quando houver seletor.<br/>3. Abra <b>E-mail dos relatórios</b>.<br/>4. Informe um endereço e clique em <b>Salvar e-mail</b>.',573,124,231)
note('Quem pode alterar','A COVISA altera o destino da própria prefeitura; o DEV administra todas. O diretor consulta as configurações no acesso padrão.',573,306,231)
box(36,447,770,100)
p('<b>Destinatário não é remetente.</b> O endereço cadastrado é quem receberá o relatório. No modo simples, a mensagem será enviada pela conta aberta no aplicativo de e-mail do usuário.<br/><br/>Informe apenas um endereço, sem senha. Deixar o campo vazio desabilita o destino para aquela prefeitura. Para preparar o e-mail, selecione a mesma prefeitura nos filtros da consulta.',50,460,742)
end()
# 8
title(8,'Preparar o e-mail: duas etapas','O modo simples funciona sem configurar SMTP. O sistema baixa o PDF e oferece os atalhos para abrir a mensagem.')
pic(confirm,36,124,363,218)
pic(ready,436,124,369,316)
note('1. Confira e baixe','Na consulta, selecione a prefeitura e clique em <b>Preparar e-mail</b>. Confira o destinatário e clique em <b>Baixar PDF e continuar</b>.',36,360,363)
note('2. Abra a mensagem','Clique em <b>Abrir mensagem no aplicativo de e-mail</b> ou <b>Abrir Outlook na web</b>. Assunto, destinatário e texto são preparados.',436,452,369)
box(36,471,363,76)
p('<b>O envio ainda não aconteceu.</b><br/>Anexe o arquivo <b>consulta.pdf</b>, revise a mensagem, remova o lembrete do corpo e clique em Enviar no seu e-mail.',49,483,337)
end()
# 9
title(9,'Dúvidas frequentes e roteiro de uso','Use este roteiro para repetir o processo com segurança e conferir o resultado antes de compartilhar.')
note('Cliquei e nenhum aplicativo abriu','O navegador pode estar sem aplicativo de e-mail associado. Use a opção Outlook na web, quando sua conta for Microsoft 365, ou abra o e-mail manualmente e anexe o PDF baixado.',36,119,365)
note('O PDF vai anexado automaticamente?','No modo simples, o anexo é manual. O link de e-mail prepara a mensagem, mas não incorpora o PDF. Se necessário, use <b>Baixar PDF novamente</b>.',438,119,365)
note('Por que não aparece no histórico de envio?','Mensagens enviadas pelo seu aplicativo não aparecem no histórico de envios diretos. O sistema não acompanha a entrega desses e-mails. Confira a pasta Enviados no aplicativo usado.',36,254,365)
note('E o envio direto pelo sistema?','Existe uma integração opcional para envio por SMTP. Ela depende da configuração de um serviço de e-mail. Cadastrar apenas o destinatário municipal não ativa essa integração.',438,254,365)
box(36,382,770,70)
p('<b>Roteiro rápido</b><br/>Relatórios &gt; Montar consulta &gt; Base e campos &gt; Filtros e agrupamento &gt; Executar consulta &gt; Conferir tabela/mapa &gt; Salvar definição &gt; Baixar PDF/Excel ou Preparar e-mail &gt; Anexar PDF e enviar.',50,394,742)
c.setFillColor(navy);c.setFont('Ubuntu-Bold',21);c.drawCentredString(W/2,H-496,'IJA DRONES')
c.setFont('Ubuntu',11);c.drawCentredString(W/2,H-521,'Documento elaborado pelo time de desenvolvimento da IJA DRONES')
p('Guia baseado nas telas e no comportamento da versão local de 17/10/2026. Exemplos capturados no banco de testes.',36,543,770,'small')
end();c.save();print(OUT)
