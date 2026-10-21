from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT

ROOT=Path.cwd()
FONT=Path('/System/Library/Fonts/Supplemental')
pdfmetrics.registerFont(TTFont('Guide',str(FONT/'Arial.ttf')))
pdfmetrics.registerFont(TTFont('GuideBold',str(FONT/'Arial Bold.ttf')))
pdfmetrics.registerFontFamily('Guide',normal='Guide',bold='GuideBold',italic='Guide',boldItalic='GuideBold')
NAVY=colors.HexColor('#194a76'); TEAL=colors.HexColor('#167d94'); TEXT=colors.HexColor('#253345'); MUTED=colors.HexColor('#607084'); PALE=colors.HexColor('#eef4f8'); LINE=colors.HexColor('#d7e2eb')
ST={
 'title':ParagraphStyle('Title',fontName='GuideBold',fontSize=22,leading=27,textColor=NAVY,spaceAfter=9),
 'subtitle':ParagraphStyle('Subtitle',fontName='Guide',fontSize=10.5,leading=15,textColor=MUTED,spaceAfter=17),
 'h':ParagraphStyle('Heading',fontName='GuideBold',fontSize=14,leading=18,textColor=NAVY,spaceBefore=9,spaceAfter=9,keepWithNext=True),
 'step':ParagraphStyle('Step',fontName='GuideBold',fontSize=10.5,leading=15,textColor=NAVY,spaceBefore=10,spaceAfter=4,keepWithNext=True),
 'body':ParagraphStyle('Body',fontName='Guide',fontSize=10,leading=14.5,textColor=TEXT,spaceAfter=7),
 'small':ParagraphStyle('Small',fontName='Guide',fontSize=9,leading=12.5,textColor=MUTED,spaceAfter=6),
 'cell':ParagraphStyle('Cell',fontName='Guide',fontSize=9.3,leading=13,textColor=TEXT),
 'th':ParagraphStyle('TH',fontName='GuideBold',fontSize=9.3,leading=13,textColor=colors.white),
}

def p(t,kind='body'):return Paragraph(t,ST[kind])
def table(rows,widths,header=True):
 data=[[p(str(x),'th' if i==0 and header else 'cell') for x in row] for i,row in enumerate(rows)]
 t=Table(data,colWidths=widths,repeatRows=1 if header else 0,hAlign='LEFT')
 styles=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),('LINEBELOW',(0,0),(-1,-1),.4,LINE)]
 if header:styles += [('BACKGROUND',(0,0),(-1,0),NAVY),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE])]
 t.setStyle(TableStyle(styles));return t

def note(title,text):
 t=Table([[p(title,'step')],[p(text,'body')]],colWidths=[495.28])
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),.5,LINE),('LEFTPADDING',(0,0),(-1,-1),13),('RIGHTPADDING',(0,0),(-1,-1),13),('TOPPADDING',(0,0),(-1,0),3),('BOTTOMPADDING',(0,-1),(-1,-1),7)]));return t

class NumberedCanvas(canvas.Canvas):
 def __init__(self,*a,**kw):super().__init__(*a,**kw);self.saved=[]
 def showPage(self):self.saved.append(dict(self.__dict__));self._startPage()
 def save(self):
  total=len(self.saved)
  for state in self.saved:
   self.__dict__.update(state);self.decorate(total);super().showPage()
  super().save()
 def decorate(self,total):
  w,h=self._pagesize
  self.setStrokeColor(LINE);self.line(50,h-43,w-50,h-43);self.line(50,40,w-50,40)
  self.setFillColor(NAVY);self.setFont('GuideBold',8);self.drawString(50,h-32,'IJA SYSTEM  |  VIGILÂNCIA EM SAÚDE')
  self.setFillColor(MUTED);self.setFont('Guide',8);self.drawRightString(w-50,h-32,self._doc_title)
  self.drawString(50,27,'20/10/2026  |  Documento de apoio ao uso do sistema')
  self.drawRightString(w-50,27,f'{self._pageNumber} / {total}')

class GuideCanvas(NumberedCanvas):
 _doc_title='Tutorial operacional LIRAa'

def build(output,story,title,canvas_class=GuideCanvas):
 d=SimpleDocTemplate(str(output),pagesize=(595.28,841.89),leftMargin=50,rightMargin=50,topMargin=66,bottomMargin=56,title=title,author='IJA System',subject='Vigilância, LIRAa e demonstração funcional')
 d.build(story,canvasmaker=canvas_class)

