"""Cadastro e consulta de controles, com alocação herdada do drone."""
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import ControlesRemotos, Drones, Equipamentos
from app.shared.access import apply_prefeitura_scope, get_user_prefeitura_id
from app.modules.equipamentos.service import _search_equipment


def drone_prefeitura(drone):
    tenant = drone.prefeitura_id
    team_tenant = drone.equipe.prefeitura_id if drone.equipe else None
    if tenant is not None and drone.equipe is not None and tenant != team_tenant:
        raise ValueError("O drone e sua equipe devem pertencer à mesma prefeitura. Revise o cadastro do drone.")
    tenant = tenant if tenant is not None else team_tenant
    if tenant is None:
        raise ValueError("O drone precisa ter prefeitura definida, diretamente ou pela equipe.")
    return tenant


def controle_query(user):
    drones = apply_prefeitura_scope(Drones.query, user, Drones.prefeitura_id).with_entities(Drones.id)
    return apply_prefeitura_scope(ControlesRemotos.query, user, ControlesRemotos.prefeitura_id).filter(
        ControlesRemotos.drone_id.in_(drones)
    )


def list_controles(user, q=None):
    return _search_equipment(controle_query(user), ControlesRemotos, q).options(
        selectinload(ControlesRemotos.drone_vinculado).selectinload(Drones.equipe),
    ).order_by(ControlesRemotos.renomacao, ControlesRemotos.id).all()


def validate_controle_form(data, *, user, existing=None):
    fields = ('modelo', 'renomacao', 'numero_serie', 'drone_id', 'status')
    form = {key: (data.get(key) or '').strip() for key in fields}
    form['status'] = form['status'] or 'Ativo'
    errors = {}
    for key, label in [('modelo', 'modelo'), ('renomacao', 'identificação'), ('numero_serie', 'número de série')]:
        if not form[key]:
            errors[key] = f'Informe o {label}.' if key != 'renomacao' else 'Informe a identificação.'
        elif len(form[key]) > 100:
            errors[key] = 'Use no máximo 100 caracteres.'
    if form['status'] not in ('Ativo', 'Inativo'):
        errors['status'] = 'Selecione Ativo ou Inativo.'
    if form['numero_serie']:
        query = Equipamentos.query.filter(func.lower(Equipamentos.numero_serie) == form['numero_serie'].lower())
        if existing is not None:
            query = query.filter(Equipamentos.id != existing.id)
        if query.first():
            errors['numero_serie'] = 'Este número de série já está cadastrado em outro equipamento.'
    drone = None
    tenant = None
    try:
        drone_id = int(form['drone_id'])
        drone = apply_prefeitura_scope(Drones.query, user, Drones.prefeitura_id).filter(Drones.id == drone_id).first()
        if drone is None:
            raise ValueError('Selecione um drone disponível para sua conta.')
        tenant = drone_prefeitura(drone)
        # Global editors must also preserve the tenant of an existing control.
        owner_tenant = existing.prefeitura_id if existing is not None else get_user_prefeitura_id(user)
        if existing is not None and owner_tenant is None:
            owner_tenant = drone_prefeitura(existing.drone_vinculado)
        if owner_tenant is not None and owner_tenant != tenant:
            raise ValueError('Controle e drone devem pertencer à mesma prefeitura.')
    except (TypeError, ValueError) as exc:
        errors['drone_id'] = str(exc) if drone is not None else 'Selecione um drone disponível para sua conta.'
    cleaned = {**form, 'drone': drone, 'prefeitura_id': tenant}
    return form, cleaned, errors


def save_controle(cleaned, *, existing=None):
    controle = existing if existing is not None else ControlesRemotos()
    for key in ('modelo', 'renomacao', 'numero_serie', 'status'):
        setattr(controle, key, cleaned[key])
    controle.drone_vinculado = cleaned['drone']
    controle.prefeitura_id = cleaned['prefeitura_id']
    # Only the drone owns the allocation; do not copy equipe_id to this row.
    controle.equipe_id = None
    db.session.add(controle)
    db.session.commit()
    return controle


def controle_form(controle):
    return {key: getattr(controle, key) or '' for key in ('modelo', 'renomacao', 'numero_serie', 'drone_id', 'status')}
