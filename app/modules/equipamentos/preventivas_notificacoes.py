"""Emit personal reminders for the due date of each accessible preventive plan."""
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import url_for
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as insert_postgres
from sqlalchemy.dialects.sqlite import insert as insert_sqlite

from app.extensions import db
from app.models import Notificacao, PreventivaPlano
from app.modules.equipamentos.preventivas import plan_matches_equipment, situation, visible_equipment


_TITLES = {
    'proxima': 'Manutenção preventiva próxima',
    'hoje': 'Manutenção preventiva vence hoje',
    'atrasada': 'Manutenção preventiva em atraso',
}


def visible_preventive_plans(user):
    equipment = {item.id: item for item in visible_equipment(user)}
    if not equipment:
        return []
    plans = PreventivaPlano.query.filter(PreventivaPlano.equipamento_id.in_(equipment)).all()
    return [plan for plan in plans if plan_matches_equipment(plan, equipment[plan.equipamento_id])]


def sync_preventive_notifications(user, plans, *, now=None):
    now = now or datetime.now(ZoneInfo('America/Sao_Paulo')).replace(tzinfo=None)
    reminders = []
    for plan in plans:
        state = situation(plan, now.date())
        title = _TITLES.get(state['status'])
        if title is None:
            continue
        due = state['vencimento']
        equipment = plan.equipamento
        reminders.append({
            'usuario_id': user.id,
            'preventiva_plano_id': plan.id,
            'chave_preventiva': f'{user.id}:{plan.id}:{due.isoformat()}:{state["status"]}',
            'titulo': title,
            'mensagem': f'{equipment.renomacao} · {equipment.modelo}. Prazo em {due:%d/%m/%Y}, com intervalo de {plan.intervalo_dias} dias.',
            'link': url_for('main.preventiva_detalhe', equipamento_id=equipment.id),
            'criada_em': now,
        })

    current_keys = [reminder['chave_preventiva'] for reminder in reminders]
    db.session.execute(update(Notificacao).where(
        Notificacao.usuario_id == user.id,
        Notificacao.preventiva_plano_id.is_not(None),
        Notificacao.apagada_em.is_(None),
        Notificacao.chave_preventiva.not_in(current_keys),
    ).values(apagada_em=now))

    if reminders:
        insert = insert_postgres if db.session.get_bind().dialect.name == 'postgresql' else insert_sqlite
        db.session.execute(insert(Notificacao.__table__).values(reminders).on_conflict_do_nothing(
            index_elements=['chave_preventiva'],
        ))
    db.session.commit()