S=[]
S += [p('LIRAa: tutorial de operação','title'),p('Planejamento, importação por CSV e registro manual de visitas','subtitle')]
S += [p('1. Preparar o levantamento','h'),p('Perfil: COVISA ou coordenação municipal com permissão de edição. Para testar, selecione <b>Pesqueira</b> e <b>Demonstração - dados fictícios</b> em todas as etapas.')]
S += [note('Ordem do trabalho','Planejar o território e a amostra → liberar a coleta → registrar ou importar visitas → confirmar → consultar os resultados e o mapa.')]
S += [p('1.1 Abrir o planejamento','step'),p('Acesse <b>Central de Vigilância → Focal e LIRAa → Planejar</b>. Selecione a prefeitura, o modo de dados e clique em <b>Aplicar</b>.')]
S += [p('1.2 Cadastrar os quarteirões','step'),p('Entre em <b>Quarteirões e áreas</b>. Para preencher na mão, informe código do quarteirão, bairro, código da área, quantidade de imóveis e referência do cadastro territorial. Clique em <b>Salvar quarteirão</b>.'),p('Para usar CSV, abra <b>Importar cadastro territorial por CSV</b>, selecione o arquivo territorial e clique em <b>Importar território</b>.')]
S += [p('1.3 Delimitar o território no mapa','step'),p('Localize o bairro ou endereço. Clique em <b>Desenhar área</b>, marque pelo menos três cantos e escolha <b>Concluir desenho</b>. Confira o limite, marque a confirmação da alteração e clique em <b>Salvar quarteirão</b>. Para ajustar um cadastro existente, use <b>Localizar / delimitar</b> ou <b>Ver área</b> na tabela.'),p('Concluir o desenho não salva o cadastro. O contorno é opcional e não calcula a quantidade de imóveis nem seleciona automaticamente a amostra.','small')]
S += [p('1.4 Criar o levantamento','step'),p('Volte aos levantamentos e clique em <b>Novo levantamento</b>. Preencha código, nome, início e fim, responsável técnico e referência do plano amostral. Clique em <b>Criar rascunho</b>.')]
S += [PageBreak(),p('Planejamento e arquivos CSV','title'),p('Montagem da amostra e importação de visitas','subtitle')]
S += [p('2. Montar e liberar a amostra','h'),p('No rascunho, escolha uma das formas de cadastrar a seleção:')]
S += [table([['Por CSV','Preenchimento manual'],['Abra <b>Importar estratos e quarteirões selecionados</b>. Envie o CSV da amostra e clique em <b>Importar amostra do rascunho</b>. O arquivo substitui a amostra do rascunho.','Em <b>Estratos e metas</b>, informe código, total de imóveis, meta e critério. Depois, em <b>Quarteirões e agentes</b>, selecione estrato e quarteirão, informe a meta e atribua o agente.']],[247.64,247.64])]
S += [Spacer(1,9),p('Confira se a soma das metas dos quarteirões fecha a meta de cada estrato. Marque a revisão da coordenação e clique em <b>Liberar levantamento para campo</b>. Para o agente visualizar suas tarefas, os quarteirões precisam estar atribuídos à sua conta.')]
S += [p('3. Entender os três arquivos','h'),table([['Arquivo','Finalidade'],['Cadastro territorial','Cadastra quarteirões, bairros, áreas e quantidade de imóveis.'],['Amostra do levantamento','Define estratos, metas, quarteirões selecionados e agentes.'],['Visitas / inspeções','Contém as situações observadas nos imóveis, resultados e, quando disponíveis, coordenadas.']],[155,340.28])]
S += [Spacer(1,8),p('Os arquivos territorial e de amostra <b>não registram inspeções</b>. No CSV de visitas, <b>municipio_id</b> é o ID interno da prefeitura, não o código IBGE. Use o layout de cada importação, preservando cabeçalhos e códigos.','small')]
S += [p('4. Importar um CSV de visitas','h'),p('1. Acesse <b>Registrar visitas → Importar visitas</b>.<br/>2. Selecione Pesqueira e <b>Demonstração</b>.<br/>3. Informe a <b>Fonte do arquivo</b>, por exemplo: levantamento fictício para demonstração.<br/>4. Selecione o CSV de visitas e clique em <b>Validar arquivo</b>.<br/>5. Confira registros, indicadores e erros apresentados.<br/>6. Se a situação for <b>VALIDADO</b>, clique em <b>Confirmar carga validada</b>.<br/>7. Confirme que o lote ficou <b>CONCLUÍDO</b>.')]
S += [note('Vínculo com o planejamento','A importação genérica de visitas não vincula automaticamente os registros aos quarteirões do planejamento. Se o levantamento já tem planejamento cadastrado, registre as visitas pelo quarteirão. Esse é o caminho para demonstrar distribuição ao agente e acompanhamento das metas.')]
S += [PageBreak(),p('Registro manual de visitas','title'),p('Coleta pelo agente e confirmação dos registros','subtitle')]
S += [p('5. Entrar na tarefa atribuída','h'),p('Entre com a conta de <b>Agente de Endemias</b> e selecione <b>Demonstração</b>. Em <b>Quarteirões atribuídos a mim</b>, clique em <b>Registrar em...</b>. A coordenação também pode registrar: no planejamento liberado, use <b>Registrar visita em [quarteirão]</b>.')]
S += [p('6. Preencher a visita','h'),table([['Campo','Orientação'],['Código do imóvel','Use uma identificação estável. Reutilize o mesmo código em visitas futuras ao mesmo imóvel.'],['Código da visita','Identifica aquela visita. O sistema já sugere um código.'],['Data da visita','Deve estar dentro do período do levantamento.'],['Situação do imóvel','Escolha inspecionado, fechado, recusado ou não inspecionado / inspeção parcial.'],['Positivo para Aedes aegypti?','Para imóvel inspecionado, informe Sim ou Não conforme a identificação realizada. Não equivale a um caso de doença.'],['Recipientes positivos','Opcional. Preencha as sete categorias ou deixe todas vazias. Use zero nas categorias sem positivos. Conte recipientes, não larvas.'],['Latitude e longitude','Opcionais para registrar a visita; necessárias para mostrar seu ponto individual no mapa. Informe o par completo.']],[158,337.28])]
S += [Spacer(1,9),p('7. Revisar e confirmar','h'),p('Marque que o imóvel pertence à amostra. Clique em <b>Revisar visita</b>, confira o resumo e clique em <b>Confirmar visita</b>. Depois, use <b>Nova visita no quarteirão</b> para continuar.'),p('Na tela geral da coordenação, os botões correspondentes são <b>Revisar registro antes de gravar</b> e, na etapa seguinte, <b>Confirmar carga validada</b>.')]
S += [note('Quando o registro entra nos resultados','A etapa de revisão prepara o registro. Ele entra no consolidado após a confirmação. No fluxo atual, não há uma segunda aprovação obrigatória da COVISA para entrar nos resultados.')]
S += [PageBreak(),p('Resultados, índices e mapa','title'),p('Conferência pela coordenação e encerramento da coleta','subtitle')]
S += [p('8. Consultar os resultados','h'),p('A COVISA acessa <b>Ver resultados</b> e seleciona a mesma prefeitura, o mesmo modo de dados e o levantamento. Confira imóveis inspecionados, positivos, pendências e índices. O período escolhido pode mostrar apenas parte da coleta.')]
S += [note('Como o sistema calcula o IIP','<b>IIP = 100 × imóveis positivos ÷ imóveis inspecionados.</b><br/>Exemplo fictício: 2 imóveis positivos entre 20 inspecionados resultam em IIP de 10%. Visitas fechadas, recusadas e não inspecionadas ficam como pendências; não entram no denominador.')]
S += [p('9. Conferir o mapa de risco','h'),p('Abra <b>Mapa de risco</b> e mantenha os filtros da coleta. Para conferir as visitas, escolha a fonte <b>Levantamento LIRAa</b>.'),table([['O que aparece','O que precisa existir'],['Pontos das visitas','Visitas confirmadas com latitude e longitude.'],['Áreas com IIP','Contornos cadastrados no planejamento e associados aos códigos de levantamento, estrato e área usados nas visitas.'],['Limite municipal','Geografia disponível para o município. Esse limite, sozinho, não comprova inspeção nem define IIP para toda a cidade.']],[158,337.28])]
S += [Spacer(1,8),p('Uma visita sem coordenadas pode participar dos indicadores, mas não terá ponto individual. Um CSV com pontos não cria automaticamente o contorno de uma área. Ausência de informação no mapa não significa ausência de focos.','small')]
S += [p('10. Encerrar o levantamento','h'),p('Depois de conferir metas e pendências, volte ao planejamento e clique em <b>Encerrar levantamento</b>. O encerramento impede novos registros planejados; os resultados já confirmados permanecem disponíveis.')]
S += [p('Conferência rápida para a demonstração','h'),p('1. Prefeitura e modo de dados iguais em todas as telas.<br/>2. Território cadastrado e, se necessário, contornos salvos.<br/>3. Amostra revisada, agentes atribuídos e levantamento liberado.<br/>4. Visitas revisadas e efetivamente confirmadas.<br/>5. Resultados e mapa filtrados pelo levantamento correto.<br/>6. Dados fictícios identificados como demonstração.')]
S += [Spacer(1,8),p('Escopo: este tutorial descreve o fluxo implementado no sistema. O plano amostral e a validação técnica do levantamento são responsabilidades da coordenação municipal.','small')]
output=ROOT/'output/pdf/IJA-System-Tutorial-LIRAa-CSV-e-Registro-Manual.pdf'
build(output,S,'LIRAa - Tutorial de importação e registro manual')
print(output)
