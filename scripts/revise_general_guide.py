"""Mantém os capítulos gerais e as telas reais; substitui índice e trechos retirados."""

import argparse
from io import BytesIO
from pathlib import Path
import shutil

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from training_pdf_style import register_fonts

ROOT = Path(__file__).resolve().parents[1]
W, H = 595.2756, 841.8898
INK, ACCENT, MUTED = map(colors.HexColor, ("#12344a", "#008ea4", "#52697f"))
MARGIN = 42
CONTENTS = (
    ("Consultas personalizadas", 3), ("Saídas, impressão e e-mail", 6),
    ("Ajuda em português", 8), ("Perfis e prefeituras", 9),
    ("Documentos da prefeitura", 10), ("Edição protegida", 11), ("Auditoria", 13),
    ("Sessões, senhas e integridade", 14), ("Relatórios operacionais e retornos", 17),
    ("Mapas e histórico de focos", 18), ("Cidadão: boletim, alertas e mobile", 19),
    ("Contatos municipais", 20), ("AZUL: assistente pública", 21),
    ("Ortomosaicos e curvas", 23), ("Saúde da aplicação e continuidade", 25),
)
REPLACEMENTS = {
    10: ("Perfis de acesso e prefeitura", (
        ("Onde acessar", "Use Usuário para consultar os cadastros permitidos ao seu perfil. DEV e Gestor de TI encontram a configuração de telas e ações na Central de TI."),
        ("Configurar um perfil", "Selecione o perfil, escolha a área e confira os módulos disponíveis. Marque apenas as ações necessárias, como Consultar, Cadastrar ou Editar. Salve e confira o acesso resultante com uma conta autorizada daquele perfil."),
        ("Vínculo com a prefeitura", "O perfil e os vínculos da conta determinam quais registros ela pode consultar. Uma permissão de tela não elimina os filtros de prefeitura, unidade ou responsabilidade aplicáveis ao registro."),
        ("Permissões e menus", "Os menus acompanham a configuração salva e as regras fixas do produto. Um módulo retirado da interface não volta a aparecer apenas porque existia uma permissão anterior para ele."),
        ("Conferir o resultado", "Revise consulta, criação, edição, exportação e exclusão separadamente. A configuração de um perfil não deve ampliar o acesso aos dados de outras prefeituras. Preserve os vínculos e o histórico dos usuários existentes."),
    )),
    18: ("Relatórios operacionais e retornos", (
        ("Onde acessar", "Menu Relatórios: /relatorios."),
        ("Como usar", "Escolha Solicitações, Ordens de serviço, Coleta de imagens ou Retornos e locais de visita. Informe os filtros de período, status, unidade e equipe disponíveis para seu perfil. Confira o recorte antes de exportar."),
        ("Leitura do resultado", "Os relatórios de solicitações e OS usam os registros operacionais existentes. O relatório de imagens reúne os anexos autorizados. Os retornos usam os vínculos explícitos entre a solicitação de origem e o atendimento seguinte."),
        ("PDF e Excel", "Use as saídas oferecidas na própria tela. O acesso aos registros e às exportações segue as permissões e os vínculos do usuário. Uma contagem de registros não comprova execução do atendimento: confira o status e a OS."),
        ("Atalhos relacionados", "Logs de voo e importação de rotas KML continuam disponíveis conforme o perfil. A ausência de um menu pode indicar restrição de acesso; consulte o responsável pela configuração da sua conta."),
    )),
    19: ("Mapas e histórico de focos", (
        ("Onde acessar", "Menu Mapas: /mapa-relatorio. A consulta de endereço fica em /consultar_endereco_geolocalizacao."),
        ("Como usar", "Escolha unidade, período, tipo de foco e situação do atendimento. Alterne entre as visualizações operacionais e consulte os contadores, a lista de registros e a indicação de itens sem coordenadas."),
        ("Histórico do foco", "Selecione um ponto ou use Histórico na tabela. A sequência acompanha os vínculos explícitos de origem e retorno, respeitando o acesso do usuário. Registros antigos sem vínculo não são associados apenas pela semelhança do endereço."),
        ("Como interpretar", "O mapa de calor representa concentração de registros. As cores e categorias operacionais não são uma classificação epidemiológica. A observação de larvas também não confirma diagnóstico de doença."),
        ("Coordenadas e recorte", "Mapa, tabela e contadores usam o mesmo recorte. Os itens sem coordenadas continuam contabilizados. Confira os filtros e a disponibilidade do mapa de fundo antes de interpretar a distribuição dos pontos."),
    )),
    43: ("AZUL: assistente do portal", (
        ("Onde acessar", "Abra o Portal do Cidadão ou o aplicativo mobile e toque na AZUL. O Guia prático reúne orientações e tutoriais dos recursos públicos disponíveis."),
        ("Perguntas e contatos", "Informe o município ao perguntar por contatos, horários e serviços. A assistente usa os contatos publicados pela prefeitura e as fontes oficiais disponíveis para orientações de prevenção e uso do portal."),
        ("Registrar relato", "Use Registrar relato para abrir o formulário guiado. Confira ocorrência, endereço, identificação, detalhes e consentimento. O protocolo só é apresentado após o sistema confirmar o envio; uma mensagem na conversa não registra uma ocorrência."),
        ("Texto e voz", "Escreva a dúvida ou use os controles de áudio quando disponíveis. A reprodução e a conversa por voz começam quando o usuário solicita. Preencha os dados pessoais nos campos do formulário."),
        ("Alcance do atendimento", "A AZUL pública não confirma diagnósticos, não modifica ordens de serviço pela conversa e não promete prazos de atendimento. Os contatos publicados e o atalho do Telegram permanecem acessíveis no portal."),
    )),
    45: ("Ortomosaicos e curvas de nível", (
        ("Onde acessar", "Abra /ortomosaicos. O módulo atende DEV, DIRETOR e a conta dedicada de ortomosaico conforme as regras fixas de acesso. A conta dedicada trabalha apenas com sua prefeitura ativa."),
        ("Consultar a biblioteca", "Escolha o município autorizado e um levantamento. Use camadas, mapa de fundo, zoom, enquadramento, tela cheia e opacidade para examinar o material."),
        ("Enviar levantamento", "Escolha Ortomosaico RGB ou DEM / curvas de nível. Informe nome, prefeitura e arquivo GeoTIFF. Para o DEM, confira o intervalo entre curvas, a resolução da grade e a unidade das elevações."),
        ("Leitura e exportação", "Depois do processamento, consulte as cotas, ajuste a aparência e use as exportações disponíveis. A estimativa de volume de água continua como ferramenta de medição do módulo."),
        ("Cuidados de interpretação", "A resolução da grade não equivale à precisão altimétrica. Um modelo de superfície pode incluir árvores e construções; isso não o transforma em modelo de terreno limpo. Confira origem, unidade e características do arquivo antes de usar a medição."),
    )),
}
PUBLIC_PAGE = ("Cidadão: boletim, alertas e mobile", (
    ("Portal e relatos", "Acesse /portal-cidadao, escolha a prefeitura responsável e registre a ocorrência com endereço, identificação, detalhes e anexos. Revise o formulário e confirme o consentimento. Guarde o protocolo após a confirmação do sistema."),
    ("Boletim e fontes públicas", "Consulte os indicadores do InfoDengue e as notícias oficiais no painel. Em Ver relatório completo, selecione município, doença e ano. Confira fonte e período; estimativas e notificações não devem ser tratadas como casos confirmados."),
    ("Alertas no celular e Telegram", "Use Receber alertas no celular e autorize as notificações quando solicitado. A disponibilidade depende da configuração do serviço e do aparelho. O atalho do Telegram permanece junto dos recursos públicos."),
    ("Aplicativo mobile", "A página /app reúne as opções de instalação. O aplicativo web instalado abre em /m/ e oferece relatos, alertas, AZUL e consulta ao boletim público."),
    ("Envio offline", "Os relatos salvos sem conexão ficam pendentes no aparelho e são reenviados quando a conexão volta. Um item pendente ainda não representa envio confirmado. Consulte Enviados / pendentes para acompanhar o resultado."),
))


