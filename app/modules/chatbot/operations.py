"""Read-only municipal attention summary using the dashboard's existing scope."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import url_for
from sqlalchemy import func, case, text

from app.extensions import db
from app.models import Solicitacao, AuditoriaUsuario, FeedbackTopico
from app.modules.admin_dashboard.service import build_admin_dashboard_query, can_access_admin_panel
from app.modules.gestao_ti.permissions import can_access_endpoint


def allowed(user):
    if not getattr(user, 'trabalha_oceano_azul', False):
        return False
    if getattr(user, 'tipo_usuario', '') == 'dev':
        return can_access_endpoint(user, 'main.dev_dashboard', 'GET', legacy=True)
    return can_access_endpoint(user, 'main.admin_dashboard', 'GET', legacy=can_access_admin_panel(user))


def tools(user):
    if not allowed(user):
        return []
    return [{'type': 'function', 'name': 'consultar_atencao_hoje', 'strict': True,
             'description': 'Consulta a atenção de hoje para funcionários da Oceano Azul: para DEV, falhas do Painel Dev e bugs reportados autorizados; para outros perfis, solicitações municipais pendentes e aprovadas sem equipe. Use quando perguntarem o que precisa de atenção ou resumo do dia. Não cobre Agro, agenda completa ou outros períodos/filtros.',
             'parameters': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}}]


def summarize(user):
    # Always recheck here: a model tool call is not an authorization grant.
    if not allowed(user):
        return 'Este resumo é exclusivo para usuários que trabalham na Oceano Azul e têm acesso ao painel correspondente.', []
    if getattr(user, 'tipo_usuario', '') == 'dev':
        return summarize_dev(user)
    today = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    query = build_admin_dashboard_query(user, '', '', '', '', '').enable_eagerloads(False)
    if db.engine.dialect.name == 'postgresql':
        db.session.execute(text("SET LOCAL statement_timeout = '15s'"))
    from app.modules.admin_dashboard.attention import criteria, LABELS
    filters = criteria(today)
    categories = [(LABELS[key], condition) for key, condition in filters.items()]
    counts = query.with_entities(*[func.coalesce(func.sum(case((condition, 1), else_=0)), 0)
                                  for _, condition in categories]).one()
    lines = [f'Resumo de atenção · {today:%d/%m/%Y} (horário de São Paulo)',
             'Solicitações municipais acessíveis ao seu usuário:']
    links, seen = [], set()
    for key, (label, condition), count in zip(filters, categories, counts):
        lines.append(f'• {label}: {count}.')
        if count:
            links.append({'label': f'Ver todas ({count}) · {label}',
                          'url': url_for('main.admin_dashboard', atencao=key, referencia=today.isoformat(), per_page=25)})
            rows = query.filter(condition).with_entities(Solicitacao.id).order_by(
                Solicitacao.data_agendamento, Solicitacao.id).limit(2).all()
            lines.append('  Exemplos: ' + ', '.join(f'#{row.id}' for row in rows) + '.')
            for row in rows:
                if row.id not in seen:
                    seen.add(row.id)
                    links.append({'label': f'Abrir solicitação #{row.id}',
                                  'url': url_for('main.admin_dashboard', protocolo=str(row.id))})
    lines.append('\nMostro até dois exemplos por grupo. Use Ver todas para navegar por páginas e refinar pelos filtros de bairro/endereço, unidade e período.\nAs contagens podem se sobrepor. Agendamento passado indica revisão necessária; não comprova atraso na execução. Este resumo não cobre todos os módulos nem substitui a Agenda. Nenhum dado foi alterado.')
    return '\n'.join(lines), links


def summarize_dev(user):
    # This function may also be called outside the tool dispatcher.
    if getattr(user, 'tipo_usuario', '') != 'dev' or not allowed(user):
        return 'Seu acesso não permite consultar o resumo DEV.', []
    from app.modules.dev_dashboard.service import _failure_filter
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if db.engine.dialect.name == 'postgresql':
        db.session.execute(text("SET LOCAL statement_timeout = '15s'"))
    failures = AuditoriaUsuario.query.filter(_failure_filter())
    recent = failures.filter(AuditoriaUsuario.criado_em >= now - timedelta(hours=24)).count()
    server = failures.filter(AuditoriaUsuario.criado_em >= now - timedelta(days=7),
                             AuditoriaUsuario.status_code >= 500).count()
    lines = ['Sua atenção como DEV · Oceano Azul',
             f'• Falhas HTTP do Painel Dev nas últimas 24 horas: {recent}.',
             f'• Erros de servidor (HTTP 5xx) nos últimos 7 dias: {server}.']
    links = [{'label': 'Abrir Painel Dev', 'url': url_for('main.dev_dashboard')}]
    if can_access_endpoint(user, 'main.feedback_listar', 'GET', legacy=True):
        from app.modules.feedback.service import build_feedback_query, FEEDBACK_ACTIVE_STATUSES
        bugs = build_feedback_query(user).filter(FeedbackTopico.categoria == 'bug',
                    FeedbackTopico.setor_suporte == 'tecnico', FeedbackTopico.status.in_(FEEDBACK_ACTIVE_STATUSES))
        lines.append(f'• Bugs reportados ainda ativos, em qualquer data: {bugs.count()}.')
        links.append({'label': 'Ver bugs reportados', 'url': url_for('main.feedback_listar')})
    lines.append('\nFalhas reconhecidas/limpas e expirações normais de sessão seguem os critérios do Painel Dev. As janelas podem se sobrepor; ocorrências não significam bugs distintos. Nenhum registro foi alterado.')
    return '\n'.join(lines), links
