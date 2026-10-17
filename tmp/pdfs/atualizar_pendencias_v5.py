from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from pypdf import PdfReader
from xml.sax.saxutils import escape
import re
from pathlib import Path
OUT=Path('output/pdf/demandas-pendentes-condomar-ija-2026-10-17-v5.pdf')
old=PdfReader('output/pdf/demandas-pendentes-condomar-ija-2026-10-17-v4.pdf')
W,H=595.28,841.89
navy=HexColor('#163e52');teal=HexColor('#078b89');gray=HexColor('#52616c')
c=canvas.Canvas(str(OUT),pagesize=(W,H))
c.setTitle('Demandas pendentes CONDOMAR - IJA System - Atualização 5')
c.setAuthor('Time de desenvolvimento da IJA DRONES')
styles={
 'body':ParagraphStyle('body',fontName='Helvetica',fontSize=10,leading=14,textColor=navy,spaceAfter=8),
 'small':ParagraphStyle('small',fontName='Helvetica',fontSize=8.5,leading=11.5,textColor=gray),
 'item':ParagraphStyle('item',fontName='Helvetica-Bold',fontSize=11,leading=14,textColor=navy),
 'intro':ParagraphStyle('intro',fontName='Helvetica',fontSize=11,leading=15,textColor=gray),
 'title':ParagraphStyle('title',fontName='Helvetica-Bold',fontSize=24,leading=28,textColor=navy),
}
y=0
page=0

def p(text,style='body',gap=9):
 global y
 obj=Paragraph(text,styles[style]); _,h=obj.wrap(W-88,900)
 if y-h<94: raise RuntimeError(f'Overflow page {page}: {text[:70]} at {y-h}')
 obj.drawOn(c,44,y-h); y-=h+gap

def start(kicker,title,intro):
 global y,page
 page+=1
 c.setFillColor(teal);c.rect(0,H-9,W,9,fill=1,stroke=0)
 c.setFillColor(gray);c.setFont('Helvetica-Bold',8);c.drawString(44,H-35,'IJA SYSTEM / CONDOMAR')
 c.setFont('Helvetica',8);c.drawRightString(W-44,H-35,'17/10/2026 | Atualização 5')
 y=H-69
 p(kicker,'small',10);p(title,'title',12);p(intro,'intro',19)

def end():
 c.setStrokeColor(HexColor('#dbe4e7'));c.line(44,73,W-44,73)
 c.setFillColor(navy);c.setFont('Helvetica-Bold',12);c.drawCentredString(W/2,54,'IJA DRONES')
 c.setFont('Helvetica',8);c.drawCentredString(W/2,40,'Documento elaborado pelo time de desenvolvimento da IJA DRONES')
 c.setFillColor(gray);c.setFont('Helvetica',8);c.drawRightString(W-44,24,str(page))
 c.showPage()

def item(title,text):
 p(escape(title),'item',5)
 status,sep,rest=text.partition(' - ')
 if sep: p('<b>'+escape(status)+'</b> - '+escape(rest))
 else:p(escape(text))

def inherited(index,tail=None):
 text=old.pages[index].extract_text()
 # Keep the existing item texts; the cover/header and editorial introductions are replaced.
 parts=re.split(r'\n(?=4\.\d)',text)
 for block in parts[1:]:
  lines=block.strip().splitlines(); title=lines[0];body=' '.join(lines[1:])
  if tail and tail in body:body=body.split(tail)[0].strip()
  if index==5:
   body=body.replace('Considerar SINAN/LIRAa como módulos atendidos.','SINAN consta no sistema; LIRAa está ATENDE por confirmação, com integração à main ainda informada como pendente.')
  item(title,body)

