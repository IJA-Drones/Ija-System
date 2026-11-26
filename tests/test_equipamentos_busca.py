"""Equipment lookup and existing associations, isolated from production."""
import unittest

from app.extensions import db
from app.models import Baterias, Drones, Equipe
from app.modules.equipamentos.service import (
    list_baterias, list_drones, list_equipamentos_dashboard,
    validate_bateria_form, validate_drone_form,
)
from tests import test_estoque_compatibilidade as fixture


class EquipmentLookupTests(unittest.TestCase):
    setUp = fixture.EstoqueCompatibilidadeTests.setUp
    tearDown = fixture.EstoqueCompatibilidadeTests.tearDown
    login = fixture.EstoqueCompatibilidadeTests.login

    def test_partial_case_insensitive_serial_and_tenant_scope(self):
        for term in ('drone-0', '  RoNe-0  '):
            self.assertEqual(list_drones(self.user, term), [self.drones[0]])
        self.assertEqual(list_drones(self.user, 'DRONE-3'), [])
        self.assertEqual(list_baterias(self.user, 'bat-teste'), [self.battery])
        self.assertEqual(list_equipamentos_dashboard(self.user, 'DRONE-3')['equipamentos'], [])
        overview = list_equipamentos_dashboard(self.user, 'DRONE-0')
        self.assertEqual(overview['equipamentos'], [self.drones[0]])
        self.assertEqual(overview['total_drones'], 3)

    def test_search_treats_wildcards_literally_and_supports_name_model(self):
        self.assertEqual(list_drones(self.user, '%'), [])
        self.assertEqual(list_baterias(self.user, '_'), [])
        self.assertEqual(list_drones(self.user, 'agras'), [self.drones[1]])
        self.assertEqual(list_baterias(self.user, 'compatível'), [self.battery])
        self.assertEqual(len(list_drones(self.user, '   ')), 3)

    def test_pages_have_search_and_preserve_escaped_query(self):
        for path in ('/equipamentos', '/equipamentos/drones', '/equipamentos/baterias'):
            response = self.client.get(path, query_string={'q': '<script>'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('name="q"', response.text)
            self.assertIn('&lt;script&gt;', response.text)
            self.assertIn('Limpar', response.text)
            self.assertNotIn('value="<script>"', response.text)
        self.assertIn('Nenhum drone encontrado', self.client.get('/equipamentos/drones?q=DRONE-3').text)
        self.assertIn('Nenhuma bateria encontrada', self.client.get('/equipamentos/baterias?q=ausente').text)

    def test_drone_rejects_serial_already_used_by_battery(self):
        _, _, errors = validate_drone_form({'numero_serie': self.battery.numero_serie}, user=self.user)
        self.assertIn('numero_serie', errors)
        _, _, errors = validate_drone_form({'numero_serie': self.drones[0].numero_serie}, existing_drone=self.drones[0], user=self.user)
        self.assertNotIn('numero_serie', errors)

    def test_battery_links_reject_foreign_drone_even_for_global_editor(self):
        for user in (self.user, self.users['dev']):
            _, _, errors = validate_bateria_form({'drone_id': str(self.drones[3].id)}, existing_bateria=self.battery, user=user)
            self.assertIn('drone_id', errors)
        _, cleaned, errors = validate_bateria_form({'drone_id': str(self.drones[0].id)}, existing_bateria=self.battery, user=self.user)
        self.assertNotIn('drone_id', errors)
        self.assertEqual(cleaned['drone_id'], self.drones[0].id)

    def test_drone_team_links_reject_foreign_or_inactive_team(self):
        teams = [Equipe(nome_equipe='Local', prefeitura_id=1), Equipe(nome_equipe='Outra', prefeitura_id=2), Equipe(nome_equipe='Inativa', prefeitura_id=1, ativa=False)]
        db.session.add_all(teams)
        db.session.commit()
        for team in teams[1:]:
            _, _, errors = validate_drone_form({'equipe_id': str(team.id)}, existing_drone=self.drones[0], user=self.user)
            self.assertIn('equipe_id', errors)
        _, cleaned, errors = validate_drone_form({'equipe_id': str(teams[0].id)}, existing_drone=self.drones[0], user=self.user)
        self.assertNotIn('equipe_id', errors)
        self.assertEqual(cleaned['equipe_id'], teams[0].id)

    def make_team(self, label, tenant=1):
        from app.models import EquipePiloto, Pilotos, Veiculos
        team = Equipe(nome_equipe=f'Equipe {label}', prefeitura_id=tenant)
        pilot = Pilotos(nome_piloto=f'Piloto {label}', prefeitura_id=tenant)
        auxiliary = Pilotos(nome_piloto=f'Auxiliar {label}', prefeitura_id=tenant)
        db.session.add_all([team, pilot, auxiliary])
        db.session.flush()
        db.session.add_all([
            EquipePiloto(equipe=team, piloto=pilot, papel='piloto'),
            EquipePiloto(equipe=team, piloto=auxiliary, papel='auxiliar'),
            Veiculos(modelo=f'Carro {label}', renomacao=f'Carro {label}', placa=f'PLACA-{label}',
                     frota='PROPRIA', operacao='PMSP', prefeitura_id=tenant, equipe=team),
        ])
        db.session.commit()
        return team, pilot

    def test_responsible_people_follow_team_changes_without_copied_assignment(self):
        from app.modules.equipamentos.service import equipment_team_assignments
        first, pilot = self.make_team('A')
        second, next_pilot = self.make_team('B')
        drone = self.drones[0]
        drone.equipe_id = first.id
        self.battery.drone_id = drone.id
        self.battery.equipe_id = second.id  # Linked drone takes precedence over an old battery team.
        db.session.commit()
        for path in ('/equipamentos/drones', '/equipamentos/baterias'):
            page = self.client.get(path, query_string={'q': drone.numero_serie if 'drones' in path else self.battery.numero_serie})
            self.assertEqual(page.status_code, 200)
            for label in ('Equipe A', 'Piloto A', 'Auxiliar A', 'PLACA-A'):
                self.assertIn(label, page.text)
            self.assertNotIn('PLACA-B', page.text)
        pilot.nome_piloto = 'Titular atualizado'
        db.session.commit()
        assignment = equipment_team_assignments([drone, self.battery], user=self.user)
        self.assertEqual(assignment[self.battery.id]['piloto'].nome_piloto, 'Titular atualizado')
        drone.equipe_id = second.id
        db.session.commit()
        assignment = equipment_team_assignments([drone, self.battery], user=self.user)
        self.assertEqual(assignment[drone.id]['piloto'], next_pilot)
        self.assertEqual(assignment[self.battery.id]['piloto'], next_pilot)
        self.assertEqual(assignment[self.battery.id]['veiculos'][0].placa, 'PLACA-B')
        drone.equipe_id = None
        db.session.commit()
        self.assertEqual(equipment_team_assignments([drone, self.battery], user=self.user), {})

    def test_assignments_do_not_expose_foreign_team_or_invalid_foreign_members(self):
        from app.models import EquipePiloto, Pilotos, Veiculos
        from app.modules.equipamentos.service import equipment_team_assignments
        local, _ = self.make_team('C')
        foreign, _ = self.make_team('D', tenant=2)
        drone = self.drones[0]
        drone.equipe_id = foreign.id
        db.session.commit()
        for user in (self.user, self.users['dev']):
            self.assertEqual(equipment_team_assignments([drone], user=user), {})
        drone.equipe_id = local.id
        member = EquipePiloto.query.filter_by(equipe_id=local.id, papel='piloto').one()
        invalid_pilot = Pilotos(nome_piloto='Sigiloso outra prefeitura', prefeitura_id=2)
        db.session.add(invalid_pilot)
        db.session.flush()
        member.piloto = invalid_pilot
        db.session.add(Veiculos(modelo='Sigiloso carro', renomacao='Sigiloso', placa='SIGILO', frota='PROPRIA', operacao='PMSP', prefeitura_id=2, equipe=local))
        db.session.commit()
        for user in (self.user, self.users['dev']):
            assignment = equipment_team_assignments([drone], user=user)[drone.id]
            self.assertIsNone(assignment['piloto'])
            self.assertEqual([vehicle.placa for vehicle in assignment['veiculos']], ['PLACA-C'])
        page = self.client.get('/equipamentos/drones')
        self.assertNotIn('Sigiloso', page.text)
        self.assertIn('Não definido na equipe', page.text)

    def test_unlinked_battery_uses_own_team_and_missing_team_is_explicit(self):
        from app.modules.equipamentos.service import equipment_team_assignments
        self.assertEqual(equipment_team_assignments([self.battery], user=self.user), {})
        self.assertIn('Sem equipe vinculada', self.client.get('/equipamentos/baterias').text)
        team, pilot = self.make_team('E')
        self.battery.equipe_id = team.id
        db.session.commit()
        assignment = equipment_team_assignments([self.battery], user=self.user)[self.battery.id]
        self.assertEqual(assignment['piloto'], pilot)
        self.battery.drone_id = self.drones[3].id  # Corrupt legacy reference must not leak its team.
        self.drones[3].equipe_id = team.id
        db.session.commit()
        self.assertEqual(equipment_team_assignments([self.battery], user=self.user), {})

    def test_legacy_equipment_and_vehicles_inherit_municipality_from_registered_team(self):
        from app.models import Veiculos
        from app.modules.equipamentos.service import equipment_team_assignments
        team, pilot = self.make_team('Legado')
        drone = self.drones[0]
        drone.equipe_id = team.id
        drone.prefeitura_id = None
        self.battery.drone_id = drone.id
        self.battery.equipe_id = team.id
        self.battery.prefeitura_id = None
        vehicle = Veiculos.query.filter_by(equipe_id=team.id).one()
        vehicle.prefeitura_id = None
        db.session.commit()
        self.assertIn(drone, list_drones(self.user))
        self.assertIn(self.battery, list_baterias(self.user))
        assignments = equipment_team_assignments([drone, self.battery], user=self.user)
        for equipment in (drone, self.battery):
            self.assertEqual(assignments[equipment.id]['piloto'], pilot)
            self.assertEqual(assignments[equipment.id]['veiculos'], [vehicle])
        page = self.client.get('/equipamentos/baterias')
        self.assertIn('Drone 0', page.text)
        self.assertIn('Piloto Legado', page.text)
        # An explicit conflicting municipality must never inherit the team scope.
        drone.prefeitura_id = 2
        vehicle.prefeitura_id = 2
        db.session.commit()
        self.assertNotIn(drone, list_drones(self.user))
        self.assertEqual(equipment_team_assignments([drone, self.battery], user=self.users['dev']), {})

    def test_legacy_battery_without_team_inherits_only_its_own_drones_scope(self):
        from app.shared.access import apply_prefeitura_scope
        from unittest.mock import patch
        team, _ = self.make_team('Origem')
        other, _ = self.make_team('Outra', tenant=2)
        self.drones[0].equipe_id = team.id
        self.drones[0].prefeitura_id = None
        self.drones[3].equipe_id = other.id
        self.battery.equipe_id = None
        self.battery.prefeitura_id = None
        self.battery.drone_id = self.drones[0].id
        db.session.commit()
        self.assertIn(self.battery, list_baterias(self.user))
        self.assertEqual(list_equipamentos_dashboard(self.user)['total_baterias'], 1)
        self.assertIn(self.battery, list_equipamentos_dashboard(self.user, 'BAT-TESTE')['equipamentos'])
        self.assertEqual(self.client.get('/equipamentos/baterias?q=BAT-TESTE').status_code, 200)
        self.assertEqual(self.client.get(f'/baterias/{self.battery.id}/editar').status_code, 200)
        with patch('app.shared.access.central_ti_team_ids', return_value=[other.id]):
            self.assertEqual(list_baterias(self.user), [])
            self.assertEqual(list_equipamentos_dashboard(self.user)['total_baterias'], 0)
        with patch('app.shared.access.central_ti_team_ids', return_value=[team.id]):
            self.assertIn(self.battery, list_baterias(self.user))
        # A conflicting explicit municipality cannot inherit from a local drone.
        self.battery.prefeitura_id = 2
        db.session.commit()
        self.assertEqual(list_baterias(self.user), [])
        self.battery.prefeitura_id = None
        self.battery.drone_id = self.drones[3].id
        db.session.commit()
        self.assertEqual(list_baterias(self.user), [])
        self.assertEqual(self.client.get(f'/baterias/{self.battery.id}/editar').status_code, 404)
        # An explicit foreign team cannot be bypassed through the drone either.
        self.battery.drone_id = self.drones[0].id
        self.battery.equipe_id = other.id
        db.session.commit()
        self.assertEqual(list_baterias(self.user), [])
