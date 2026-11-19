"""Read-only Agro tools. Recheck module permissions and reuse screen row scopes."""
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import abort, url_for
from sqlalchemy import text
from app.extensions import db
from app.models import ClienteAgro, OrcamentoAgro, ContratoAgro, OrdemServicoAgro, RdMapeamentoAgro
from app.modules.agro import service
from app.modules.consultas.service import QueryError
from app.modules.gestao_ti.permissions import can_access_endpoint, has_permission, profile_code
from app.shared.access import is_admin_global_user

SOURCES = {
    'clientes': ('Clientes', 'agro_clientes_listar', ClienteAgro),
    'orcamentos': ('Orçamentos', 'agro_orcamentos_listar', OrcamentoAgro),
    'contratos': ('Contratos', 'agro_contratos_listar', ContratoAgro),
    'os': ('Ordens de serviço', 'agro_os_listar', OrdemServicoAgro),
    'mapeamentos': ('Mapeamentos', 'agro_orcamentos_template_mapeamento', OrcamentoAgro),
}


def is_pilot(user):
    return profile_code(user) == 'piloto_agro'


def endpoint(user, source):
    if is_pilot(user):
        return 'agro_piloto_mapeamentos_listar' if source == 'mapeamentos' else 'agro_piloto_os_listar'
    return SOURCES[source][1]


def allowed_sources(user):
    if is_pilot(user):
        pilot = getattr(user, 'piloto_agro', None)
        if not pilot or not getattr(pilot, 'ativo', False) or not getattr(pilot, 'equipe_agro_id', None):
            return []
        candidates = ('contratos', 'os', 'mapeamentos')
    else:
        candidates = SOURCES
    result = []
    for source in candidates:
        legacy = True if is_pilot(user) else (
            is_admin_global_user(user) if source == 'mapeamentos' else service.can_access_agro_panel(user))
        if not can_access_endpoint(user, 'main.' + endpoint(user, source), 'GET', legacy=legacy):
            continue
        if is_pilot(user) and source == 'contratos' and not has_permission(user, 'agro.contratos.consultar', legacy=True):
            continue
        result.append(source)
    return result


def tools(user):
    sources = allowed_sources(user)
    if not sources:
        return []
    return [
        {'type': 'function', 'name': 'buscar_agro', 'strict': True,
         'description': 'Consulta registros do Agro com contagem e até cinco exemplos. Use somente fonte, texto de busca q e status explicitamente pedidos. Não aceita datas, valores, equipe ou outros filtros: peça esclarecimento se exigidos, nunca descarte filtros. Clientes/orçamentos e mapeamentos administrativos não aceitam status. Contratos: EM ELABORACAO ou APROVADO; piloto vê somente aprovados sem OS. OS: PLANEJADA, EM EXECUCAO, CONCLUIDA, CANCELADA. RD do piloto: AGUARDANDO PREENCHIMENTO ou PREENCHIDO. Mapeamentos administrativos são orçamentos marcados para mapeamento e sem contrato. Não gera arquivos.',
         'parameters': {'type': 'object', 'additionalProperties': False, 'required': ['fonte', 'q', 'status'],
                        'properties': {'fonte': {'type': 'string', 'enum': sources},
                                       'q': {'type': 'string', 'description': 'Texto da busca da tela, ou vazio.'},
                                       'status': {'type': 'string', 'description': 'Status exato, ou vazio.'}}}},
        {'type': 'function', 'name': 'consultar_pendencias_agro', 'strict': True,
         'description': 'Resumo atual do Agro: mapeamentos pendentes, contratos aprovados sem OS e OS planejadas/em execução, somente nos módulos autorizados. Considera todas as datas; não é agenda de hoje nem aceita filtros.',
         'parameters': {'type': 'object', 'additionalProperties': False, 'required': [], 'properties': {}}},
    ]


def query_for(user, source, q='', status=''):
    # Called by both tools; never rely on tool visibility for authorization.
    if source not in allowed_sources(user):
        abort(403)
    if is_pilot(user):
        from app.modules.agro.routes import _build_piloto_agro_contratos_query, _build_piloto_agro_ordens_servico_query
        pilot = user.piloto_agro
        if source == 'contratos':
            return _build_piloto_agro_contratos_query(pilot, q).filter(~ContratoAgro.ordens_servico.any())
        if source == 'os':
            return _build_piloto_agro_ordens_servico_query(pilot, q, status)
        from app.modules.agro.service import build_piloto_mapeamentos_query
        return build_piloto_mapeamentos_query(pilot, q, status)
    if source == 'clientes':
        return service.build_clientes_agro_query(user, q)
    if source == 'orcamentos':
        return service.build_orcamentos_agro_query(user, q)
    if source == 'contratos':
        return service.build_contratos_agro_query(user, q, status)
    if source == 'os':
        return service.build_ordens_servico_agro_query(user, q, status)
    return service.build_orcamentos_agro_query(user, q, mapeamento='SIM').filter(~OrcamentoAgro.contrato.has())


