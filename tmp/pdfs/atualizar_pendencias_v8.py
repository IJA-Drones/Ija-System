from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from pypdf import PdfReader
from xml.sax.saxutils import escape
import re
from pathlib import Path
OUT=Path('output/pdf/demandas-pendentes-condomar-ija-2026-10-17-v8.pdf')
old=PdfReader('/Users/joaopedro/Downloads/demandas-pendentes-condomar-ija-2026-10-17-v6.pdf')
W,H=595.28,841.89
navy=HexColor('#163e52');teal=HexColor('#078b89');gray=HexColor('#52616c')
c=canvas.Canvas(str(OUT),pagesize=(W,H))
c.setTitle('Demandas pendentes CONDOMAR - IJA System - Atualização 8')
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
 text=re.sub(r'\b(ATENDE|PARCIAL|PENDENTE|IMPLEMENTADO LOCALMENTE)\b',lambda m: '<font color="'+{'ATENDE':'#147545','PARCIAL':'#9b6200','PENDENTE':'#bc303a','IMPLEMENTADO LOCALMENTE':'#176b98'}[m.group(0)]+'"><b>'+m.group(0)+'</b></font>',text)
 obj=Paragraph(text,styles[style]); _,h=obj.wrap(W-88,900)
 if y-h<94: raise RuntimeError(f'Overflow page {page}: {text[:70]} at {y-h}')
 obj.drawOn(c,44,y-h); y-=h+gap

def start(kicker,title,intro):
 global y,page
 page+=1
 c.setFillColor(teal);c.rect(0,H-9,W,9,fill=1,stroke=0)
 c.setFillColor(gray);c.setFont('Helvetica-Bold',8);c.drawString(44,H-35,'IJA SYSTEM / CONDOMAR')
 c.setFont('Helvetica',8);c.drawRightString(W-44,H-35,'17/10/2026 | Atualização 8')
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
 text=old.pages[index].extract_text().split('\nIJA DRONES')[0]
 parts=re.split(r'\n(?=(?:4|5)\.\d)',text)
 for block in parts[1:]:
  lines=block.strip().splitlines();title=lines[0];body=' '.join(lines[1:])
  if tail and tail in body:body=body.split(tail)[0].strip()
  for marker in ('Escopo registrado:', 'Registro do aceite:', 'Escopo técnico documentado:'):
   if marker in body:
    body,note=body.split(marker,1)
    item(title,body.strip());p('<b>'+marker+'</b> '+escape(note),'small',12)
    break
  else:item(title,body)

start('ACOMPANHAMENTO INTERNO','Demandas pendentes','CONDOMAR / IJA SYSTEM - situação após os novos fluxos do cidadão e contatos municipais.')
p('Esta versão substitui a atualização 7. Os itens 4.8, XI, XV e XVI passam a ATENDE por confirmação do responsável. Preserva as entregas e os aceites anteriores; não constitui nova auditoria integral nem aceite formal do contratante.')
item('4.8, VII | Suspeita de adoecimento','ATENDE no fluxo implementado - Formulário público por prefeitura, protocolo, caixa da COVISA, notificações internas, ciência, encaminhamento à UVIS, acompanhamento, conclusão, histórico e relatório PDF.')
item('Contatos das prefeituras e Azul','IMPLEMENTADO LOCALMENTE - Cadastro municipal de telefone, WhatsApp, Instagram, e-mail, horários e serviços. Publicação no portal sem login e consulta da mesma base pela Azul. COVISA edita sua prefeitura; DEV administra; DIRETOR consulta.')
item('Classificações atualizadas','ATENDE por confirmação do responsável - Compartilhamento em redes sociais (4.8, XI), assistente com contexto local (4.8, XV) e chat social e atendimento contínuo (4.8, XVI). Esses itens saem da lista de desenvolvimento pendente desta edição.')
item('O que permanece em desenvolvimento','PARCIAL - Publicação de ações e resultados (4.8, IV), demais integrações/legados e dicionário de dados. Permanecem também as comprovações operacionais e contratuais registradas neste documento.')
item('Produção: banco preparado','Migração d82b46fa910c aplicada e verificada em produção, com as tabelas de contatos públicos e histórico. O upgrade não comprova, sozinho, a publicação do código. Os contatos demonstrativos de São Paulo ficaram somente no teste.')
p('<b>Próxima prioridade sugerida:</b> consolidar a publicação de ações realizadas e resultados autorizados por município e período (4.8, IV).')
p('Escopo herdado: páginas físicas 29 a 32 do edital e continuação do item 5.1.19 na página 33. Legenda: ATENDE = atendimento no escopo registrado; PARCIAL = cobertura restante; PENDENTE = entrega ou comprovação não encerrada.','small')
end()

start('01 / SEGURANÇA','Itens atendidos','Classificações anteriores preservadas, com o escopo e os aceites internos explicitados.')
inherited(1)
end()
start('02 / RELATÓRIOS','Consultas, canais e ajuda','As entregas e confirmações desta seção continuam atendidas no escopo registrado.')
inherited(2)
end()
start('03 / VIGILÂNCIA','Aceites do item 4.8 preservados','Mantidos os aceites registrados na versão 6. As observações abaixo descrevem o escopo daquela avaliação.')
inherited(3)
end()

