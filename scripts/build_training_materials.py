"""Recria os dois guias de operação e o kit sintético; não acessa o banco.

Executar com Python que tenha reportlab e Pillow instalados.
Os PDFs gerais, SINAN e compartilhamento são materiais existentes revisados.
"""

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Image, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1] / "app/resources/treinamentos"
BLUE = colors.HexColor("#1b4d79")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TrainingTitle", fontName="Helvetica-Bold", fontSize=19, leading=24, textColor=BLUE, spaceAfter=10))
styles.add(ParagraphStyle(name="TrainingBody", fontName="Helvetica", fontSize=10, leading=15, spaceAfter=9))
styles.add(ParagraphStyle(name="TrainingHeading", fontName="Helvetica-Bold", fontSize=12, leading=17, textColor=BLUE, spaceBefore=10, spaceAfter=8))
styles.add(ParagraphStyle(name="TrainingCaption", fontSize=8, leading=11, textColor=colors.HexColor("#536678"), spaceBefore=6, spaceAfter=9))


def paragraph(text, style="TrainingBody"):
    return Paragraph(text, styles[style])


def step(number, title, text):
    return [paragraph(f"{number}. {title}", "TrainingHeading"), paragraph(text)]


def picture(name, caption):
    image = Image(str(ROOT / "ilustracoes" / name))
    image._restrictSize(17 * cm, 8.7 * cm)
    return [image, paragraph(caption, "TrainingCaption")]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#dce5ed"))
    canvas.line(1.8 * cm, 1.5 * cm, 19.2 * cm, 1.5 * cm)
    canvas.setFillColor(colors.HexColor("#536678"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(1.8 * cm, 1.1 * cm, "OCEANO AZUL | TREINAMENTOS | Atualizado em 21/10/2026")
    canvas.drawRightString(19.2 * cm, 1.1 * cm, str(doc.page))
    canvas.restoreState()


def build(name, title, story):
    doc = SimpleDocTemplate(str(ROOT / "manuais" / name), pagesize=(21 * cm, 29.7 * cm),
                            topMargin=1.6 * cm, bottomMargin=2 * cm, leftMargin=1.8 * cm,
                            rightMargin=1.8 * cm, title=title, author="Oceano Azul")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main():
    story = [paragraph("LIRAa e focal: roteiro de treinamento", "TrainingTitle"),
             paragraph("Pesqueira / PE | Cadastro territorial, amostra e visitas | Demonstração"),
             paragraph("Este kit contém 3 quarteirões, 3 estratos e 24 visitas. Os locais e as coordenadas de ruas são reais; imóveis, amostragem e resultados de saúde são fictícios. Os contornos são demonstrativos, não o cadastro territorial oficial da prefeitura.")]
    story += step(1, "Selecione o município e a origem", "Entre com COVISA ou coordenação autorizada. Abra Vigilância → Focal e LIRAa → Planejamento. Use Pesqueira e <b>Demonstração</b> em todas as etapas. O CSV de visitas usa o ID interno <b>14</b>; o código IBGE é <b>2610905</b>. Se o cadastro do ambiente for diferente, ajuste municipio_id antes de importar.")
    story += step(2, "Cadastre os quarteirões: arquivo 01", "Na seção de cadastro territorial, importe <b>01_Cadastro_territorial_Centro_Pesqueira_poligonos_DEMO.csv</b>. O arquivo cadastra três quarteirões do Centro e seus polígonos. Ele não registra visitas e não calcula o IIP sozinho.")
    story += step(3, "Crie o levantamento em rascunho", "Informe um código de sua escolha, título, responsável e referência do plano. O período precisa incluir <b>21/10/2026</b>, data das visitas deste kit. Exemplo de período: 20/10/2026 a 23/10/2026. Abra o levantamento criado; a amostra entra enquanto ele está em <b>rascunho</b>.")
    story += picture("planejamento.png", "Tela ilustrativa de planejamento de uma versão anterior. Códigos, contagens e situação da captura não são os valores esperados deste kit; siga o roteiro atualizado.")
    story += [PageBreak(), paragraph("Amostra e importação das visitas", "TrainingTitle")]
    story += step(4, "Importe a amostra: arquivo 02", "Dentro do levantamento em rascunho, abra <b>Importar amostra · estratos e quarteirões</b> e envie <b>02_Amostra_Centro_Pesqueira_agente_DEMO.csv</b>. O levantamento aberto é o destino: não é necessário repetir seu código no arquivo de amostra. Confira 3 estratos, 3 quarteirões e meta de 8 visitas por quarteirão.")
    story += [paragraph("O arquivo 02 indica o agente de ID <b>167</b> no ambiente de Pesqueira. Em outro cadastro, ajuste agente_id para uma conta válida da mesma prefeitura antes de importar. Depois confira as atribuições na tela.")]
    story += step(5, "Revise e libere", "Confira os vínculos, as metas e os agentes. Marque a revisão da amostra e clique em <b>Liberar levantamento para campo</b>. A liberação é necessária para receber visitas planejadas; ela não deve ser feita antes da importação da amostra.")
    story += step(6, "Importe as visitas: arquivo 03", "Use <b>Importar visitas deste levantamento</b> ou abra Importação e validação. Selecione explicitamente o levantamento de destino. Envie <b>03_Visitas_LIRAa_Centro_Pesqueira_coordenadas_reais_DEMO.csv</b>, confira a prévia e confirme a carga. Uma prévia válida ainda não é uma carga concluída.")
    story += [paragraph("O arquivo 03 contém o código <b>teste-1</b>. Se você criou outro código, o seletor de destino permite usar esse levantamento. Ele precisa estar liberado e conter os estratos e quarteirões do arquivo. Selecionar o destino não cria o planejamento nem dispensa esses vínculos."),
              paragraph("Se aparecer 'levantamento precisa estar liberado', confira o destino selecionado, município, origem Demonstração e situação. Se aparecer 'levantamento não encontrado', selecione o destino correto antes de validar novamente."),
              paragraph("As três funções dos CSVs", "TrainingHeading")]
    rows = [[paragraph("Arquivo"), paragraph("Onde importar / função")],
            [paragraph("01 · Cadastro territorial"), paragraph("Planejamento → Cadastro territorial. Cadastra quarteirões e contornos.")],
            [paragraph("02 · Amostra"), paragraph("Dentro do levantamento em rascunho. Vincula estratos, quarteirões, metas e agentes.")],
            [paragraph("03 · Visitas"), paragraph("Importar visitas, com destino liberado. Registra inspeções e alimenta os indicadores após confirmação.")]]
    table=Table(rows,colWidths=[5.0*cm,12.0*cm],hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#eef4f9")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),7),("LINEBELOW",(0,0),(-1,-1),.4,colors.HexColor("#dce5ed"))]))
    story += [table, PageBreak(), paragraph("Registro manual e conferência", "TrainingTitle")]
    story += step(7, "Preencha sem CSV", "A coordenação pode cadastrar quarteirões, estratos e amostra pela tela. Atribua os quarteirões e libere o levantamento. O agente entra com a própria conta e abre <b>Meus levantamentos</b>. Escolhe um quarteirão atribuído e registra cada visita, situação do imóvel, recipientes, resultado e coordenadas conforme os campos disponíveis. Salve e confirme o registro pelo fluxo exibido.")
    story += [paragraph("Um imóvel fechado ou recusado deve permanecer como pendência, e não como inspecionado. Larva observada em uma OS não substitui uma inspeção LIRAa. O reaproveitamento de endereço da OS é apenas um auxílio ao preenchimento.")]
    story += picture("agente.png", "Exemplo de preenchimento manual em conta de agente. Use os vínculos e o período do levantamento que você liberou.")
    story += step(8, "Confira os resultados", "Após confirmar as 24 visitas do kit, confira: <b>21 imóveis inspecionados, 3 positivos e 3 pendências</b>. Os IIPs esperados são Q01: <b>16,67%</b>; Q02: <b>28,57%</b>; Q03: <b>0%</b>. IIP = imóveis positivos ÷ imóveis inspecionados × 100. Os códigos completos são DEMO-PES-CENTRO-Q01, Q02 e Q03.")
    story += [paragraph("Se você já importou as 24 visitas, não registre novamente os mesmos imóveis para comparar os totais acima. Para praticar o preenchimento manual, use um levantamento separado com a sua própria amostra. A limpeza de testes deve respeitar as permissões e a origem dos registros."),
              paragraph("Base cartográfica: © OpenStreetMap contributors, ODbL 1.0. Contornos não oficiais e dados de saúde sintéticos.", "TrainingCaption")]
    build("tutorial-liraa.pdf", "LIRAa e focal - Treinamento", story)
    # Mantém o manual e o kit atualizados ao reconstruir os materiais gerais.
    from build_liraa_manual import build_manual
    build_manual()

    story = [paragraph("Mapa de risco: roteiro de treinamento", "TrainingTitle"),
             paragraph("Conferência dos dados internos e da versão pública agregada"),
             paragraph("O mapa é alimentado pelos registros salvos. Cadastro territorial e amostra definem o planejamento; as visitas confirmadas alimentam os resultados entomológicos. As notificações SINAN são uma fonte epidemiológica distinta.")]
    story += step(1, "Conclua as cargas", "Importe os arquivos 01, 02 e 03 na sequência do tutorial LIRAa. Para a comparação com notificações, importe o arquivo <b>04_SINAN_Dengue_2026_Pesqueira_DEMO.csv</b> no SINAN, usando dengue, Pesqueira, 2026 e Demonstração. O arquivo SINAN contém 6 registros fictícios.")
    story += step(2, "Selecione o mesmo contexto", "Abra Vigilância → Mapa de risco. Escolha a fonte Levantamento LIRAa, Pesqueira, Demonstração e o levantamento em que você confirmou as visitas. Deixe as datas vazias ou use um intervalo que inclua 21/10/2026. No comparativo SINAN, use a doença e o ano correspondentes ao lote importado.")
    story += step(3, "Confira as camadas", "Use <b>Enquadrar levantamento</b> para aproximar a coleta; <b>Ver município</b> para o limite municipal; e <b>Ver Pernambuco</b> para o contexto estadual. Ative os contornos e IIP e, na área interna, as visitas com coordenadas. Espere 24 visitas e os contornos do planejamento deste kit.")
    story += picture("mapa.png", "Mapa de uma demonstração anterior, ilustrando contornos e visitas. Códigos, pontos e valores da imagem diferem do kit atual.")
    story += [PageBreak(), paragraph("Indicadores e Portal do Cidadão", "TrainingTitle")]
    story += step(4, "Interprete o IIP", "O índice de infestação predial considera os imóveis positivos entre os efetivamente inspecionados. Pendências não entram como inspeções. Para este kit: Q01 = 1/6 = 16,67%; Q02 = 2/7 = 28,57%; Q03 = 0/8 = 0%. Os valores altos são intencionais para demonstrar a visualização e não descrevem a situação sanitária real de Pesqueira.")
    story += [paragraph("Os pontos do CSV são posições em vias reais. Não são coordenadas verificadas de domicílios ou pacientes. O SINAN do arquivo 04 também é inteiramente fictício. Os contornos deste kit são demonstrativos, não os limites oficiais dos quarteirões da prefeitura.")]
    story += step(5, "Confira o portal público", "Abra o Portal do Cidadão, selecione Pesqueira e a origem Demonstração no mapa. Use o mesmo contexto das cargas. O portal exibe uma visão agregada: não publica a lista de pacientes, nomes, endereços ou os detalhes individuais da visita. A visualização pública depende dos filtros, da configuração municipal e dos dados disponíveis.")
    story += step(6, "Se o resultado não aparecer", "Confira se a carga de visitas está concluída, se o município e a origem coincidem e se o período inclui a coleta. Verifique os vínculos de estrato, área e quarteirão para o IIP. Para SINAN, confira lote concluído, doença, ano e vínculo IBGE da prefeitura. Não importe novamente apenas para tentar atualizar o mapa.")
    story += [paragraph("Limites de interpretação", "TrainingHeading"),
              paragraph("IIP, volume de notificações e uma análise histórica de risco são medidas diferentes. A visualização territorial do levantamento comprova o fluxo dos dados; por si só não equivale a uma análise histórica completa ou à aprovação da prova de conceito."),
              paragraph("Base cartográfica: © OpenStreetMap contributors, ODbL 1.0, nos arquivos de teste; limites municipais disponibilizados pelo sistema conforme a fonte IBGE.", "TrainingCaption")]
    build("tutorial-mapa-de-risco.pdf", "Mapa de risco - Treinamento", story)

    readme = """TREINAMENTO - PESQUEIRA / PE - DEMONSTRAÇÃO
Atualizado em 21/10/2026

Todos os registros de saúde, imóveis, metas e amostras são fictícios.
Os CSVs LIRAa usam coordenadas de ruas reais de Pesqueira e contornos
demonstrativos não oficiais. Base: © OpenStreetMap contributors, ODbL 1.0.
https://www.openstreetmap.org/copyright

Use Demonstração em todas as telas. Nunca apresente estes registros como reais.

LIRAa: 01 cadastro territorial → criar rascunho → 02 amostra dentro do
rascunho → conferir agentes e liberar → 03 visitas, selecionando o destino
na importação → validar e confirmar a carga → resultados e mapa de risco.

As visitas são de 21/10/2026. O período do levantamento deve incluir essa data.
Arquivo 03: municipio_id=14 e levantamento_codigo=teste-1.
O seletor permite importar em outro levantamento liberado que tenha os mesmos
estratos e quarteirões. Ele não cria a amostra nem substitui os vínculos.
Arquivo 02: agente_id=167. Confira a conta da mesma prefeitura antes da carga.
Os IDs são do cadastro atual de Pesqueira; ajuste-os para outro ambiente.

O kit LIRAa tem 3 quarteirões, 3 estratos e 24 visitas.
Esperado: 21 inspecionados, 3 positivos, 3 pendências.
IIP: Q01 16,67%; Q02 28,57%; Q03 0%.
Para praticar manualmente sem alterar estes totais, use outro levantamento.

SINAN: arquivo 04 → SINAN → Importar dados → Arquivo CSV.
Escolha Pesqueira, dengue, 2026 e Demonstração. Esperado: 6 registros
(2 confirmados, 3 suspeitos e 1 descartado). IBGE 2610905.

Compartilhamento: use a imagem 05 e o texto 06 em Ações realizadas, com
origem Demonstração. Prepare o rascunho, confira a prévia, envie à revisão
e publique somente após a conferência e com permissão editorial.
O kit não publica conteúdo nem envia mensagens automaticamente.

Os manuais completos estão na página Treinamentos do sistema.
"""
    (ROOT / "testes/LEIA_PRIMEIRO.txt").write_text(readme, encoding="utf-8")
    with ZipFile(ROOT / "kit-testes-pesqueira-demo.zip", "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "testes").iterdir()):
            archive.write(path, f"Pesqueira-DEMO/{path.name}")


if __name__ == "__main__":
    main()
