"""Organização e histórico de conferência das baterias."""
import re
from datetime import datetime, timezone

from app.extensions import db
from app.models import BateriaAtualizacao

BATTERY_FIELDS = ('modelo', 'renomacao', 'numero_serie', 'status', 'categoria', 'ano_fabricacao', 'ciclo', 'ultima_manutencao', 'drone_id')
FIELD_LABELS = dict(modelo='Modelo', renomacao='Identificação', numero_serie='Número de série', status='Status',
                    categoria='Categoria', ano_fabricacao='Ano de fabricação', ciclo='Ciclos',
                    ultima_manutencao='Última manutenção', drone_id='Drone vinculado')


def battery_snapshot(bateria):
    values = {}
    for key in BATTERY_FIELDS:
        value = getattr(bateria, key)
        values[key] = value.isoformat() if hasattr(value, 'isoformat') else value
    from app.models import Drones
    drone = db.session.get(Drones, bateria.drone_id) if bateria.drone_id else None
    owner = bateria.prefeitura_id or (bateria.equipe.prefeitura_id if bateria.equipe else None)
    target = (drone.prefeitura_id or (drone.equipe.prefeitura_id if drone.equipe else None)) if drone else None
    values["drone_rotulo"] = ((drone.renomacao + ' · S/N ' + (drone.numero_serie or 'Não informado'))
        if drone and (owner is None or owner == target) else ('Vínculo a revisar' if drone else 'Sem drone'))
    return values


def record_battery_update(bateria, *, user, before=None, tipo='edicao', confirm_cycles=False, cycles_observed_at=None):
    after = battery_snapshot(bateria)
    before = before or {}
    changes = {key: {'antes': before.get(key), 'depois': value} for key, value in after.items() if key in BATTERY_FIELDS and before.get(key) != value}
    if 'drone_id' in changes:
        changes['drone_id'].update(antes_texto=before.get('drone_rotulo', 'Sem drone'), depois_texto=after['drone_rotulo'])
    if not changes and tipo == 'edicao':
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    name = 'DJI' if tipo == 'sincronizacao_dji' else (getattr(user, 'nome_uvis', None) or getattr(user, 'login', None) or 'Não identificado')[:200]
    bateria.atualizado_em = now
    bateria.atualizado_por_id = getattr(user, 'id', None)
    if confirm_cycles or ('ciclo' in changes and after['ciclo'] is not None):
        bateria.ciclos_atualizados_em = cycles_observed_at or now
    elif 'ciclo' in changes:
        bateria.ciclos_atualizados_em = None
    db.session.add(BateriaAtualizacao(bateria=bateria, prefeitura_id=resolve_battery_tenant(existing=bateria),
        usuario_id=getattr(user, 'id', None), usuario_nome=name, criado_em=now, tipo=tipo, alteracoes=changes))
    return True


def parse_cycle_count(raw):
    if isinstance(raw, bool) or not isinstance(raw, (int, str)) or not re.fullmatch(r'\d+', str(raw)):
        raise ValueError('Informe um número inteiro de ciclos, igual ou maior que zero.')
    value = int(raw)
    if value > 2147483647:
        raise ValueError('O número de ciclos informado é muito alto.')
    return value


def battery_family(bateria, *, valid_drone=False):
    model = bateria.drone_vinculado.modelo if valid_drone else bateria.modelo
    model = (model or '').upper()
    if 'MATRICE' in model:
        return 'matrice'
    if re.search(r'\bT10\b', model):
        return 'agras_t10'
    return 'outros'


def battery_inventory(user, filters):
    from app.modules.equipamentos.service import list_baterias, list_drones_for_baterias, equipment_team_assignments
    batteries = list_baterias(user=user)
    assignments = equipment_team_assignments(batteries, user=user)
    drones = {drone.id: drone for drone in list_drones_for_baterias(user=user)}
    families, safe_drones = {}, {}
    teams, pilots, vehicles = {}, {}, {}
    for battery in batteries:
        parent = drones.get(battery.drone_id)
        valid = parent is not None and (battery.id in assignments or (
            battery.prefeitura_id is not None and battery.prefeitura_id == parent.prefeitura_id))
        safe_drones[battery.id] = parent if valid else None
        families[battery.id] = battery_family(battery, valid_drone=valid)
        allocation = assignments.get(battery.id)
        if allocation:
            teams[allocation['equipe'].id] = allocation['equipe']
            for pilot in (allocation['piloto'], allocation['auxiliar']):
                if pilot:
                    pilots[pilot.id] = pilot
            for vehicle in allocation['veiculos']:
                vehicles[vehicle.id] = vehicle
    counters = dict(total=len(batteries), matrice=sum(f=='matrice' for f in families.values()),
                    agras_t10=sum(f=='agras_t10' for f in families.values()),
                    sem_drone=sum(b.drone_id is None for b in batteries))
    rows = []
    term = filters.get('q', '').strip().casefold()
    for battery in batteries:
        allocation = assignments.get(battery.id)
        parent = safe_drones[battery.id]
        if term and not any(term in str(value or '').casefold() for value in (battery.renomacao, battery.modelo, battery.numero_serie)):
            continue
        if filters.get('familia') and filters['familia'] != families[battery.id]:
            continue
        if filters.get('status') and battery.status != filters['status']:
            continue
        if filters.get('drone_id') and (parent is None or str(parent.id) != filters['drone_id']):
            continue
        if filters.get('equipe_id') and (not allocation or str(allocation['equipe'].id) != filters['equipe_id']):
            continue
        if filters.get('responsavel_id') and (not allocation or filters['responsavel_id'] not in
                {str(p.id) for p in (allocation['piloto'], allocation['auxiliar']) if p}):
            continue
        if filters.get('veiculo_id') and (not allocation or filters['veiculo_id'] not in {str(v.id) for v in allocation['veiculos']}):
            continue
        if filters.get('vinculo') == 'sem_drone' and battery.drone_id is not None:
            continue
        if filters.get('vinculo') == 'sem_atualizacao' and battery.atualizado_em is not None:
            continue
        rows.append(battery)
    try:
        page = max(1, int(filters.get('page') or 1))
    except ValueError:
        page = 1
    total = len(rows)
    pages = max(1, (total+14)//15)
    page = min(page, pages)
    return dict(baterias=rows[(page-1)*15:page*15], responsabilidades=assignments, familias=families,
                drones_seguros=safe_drones, counters=counters, total=total, page=page, pages=pages,
                filter_drones=sorted({d.id:d for d in safe_drones.values() if d}.values(), key=lambda d:d.renomacao),
                filter_equipes=sorted(teams.values(), key=lambda t:t.nome_equipe),
                filter_pilotos=sorted(pilots.values(), key=lambda p:p.nome_piloto),
                filter_veiculos=sorted(vehicles.values(), key=lambda v:v.placa))


def resolve_battery_tenant(*, owner=None, drone=None, existing=None):
    from app.modules.equipamentos.controles import drone_prefeitura
    if existing is not None:
        owner = existing.prefeitura_id
        if owner is None and existing.drone_vinculado is not None:
            owner = drone_prefeitura(existing.drone_vinculado)
        if owner is None and existing.equipe is not None:
            owner = existing.equipe.prefeitura_id
    if drone is not None:
        target = drone_prefeitura(drone)
        if owner is not None and target != owner:
            raise ValueError('Bateria e drone devem pertencer à mesma prefeitura.')
        owner = target
    if owner is None:
        raise ValueError('Defina a prefeitura da bateria por um drone válido ou pela sua conta.')
    return owner