start('ACOMPANHAMENTO INTERNO','Demandas pendentes','CONDOMAR / IJA SYSTEM - situação consolidada após a evolução do mapa operacional.')
p('Esta versão substitui a atualização 4. Mantém os aceites registrados e atualiza os itens 4.8, II, VIII, XIII, XII e XIV com a melhoria feita na tela Mapas. Não constitui nova auditoria integral nem aceite formal do contratante.')
item('O que foi entregue agora','IMPLEMENTADO LOCALMENTE - Filtros de pendências, atrasados e retornos; lista com solicitações sem coordenadas válidas; histórico da solicitação de origem e de seus retornos, com os dados das OS existentes.')
item('Mesma operação, sem cadastro duplicado','Uma solicitação representa um foco/depósito, conforme a regra informada pelo responsável. A solução reutiliza solicitações e OS, sem novas tabelas ou migração de banco.')
item('O que isso ainda não entrega','PENDENTE - Cruzamento territorial de levantamento aéreo, SINAN, FOCAL/LIRAa e IIP. Não foi criada classificação epidemiológica de risco: não há regra aprovada pela vigilância.')
item('SINAN e LIRAa','ATENDE por confirmação do responsável - SINAN já consta no sistema. Para LIRAa, a informação posterior é que o código do outro desenvolvedor ainda entrará na main. O aceite interno é mantido; publicação e integração precisam de evidência própria.')
p('<b>Prioridade atual:</b> homologar o acompanhamento operacional, receber o LIRAa e definir com a área técnica como compor território, período e indicadores. As demais pendências seguem nas páginas seguintes.')
p('Escopo herdado: páginas físicas 29 a 32 do edital, com continuação do item 5.1.19 na página 33. Nesta emissão não houve consulta ou alteração do banco de produção.','small')
end()
start('01 / SEGURANÇA','Itens atendidos','Classificações anteriores preservadas, com o escopo e os aceites internos explicitados.')
inherited(1)
end()
start('02 / RELATÓRIOS','Consultas, canais e ajuda','As entregas e confirmações desta seção continuam atendidas no escopo registrado.')
inherited(2)
end()
start('03 / VIGILÂNCIA','O que avançou no item 4.8','O mapa passa a acompanhar a operação existente. A integração epidemiológica permanece uma etapa distinta.')
item('4.8, I, III, V e VI | SINAN e LIRAa','ATENDE por confirmação do responsável - Preservados os aceites de tratamento focal/LIRAa, infestação predial, indicadores SINAN e casos no mapa. SINAN existe; LIRAa ainda depende da entrada informada na main e de comprovação da versão publicada. Não houve nova auditoria desses módulos.')
item('4.8, II | Depósitos preferenciais','PARCIAL, com avanço - Solicitação representa um foco/depósito. O histórico usa os vínculos explícitos de retorno e mostra categoria/criadouro, situação e larvas registradas nas OS de piloto/equipe Oceano e equipe UVIS. Não foi criado cadastro paralelo de imóveis, depósitos ou inspeções.')
p('<b>Para fechar:</b> demonstrar uma sequência real de origem, atendimento e retornos; validar com a área técnica a correspondência imóvel/inspeção e as categorias exigidas. Registros antigos sem vínculo não são associados automaticamente por endereço. Edições cadastrais permanecem na auditoria existente.','small',12)
item('4.8, VIII e XIII | Relatórios técnicos e áreas pendentes','PARCIAL, com avanço - Mapa, lista e contadores usam o mesmo recorte operacional; há pendências, atrasos, retornos e indicação de solicitações sem coordenadas. O histórico apresenta os atendimentos vinculados, inclusive fora do período selecionado.')
p('<b>Para fechar:</b> compor dados operacionais, epidemiológicos e entomológicos com critérios territoriais e temporais compatíveis e totais conciliados. Validar a evolução das pendências: a tela mostra a situação atual, não uma série histórica de saldos pendentes em cada data.','small',12)
item('4.8, XII e XIV | Integração espacial e risco','PENDENTE de comprovação integrada - Ainda falta combinar levantamento aéreo, FOCAL/LIRAa, IIP e casos no mesmo resultado territorial por período. O mapa de calor representa densidade de registros; as cores operacionais não são faixas de risco.')
p('<b>Dependência:</b> definir e aprovar indicadores, pesos/faixas, períodos e regra de classificação com a vigilância. Nenhuma pontuação de risco foi inventada.','small')
end()
start('04 / CIDADÃO E CANAIS','Fluxos públicos','Pendências anteriores mantidas por não haver nova evidência de encerramento nesta atualização.')
inherited(4,tail='Próximo desenvolvimento funcional sugerido:')
end()
start('05 / INTEGRAÇÕES','Bases e geoprocessamento','A entrega dos módulos de origem não comprova, sozinha, sua composição territorial e operacional.')
inherited(5,tail='Curvas derivadas de MDS')
p('Curvas derivadas de MDS podem representar vegetação e construções. Preservar origem, parâmetros e evidências de precisão dos produtos. O novo histórico operacional não associa automaticamente ortomosaicos ou curvas aos indicadores de vigilância.','small')
end()
start('06 / COMPROVAÇÃO','Operação e documentação','Os itens abaixo dependem de evidências e responsáveis próprios. Ausência de comprovação nesta revisão não significa ausência de execução.')
rows=[
('4.4.5 | Disponibilidade 24x7','Monitoramento, resposta a incidentes, recuperação e histórico de disponibilidade.'),
('4.9.1 a 4.9.4 | Treinamentos','Plano, público, conteúdo, carga horária, materiais, local e participação.'),
('4.10.2 e 4.10.3 | Serviços de campo','Medição de áreas e comprovação dos serviços. Distinguir área monitorada de área efetivamente tratada.'),
('4.11.1 | Titularidade','Titularidade dos produtos e autorizações de uso/publicação conforme o instrumento contratual.'),
('5.1.1 | Dicionário de dados','PARCIAL - Formalizar campos, significados, regras, domínios, relações e versão de entrega.'),
('5.1.2 a 5.1.6 | Garantias e continuidade','Correções sem ônus, confidencialidade, continuidade, divulgação autorizada e transferência de conhecimento.'),
('5.1.7 a 5.1.10 | Planejamento','Cronograma, acompanhamento, rotinas com TI/SMS e logística dos treinamentos.'),
('5.1.11 a 5.1.14 | Responsabilidades','Substituição/supervisão de pessoal, responsabilidades e representante designado.'),
('5.1.15 a 5.1.19 | Execução contratual','Qualificação, preposto/substituto, comunicações, identificação, prazos e qualidade.')]
for t,b in rows:item(t,b)
p('Os itens 1.2 a 1.4, 2, 3 e 4.1 a 4.3 seguem vinculados à proposta e à execução dos serviços. Guardar evidências da versão publicada, migrações aplicadas, políticas de acesso e operação dos trabalhadores.','small')
end()
start('07 / PRÓXIMOS PASSOS','Plano de conclusão','Priorizar a comprovação do que já existe e a integração entre as fontes, aproveitando os cadastros atuais.')
for t,b in [
('1. Homologar o mapa operacional','Demonstrar uma solicitação real, suas OS e retornos; conferir pendências, atrasados, filtros e isolamento municipal. Validar os critérios de conclusão: OS respondida não comprova eliminação do foco.'),
('2. Receber o LIRAa e conciliar as fontes','Após a integração à main, identificar território, período e unidade de cada indicador. Conciliar totais operacionais, SINAN e FOCAL/LIRAa/IIP sem duplicar registros ou somar recortes incompatíveis.'),
('3. Definir a integração e a regra de risco','Relacionar os produtos aéreos e os indicadores por território/período. Obter da vigilância a regra aprovada antes de classificar risco. Homologar os itens 4.8, XII e XIV.'),
('4. Concluir cidadão, canais e demais bases','Retomar suspeita de adoecimento, ações públicas, compartilhamento, contexto municipal do assistente, canais sociais, legados e documentação. Comprovar syslog ou obter aceite formal aplicável à exigência.')]:item(t,b)
p('<b>Validação da nova entrega:</b> 73 testes de backend e 538 subtestes; 11 testes de frontend. Lista e histórico conferidos em navegador com dados sintéticos. O Google Maps não carregou no ambiente isolado por ausência de chave válida; falta conferir visualmente no ambiente com a chave do site. Não houve publicação nesta etapa.','small',12)
p('<b>Base e limites desta edição:</b> PDF de pendências v4, decisões desta conversa e leitura do código local de Mapas (HEAD 361e5ab com alterações de trabalho). Os demais itens mantêm as avaliações anteriores; não foi refeita auditoria integral. ATENDE por confirmação registra o aceite do responsável, não uma verificação técnica nova. PARCIAL indica abrangência/evidência restante; PENDENTE indica entrega ou comprovação não encerrada.','small',12)
p('Skybox comprova arquivamento, não recepção syslog. O fluxo simples de e-mail prepara a mensagem no aplicativo do usuário; não equivale ao envio direto por SMTP. Essas distinções permanecem registradas sem alterar os aceites internos anteriores.','small')
end()
c.save()
r=PdfReader(str(OUT));assert len(r.pages)==8
print(OUT.resolve())
print('Pages:',len(r.pages))
