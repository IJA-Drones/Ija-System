"""Build the report using the guides' shared identity and real UI captures.

Run from the repository with .venv/bin/python. Captures are temporary inputs;
only this source, its JSON evidence and the final PDF need to remain.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from scripts.training_pdf_style import (
    WIDTH as W, HEIGHT as H, MARGIN as M, CONTENT as CW, INK, ACCENT,
    MUTED, SOFT, LINE, register_fonts, text, paragraph, panel,
)

HERE = Path(__file__).with_suffix('.json')
EVIDENCE = json.loads(HERE.read_text())
TOTAL = 5


def chrome(c, page):
    c.setFillColor(ACCENT); c.rect(0, H-8, W, 8, fill=1, stroke=0)
    text(c, 'OCEANO AZUL / CENTRAL DE TREINAMENTOS', M, H-27, 350, 7.7, 11, True, ACCENT)
    c.setFillColor(MUTED); c.setFont('Training', 8); c.drawRightString(W-M, H-35, '23 NOV 2026')
    c.setStrokeColor(LINE); c.line(M, 52, W-M, 52)
    text(c, 'IJA DRONES  |  OCEANO AZUL', M, 40, 350, 8, 11, True)
    text(c, 'Relatório de melhorias do guia de treinamento', M, 25, 400, 7.3, 10, color=MUTED)
    c.setFont('Training', 8); c.drawRightString(W-M, 32, f'{page} / {TOTAL}')


def heading(c, number, title, subtitle):
    y = text(c, number, M, H-65, size=8.5, leading=12, bold=True, color=ACCENT)
    y = text(c, title, M, y-12, size=24, leading=30, bold=True)
    y = text(c, subtitle, M, y-10, size=10, leading=15, color=MUTED)
    return y-19


def body(c, value, y, x=M, width=CW, size=9.5, color=INK):
    return text(c, value, x, y, width, size, 14, color=color)


def section(c, title, y, x=M, width=CW):
    return text(c, title, x, y, width, 12, 16, True, ACCENT)-8


def figure(c, path, y, caption, width=CW, max_h=500, x=M):
    iw, ih = Image.open(path).size
    scale = min(width/iw, max_h/ih)
    dw, dh = iw*scale, ih*scale
    left = x+(width-dw)/2
    c.saveState()
    border = c.beginPath(); border.roundRect(left, y-dh, dw, dh, 7)
    c.clipPath(border, stroke=0)
    c.drawImage(ImageReader(str(path)), left, y-dh, dw, dh, mask='auto')
    c.restoreState()
    c.setStrokeColor(LINE); c.setLineWidth(.7); c.roundRect(left, y-dh, dw, dh, 7, fill=0, stroke=1)
    return text(c, caption, x, y-dh-8, width, 8, 11, color=MUTED)-15


def table(c, rows, y, widths, header):
    c.setFillColor(INK); c.roundRect(M, y-28, sum(widths), 28, 6, fill=1, stroke=0)
    x = M
    for value, width in zip(header, widths):
        text(c, value, x+10, y-8, width-20, 8.5, 12, True, colors.white); x += width
    y -= 28
    for index, row in enumerate(rows):
        parts=[paragraph(value, width-20, 8.6, 12) for value,width in zip(row,widths)]
        height=max(p[1] for p in parts)+18
        if index%2==0:
            c.setFillColor(SOFT); c.rect(M,y-height,sum(widths),height,fill=1,stroke=0)
        x=M
        for (p, ph), width in zip(parts,widths): p.drawOn(c,x+10,y-9-ph); x+=width
        y-=height
        c.setStrokeColor(LINE); c.line(M,y,M+sum(widths),y)
    return y-16


def end(c, y):
    if y<64: raise RuntimeError(f'Content overlaps footer: {y:.1f}')
    c.showPage()


def build(captures, output):
    register_fonts(); output.parent.mkdir(parents=True, exist_ok=True)
    c=canvas.Canvas(str(output), pagesize=(W,H), pageCompression=1)
    c.setTitle('Melhorias no guia de treinamento - Oceano Azul')
    c.setAuthor('Relatório técnico do projeto')
    c.setSubject('Implementação local, evidências visuais e limites da validação em 23/11/2026')
    c.setCreator('Gerado a partir do código, dos testes e de capturas locais')

    chrome(c,1)
    y=heading(c,'RELATÓRIO DE MELHORIAS','Guia prático\nde treinamentos','Aprender na prática com a Azul. Organização por módulos, orientação nas telas reais e acesso conforme o perfil.')
    y=body(c,'Este relatório registra o que foi implementado e o que foi comprovado na revisão de 23/11/2026. A geração e a narração com serviços reais ainda aguardam validação.',y)-14
    y=figure(c,captures/'01-modulos.png',y,'Figura 1. Modal atual com a Azul, busca, áreas e cartões por módulo. Conta fictícia com acesso às áreas exibidas. Captura real da interface em ambiente local.',max_h=350)
    y=panel(c,'Estado da entrega','Implementação local disponível. Prints capturados com contas fictícias; respostas de IA simuladas somente para demonstrar a interface.',M,y)
    end(c,y)

    chrome(c,2)
    y=heading(c,'01 / ORGANIZAÇÃO E ACESSO','Do módulo à função','O usuário escolhe primeiro o assunto e depois a atividade que deseja aprender. O catálogo segue a navegação e as permissões do sistema.')
    y=figure(c,captures/'03-funcoes.png',y,'Figura 2. Recorte das funções do módulo Solicitações. A escolha de Nova solicitação abre a tela correspondente e inicia o guia.',max_h=190)
    y=section(c,'Conteúdo adequado ao perfil',y)
    y=figure(c,captures/'02-perfil-uvis.png',y,'Figura 3. Recorte do catálogo de uma conta UVIS fictícia. A conferência do catálogo confirmou a ausência de módulos Agro e Financeiro para esse acesso.',max_h=190)
    y=table(c,[
        ('Escolha por módulo','Cartões, busca e filtros por área organizam os tutoriais disponíveis.'),
        ('Escolha por função','As opções correspondem a funções autorizadas da navegação, como consultar ou cadastrar.'),
        ('Permissões','Acesso à Azul e à função são verificados novamente em cada chamada de geração.'),
        ('Operação e piloto','Tutoriais específicos permanecem sujeitos às permissões da operação; não são liberados automaticamente para UVIS.'),
    ],y,[135,CW-135],['Melhoria','Comportamento implementado'])
    end(c,y)

    chrome(c,3)
    y=heading(c,'02 / ORIENTAÇÃO CONTEXTUAL','A Azul acompanha a tela real','O guia destaca controles da página e oferece navegação por etapas, esclarecimento de dúvidas e opção de solicitar narração.')
    y=figure(c,captures/'04-tutorial-tela-real.png',y,'Figura 4. Recorte do formulário real de solicitação com orientação sobre Tipo de visita. O texto da IA nesta captura foi simulado; não houve envio de solicitação nem reprodução de voz.',max_h=467)
    y=panel(c,'Orientação sem confirmação automática','A pessoa pode voltar, avançar, ver as etapas, fazer perguntas e atualizar o guia. Salvar, enviar ou aprovar continua dependendo da confirmação do usuário e das validações do sistema.',M,y)
    end(c,y)

    chrome(c,4)
    y=heading(c,'03 / EXPERIÊNCIA E PROTEÇÃO','Uso no celular e controle da IA','A apresentação acompanha a largura da tela. A geração de novas respostas ocorre mediante uma escolha ou solicitação do usuário.')
    image_top=y
    image_bottom=figure(c,captures/'05-mobile.png',image_top,'Figura 5. Modal no celular, com cartões acessíveis por rolagem e botão de fechar.',width=200,max_h=443,x=M)
    x=M+220; width=CW-220; r=image_top
    r=section(c,'Navegação conferida',r,x,width)
    r=body(c,'Modal, busca, seleção de módulo e função, abertura da página e retorno à escolha de tutorial.',r,x,width)-17
    r=section(c,'Dúvidas durante o guia',r,x,width)
    r=body(c,'Perguntar à Azul mantém a orientação na função selecionada. Atualizar etapas solicita um novo plano quando o formulário mudar.',r,x,width)-17
    r=section(c,'Voz opcional',r,x,width)
    r=body(c,'Ouvir etapa e Ouvir resposta reutilizam a integração e a voz configuradas da Azul. O áudio real ainda precisa ser validado.',r,x,width)-17
    r=section(c,'Uso controlado',r,x,width)
    r=body(c,'Abrir e pesquisar os cartões não consome IA. O início após a navegação usa um marcador de sessão consumido uma vez, evitando nova geração silenciosa ao recarregar.',r,x,width)-17
    r=section(c,'Dados do formulário',r,x,width)
    r=body(c,'O retrato enviado ao guia reúne rótulos e orientações dos controles. Valores digitados, senhas, anexos e linhas de tabela não entram nesse retrato.',r,x,width)
    y=min(image_bottom,r)-10
    y=panel(c,'Respostas e ações','A resposta estruturada é validada e só pode referenciar os IDs de controles recebidos. O tutorial não dispõe de ferramentas de consulta ou alteração de registros.',M,y)
    end(c,y)

    chrome(c,5)
    y=heading(c,'04 / VERIFICAÇÃO E PENDÊNCIAS','Situação comprovada','Conferência executada em 23/11/2026. Testes de servidor com SQLite descartável; interface com respostas simuladas da IA e sem consumo de créditos do provedor.')
    y=table(c,[
        ('Python','39 aprovados; 1 falha','A falha é uma divergência no inventário de templates.'),
        ('JavaScript','17 aprovados','Controles de acesso, ajuda, voz e cache nas suítes selecionadas.'),
        ('Capturas','5 prints reais','Contas fictícias; texto de IA simulado; nenhuma gravação operacional.'),
    ],y,[82,145,CW-227],['Verificação','Resultado atual','Escopo'])
    y=section(c,'Pendência documental identificada',y)
    y=body(c,'O inventário salvo contém 198 templates; a varredura atual identifica 200. As duas entradas adicionais são agro_parceiro.html e agro_parceiros.html. O teste acusa essa diferença; o inventário não foi alterado nesta emissão do relatório.',y)-15
    y=panel(c,'O que a contagem significa','O inventário mede templates integrados ao componente e lista 23 identificadores de perfil. Ele não comprova 200 tutoriais individuais revisados nem todas as combinações de tela e usuário.',M,y)-17
    y=section(c,'Validações ainda necessárias',y)
    y=body(c,'1. Atualizar o inventário para as duas novas telas do Agro.\n2. Testar os tutoriais com o provedor real e conferir clareza e aderência das etapas.\n3. Validar a narração real e as configurações de voz da Azul.\n4. Realizar o aceite dos fluxos pelos usuários responsáveis de cada área.',y)-17
    y=section(c,'Materiais de apoio',y)
    y=body(c,'A Central mantém PDFs por módulo e a Central de vídeos com reprodução externa pelo Drive. Esses materiais complementam o guia prático e seguem suas políticas próprias de acesso.',y)-16
    y=text(c,'Fontes conferidas: documentação de treinamentos; practical.py; screen-guide.js; testes do guia prático, permissões, ajuda, voz e cache. As capturas usam os templates atuais do projeto local.',M,y,CW,7.7,11,color=MUTED)
    end(c,y)
    c.save()
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures',type=Path,default=Path('/tmp/ija-training-report'))
    parser.add_argument('--output',type=Path,default=ROOT/'output/pdf/relatorio-melhorias-guia-treinamento.pdf')
    args=parser.parse_args(); print(build(args.captures,args.output))
