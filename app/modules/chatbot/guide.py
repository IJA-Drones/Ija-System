"""Short permission-aware tours. A tour never reads or changes business records."""
from flask import url_for
from werkzeug.routing import BuildError

from app.modules.chatbot import exports, operations, search, voice
from app.modules.chatbot.azul import help_context
from app.modules.gestao_ti.permissions import can_access_endpoint

WORKFLOWS = {
    'prefeitura.solicitacoes': ('Acompanhe suas solicitações',
        'Use os filtros visíveis para localizar uma solicitação por situação ou período. '
        'Abra os detalhes para conferir o pedido, o status e as informações disponíveis. '
        'Os registros exibidos seguem os vínculos da sua conta.'),
    'prefeitura.os': ('Acompanhe as ordens de serviço',
        'Localize uma ordem na listagem e abra seus detalhes. Confira a situação e as '
        'informações da operação antes de usar as ações disponíveis para seu acesso.'),
    'agro.clientes': ('Encontre o cliente',
        'Procure o cliente na listagem e abra seu cadastro para conferir as informações. '
        'As opções para cadastrar ou editar aparecem conforme seu acesso.'),
    'agro.comercial': ('Confira seu orçamento',
        'Abra um orçamento disponível e confira o cliente e os serviços. Revise os '
        'valores e as informações antes de confirmar uma ação na tela.'),
    'agro.contratos': ('Consulte o contrato',
        'Localize o contrato e abra seus detalhes. Confira o cliente, os serviços e '
        'a situação. Use somente as ações que estiverem disponíveis para sua conta.'),
    'agro.os': ('Acompanhe a operação Agro',
        'Localize a ordem de serviço e abra seus detalhes para conferir a operação. '
        'Os registros e as ações disponíveis dependem do seu perfil e dos seus vínculos.'),
    'agro.talentos': ('Consulte o banco de talentos',
        'Abra um candidato para conferir o currículo e o perfil extraído pela Azul. '
        'A análise precisa de revisão humana; ela não representa uma decisão de contratação.'),
}

RECORDED_STEPS = {
    'start': ('Comece pelos recursos do seu acesso',
        'O menu do sistema reúne as áreas disponíveis para você. Escolha um dos '
        'atalhos abaixo ou use “Meu acesso” para conhecer seus recursos.'),
    'screen': ('Abra uma área e peça orientação',
        'Entre na tela em que deseja trabalhar e escolha “Ajuda nesta tela”. '
        'A Azul usa o guia do sistema e os recursos permitidos para orientar você. '
        'Se um recurso não aparecer no seu acesso, procure o administrador.'),
    'review': ('Confira antes de confirmar',
        'Revise os dados e os campos obrigatórios antes de salvar ou enviar um formulário. '
        'Este tutorial apenas orienta: quem confirma uma ação na tela é você.'),
    'continue': ('Continue com a Azul',
        'Escreva sua dúvida em linguagem simples. Nas novas respostas, “Ouvir resposta” '
        'reproduz a voz gerada por inteligência artificial, quando disponível. '
        'Você pode parar o áudio a qualquer momento e reabrir este guia quando precisar.'),
}


def build(user, page):
    context = help_context(user, page)
    links = context['atalhos']
    current = next((link for link in links if link['url'] == page), None)
    steps = []

    def add(title, body, target='[data-compose-input]', choices=None, question=None, intent=None):
        steps.append({'title': title, 'body': body, 'target': target,
                      'links': choices or [], 'question': question, 'intent': intent,
                      'speech': voice.offer(title + '. ' + body, user)})

    add(*RECORDED_STEPS['start'],
        '[data-intent="access_overview"]', links[:6],
        'O que posso acessar no sistema?', 'access_overview')
    if current and current['modulo'] in WORKFLOWS:
        title, body = WORKFLOWS[current['modulo']]
        add(title, body, 'screen-list', question='Como usar esta tela?')
    elif current and current['modulo'].startswith('financeiro.'):
        add('Confira a empresa e o período',
            'Antes de consultar um lançamento, confira a empresa selecionada e os '
            'filtros da tela. Abra um item para revisar seus detalhes. As ações de '
            'gravação dependem das permissões da sua conta.', 'screen-list',
            question='Como usar esta tela?')
    else:
        add(*RECORDED_STEPS['screen'],
            '[data-question="Como usar esta tela?"]', question='Como usar esta tela?')
    add(*RECORDED_STEPS['review'], 'screen-form')
    if search.allowed(user):
        add('Busque solicitações em uma frase',
            'Por exemplo: “Busque solicitações pendentes no bairro Centro”. '
            'A Azul apresenta a quantidade encontrada e um atalho para a lista filtrada. '
            'Esta busca cobre solicitações municipais.',
            '[data-search-guide]', question='Quero buscar solicitações municipais. Quais filtros posso informar?')
    if operations.allowed(user):
        add('Veja o que precisa de atenção',
            'Use “Minha atenção hoje” para consultar o resumo disponível para seu '
            'perfil. Abra os atalhos da resposta para conferir os itens na tela.',
            '[data-intent="attention_today"]', question='O que precisa da minha atenção hoje?', intent='attention_today')
    if exports.allowed_sources(user):
        add('Prepare um relatório com revisão',
            'Escolha “Gerar relatório” e informe a base municipal, o formato, o período '
            'e os filtros desejados. Confira a prévia. O arquivo só é gerado depois '
            'de você escolher “Confirmar e baixar”.',
            '[data-intent="start_report"]', question='Quero gerar um relatório.', intent='start_report')
    training = []
    if can_access_endpoint(user, 'main.treinamentos', 'GET', legacy=True):
        try:
            training = [{'label': 'Abrir treinamentos', 'url': url_for('main.treinamentos')}]
        except BuildError:
            # Isolated deployments may omit the training module entirely.
            pass
    add(*RECORDED_STEPS['continue'],
        '[data-compose-input]', training)
    return steps
