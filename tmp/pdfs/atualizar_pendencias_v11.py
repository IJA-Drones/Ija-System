from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from pypdf import PdfReader
from xml.sax.saxutils import escape
import re
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
for name,file in [('Arial','Arial.ttf'),('ArialB','Arial Bold.ttf')]:
 pdfmetrics.registerFont(TTFont(name,'/System/Library/Fonts/Supplemental/'+file))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='ArialB',italic='Arial',boldItalic='ArialB')
OUT=Path('output/pdf/demandas-pendentes-condomar-ija-2026-10-17-v11.pdf')
old=PdfReader('/Users/joaopedro/Downloads/demandas-pendentes-condomar-ija-2026-10-17-v6.pdf')
W,H=595.28,841.89
navy=HexColor('#163e52');teal=HexColor('#078b89');gray=HexColor('#52616c')
c=canvas.Canvas(str(OUT),pagesize=(W,H))
c.setTitle('Situação consolidada CONDOMAR - IJA System - Atualização 11')
c.setAuthor('Time de desenvolvimento da IJA DRONES')
styles={
 'body':ParagraphStyle('body',fontName='Arial',fontSize=10,leading=14,textColor=navy,spaceAfter=8),
 'small':ParagraphStyle('small',fontName='Arial',fontSize=8.5,leading=11.5,textColor=gray),
 'item':ParagraphStyle('item',fontName='ArialB',fontSize=11,leading=14,textColor=navy),
 'intro':ParagraphStyle('intro',fontName='Arial',fontSize=11,leading=15,textColor=gray),
 'title':ParagraphStyle('title',fontName='ArialB',fontSize=24,leading=28,textColor=navy),
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
 c.setFillColor(gray);c.setFont('ArialB',8);c.drawString(44,H-35,'IJA SYSTEM / CONDOMAR')
 c.setFont('Arial',8);c.drawRightString(W-44,H-35,'17/10/2026 | Atualização 11')
 y=H-69
 p(kicker,'small',10);p(title,'title',12)
 if intro: p(intro,'intro',19)

def end():
 c.setStrokeColor(HexColor('#dbe4e7'));c.line(44,73,W-44,73)
 c.setFillColor(navy);c.setFont('ArialB',12);c.drawCentredString(W/2,54,'IJA DRONES')
 c.setFont('Arial',8);c.drawCentredString(W/2,40,'Documento elaborado pelo time de desenvolvimento da IJA DRONES')
 c.setFillColor(gray);c.setFont('Arial',8);c.drawRightString(W-44,24,str(page))
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
  overrides={
   '4.6.1 | Integrações SMS/MS e transição':'ATENDE por confirmação do responsável - Integrações SMS/MS e continuidade durante a transição consideradas atendidas. Preservados os aceites de SINAN e LIRAa. Esta revisão documental não reexecutou integrações nem validou novamente a publicação do LIRAa.',
   '4.7.1, I | Extração de legados':'ATENDE por confirmação do responsável - Extração das origens legadas e sua rastreabilidade consideradas atendidas no acompanhamento interno. Classificação atualizada conforme anotação, sem nova execução de extratores ou conferência de arquivos nesta edição.',
   '4.7.1, II | Limpeza e reconciliação':'ATENDE por confirmação do responsável - Limpeza, correção, enriquecimento, deduplicação, reconciliação e reprocessamento considerados atendidos. Esta edição registra o aceite informado, sem nova auditoria de cargas.',
   '5.1.1 | Dicionário de dados':'ATENDE por confirmação do responsável - Dicionário de dados considerado atendido, abrangendo campos, significados, regras, domínios e relações. Classificação atualizada conforme anotação, sem nova revisão do documento técnico nesta edição.'
  }
  body=overrides.get(title,body)
  for marker in ('Escopo registrado:', 'Registro do aceite:', 'Escopo técnico documentado:'):
   if marker in body:
    body,note=body.split(marker,1)
    item(title,body.strip());p('<b>'+marker+'</b> '+escape(note),'small',12)
    break
  else:item(title,body)

start('ACOMPANHAMENTO INTERNO','Situação consolidada','')
item('4.8, VII | Suspeita de adoecimento','ATENDE no fluxo implementado - Formulário público por prefeitura, protocolo, caixa da COVISA, notificações internas, ciência, encaminhamento à UVIS, acompanhamento, conclusão, histórico e relatório PDF.')
item('Contatos das prefeituras e Azul','ATENDE por confirmação do responsável - Cadastro municipal de telefone, WhatsApp, Instagram, e-mail, horários e serviços. Publicação no portal sem login e consulta da mesma base pela Azul. COVISA edita sua prefeitura; DEV administra; DIRETOR consulta.')
item('Classificações atualizadas','ATENDE por confirmação do responsável - Ações disponíveis à sociedade (4.8, IV), integrações SMS/MS e transição (4.6.1), extração de legados (4.7.1, I), limpeza e reconciliação (4.7.1, II) e dicionário de dados (5.1.1). Mantidos os aceites de compartilhamento, assistente local e chat social.')
item('Produção: banco preparado','Migração d82b46fa910c aplicada e verificada em produção, com as tabelas de contatos públicos e histórico. O upgrade não comprova, sozinho, a publicação do código. Os contatos demonstrativos de São Paulo ficaram somente no teste.')
p('<b>Critério desta atualização:</b> revisão documental de classificações e apresentação, sem nova execução de testes ou alteração do sistema.')
p('Escopo herdado: páginas físicas 29 a 32 do edital e continuação do item 5.1.19 na página 33. ATENDE por confirmação registra o aceite informado pelo responsável, preservando o escopo técnico já descrito.','small')
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

start('04 / CIDADÃO E CANAIS','Fluxos públicos atualizados','Suspeita de adoecimento entregue. Mantidos os aceites anteriores e registrado o atendimento do item 4.8, IV por confirmação do responsável.')
item('4.8, IX e X | Portal mobile e denúncias','ATENDE - Mantidos portal, informação, formulário com localização/mídia, chat e triagem de focos. Agora há também acesso ao diretório de contatos das prefeituras.')
item('4.8, IV | Ações disponíveis à sociedade','ATENDE por confirmação do responsável - Divulgação de ações e resultados à sociedade considerada atendida no acompanhamento interno. Prevenção, notícias, boletim, relatos e contatos estão disponíveis. Esta edição registra a confirmação, sem nova auditoria das publicações por município e período.')
item('4.8, VII | Relato de suspeita de adoecimento','ATENDE no fluxo implementado - Cidadão escolhe a prefeitura e recebe protocolo. COVISA recebe notificação interna, registra ciência e encaminha à UVIS. Há acompanhamento, conclusão, histórico e relatório PDF com controle municipal de acesso. Relato não equivale a diagnóstico nem cria caso confirmado no SINAN.')
item('4.8, XI | Compartilhamento em redes sociais','ATENDE por confirmação do responsável - Compartilhamento em redes sociais considerado atendido no acompanhamento interno. Os canais municipais estão publicados no portal. Esta edição registra o aceite informado, sem nova demonstração técnica do compartilhamento de ações.')
item('4.8, XV | Assistente com contexto local','ATENDE por confirmação do responsável - A Azul consulta os contatos, horários e serviços publicados pela prefeitura; houve resposta real conferida no teste com dados de São Paulo. A classificação registra o aceite informado, sem nova verificação da cobertura territorial nesta edição.')
item('4.8, XVI | Chat social e atendimento contínuo','ATENDE por confirmação do responsável - Chat social e atendimento contínuo considerados atendidos no acompanhamento interno. O fluxo demonstrado usa diretório, chat web e abertura externa de WhatsApp/Instagram. O aceite não representa nova comprovação de conectores sociais nesta edição.')
end()

start('05 / INTEGRAÇÕES','Bases e geoprocessamento','Itens 4.6.1 e 4.7.1, I e II atualizados para ATENDE por confirmação do responsável. Demais aceites preservados.')
inherited(5,tail='Curvas derivadas de MDS')
p('Curvas derivadas de MDS podem representar vegetação e construções. Preservar origem, parâmetros e evidências de precisão. A situação de publicação do LIRAa não foi revalidada nesta edição; mantém-se o aceite interno anterior.','small')
end()

start('06 / REGISTROS','Operação e documentação','Referências operacionais e contratuais preservadas. Dicionário de dados atualizado para ATENDE por confirmação do responsável.')
inherited(6,tail='Os itens 1.2 a 1.4')
p('Os itens 1.2 a 1.4, 2, 3 e 4.1 a 4.3 seguem vinculados à proposta e à execução dos serviços. Este quadro reúne referências de acompanhamento e não constitui nova verificação documental ou operacional.','small')
end()

c.save()
r=PdfReader(str(OUT));assert len(r.pages)==7
print(OUT.resolve())
