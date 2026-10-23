"""Manual do fluxo atual: capturas locais, CSVs pequenos e nenhum acesso ao banco.

Executar com o Python de documentos (reportlab/Pillow disponíveis).
"""
from pathlib import Path
from shutil import copyfile
from zipfile import ZipFile, ZIP_DEFLATED

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Table, TableStyle, PageBreak, Spacer

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app/resources/treinamentos"
PICTURES = RESOURCES / "ilustracoes/liraa-atual"
KIT = ROOT / "output/liraa-pesqueira-20261022"
# Streams binários compactos para imagens e detecção correta do PDF no Git.
rl_config.useA85 = False
BLUE = colors.HexColor("#1b4d79")
TEXT = colors.HexColor("#27394b")
STYLES = {
    "title": ParagraphStyle("ManualTitle", fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=BLUE, spaceAfter=10),
    "heading": ParagraphStyle("ManualHeading", fontName="Helvetica-Bold", fontSize=12, leading=17, textColor=BLUE, spaceBefore=9, spaceAfter=7, keepWithNext=True),
    "body": ParagraphStyle("ManualBody", fontName="Helvetica", fontSize=10, leading=14, textColor=TEXT, spaceAfter=8),
    "caption": ParagraphStyle("ManualCaption", fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#536678"), spaceBefore=5, spaceAfter=10),
    "cell": ParagraphStyle("ManualCell", fontName="Helvetica", fontSize=9, leading=13, textColor=TEXT),
}

def p(text, kind="body"):
    return Paragraph(text, STYLES[kind])

def photo(name, caption):
    image = Image(str(PICTURES / name))
    image.drawHeight *= 18 * cm / image.drawWidth
    image.drawWidth = 18 * cm
    return [image, p(caption, "caption")]

def table(rows, widths):
    rendered = [[p(str(value), "cell") for value in row] for row in rows]
    result = Table(rendered, colWidths=[w * cm for w in widths], hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf3f8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#dce5ed")),
    ]))
    return result

