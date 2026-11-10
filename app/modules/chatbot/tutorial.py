"""A synthetic training room. No business records, forms or model calls."""
from copy import deepcopy

from flask import abort, make_response, render_template, request
from flask_login import current_user

from app.modules.chatbot import voice
from app.modules.chatbot.azul import help_context
from app.modules.gestao_ti.permissions import can_access_endpoint, route_access


def step(title, body, action, target):
    return dict(title=title, body=body, action=action, target=target)


PUBLIC = [
    dict(id='foco', kind='foco', title='Seu primeiro relato de foco', icon='◎', minutes=3,
         description='Escolha o município, indique o local e revise um relato de exemplo.', steps=[
             step('Escolha o município', 'Vamos praticar em Município Exemplo. Selecione essa opção para começar.', 'city', 'city'),
             step('Encontre o caminho do relato', 'Clique em Relatar foco. Esse caminho serve para um problema no ambiente.', 'open', 'open'),
             step('Identifique a ocorrência', 'Neste exemplo, encontramos água parada. Escolha Aedes para continuar o exercício.', 'type', 'type'),
             step('Indique o local', 'Clique no ponto destacado do desenho. Ele representa um endereço inventado, sem localização real.', 'location', 'location'),
             step('Revise as informações', 'O relato de exemplo já está preenchido. Abra a revisão e confira os dados antes de continuar.', 'review', 'review'),
             step('Confira a confirmação', 'Leia o resumo e marque que entendeu que este exercício usa dados fictícios. No sistema real, confira também o consentimento do formulário.', 'consent', 'consent'),
             step('Conclua o envio simulado', 'Clique em Enviar simulação. Você verá uma confirmação de treinamento, sem registrar uma ocorrência real.', 'send', 'send'),
         ]),
    dict(id='saude', kind='saude', title='Relato de suspeita de adoecimento', icon='♡', minutes=2,
         description='Aprenda a encontrar o formulário correto e revisar uma situação inventada.', steps=[
             step('Use o caminho específico de saúde', 'Clique em Relatar caso suspeito. Esse formulário é diferente do relato de foco no ambiente.', 'open', 'open'),
             step('Observe os campos de saúde', 'Escolha o exemplo de sintomas. Aqui usamos uma situação inventada; não digite informações pessoais.', 'symptom', 'symptom'),
             step('Revise o exemplo', 'Abra a revisão. Uma suspeita de adoecimento não é diagnóstico nem confirmação de caso.', 'review', 'review'),
             step('Confira antes de prosseguir', 'Marque a confirmação do exercício. No uso real, os dados ficam no formulário específico, e não na conversa da Azul.', 'consent', 'consent'),
             step('Envie somente a simulação', 'Conclua o exercício. O envio real deve ser feito no formulário do portal e não substitui atendimento de saúde.', 'send', 'send'),
         ]),
    dict(id='boletim', kind='boletim', title='Entenda o boletim de saúde', icon='▥', minutes=2,
         description='Pratique os filtros e confira o período e a fonte antes de interpretar números.', steps=[
             step('Selecione o município', 'Escolha Município Exemplo. Todos os números desta sala foram inventados para ensinar os controles.', 'city', 'city'),
             step('Escolha a doença', 'Selecione Dengue. No boletim real, cada seleção deve ser interpretada conforme a doença informada.', 'disease', 'disease'),
             step('Confira o período', 'Selecione 2026 para visualizar o exemplo. Confira sempre o ano e o período de referência no sistema real.', 'period', 'period'),
             step('Leia a identificação da fonte', 'Abra Sobre estes dados. Estes números não são indicadores reais e não devem orientar decisões de saúde.', 'source', 'source'),
             step('Conclua a leitura', 'Antes de interpretar um boletim real, confira município, doença, período e fonte. Confirme para concluir o exercício.', 'finish', 'finish'),
         ]),
]