def timeout():
    if db.engine.dialect.name == 'postgresql':
        db.session.execute(text("SET LOCAL statement_timeout = '15s'"))


def execute(user, plan):
    if (not isinstance(plan, dict) or set(plan) != {'fonte', 'q', 'status'}
            or any(not isinstance(v, str) or len(v) > 120 for v in plan.values())):
        raise QueryError('Informe apenas a fonte Agro, texto de busca e status; outros filtros não são suportados.')
    source, q, status = (plan[k].strip() for k in ('fonte', 'q', 'status'))
    if source not in allowed_sources(user):
        abort(403)
    statuses = {'contratos': (ContratoAgro.STATUS_APROVADO,) if is_pilot(user) else ContratoAgro.STATUS_OPTIONS,
                'os': OrdemServicoAgro.STATUS_OPTIONS,
                'mapeamentos': RdMapeamentoAgro.STATUS_OPTIONS if is_pilot(user) else ()}.get(source, ())
    if status and status not in statuses:
        raise QueryError('Status não suportado para essa consulta Agro. Opções: ' + (', '.join(statuses) or 'sem filtro de status') + '.')
    query = query_for(user, source, q, status).enable_eagerloads(False)
    model = RdMapeamentoAgro if is_pilot(user) and source == 'mapeamentos' else SOURCES[source][2]
    timeout()
    count = query.count()
    ids = query.with_entities(model.id).limit(5).all()
    label = SOURCES[source][0]
    answer = f'{label} no Agro: {count} registro(s) no seu acesso.'
    if q:
        answer += f'\nBusca textual: {q}.'
    if status:
        answer += f'\nStatus: {status}.'
    if is_pilot(user):
        answer += '\nEscopo: sua equipe vinculada.'
        if source == 'contratos':
            answer += ' Contratos aprovados aguardando OS.'
    elif source == 'mapeamentos':
        answer += '\nOrçamentos marcados para mapeamento, ainda sem contrato; podem incluir RD ainda não criada.'
    if ids:
        answer += '\nAté cinco exemplos (IDs): ' + ', '.join(f'#{row.id}' for row in ids) + '.'
    else:
        answer += '\nNenhum registro encontrado com esses filtros.'
    params = {k: v for k, v in {'q': q, 'status': status}.items() if v}
    if is_pilot(user) and source == 'contratos':
        params['status'] = 'AGUARDANDO_OS'
    answer += '\nAbra a lista para conferir os registros. Nenhum dado foi alterado.'
    return answer, [{'label': f'Abrir {label.lower()} ({count})', 'url': url_for('main.' + endpoint(user, source), **params)}]


def summarize(user):
    sources = allowed_sources(user)
    if not sources:
        abort(403)
    timeout()
    today = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    lines = [f'Pendências do Agro · consulta em {today:%d/%m/%Y} (São Paulo)',
             'Situação atual de todas as datas; não é uma agenda de serviços para hoje.']
    links = []
    if is_pilot(user):
        lines.append('Somente registros da sua equipe vinculada.')
    categories = []
    if 'mapeamentos' in sources:
        query = query_for(user, 'mapeamentos')
        if is_pilot(user):
            query = query.filter(RdMapeamentoAgro.status != RdMapeamentoAgro.STATUS_PREENCHIDO)
        else:
            query = query.filter(~OrcamentoAgro.rd_mapeamento.has(RdMapeamentoAgro.status == RdMapeamentoAgro.STATUS_PREENCHIDO))
        categories.append(('Mapeamentos pendentes' + (' (inclui RD não criada)' if not is_pilot(user) else ''), 'mapeamentos', query))
    if 'contratos' in sources:
        categories.append(('Contratos aprovados sem OS', 'contratos', query_for(user, 'contratos').filter(
            ContratoAgro.status == ContratoAgro.STATUS_APROVADO, ~ContratoAgro.ordens_servico.any())))
    if 'os' in sources:
        for status, label in [(OrdemServicoAgro.STATUS_PLANEJADA, 'OS planejadas'), (OrdemServicoAgro.STATUS_EM_EXECUCAO, 'OS em execução')]:
            categories.append((label, 'os', query_for(user, 'os', status=status)))
    for label, source, query in categories:
        lines.append(f'• {label}: {query.enable_eagerloads(False).count()}.')
        link = {'label': 'Conferir ' + SOURCES[source][0].lower(), 'url': url_for('main.' + endpoint(user, source))}
        if link not in links:
            links.append(link)
    if not categories:
        lines.append('Seu acesso permite consultas de cadastros, mas não inclui os módulos operacionais deste resumo.')
    lines.append('As listas abrem para conferência e podem incluir outras situações. Módulos sem permissão foram omitidos. Nenhum registro foi alterado.')
    return '\n'.join(lines), links