def paragraph(c, text, y, size=10, leading=15, bold=False, color=INK):
    style = ParagraphStyle("guide", fontName="Training-Bold" if bold else "Training", fontSize=size,
                           leading=leading, textColor=color, splitLongWords=False)
    flow = Paragraph(text, style)
    _width, height = flow.wrap(W - 2 * MARGIN, H)
    flow.drawOn(c, MARGIN, y - height)
    return y - height


def generated_page(title, sections=(), cover=False, toc=False, toc_rects=None):
    output = BytesIO()
    c = canvas.Canvas(output, pagesize=(W, H))
    y = H - (145 if cover else 92)
    if cover:
        y = paragraph(c, "IJA SYSTEM / GUIA DE USO", y, 10, 15, True, ACCENT) - 20
    y = paragraph(c, title, y, 31 if cover else 22, 39 if cover else 29, True) - 19
    if cover:
        y = paragraph(c, "Acesso, operação e recursos disponíveis", y, 14, 21, color=MUTED) - 27
        for heading, body in (
            ("Para consultar no dia a dia", "Consultas, relatórios, equipes, mapas operacionais, documentos, segurança de acesso, ortomosaicos e atendimento ao cidadão."),
            ("Use conforme seu perfil", "Menus, ações e registros disponíveis dependem das permissões e dos vínculos da conta. O guia não concede acesso a funções ou dados."),
            ("Revisão de 18/11/2026", "Conteúdo geral preservado, com revisão do escopo publicado e dos recursos do cidadão. As telas de apoio mantidas são capturas do produto, apresentadas como orientação de uso."),
        ):
            y = paragraph(c, heading, y, 12, 18, True, ACCENT) - 8
            y = paragraph(c, body, y, 11, 17) - 23
    elif toc:
        y = paragraph(c, "Selecione um assunto para abrir o capítulo. Os números correspondem a esta revisão.", y, 10, 15, color=MUTED) - 21
        for label, page in CONTENTS:
            c.setFont("Training", 10)
            c.setFillColor(INK)
            c.drawString(MARGIN, y, label)
            c.drawRightString(W - MARGIN, y, str(page))
            if toc_rects is not None:
                toc_rects.append((MARGIN-3, y-5, W-MARGIN+3, y+14))
            y -= 27
    else:
        for heading, body in sections:
            y = paragraph(c, heading, y, 12, 18, True, ACCENT) - 7
            y = paragraph(c, body, y) - 19
    if y < 76:
        raise ValueError(f"Conteúdo ultrapassa a área útil: {title}")
    c.save()
    return PdfReader(output).pages[0]