# Only module names from the user's verified navigation are used to choose tracks.
# Values below are invented constants, never loaded from operational queries.
INTERNAL = {
    'prefeitura.solicitacoes': ('solicitacoes', 'Solicitações municipais', 'Solicitação', 'Pendente',
        [('Protocolo', 'DEMO-001'), ('Bairro', 'Bairro Exemplo'), ('Ocorrência', 'Água parada — exemplo')],
        'Confira o pedido e o status antes de encaminhar uma ação. O filtro deste exercício apenas organiza a lista fictícia.'),
    'prefeitura.os': ('os', 'Ordens de serviço', 'Ordem de serviço', 'Agendada',
        [('Ordem', 'DEMO-OS-001'), ('Equipe', 'Equipe de Treinamento'), ('Local', 'Área de Exemplo')],
        'Confira a situação, a equipe e o local da operação. Consultar uma ordem não confirma que o serviço foi executado.'),
    'agro.clientes': ('clientes', 'Clientes Agro', 'Cliente', 'Ativo',
        [('Cliente', 'Cliente de Exemplo'), ('Propriedade', 'Fazenda de Treinamento'), ('Cidade', 'Município Exemplo')],
        'Confira o cadastro e a propriedade. No sistema real, ações de cadastro e edição dependem do seu acesso.'),
    'agro.comercial': ('orcamentos', 'Orçamentos Agro', 'Orçamento', 'Em análise',
        [('Orçamento', 'DEMO-ORC-001'), ('Cliente', 'Cliente de Exemplo'), ('Serviço', 'Operação demonstrativa')],
        'Revise o cliente e os serviços antes de confirmar uma ação comercial. Os valores deste exercício são fictícios.'),
    'agro.contratos': ('contratos', 'Contratos Agro', 'Contrato', 'Em análise',
        [('Contrato', 'DEMO-CTR-001'), ('Cliente', 'Cliente de Exemplo'), ('Serviço', 'Operação demonstrativa')],
        'Confira o cliente, os serviços e a situação. Este exercício não assina nem altera contratos.'),
    'agro.os': ('os-agro', 'Ordens de serviço Agro', 'Ordem de serviço', 'Agendada',
        [('Ordem', 'DEMO-AGRO-001'), ('Propriedade', 'Fazenda de Treinamento'), ('Equipe', 'Equipe de Treinamento')],
        'Confira os detalhes da operação e a situação. Consultar uma ordem não equivale a iniciar ou finalizar a execução.'),
    'agro.talentos': ('talentos', 'Banco de talentos', 'Candidato', 'Em análise',
        [('Candidato', 'Pessoa de Exemplo'), ('Currículo', 'Documento fictício'), ('Experiência', 'Perfil de treinamento')],
        'O perfil extraído pela Azul precisa de revisão humana. Ele não representa nota, ranking ou decisão de contratação.'),
}


def list_lesson(module, definition):
    identifier, title, noun, status, fields, guidance = definition
    return dict(id=identifier, kind='lista', module=module, title=title, noun=noun, status=status,
                fields=fields, icon='▤', minutes=2,
                description='Pratique como localizar um item e conferir seus detalhes, com dados fictícios.',
                steps=[
                    step('Encontre a área no menu', f'Clique em {title} no menu de treinamento. Nesta sala, os controles não abrem os cadastros reais.', 'menu', 'menu'),
                    step('Use o filtro da lista', f'Selecione {status} no filtro. Vamos localizar um exemplo antes de abrir os detalhes.', 'filter', 'filter'),
                    step('Abra um item', f'Clique na primeira linha. O identificador DEMO indica um registro criado apenas para este exercício.', 'item', 'item'),
                    step('Confira as informações', guidance + ' Abra Conferir informações para continuar.', 'details', 'details'),
                    step('Conclua a consulta', 'Você localizou e revisou um exemplo. No sistema real, confira as informações e as permissões antes de qualquer alteração.', 'finish', 'finish'),
                ])


def catalog(audience, user):
    if audience == 'publico':
        return deepcopy(PUBLIC)
    if audience != 'sistema':
        abort(400)
    if not user.is_authenticated:
        abort(401)
    if (not route_access(user, True)
            or not can_access_endpoint(user, 'main.azul_help', 'POST', legacy=True)):
        abort(403)
    modules = {link['modulo'] for link in help_context(user, '')['atalhos']}
    lessons = [list_lesson(module, definition) for module, definition in INTERNAL.items() if module in modules]
    if any(module.startswith('financeiro.') for module in modules):
        lessons.append(list_lesson('financeiro', ('financeiro', 'Consulta financeira', 'Lançamento', 'Pendente',
            [('Lançamento', 'DEMO-FIN-001'), ('Empresa', 'Empresa de Exemplo'), ('Valor fictício', 'R$ 250,00')],
            'Confira a empresa selecionada e o período antes de interpretar o lançamento. Este exercício não realiza pagamentos.')))
    # A useful introduction remains available even when no supported internal track is authorized.
    return lessons + deepcopy(PUBLIC)


def page():
    audience = request.args.get('publico', 'publico')
    lessons = catalog(audience, current_user)
    if audience == 'sistema':
        narration = lambda text: voice.offer(text, current_user)
    else:
        from app.modules.portal_cidadao.companion import offer
        narration = offer
    for lesson in lessons:
        for item in lesson['steps']:
            item['speech'] = narration(item['title'] + '. ' + item['body'])
    response = make_response(render_template('azul_tutorial.html', lessons=lessons))
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'none'; "
        "form-action 'none'; base-uri 'none'; frame-ancestors 'self'; sandbox allow-scripts"
    )
    return response
