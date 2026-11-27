"""Route weekly fleet defects to the maintenance users who can open an OS."""
from flask import url_for
from sqlalchemy import select

from app.extensions import db
from app.models import ChecklistSemanalVeiculo, Equipe, Notificacao, Usuario, Veiculos
from app.modules.agenda_notificacoes import agora_brasilia_naive, criar_notificacao
from app.modules.equipamentos.service import (
    can_open_maintenance_os, maintenance_prefeitura_id, maintenance_vehicles_query,
)
from app.shared.access import get_user_prefeitura_id, normalize_role


def visible_vehicle_checklists(user):
    vehicle_ids = maintenance_vehicles_query(user).with_entities(Veiculos.id)
    query = ChecklistSemanalVeiculo.query.filter(ChecklistSemanalVeiculo.veiculo_id.in_(vehicle_ids))
    tenant = get_user_prefeitura_id(user)
    if tenant is not None:
        query = query.filter(
            ChecklistSemanalVeiculo.equipe_id.is_(None)
            | ChecklistSemanalVeiculo.equipe.has(Equipe.prefeitura_id == tenant)
        )
    return query


def checklist_defects(checklist):
    from app.modules.piloto_checklists.service import (
        CHECKLIST_VEICULO_BOOL_LABELS, CHECKLIST_VEICULO_TEXT_GROUPS,
    )

    fields = {field for field, _ in CHECKLIST_VEICULO_BOOL_LABELS if getattr(checklist, field) is False}
    if not fields:
        return [], ""
    defects = [label for field, label in CHECKLIST_VEICULO_BOOL_LABELS if field in fields]
    descriptions = [
        value for field, group in CHECKLIST_VEICULO_TEXT_GROUPS.items()
        if fields.intersection(group) and (value := getattr(checklist, field))
    ]
    report = f"Itens com defeito no checklist semanal: {', '.join(defects)}."
    if descriptions:
        report += "\n" + "\n".join(descriptions)
    return defects, report[:20000]


def receives_checklist_alerts(user):
    return normalize_role(user.tipo_usuario) == "manutencao" and can_open_maintenance_os(user)


def sync_vehicle_checklist_alerts(checklist):
    # A second save of the same weekly entry must see the alerts from the first.
    db.session.flush()
    db.session.execute(select(ChecklistSemanalVeiculo.id).where(
        ChecklistSemanalVeiculo.id == checklist.id,
    ).with_for_update()).scalar_one()
    existing = {
        notification.usuario_id: notification
        for notification in Notificacao.query.filter_by(checklist_veiculo_id=checklist.id).all()
    }
    defects, report = checklist_defects(checklist)
    now = agora_brasilia_naive()
    if not defects:
        for notification in existing.values():
            notification.apagada_em = notification.apagada_em or now
            notification.mensagem = ""
        return

    vehicle = checklist.veiculo
    tenant = maintenance_prefeitura_id(vehicle)
    if tenant is None or (checklist.equipe and checklist.equipe.prefeitura_id != tenant):
        return
    message = report if len(report) <= 400 else report[:399].rstrip() + "…"
    for user in Usuario.query.filter_by(tipo_usuario="manutencao", prefeitura_id=tenant).all():
        if not receives_checklist_alerts(user):
            continue
        if not maintenance_vehicles_query(user).filter(Veiculos.id == vehicle.id).with_entities(Veiculos.id).first():
            continue
        plate = vehicle.placa or vehicle.renomacao
        title = f"Pendências no checklist · {plate}"
        link = url_for("main.equipamento_manutencao_nova", checklist_veiculo_id=checklist.id)
        notification = existing.get(user.id)
        if notification is None:
            notification = criar_notificacao(user.id, title, message, link, commit=False)
            notification.checklist_veiculo_id = checklist.id
        elif notification.mensagem != message:
            notification.titulo = title
            notification.mensagem = message
            notification.criada_em = now
            notification.lida_em = notification.apagada_em = None