def chrome(page, number, total):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(W, H))
    c.setFillColor(colors.white)
    c.rect(0, H-61, W, 61, fill=1, stroke=0)
    c.rect(0, 0, W, 57, fill=1, stroke=0)
    c.setFont("Training-Bold", 8)
    c.setFillColor(INK)
    c.drawString(MARGIN, H-31, "IJA DRONES | GUIA DO SISTEMA")
    c.setFont("Training", 7.5)
    c.setFillColor(MUTED)
    c.drawRightString(W-MARGIN, H-31, "18/11/2026 | REVISÃO DE ESCOPO")
    c.setStrokeColor(colors.HexColor("#d5e3ea"))
    c.line(MARGIN, H-44, W-MARGIN, H-44)
    c.line(MARGIN, 51, W-MARGIN, 51)
    c.drawCentredString(W/2, 35, "Guia de acesso e funcionamento do sistema")
    c.drawCentredString(W/2, 22, f"{number} / {total}")
    c.save()
    page.merge_page(PdfReader(buffer).pages[0])


def revise(source, output):
    register_fonts()
    original = PdfReader(source)
    if len(original.pages) != 49 or "Pesqueira" not in (original.pages[37].extract_text() or ""):
        raise ValueError("A origem não corresponde à revisão de 49 páginas identificada.")
    toc_rects = []
    pages = [generated_page("Guia de acesso e funcionamento do sistema", cover=True),
             generated_page("Onde encontrar cada função", toc=True, toc_rects=toc_rects)]
    for source_page in list(range(4, 20)) + [None] + list(range(42, 50)):
        if source_page is None:
            page = generated_page(*PUBLIC_PAGE)
        elif source_page in REPLACEMENTS:
            page = generated_page(*REPLACEMENTS[source_page])
        else:
            page = original.pages[source_page-1]
        pages.append(page)
    writer = PdfWriter()
    for index, page in enumerate(pages, 1):
        chrome(page, index, len(pages))
        writer.add_page(page, excluded_keys=["/Annots"])
    for rect, (label, page_number) in zip(toc_rects, CONTENTS, strict=True):
        writer.add_outline_item(label, page_number-1)
        writer.add_annotation(1, Link(rect=rect, target_page_index=page_number-1))
    writer.add_metadata({"/Title": "Guia de acesso e funcionamento do sistema", "/Author": "IJA Drones / Oceano Azul",
                         "/Subject": "Recursos disponíveis e orientações de uso; revisão de 18/11/2026"})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        writer.write(stream)
    final = PdfReader(output)
    text = "\n".join(page.extract_text() or "" for page in final.pages)
    if "pesqueira" in text.lower() or len(final.pages) != 27:
        raise ValueError("A conferência do guia revisado falhou.")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    output = revise(args.source, ROOT / "output/pdf/IJA-DRONES-Guia-do-Sistema-Atualizado-20261118.pdf")
    published = ROOT / "app/resources/treinamentos/manuais/guia-do-sistema.pdf"
    published.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output, published)
    print(f"Guia revisado: {len(PdfReader(output).pages)} páginas; cópia publicada em {published}")
