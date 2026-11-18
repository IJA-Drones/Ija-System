"""Equipment suggestions and historical identification, using only in-memory SQLite."""
import re
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import (ChecklistSemanalDrone, ChecklistSemanalVeiculo, Drones, Equipe, EquipePiloto,
                        OrdemServico, Prefeitura, Solicitacao, Usuario, Veiculos)
from app.modules.piloto_checklists.service import build_piloto_checklist_context
from test_sprint1_workflows import app, client, execution_form  # noqa: F401


def drone(tag, **overrides):
    values = dict(status='Ativo', modelo=f'Modelo {tag}', renomacao=f'Drone {tag}',
                  categoria='Pulverizacao', numero_serie=f'SERIE-{tag}',
                  registro_anatel=f'ANATEL-{tag}', registro_anac=f'ANAC-{tag}',
                  pmd_kg=25, prefeitura_id=1, equipe_id=1)
    values.update(overrides)
    item = Drones(**values)
    db.session.add(item)
    db.session.flush()
    return item


def vehicle(tag, **overrides):
    values = dict(status='Ativo', modelo=f'Veiculo {tag}', renomacao=f'Veiculo {tag}',
                  placa=tag, frota='PROPRIA', operacao='PMSP', km_atual=1200,
                  prefeitura_id=1, equipe_id=1)
    values.update(overrides)
    item = Veiculos(**values)
    db.session.add(item)
    db.session.flush()
    return item


@pytest.fixture
def equipment(app):
    with app.app_context():
        db.session.add(Prefeitura(id=2, nome='Outro municipio ficticio', slug='outro-teste'))
        db.session.add_all([
            Equipe(id=2, nome_equipe='Outra equipe ficticia', prefeitura_id=1, ativa=True),
            Equipe(id=3, nome_equipe='Equipe de outro municipio', prefeitura_id=2, ativa=True),
        ])
        db.session.get(Solicitacao, 1).status = 'APROVADO'
        p = drone('P')
        m = drone('M', categoria='Monitoramento')
        v = vehicle('TEST001')
        db.session.commit()
        yield SimpleNamespace(app=app, p=p, m=m, v=v, pilot=db.session.get(Usuario, 3),
                              request=db.session.get(Solicitacao, 1))


def selected(response, field):
    markup = response.get_data(as_text=True)
    match = re.search(r'<select\b[^>]*id="' + field + r'"[^>]*>(.*?)</select>', markup, re.S)
    assert match, field
    values = re.findall(r'<option\b[^>]*value="([^"]*)"[^>]*\bselected\b', match[1])
    return values


@pytest.mark.parametrize('uid,path', [(3, '/piloto/os/1/formulario'), (1, '/admin/os/1/formulario')])
def test_os_suggests_unique_team_drone_per_category_without_saving(equipment, uid, path):
    e = equipment
    response = client(e.app, uid).get(path)
    assert response.status_code == 200
    assert selected(response, 'drone_id') == [str(e.p.id)]
    assert selected(response, 'drone_monitoramento_id') == [str(e.m.id)]
    markup = response.get_data(as_text=True)
    assert markup.count('data-auto-selected="true"') == 2
    for suffix in ('pulv', 'monit'):
        for field in ('serie', 'modelo', 'renomacao', 'registro_anatel', 'registro_anac'):
            assert f'id="drone_{field}_{suffix}"' in markup
    assert OrdemServico.query.count() == 0
    assert not db.session.new and not db.session.dirty


def test_os_leaves_ambiguous_category_for_manual_choice(equipment):
    e = equipment
    drone('P2')
    db.session.commit()
    response = client(e.app, 3).get('/piloto/os/1/formulario')
    assert selected(response, 'drone_id') == []
    assert selected(response, 'drone_monitoramento_id') == [str(e.m.id)]


def test_os_never_suggests_inactive_foreign_team_municipality_or_wrong_category(equipment):
    e = equipment
    e.p.status = 'Inativo'
    drone('FOREIGN-TEAM', equipe_id=2)
    drone('FOREIGN-CITY', equipe_id=1, prefeitura_id=2)
    drone('OTHER-KIND', categoria='Outro equipamento')
    db.session.commit()
    response = client(e.app, 3).get('/piloto/os/1/formulario')
    assert selected(response, 'drone_id') == []
    assert 'Drone FOREIGN-' not in response.get_data(as_text=True)


