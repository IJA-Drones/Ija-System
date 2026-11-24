"""Short, read-only DEV briefing for explicit playback after login."""
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import case, func

from app.extensions import db
from app.models import AuditoriaUsuario, FeedbackTopico
from app.modules.chatbot import dev_health, voice
from app.modules.dev_dashboard.service import _failure_filter
from app.modules.feedback.service import build_feedback_query, FEEDBACK_ACTIVE_STATUSES
from app.modules.gestao_ti.permissions import can_access_endpoint

INVITATION = 'Gostaria de ouvir suas pendências de hoje?'


def allowed(user):
    return (dev_health.allowed(user)
            and can_access_endpoint(user, 'main.dev_dashboard_briefing', 'GET', legacy=True)
            and can_access_endpoint(user, 'main.azul_help', 'POST', legacy=True))


def build(user):
    if not allowed(user):
        raise PermissionError('O resumo de desenvolvimento exige acesso DEV ao painel, aos erros e à Azul.')
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = now - timedelta(hours=24)
    failures = AuditoriaUsuario.query.filter(_failure_filter(), AuditoriaUsuario.criado_em >= start,
                                             AuditoriaUsuario.criado_em <= now)
    total = failures.count()
    server = failures.filter(AuditoriaUsuario.status_code >= 500).count()
    groups = failures.with_entities(
        AuditoriaUsuario.endpoint, AuditoriaUsuario.path, AuditoriaUsuario.metodo, AuditoriaUsuario.status_code,
        func.count(AuditoriaUsuario.id).label('total'), func.max(AuditoriaUsuario.id).label('example_id'),
    ).group_by(AuditoriaUsuario.endpoint, AuditoriaUsuario.path, AuditoriaUsuario.metodo, AuditoriaUsuario.status_code).order_by(
        case((AuditoriaUsuario.status_code >= 500, 1), else_=0).desc(),
        func.count(AuditoriaUsuario.id).desc(), func.max(AuditoriaUsuario.id).desc(),
    ).limit(3).all()
    lines = [f'Este é o seu resumo de desenvolvimento das últimas 24 horas. Houve {total} falha'
             + (' HTTP' if total == 1 else 's HTTP') + f', sendo {server} de servidor.']
    labels = {'main.admin_dashboard': 'painel administrativo', 'main.financeiro_central': 'central financeira',
              'main.admin_logs_usuarios': 'auditoria de usuários', 'main.admin_historico_os': 'histórico de ordens de serviço',
              'main.ortomosaico_arquivo': 'arquivo de ortomosaico', 'main.azul_help': 'ajuda da Azul',
              'main.os_upload_complementary_stream': 'upload complementar da ordem de serviço',
              'main.video_upload_session_chunk': 'envio de partes de vídeo'}
    links = []
    for row in groups:
        known = row.endpoint in current_app.view_functions
        label = labels.get(row.endpoint) or (row.endpoint.split('.')[-1].replace('_', ' ') if known else 'endereço sem rota registrada')
        lines.append(f'HTTP {row.status_code}, em {label}: {row.total} ocorrência' + ('.' if row.total == 1 else 's.'))
        links.append({'label': f'Investigar #{row.example_id} · HTTP {row.status_code}', 'url': f'/dev?erro={row.example_id}'})
    bug_count = None
    if can_access_endpoint(user, 'main.feedback_listar', 'GET', legacy=True):
        bug_count = build_feedback_query(user).filter(
            FeedbackTopico.categoria == 'bug', FeedbackTopico.setor_suporte == 'tecnico',
            FeedbackTopico.status.in_(FEEDBACK_ACTIVE_STATUSES), FeedbackTopico.criado_em >= start,
            FeedbackTopico.criado_em <= now,
        ).count()
        lines.append('Nenhum novo bug técnico reportado nesse período continua em aberto.' if not bug_count else
                     'Há também 1 novo bug técnico reportado nesse período e ainda em aberto.' if bug_count == 1 else
                     f'Há também {bug_count} novos bugs técnicos reportados nesse período e ainda em aberto.')
        links.append({'label': 'Consultar bugs reportados', 'url': '/feedback'})
    if server:
        lines.append('Comece pelas falhas de servidor. Abra os registros indicados para conferir os logs e a causa antes de corrigir.')
    elif total:
        lines.append('Comece pelo grupo mais recorrente e confira se a resposta foi esperada antes de tratar como defeito.')
    elif bug_count:
        lines.append('Comece pelos bugs reportados. Não há falhas HTTP auditadas nessa janela pelos critérios do painel.')
    else:
        lines.append('Não há falhas HTTP auditadas nessa janela pelos critérios do painel. Confira também as verificações de infraestrutura.')
    lines.append('Os números contam ocorrências; um mesmo problema pode gerar mais de uma.')
    text = '\n\n'.join(lines)
    return {'answer': text, 'speech': voice.offer(text, user), 'links': links,
            'metrics': {'errors_24h': total, 'server_errors_24h': server, 'new_open_bugs_24h': bug_count},
            'generated_at': now.replace(tzinfo=timezone.utc).isoformat()}