start('04 / CIDADÃO E CANAIS','Fluxos públicos atualizados','Suspeita de adoecimento entregue. Itens 4.8, XI, XV e XVI reclassificados conforme confirmação do responsável.')
item('4.8, IX e X | Portal mobile e denúncias','ATENDE - Mantidos portal, informação, formulário com localização/mídia, chat e triagem de focos. Agora há também acesso ao diretório de contatos das prefeituras.')
item('4.8, IV | Ações disponíveis à sociedade','PARCIAL - Prevenção, notícias, boletim, relatos e contatos estão disponíveis. Falta consolidar a publicação das ações realizadas e dos resultados autorizados, por município e período.')
item('4.8, VII | Relato de suspeita de adoecimento','ATENDE no fluxo implementado - Cidadão escolhe a prefeitura e recebe protocolo. COVISA recebe notificação interna, registra ciência e encaminha à UVIS. Há acompanhamento, conclusão, histórico e relatório PDF com controle municipal de acesso. Relato não equivale a diagnóstico nem cria caso confirmado no SINAN.')
item('4.8, XI | Compartilhamento em redes sociais','ATENDE por confirmação do responsável - Compartilhamento em redes sociais considerado atendido no acompanhamento interno. Os canais municipais estão publicados no portal. Esta edição registra o aceite informado, sem nova demonstração técnica do compartilhamento de ações.')
item('4.8, XV | Assistente com contexto local','ATENDE por confirmação do responsável - A Azul consulta os contatos, horários e serviços publicados pela prefeitura; houve resposta real conferida no teste com dados de São Paulo. A classificação registra o aceite informado, sem nova verificação da cobertura territorial nesta edição.')
item('4.8, XVI | Chat social e atendimento contínuo','ATENDE por confirmação do responsável - Chat social e atendimento contínuo considerados atendidos no acompanhamento interno. O fluxo demonstrado usa diretório, chat web e abertura externa de WhatsApp/Instagram. O aceite não representa nova comprovação de conectores sociais nesta edição.')
end()

start('05 / INTEGRAÇÕES','Bases e geoprocessamento','Avaliações herdadas da versão 6. A entrega de contatos municipais não modifica estes escopos.')
inherited(5,tail='Curvas derivadas de MDS')
p('Curvas derivadas de MDS podem representar vegetação e construções. Preservar origem, parâmetros e evidências de precisão. A situação de publicação do LIRAa não foi revalidada nesta edição; mantém-se o aceite interno anterior.','small')
end()

start('06 / COMPROVAÇÃO','Operação e documentação','Pendências de evidência preservadas. Ausência de comprovação nesta revisão não significa ausência de execução.')
inherited(6,tail='Os itens 1.2 a 1.4')
p('Os itens 1.2 a 1.4, 2, 3 e 4.1 a 4.3 seguem vinculados à proposta e à execução dos serviços. Reunir evidências da versão publicada, migrações, acesso, disponibilidade e operação dos trabalhadores.','small')
end()

start('07 / PRÓXIMOS PASSOS','O que falta agora','Foco nas pendências restantes e na preservação das evidências dos itens aceitos.')
for title,body in [
 ('1. Publicação de ações e resultados | 4.8, IV','Consolidar a divulgação das ações realizadas e dos resultados autorizados por município e período. Reutilizar os dados existentes e evitar exposição de cidadãos.'),
 ('2. Finalizar integrações e legados','Concluir os escopos restantes de 4.6.1 e 4.7.1, I e II, com rastreabilidade, reconciliação e continuidade. Preservar os aceites já registrados para os demais itens.'),
 ('3. Organizar documentação e comprovações','Concluir o dicionário de dados (5.1.1) e reunir registros de treinamento, disponibilidade, serviços de campo e execução contratual descritos na página 7.'),
 ('4. Preservar as entregas aceitas','Guardar versões publicadas, demonstrações e registros dos itens 4.8, XI, XV e XVI, agora ATENDE por confirmação do responsável. Conferir os fluxos no site após a implantação.')]:item(title,body)
p('<b>Evidências preservadas:</b> 144 testes de backend, 473 subtestes e 10 testes JavaScript aprovados na validação registrada nesta conversa. No PostgreSQL de teste foram conferidos gravação, publicação/retirada, histórico e conflito de versão. Portal anônimo e resposta real da Azul foram demonstrados. Guias ilustrados de suspeita de adoecimento e contatos municipais estão disponíveis.','small',12)
p('<b>Implantação:</b> produção atualizada à revisão d82b46fa910c, com estrutura e consulta validadas. Confirmar a versão do código publicada e executar a conferência final no site. Nenhum dado demonstrativo foi copiado para produção.','small',12)
p('<b>Base desta edição:</b> versão 7 e confirmação do responsável para os itens 4.8, XI, XV e XVI. Atualização documental de status, resumo e plano; não houve nova auditoria integral nem repetição de testes. Os demais aceites, inclusive SINAN/LIRAa e integração espacial, permanecem preservados.','small',12)
p('Mantidas as distinções técnicas já documentadas: Skybox comprova arquivamento; e-mail assistido não implica SMTP ativo; o fluxo social demonstrado abre canais externos. ATENDE por confirmação registra o aceite informado, sem declarar validação técnica adicional.','small')
end()
c.save()
r=PdfReader(str(OUT));assert len(r.pages)==8
print(OUT.resolve())
