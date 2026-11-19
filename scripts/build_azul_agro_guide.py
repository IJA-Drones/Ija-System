"""Rebuild the synthetic, six-page Agro Azul training guide."""
from pathlib import Path
import shutil
from reportlab.pdfgen import canvas
from training_pdf_style import register_fonts, chrome, heading, panel, text, MARGIN, WIDTH, HEIGHT

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ('Comece aqui', 'Azul no Agro', 'Guia prático do segundo pacote | Administrativo e pilotos', [
        ('O que você pode fazer', 'Entender pendências, resumir uma OS, conferir dados salvos de RD e OS, buscar por período e receber ajuda de preenchimento.'),
        ('Como abrir', 'Entre no Agro e clique em Azul. Digite a pergunta ou use Pendências do Agro, Consultar Agro e Guia prático. Para orientação da página atual, use Ajuda nesta tela.'),
        ('Quem vê o quê', 'O administrativo consulta os módulos e registros autorizados para seu usuário. O piloto ativo consulta somente a equipe vinculada. Digitar outro ID não concede acesso. Um registro fora do acesso recebe a mesma resposta de um registro inexistente.'),
        ('Antes de começar', 'Os IDs deste guia são exemplos: troque pelo ID real. A Azul não salva, edita nem conclui registros pelo chat. As buscas livres e os resumos por ID dependem da IA disponível; pendências e perguntas exatas de ajuda funcionam pelo guia local.'),
        ('Onde encontrar este material', 'Treinamentos > Agro > Guias e apresentações por módulo > Azul no Agro: segundo pacote. No Guia prático da Azul, consulte as orientações e o atalho para o PDF.')]),
    ('Função 1', 'Pendências explicadas', 'Entenda por que um item precisa de atenção.', [
        ('O que pedir', '“Quais as prioridades do Agro?” ou “Resumo de pendências do Agro”. Você também pode clicar em Pendências do Agro.'),
        ('O que aparece', 'Contagens de mapeamentos pendentes, contratos aprovados sem OS, OS planejadas e OS em execução. Quando há pendências, a resposta explica o motivo e mostra até cinco IDs por categoria.'),
        ('Como interpretar', 'Mapeamento pendente: confira a RD. Contrato aprovado sem OS: prepare a etapa operacional. OS planejada: revise data, equipe e preparação. OS em execução: confira o preenchimento e a continuidade.'),
        ('Diferença entre os acessos', 'No administrativo, os IDs de mapeamento apresentados nas pendências são de orçamentos e podem incluir RD ainda não criada. Para o piloto, são IDs de RDs da equipe. Módulos sem permissão são omitidos.'),
        ('Limites e próximo passo', 'O resumo considera todas as datas. Não é agenda do dia nem classificação automática por urgência. A Azul não declara atraso sem evidência. Abra a lista indicada para conferir os registros; ela pode conter outras situações.')]),
    ('Função 2', 'Resumo de uma OS', 'Leia as informações essenciais de um registro autorizado.', [
        ('O que pedir', '“Resuma a OS 6”. Use o ID numérico da OS correta. Se o ID não estiver claro, informe-o antes da consulta.'),
        ('O que aparece', 'Situação, propriedade, equipe, piloto, identificador, data de aplicação, serviço, cultura, área registrada e identificação dos drones de pulverização e mapeamento.'),
        ('Informação ausente', 'Quando um campo não está preenchido, a Azul informa “não informado”. Ela não estima área, data, equipamento ou execução. O resumo usa o registro salvo no sistema.'),
        ('Controle de acesso', 'O piloto vê somente OS da equipe vinculada. O administrativo mantém suas permissões e o escopo de registros. O resumo não libera edição nem revela um registro de outra equipe.'),
        ('Próximo passo', 'Abra a lista autorizada indicada na resposta. Use o ID para encontrar a OS e conferir o formulário. Para verificar problemas de preenchimento, peça “Confira a OS 6”.')]),
    ('Função 3', 'Conferência de RD e OS', 'Revise os dados salvos antes de concluir pela tela.', [
        ('O que pedir', '“Confira a RD 3” ou “Confira a OS 6”. Para mapeamento, use o ID da RD, não o ID do orçamento.'),
        ('Conferência da RD', 'A Azul usa as validações do formulário para conclusão: equipe, cliente, propriedade, município, UF, data, responsável e respostas obrigatórias da área. Também verifica os valores preenchidos conforme as regras existentes.'),
        ('Conferência da OS', 'Aponta problemas previstos no formulário, como data ausente, identificação, equipe e seleção de equipamentos. Relatório PDF e mapa são anexos opcionais: a ausência aparece como informação, não como obrigação.'),
        ('O que não foi conferido', 'Texto digitado e ainda não salvo não entra na consulta. A conferência não atesta segurança operacional, não substitui revisão técnica e não conclui o serviço.'),
        ('Como corrigir', 'Abra o formulário, revise os campos indicados e salve pela tela. Depois, consulte novamente. “Nenhum erro encontrado” significa que as validações consultadas não apontaram erro nos dados salvos.')]),
    ('Função 4', 'Busca por período', 'Encontre registros usando texto, situação e datas.', [
        ('O que pedir', '“Busque minhas OS em execução entre 01/11/2026 e 19/11/2026.” Ou: “Busque mapeamentos pendentes da minha equipe.” Informe somente os filtros necessários.'),
        ('Qual data é usada', 'OS: data de aplicação. RD do piloto: data do relatório. Clientes, orçamentos, contratos e mapeamentos administrativos: data de criação. Se precisar de outro tipo de data, esclareça o pedido.'),
        ('Como o intervalo funciona', 'As datas inicial e final entram no resultado. Registros sem a data usada não entram quando há período. Intervalos inválidos são recusados. A resposta mostra a contagem e até cinco IDs.'),
        ('Permissões e filtros', '“Minha equipe” usa o vínculo do piloto. Não há filtro para consultar outra equipe nem filtro de valores. A Azul deve pedir esclarecimento quando um filtro não for suportado, em vez de ignorá-lo.'),
        ('Atenção ao abrir a lista', 'O período é aplicado à resposta do chat. O atalho de destino aplica busca/status suportados pela tela, mas não aplica o mesmo período. Confira as datas dos registros ao abrir a lista.')]),
    ('Função 5', 'Ajuda no preenchimento', 'Siga as etapas sem inventar dados da operação.', [
        ('O que pedir', '“Como preencher a RD?”, “Como preencher a OS?” ou “Passo a passo desta tela”. Dentro de um formulário reconhecido, “Como usar esta tela?” também explica a sequência.'),
        ('Passo a passo da RD', 'Confira equipe, cliente, propriedade e município. Para concluir, informe UF, data e responsável. Registre os dados reais do mapeamento e responda sobre energia, postes, acesso à área e árvores secas. Revise antes de concluir.'),
        ('Passo a passo da OS', 'Confira identificador, cliente, propriedade, data e equipe do contrato. Selecione os drones adequados quando aplicável. Preencha os dados reais de execução, revise anexos opcionais e confira a situação antes de salvar.'),
        ('Ajuda e conferência são diferentes', 'A ajuda explica o formulário de modo geral e não lê o que você está digitando. A conferência por ID consulta o registro salvo. Salvar ou concluir continua sendo uma ação sua na tela.'),
        ('Se algo não aparecer', 'Confira a equipe e as permissões com o administrador. Se a consulta livre estiver indisponível, use os atalhos e o guia local. Não compartilhe senha no chat. Documento com exemplos fictícios e sem dados de clientes.')]),
]


def build():
    register_fonts()
    output = ROOT / 'output/pdf/guia-azul-agro-segundo-pacote.pdf'
    output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output), pagesize=(WIDTH, HEIGHT))
    c.setTitle('Azul no Agro - Segundo pacote')
    c.setAuthor('Oceano Azul / IJA System')
    for number, (eyebrow, title, subtitle, blocks) in enumerate(PAGES, 1):
        chrome(c, number, len(PAGES), '19 NOV 2026')
        y = heading(c, eyebrow, title, subtitle)
        for label, body in blocks:
            y = panel(c, label, body, MARGIN, y) - 12
        if y < 65:
            raise ValueError(f'Page {number} exceeds footer: {y}')
        c.showPage()
    c.save()
    target = ROOT / 'app/resources/treinamentos/manuais/biblioteca' / output.name
    shutil.copyfile(output, target)
    return output

if __name__ == '__main__':
    print(build())