@pytest.mark.parametrize('situation,pulv,monit', [
    ('NENHUM VOO REALIZADO', False, False), ('APENAS MONITORADO', False, True),
])
def test_os_suggestions_respect_no_flight_and_monitoring(equipment, situation, pulv, monit):
    e = equipment
    db.session.add(OrdemServico(solicitacao_id=1, equipe_id=1, situacao_aplicacao=situation))
    db.session.commit()
    response = client(e.app, 3).get('/piloto/os/1/formulario')
    assert selected(response, 'drone_id') == ([str(e.p.id)] if pulv else [])
    assert selected(response, 'drone_monitoramento_id') == ([str(e.m.id)] if monit else [])


@pytest.mark.parametrize('uid,path', [(3, '/piloto/os/1/formulario'), (1, '/admin/os/1/formulario'),
                                    (2, '/uvis/os/1/formulario')])
def test_historical_or_read_only_os_does_not_infer_missing_equipment(equipment, uid, path):
    e = equipment
    e.request.status = 'CONCLUÍDO'
    db.session.add(OrdemServico(solicitacao_id=1, equipe_id=1))
    db.session.commit()
    response = client(e.app, uid).get(path)
    assert response.status_code == 200
    assert selected(response, 'drone_id') == []
    assert selected(response, 'drone_monitoramento_id') == []
    assert 'data-auto-selected="true"' not in response.get_data(as_text=True)


def test_os_does_not_replace_legacy_manual_identification(equipment):
    e = equipment
    db.session.add(OrdemServico(solicitacao_id=1, equipe_id=1,
                               prefixo_aeronave_pulverizacao='IDENTIFICACAO ANTIGA'))
    db.session.commit()
    response = client(e.app, 3).get('/piloto/os/1/formulario')
    assert selected(response, 'drone_id') == []
    assert 'value="IDENTIFICACAO ANTIGA"' in response.get_data(as_text=True)


@pytest.mark.parametrize('submitted', ['unchanged', 'absent'])
def test_os_retains_recorded_drone_and_snapshot_after_registration_changes(equipment, submitted):
    e = equipment
    order = OrdemServico(solicitacao_id=1, equipe_id=1, drone_id=e.p.id,
        drone_denominacao='Aeronave registrada', drone_modelo='Modelo registrado',
        drone_numero_serie='Serie registrada', drone_registro_anatel='Anatel registrada',
        drone_registro_anac='Anac registrada', prefixo_aeronave_pulverizacao='Prefixo registrado')
    db.session.add(order)
    e.p.renomacao = 'Cadastro atual de outra equipe'
    e.p.status = 'Inativo'
    e.p.equipe_id = 2
    db.session.commit()
    c = client(e.app, 3)
    response = c.get('/piloto/os/1/formulario')
    assert selected(response, 'drone_id') == [str(e.p.id)]
    assert 'registrado nesta OS' in response.get_data(as_text=True)
    assert 'Cadastro atual de outra equipe' not in response.get_data(as_text=True)
    fields = execution_form('MONITORADO E LARVICIDA APLICADO')
    if submitted == 'unchanged':
        fields['drone_id'] = str(e.p.id)
    assert c.post('/piloto/os/1/formulario', data=fields).status_code == 302
    db.session.refresh(order)
    assert order.drone_id == e.p.id
    assert order.drone_denominacao == 'Aeronave registrada'
    assert order.drone_modelo == 'Modelo registrado'
    assert order.drone_numero_serie == 'Serie registrada'
    assert order.drone_registro_anatel == 'Anatel registrada'
    assert order.drone_registro_anac == 'Anac registrada'
    assert order.prefixo_aeronave_pulverizacao == 'Prefixo registrado'


