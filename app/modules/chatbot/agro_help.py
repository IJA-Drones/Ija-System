"""Reviewed screen guidance; never claims to have read or changed a record."""
from urllib.parse import urlsplit
from flask import current_app, request
from werkzeug.exceptions import HTTPException
from app.modules.gestao_ti.permissions import can_access_endpoint
from app.modules.agro.service import can_edit_agro_panel
from app.modules.chatbot.agro import is_pilot
from app.modules.chatbot.service import normalize_chatbot_text


def topic(module, title, question, answer):
    return {'id': module, 'module': 'agro.' + module, 'title': title, 'question': question,
            'answer': answer + '\nAs ações disponíveis dependem das permissões da sua conta. A Azul não altera registros pelo chat.'}


TOPICS = [
    topic('clientes', 'Clientes do Agro', 'Como consultar clientes no Agro?',
          'Em Clientes, use a busca para localizar o cadastro. Confira os dados antes de cadastrar outro cliente. '
          'Para criar ou editar, use a ação disponível na tela e revise os campos obrigatórios antes de salvar.'),
    topic('comercial', 'Orçamentos do Agro', 'Como usar os orçamentos do Agro?',
          'Em Orçamentos, localize o cliente ou a propriedade pela busca. Abra o orçamento e confira serviço, cultura, '
          'área e valores. Revise a necessidade de mapeamento e os dados antes de seguir para o contrato. '
          'O PDF é gerado pelas ações da tela; este pacote da Azul não exporta documentos do Agro.'),
    topic('contratos', 'Contratos do Agro', 'Como acompanhar contratos no Agro?',
          'Em Contratos, use a busca e o filtro de status. Confira cliente, propriedade, equipe e situação. '
          'Contrato aprovado sem OS é uma pendência de preparação operacional; não significa que o serviço já foi executado. '
          'Abra o registro para conferir quais ações estão liberadas.'),
    topic('mapeamentos', 'Mapeamentos do Agro', 'Como acompanhar mapeamentos no Agro?',
          'No administrativo, Mapeamentos mostra orçamentos marcados para mapeamento e ainda sem contrato. '
          'Confira a equipe responsável e a RD vinculada; pode haver RD ainda não criada. '
          'Para o piloto, Mapeamentos mostra as RDs da equipe vinculada, com busca e filtro de status. '
          'Abra a RD para revisar e preencher os dados solicitados. PREENCHIDO indica que a etapa foi preenchida.'),
    topic('os', 'Ordens de serviço do Agro', 'Como acompanhar OS no Agro?',
          'Em Ordens de serviço, use a busca e o status para localizar a operação. Confira propriedade, equipe, piloto, '
          'equipamentos e dados da execução. PLANEJADA e EM EXECUCAO identificam ordens ainda ativas; '
          'CONCLUIDA e CANCELADA são situações diferentes. Para pilotos, a lista segue a equipe vinculada e também '
          'pode mostrar contratos aprovados aguardando OS. Revise o preenchimento antes de concluir pela tela.'),
]


def available(context):
    modules = {link['modulo'] for link in context['atalhos']}
    return [item for item in TOPICS if item['module'] in modules]


def current_topic(context, page):
    try:
        parsed = urlsplit(page)
    except ValueError:
        return None
    if parsed.netloc or parsed.scheme:
        return None
    path = parsed.path
    link = next((link for link in context['atalhos'] if link['url'] == path), None)
    module = link['modulo'] if link else context.get('modulo_formulario_agro')
    return next((item for item in available(context) if item['module'] == module), None)


def match(message, context, page=''):
    normalized = normalize_chatbot_text(message).strip(' ?!.')
    if normalized in {'como usar esta tela', 'ajuda nesta tela', 'me explique esta tela'}:
        return current_topic(context, page)
    return next((item for item in available(context)
                 if normalize_chatbot_text(item['question']).strip(' ?!.') == normalized), None)


def suggestions(context, page):
    current = current_topic(context, page)
    items = available(context)
    return (([current] if current else []) + [item for item in items if item != current])[:3]


FORM_MODULES = {
    'agro_cliente_novo': 'clientes', 'agro_cliente_editar': 'clientes',
    'agro_orcamento_novo': 'comercial', 'agro_orcamento_editar': 'comercial',
    'agro_contrato_editar': 'contratos', 'agro_rd_mapeamento_editar': 'mapeamentos',
    'agro_piloto_rd_mapeamento': 'mapeamentos', 'agro_os_nova': 'os', 'agro_os_editar': 'os',
}


def form_module(user, page):
    """Resolve only known GET screens, never read an ID or infer record access."""
    try:
        parsed = urlsplit(page)
    except ValueError:
        return None
    if parsed.netloc or parsed.scheme or not parsed.path.startswith('/'):
        return None
    try:
        endpoint, args = current_app.url_map.bind_to_environ(request.environ).match(parsed.path, method='GET')
    except HTTPException:
        return None
    module = FORM_MODULES.get(endpoint.removeprefix('main.'))
    if not module:
        return None
    pilot_screen = endpoint in {'main.agro_piloto_rd_mapeamento', 'main.agro_os_nova', 'main.agro_os_editar'}
    legacy = (pilot_screen and is_pilot(user)) or can_edit_agro_panel(user)
    if can_access_endpoint(user, endpoint, 'GET', args=args, legacy=legacy):
        return 'agro.' + module
    return None