def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#dce5ed"))
    canvas.line(1.5 * cm, 1.3 * cm, 19.5 * cm, 1.3 * cm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#536678"))
    canvas.drawString(1.5 * cm, .9 * cm, "OCEANO AZUL | LIRAa | Interface atual - 22/10/2026 | Demonstração")
    canvas.drawRightString(19.5 * cm, .9 * cm, str(document.page))
    canvas.restoreState()

def build_manual():
    output = ROOT / "output/pdf/manual-liraa-atualizado.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    story = [p("LIRAa: importação e conferência", "title"),
        p("Pesqueira / PE · Guia atualizado em 22/10/2026", "caption"),
        p("Siga as quatro etapas da tela: <b>Quarteirões / Levantamento e amostra / Visitas / Resultados</b>. O link <b>Manual do LIRAa</b> abre este guia em outra aba; <b>CSVs de demonstração</b> baixa os arquivos correspondentes."),
        p("As capturas são da interface atual em uma base isolada. Ruas e referências de Pesqueira são reais; imóveis, metas, visitas, resultados e contornos são demonstrativos. As imagens não representam dados sanitários reais do município.", "caption"),
        table([["Arquivo do kit atualizado", "Função"],
            ["01_quarteiroes.csv", "Cadastra 3 quarteirões e contornos ilustrativos."],
            ["02_amostra.csv", "Vincula 3 estratos e metas ao levantamento em rascunho."],
            ["03_visitas.csv", "Registra 24 visitas após a liberação e a confirmação da carga."]], [7, 11]),
        p("1. Cadastre os quarteirões primeiro", "heading"),
        p("Escolha Pesqueira e <b>Demonstração</b>. Abra <b>Quarteirões</b> e envie o arquivo 01 em <b>Importar quarteirões e contornos</b>. Como o kit inclui polígonos, marque <b>Conferi os contornos incluídos no arquivo</b> antes de importar."),
        *photo("quarteiroes.jpg", "A confirmação dos contornos está ao lado do envio. Cadastro manual e mapa ficam recolhidos e podem ser abertos quando necessário."),
        p("Depois da carga, confira os códigos DEMO-Q01, DEMO-Q02 e DEMO-Q03. Os nomes das vias aparecem no campo de área. Continue para os levantamentos.")]

    story += [PageBreak(), p("2. Levantamento e amostra", "title"),
        p("Clique em <b>Novo levantamento</b>. Informe um código, nome, período, coordenação e referência. O kit contém visitas de <b>22/10/2026</b>; use, por exemplo, o período de 22/10/2026 a 23/10/2026."),
        *photo("criar.jpg", "Exemplo de preenchimento em base isolada. PES-DEMO-RASCUNHO é um código ilustrativo; você pode escolher outro."),
        p("Importe a amostra no rascunho", "heading"),
        p("Abra o levantamento criado e envie <b>02_amostra.csv</b> em <b>Importar amostra</b>. O arquivo utiliza os quarteirões já cadastrados, na mesma prefeitura e origem de dados. Não é preciso repetir o código do levantamento no CSV 02."),
        *photo("importar-amostra.jpg", "A tela informa qual rascunho receberá a amostra. A nova importação substitui a amostra atual desse rascunho."),
        p("Confira <b>3 estratos, 3 quarteirões e meta de 24 imóveis</b>: 8 em cada quarteirão. O kit não fixa um agente; selecione uma conta de campo da mesma prefeitura se for demonstrar as tarefas do agente."),
        p("A amostra só pode ser alterada em <b>RASCUNHO</b>. Levantamentos liberados ou encerrados têm a amostra protegida. As datas das visitas serão verificadas na carga do arquivo 03.")]

    story += [PageBreak(), p("3. Libere e importe as visitas", "title"),
        p("Revise os estratos, quarteirões, metas e agentes. Marque a confirmação de revisão e clique em <b>Liberar levantamento para campo</b>. Depois, use <b>Importar visitas deste levantamento</b> ou a etapa <b>Visitas</b>."),
        *photo("visitas.jpg", "Selecione o levantamento liberado antes de escolher o arquivo de visitas. Identificação e origem dos dados ficam disponíveis em Alterar identificação."),
        p("Valide e confirme", "heading"),
        p("Envie <b>03_visitas.csv</b> e clique em <b>Validar arquivo</b>. Confira a prévia, os erros e o destino. Somente depois use <b>Confirmar carga validada</b>. Validar o arquivo, sozinho, ainda não salva as visitas operacionais."),
        p("O CSV traz municipio_id=<b>14</b>, correspondente a Pesqueira no ambiente conferido, e levantamento_codigo=<b>PES-DEMO-2026</b>. Se seu levantamento tiver outro código, escolha-o no seletor de destino. Ele precisa estar liberado e conter os mesmos quarteirões e estratos."),
        p("Se as datas não coincidirem", "heading"),
        p("Use <b>Conferir / ampliar período do levantamento</b>. Em <b>Mais opções do levantamento</b>, amplie o intervalo para incluir as visitas, informe o motivo e confirme. A ampliação preserva a amostra e as datas originais das visitas; não reduz o período atual."),
        p("Para preencher manualmente, abra um quarteirão atribuído em um levantamento liberado e use Registrar visita. Imóvel fechado ou recusado deve continuar como pendência, sem ser contado como inspecionado.")]

    story += [PageBreak(), p("4. Confira os resultados", "title"),
        p("Na etapa <b>Resultados</b>, selecione Pesqueira, Demonstração e o levantamento em que a carga foi concluída. Deixe o período sem filtro ou inclua 22/10/2026. O kit deve produzir <b>24 visitas, 21 imóveis inspecionados, 3 positivos e 3 pendências</b>."),
        *photo("resultados.jpg", "Gráficos com as vias reais de referência e resultados inteiramente fictícios, conferidos após a importação do kit atualizado."),
        table([["Quarteirão", "Inspecionados", "Positivos", "Pendentes", "IIP"],
            ["DEMO-Q01", 6, 1, 2, "16,67%"],
            ["DEMO-Q02", 7, 2, 1, "28,57%"],
            ["DEMO-Q03", 8, 0, 0, "0,00%"]], [4.2, 3.7, 3.2, 3.4, 3.5]),
        Spacer(1, 8),
        p("IIP = imóveis positivos ÷ imóveis inspecionados × 100. As pendências não entram no denominador. Em <b>Exportar e imprimir</b>, escolha a saída do recorte aplicado. O mapa utiliza os contornos e as visitas confirmadas."),
        p("Se a importação for interrompida", "heading"),
        p("<b>Confirmação dos contornos:</b> marque a caixa antes do envio do arquivo 01.<br/><b>Quarteirão não cadastrado:</b> importe o arquivo 01 na mesma prefeitura e origem.<br/><b>Amostra protegida:</b> abra um rascunho para importar o arquivo 02.<br/><b>Período incompatível:</b> confira as datas e amplie o intervalo pela opção indicada.<br/><b>Agente incompatível:</b> use uma conta da mesma prefeitura ou deixe sem atribuição no teste."),
        p("Vias conferidas em fontes públicas da Prefeitura de Pesqueira: edital de apoio ao Carnaval 2026, notícias de pavimentação e Portal da Transparência. Geometrias reaproveitadas do kit do repositório, atribuídas a © OpenStreetMap contributors (ODbL 1.0). Fontes e instruções completas estão em LEIA_PRIMEIRO.txt, no kit. Os contornos não são a malha territorial oficial.", "caption")]

    SimpleDocTemplate(str(output), pagesize=(21 * cm, 29.7 * cm),
        topMargin=1.4 * cm, bottomMargin=1.8 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title="LIRAa - Importação e conferência - Interface atual", author="Oceano Azul").build(story, onFirstPage=footer, onLaterPages=footer)
    copyfile(output, RESOURCES / "manuais/tutorial-liraa.pdf")
    kit_path = RESOURCES / "kits/liraa-pesqueira-20261022.zip"
    kit_path.parent.mkdir(exist_ok=True)
    csv_dir = RESOURCES / "testes/liraa-atual"
    csv_dir.mkdir(parents=True, exist_ok=True)
    for name in ("01_quarteiroes.csv", "02_amostra.csv", "03_visitas.csv"):
        copyfile(KIT / name, csv_dir / name)
    with ZipFile(kit_path, "w", compression=ZIP_DEFLATED) as archive:
        for name in ("01_quarteiroes.csv", "02_amostra.csv", "03_visitas.csv", "LEIA_PRIMEIRO.txt"):
            archive.write(KIT / name, name)
        archive.write(output, "Manual_LIRAa.pdf")
    copyfile(kit_path, KIT / "kit-liraa-pesqueira.zip")
    return output

if __name__ == "__main__":
    print(build_manual())
