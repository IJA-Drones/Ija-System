"""Validated search plans: only server-owned filters and destinations."""
from datetime import date
from flask import abort, url_for
from sqlalchemy import text
from app.extensions import db
from app.modules.admin_dashboard.service import build_admin_dashboard_query, can_access_admin_panel
from app.modules.gestao_ti.permissions import can_access_endpoint
from app.modules.consultas.service import QueryError

STATUSES = ['', 'PENDENTE', 'EM ANÁLISE', 'APROVADO', 'APROVADO COM RECOMENDAÇÕES', 'NEGADO', 'CONCLUÍDO']
FIELDS = ('status', 'bairro', 'endereco', 'protocolo', 'inicio', 'fim')


def allowed(user):
    return can_access_endpoint(user, 'main.admin_dashboard', 'GET', legacy=can_access_admin_panel(user))


def tools(user):
    if not allowed(user):
        return []
    return [{'type':'function', 'name':'buscar_solicitacoes', 'strict':True,
        'description':'Busca solicitações municipais com filtros combinados. Retorna contagem e atalho para lista paginada. Bairro é nome exato; endereço/protocolo são buscas textuais. Datas filtram AGENDAMENTO. Não cobre OS, canceladas, Agro, equipe, prioridade, prefeitura escolhida ou outros filtros. Se o pedido exigir filtro não suportado, peça esclarecimento, nunca descarte esse filtro.',
        'parameters':{'type':'object', 'additionalProperties':False, 'required':list(FIELDS),
            'properties':{key:({'type':'string','enum':STATUSES} if key=='status' else
                {'type':'string','description': 'YYYY-MM-DD ou vazio.' if key in ('inicio','fim') else 'Texto solicitado ou vazio para não filtrar.'}) for key in FIELDS}}}]


def execute(user, plan):
    if not allowed(user):
        abort(403)
    if (not isinstance(plan, dict) or set(plan) != set(FIELDS)
            or any(not isinstance(v,str) or len(v)>120 for v in plan.values())
            or plan['status'] not in STATUSES):
        raise QueryError('Filtros de busca inválidos. Informe status, bairro, endereço, protocolo ou período de agendamento.')
    plan = {k:v.strip() for k,v in plan.items()}
    try:
        for key in ('inicio','fim'):
            if plan[key]:
                plan[key] = date.fromisoformat(plan[key]).isoformat()
        if plan['inicio'] and plan['fim'] and plan['inicio'] > plan['fim']:
            raise ValueError()
    except ValueError:
        raise QueryError('Informe um período de agendamento válido, com início anterior ao fim.') from None
    query = build_admin_dashboard_query(user, plan['status'], '', '', '', plan['protocolo'],
        filtro_endereco=plan['endereco'], filtro_bairro=plan['bairro'],
        filtro_data_ini=plan['inicio'], filtro_data_fim=plan['fim']).enable_eagerloads(False)
    if db.engine.dialect.name == 'postgresql':
        db.session.execute(text("SET LOCAL statement_timeout = '15s'"))
    count = query.count()
    labels = {'status':'Status', 'bairro':'Bairro (exato)', 'endereco':'Endereço', 'protocolo':'Protocolo/ID', 'inicio':'Agendamento a partir de', 'fim':'Agendamento até'}
    description = '\n'.join(f'{labels[k]}: {v}' for k,v in plan.items() if v) or 'Todas as solicitações não canceladas acessíveis ao seu usuário.'
    answer = f'Encontrei {count} solicitações municipais.\n{description}\n\n'
    answer += 'Abra a lista para conferir e refinar os filtros. Ela mostra 25 registros por página e atualiza os dados ao abrir.' if count else 'Não encontrei registros com esses filtros no seu acesso. Você pode ajustar o bairro, status ou período.'
    params = {key:plan[field] for key,field in [('status','status'),('bairro','bairro'),('endereco','endereco'),('protocolo','protocolo'),('data_ini','inicio'),('data_fim','fim')] if plan[field]}
    return answer, [{'label':f'Abrir lista filtrada ({count})', 'url':url_for('main.admin_dashboard', per_page=25, **params)}]
