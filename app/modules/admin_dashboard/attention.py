"""Shared criteria for Azul counts and the paginated municipal panel."""
from datetime import date
from flask import abort
from app.models import Solicitacao

LABELS = {
    'hoje': 'Pendentes/em análise agendadas para hoje',
    'anteriores': 'Pendentes/em análise com agendamento anterior à referência',
    'sem_equipe': 'Aprovadas sem equipe, em qualquer data',
}


def criteria(day):
    pending = Solicitacao.status.in_(['PENDENTE', 'EM ANALISE', 'EM ANÁLISE'])
    return {
        'hoje': pending & (Solicitacao.data_agendamento == day),
        'anteriores': pending & (Solicitacao.data_agendamento < day),
        'sem_equipe': Solicitacao.status.in_(['APROVADO', 'APROVADO COM RECOMENDACOES', 'APROVADO COM RECOMENDAÇÕES']) & Solicitacao.equipe_id.is_(None),
    }


def parse(args):
    group = args.get('atencao', '')
    if not group:
        return None
    try:
        day = date.fromisoformat(args.get('referencia', ''))
    except (ValueError, TypeError):
        abort(400, description='Referência do resumo inválida. Peça um novo resumo à Azul.')
    if group not in LABELS:
        abort(400, description='Grupo de atenção inválido.')
    return {'group': group, 'day': day, 'label': LABELS[group]}


def apply(query, selection):
    return query.filter(criteria(selection['day'])[selection['group']]) if selection else query