def test_os_saves_selected_equipment_only_on_submit_and_clears_on_explicit_removal(equipment):
    e = equipment
    c = client(e.app, 3)
    response = c.get('/piloto/os/1/formulario')
    assert OrdemServico.query.count() == 0
    fields = execution_form('MONITORADO E LARVICIDA APLICADO',
        drone_id=selected(response, 'drone_id')[0],
        drone_monitoramento_id=selected(response, 'drone_monitoramento_id')[0])
    assert c.post('/piloto/os/1/formulario', data=fields).status_code == 302
    order = OrdemServico.query.one()
    for prefix, item in [('drone_', e.p), ('drone_monitoramento_', e.m)]:
        assert getattr(order, prefix + 'modelo') == item.modelo
        assert getattr(order, prefix + 'numero_serie') == item.numero_serie
        assert getattr(order, prefix + 'registro_anatel') == item.registro_anatel
        assert getattr(order, prefix + 'registro_anac') == item.registro_anac
    assert order.drone_id == e.p.id and order.drone_monitoramento_id == e.m.id
    fields.update(drone_id='', drone_monitoramento_id='')
    assert c.post('/piloto/os/1/formulario', data=fields).status_code == 302
    db.session.refresh(order)
    assert order.drone_id is None and order.drone_monitoramento_id is None
    assert not order.drone_numero_serie and not order.drone_monitoramento_numero_serie


@pytest.mark.parametrize('invalid', ['team', 'municipality', 'inactive', 'category'])
def test_os_rejects_a_new_invalid_drone_even_after_an_automatic_suggestion(equipment, invalid):
    e = equipment
    changes = {'team': dict(equipe_id=2), 'municipality': dict(prefeitura_id=2),
               'inactive': dict(status='Inativo'), 'category': dict(categoria='Monitoramento')}[invalid]
    other = drone('INVALID', **changes)
    db.session.commit()
    c = client(e.app, 3)
    c.get('/piloto/os/1/formulario')
    response = c.post('/piloto/os/1/formulario', data=execution_form(
        'MONITORADO E LARVICIDA APLICADO', drone_id=str(other.id)))
    assert response.status_code == 302
    assert response.location.endswith('/piloto/os/1/formulario')
    # The fixture holds its app context open; mirror the request teardown rollback.
    db.session.rollback()
    assert OrdemServico.query.count() == 0


def test_checklist_prefers_unique_active_team_vehicle_and_preserves_explicit_choice(equipment):
    e = equipment
    e.m.status = 'Inativo'  # One active drone for this checklist.
    db.session.add(EquipePiloto(equipe_id=2, piloto_id=1, papel='auxiliar'))
    other = vehicle('TEST002', equipe_id=2, responsavel='Piloto de teste')
    vehicle('TEST003', status='Inativo')
    vehicle('TEST004', prefeitura_id=2, responsavel='Piloto de teste')
    db.session.commit()
    context = build_piloto_checklist_context(e.pilot, MultiDict())
    assert context['veiculo_padrao_id'] == e.v.id
    assert context['drone_padrao_id'] == e.p.id
    assert context['veiculo_autopreenchido'] and context['drone_autopreenchido']
    assert len(context['veiculos_equipe']) == 3
    context = build_piloto_checklist_context(e.pilot, MultiDict({'veiculo_id': str(other.id), 'drone_id': str(e.p.id)}))
    assert context['veiculo_padrao_id'] == other.id
    assert not context['veiculo_autopreenchido'] and not context['drone_autopreenchido']
    response = client(e.app, 3).get('/piloto/checklists/semanais')
    assert response.status_code == 200
    assert selected(response, 'veiculo_id') == [str(e.v.id)]
    assert selected(response, 'drone_id') == [str(e.p.id)]
    assert ChecklistSemanalVeiculo.query.count() == 0
    assert ChecklistSemanalDrone.query.count() == 0


def test_checklist_requires_manual_choice_for_ambiguous_equipment_and_ignores_inactive_default(equipment):
    e = equipment
    vehicle('TEST002')
    db.session.commit()
    context = build_piloto_checklist_context(e.pilot, MultiDict())
    assert context['veiculo_padrao_id'] is None and context['drone_padrao_id'] is None
    assert not context['veiculo_autopreenchido'] and not context['drone_autopreenchido']
    for item in Veiculos.query.all():
        item.status = 'Inativo'
    e.p.status = e.m.status = 'Inativo'
    db.session.commit()
    context = build_piloto_checklist_context(e.pilot, MultiDict({'veiculo_id': '99999', 'drone_id': '99999'}))
    assert context['veiculo_padrao_id'] is None and context['drone_padrao_id'] is None
