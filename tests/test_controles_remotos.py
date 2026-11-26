"""Remote control registration and tenant hierarchy in disposable SQLite only."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from flask import g
from sqlalchemy.exc import IntegrityError
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.extensions import db
from app.models import CentralTiSelecao, ControleRemotoAtualizacao, ControlesRemotos, Equipe
from app.modules.equipamentos.controles import list_controles, validate_controle_form
from app.modules.equipamentos.service import delete_drone, equipment_team_assignments, list_equipamentos_dashboard
from app.modules.gestao_ti.permissions import validate_route_policy
from tests import test_equipamentos_busca as fixture


class ControlesTests(unittest.TestCase):
    tearDown = fixture.EquipmentLookupTests.tearDown
    login = fixture.EquipmentLookupTests.login
    make_team = fixture.EquipmentLookupTests.make_team

    def setUp(self):
        fixture.EquipmentLookupTests.setUp(self)
        db.session.add(CentralTiSelecao(perfil_codigo='manutencao', codigo='prefeitura.equipamentos.criar'))
        db.session.commit()
        g.pop('_central_ti_permissions', None)

    def payload(self, **extra):
        return dict(modelo='DJI RC Plus', renomacao='Controle Norte', numero_serie='RC-TESTE-001',
                    drone_id=str(self.drones[0].id), status='Ativo', **extra)

    def create(self, **extra):
        data = self.payload()
        data.update(extra)
        response = self.client.post('/controles/cadastrar', data=data)
        self.assertEqual(response.status_code, 302, response.text[:300])
        return ControlesRemotos.query.order_by(ControlesRemotos.id.desc()).first()

    def test_create_edit_search_and_overview(self):
        controle = self.create()
        self.assertEqual(controle.prefeitura_id, 1)
        self.assertIsNone(controle.equipe_id)
        self.assertEqual(controle.drone_id, self.drones[0].id)
        for term in ('rc-teste-001', 'TESTE-001', 'Norte', 'RC Plus'):
            self.assertEqual(list_controles(self.user, term), [controle])
        self.assertEqual(list_controles(self.user, '%'), [])
        self.assertEqual(list_equipamentos_dashboard(self.user)['total_controles'], 1)
        page = self.client.get('/equipamentos/controles?q=rc-teste-001')
        self.assertEqual(page.status_code, 200)
        self.assertIn('RC-TESTE-001', page.text)
        self.assertIn('Novo controle remoto', page.text)
        self.assertIn('RC-TESTE-001', self.client.get('/equipamentos/drones').text)
        data = self.payload()
        data.update(renomacao='Controle Reserva', status='Inativo', drone_id=str(self.drones[1].id))
        response = self.client.post(f'/controles/{controle.id}/editar', data=data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(controle.drone_id, self.drones[1].id)
        self.assertEqual(controle.status, 'Inativo')
        self.assertEqual(ControlesRemotos.query.count(), 1)
        self.assertIn('Controle Reserva', self.client.get(f'/controles/{controle.id}/editar').text)
        self.client.post(f'/controles/{controle.id}/editar', data=data)
        events = ControleRemotoAtualizacao.query.filter_by(controle_id=controle.id).order_by(ControleRemotoAtualizacao.id).all()
        self.assertEqual([event.tipo for event in events], ['cadastro', 'edicao'])
        self.assertEqual(events[1].alteracoes['renomacao'], {'antes': 'Controle Norte', 'depois': 'Controle Reserva'})
        self.assertEqual(events[1].usuario_id, self.user.id)
        history = self.client.get(f'/equipamentos/controles/{controle.id}/historico')
        self.assertEqual(history.status_code, 200)
        self.assertIn('Controle Norte', history.text)
        self.assertIn('Controle Reserva', history.text)

    def test_follows_drone_team_and_roster_without_copied_team(self):
        north, pilot = self.make_team('Norte')
        south, other_pilot = self.make_team('Sul')
        self.drones[0].equipe_id = north.id
        db.session.commit()
        controle = self.create()
        page = self.client.get('/equipamentos/controles')
        for text in ('Piloto Norte', 'Auxiliar Norte', 'PLACA-Norte'):
            self.assertIn(text, page.text)
        self.drones[0].equipe_id = south.id
        db.session.commit()
        assignment = equipment_team_assignments([controle], user=self.user)[controle.id]
        self.assertEqual(assignment['piloto'], other_pilot)
        self.assertIsNone(controle.equipe_id)
        self.assertNotIn('Piloto Norte', self.client.get('/equipamentos/controles').text)

    def test_foreign_drone_cannot_be_forged_or_shown_in_select(self):
        data = self.payload()
        data['drone_id'] = str(self.drones[3].id)
        response = self.client.post('/controles/cadastrar', data=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ControlesRemotos.query.count(), 0)
        self.assertIn('Selecione um drone disponível', response.text)
        self.assertNotIn('DRONE-3', response.text)

    def test_foreign_control_and_global_cross_municipality_reassignment_denied(self):
        controle = self.create()
        self.login('dev')
        data = self.payload()
        data['drone_id'] = str(self.drones[3].id)
        response = self.client.post(f'/controles/{controle.id}/editar', data=data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('mesma prefeitura', response.text)
        self.assertEqual(controle.drone_id, self.drones[0].id)
        # A foreign control must not be visible by ID, by search or in the overview.
        foreign = ControlesRemotos(modelo='RC', renomacao='Sigiloso', numero_serie='RC-FOREIGN',
                                  prefeitura_id=2, drone_id=self.drones[3].id)
        db.session.add(foreign)
        db.session.commit()
        self.login('manutencao')
        self.assertEqual(list_controles(self.user, 'RC-FOREIGN'), [])
        for method in ('get', 'post'):
            self.assertEqual(getattr(self.client, method)(f'/controles/{foreign.id}/editar', data=data if method=='post' else None).status_code, 404)

    def test_legacy_drone_resolves_prefeitura_but_missing_or_conflicting_root_is_rejected(self):
        team, _ = self.make_team('Legado')
        self.drones[0].prefeitura_id = None
        self.drones[0].equipe_id = team.id
        db.session.commit()
        controle = self.create()
        self.assertEqual(controle.prefeitura_id, 1)
        self.assertIn('Piloto Legado', self.client.get('/equipamentos/controles').text)
        self.drones[0].equipe_id = None
        db.session.commit()
        _, _, errors = validate_controle_form(self.payload(), user=self.users['dev'])
        self.assertIn('drone_id', errors)
        self.drones[0].prefeitura_id = 2
        self.drones[0].equipe_id = team.id
        db.session.commit()
        _, _, errors = validate_controle_form(self.payload(), user=self.users['dev'])
        self.assertIn('drone_id', errors)

    def test_serial_required_unique_across_all_equipment_and_database_constraint(self):
        for serial in ('', self.battery.numero_serie.lower(), self.drones[0].numero_serie):
            data = self.payload()
            data['numero_serie'] = serial
            _, _, errors = validate_controle_form(data, user=self.user)
            self.assertIn('numero_serie', errors)
        controle = self.create()
        _, _, errors = validate_controle_form(self.payload(), user=self.user, existing=controle)
        self.assertEqual(errors, {})
        db.session.add(ControlesRemotos(modelo='Outro', renomacao='Outro', numero_serie=controle.numero_serie,
                                       prefeitura_id=1, drone_id=self.drones[0].id))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_validation_status_lengths_and_drone_are_server_side(self):
        data = {'modelo': 'x'*101, 'renomacao': '', 'numero_serie': 'x'*101, 'drone_id': 'abc',
                'status': 'Em Manutenção', 'prefeitura_id': '2', 'equipe_id': '999'}
        _, _, errors = validate_controle_form(data, user=self.user)
        self.assertEqual(set(errors), {'modelo', 'renomacao', 'numero_serie', 'drone_id', 'status'})
        controle = self.create(prefeitura_id='2', equipe_id='999')
        self.assertEqual(controle.prefeitura_id, 1)
        self.assertIsNone(controle.equipe_id)

    def test_read_only_permissions_and_route_policy(self):
        controle = self.create()
        CentralTiSelecao.query.filter(CentralTiSelecao.perfil_codigo=='manutencao',
            CentralTiSelecao.codigo.in_(['prefeitura.equipamentos.criar', 'prefeitura.equipamentos.editar'])).delete(synchronize_session=False)
        db.session.commit()
        g.pop('_central_ti_permissions', None)
        page = self.client.get('/equipamentos/controles')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('Novo controle remoto', page.text)
        self.assertIn('Somente leitura', page.text)
        self.assertEqual(self.client.post('/controles/cadastrar', data=self.payload()).status_code, 403)
        self.assertEqual(self.client.post(f'/controles/{controle.id}/editar', data=self.payload()).status_code, 403)
        self.assertFalse(validate_route_policy(self.app))

    def test_team_restrictions_and_missing_user_prefeitura_still_apply(self):
        north, _ = self.make_team('Restrita')
        south, _ = self.make_team('Outra')
        self.drones[0].equipe_id = north.id
        db.session.commit()
        controle = self.create()
        with patch('app.shared.access.central_ti_team_ids', return_value=[south.id]):
            self.assertEqual(list_controles(self.user), [])
        with patch('app.shared.access.central_ti_team_ids', return_value=[north.id]):
            self.assertEqual(list_controles(self.user), [controle])
        self.user.prefeitura_id = None
        db.session.commit()
        self.assertEqual(list_controles(self.user), [])

    def test_drone_cannot_be_deleted_while_control_is_linked(self):
        self.create()
        with self.assertRaisesRegex(ValueError, 'controles remotos'):
            delete_drone(self.drones[0])
        self.assertEqual(ControlesRemotos.query.count(), 1)

    def test_csrf_and_required_authentication(self):
        self.app.config['CSRF_PROTECTION_ENABLED'] = True
        page = self.client.get('/controles/cadastrar')
        self.assertIn('name="_csrf_token"', page.text)
        self.assertEqual(self.client.post('/controles/cadastrar', data=self.payload()).status_code, 403)
        with self.client.session_transaction() as session:
            token = session['_ija_csrf']
        self.create(_csrf_token=token)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get('/equipamentos/controles').status_code, 302)


def test_migration_upgrade_and_safe_downgrade():
    path = Path(__file__).resolve().parents[1]/'migrations/versions/f79c31d5a802_controles_remotos.py'
    spec = importlib.util.spec_from_file_location('control_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(sa.text('CREATE TABLE equipamentos (id INTEGER PRIMARY KEY)'))
        connection.execute(sa.text('CREATE TABLE drones (id INTEGER PRIMARY KEY)'))
        context = MigrationContext.configure(connection)
        with patch.object(module, 'op', Operations(context)):
            module.upgrade()
            inspector = sa.inspect(connection)
            assert {'id', 'drone_id'} == {col['name'] for col in inspector.get_columns('controles_remotos')}
            connection.execute(sa.text('INSERT INTO controles_remotos (id, drone_id) VALUES (1, 2)'))
            with unittest.TestCase().assertRaisesRegex(RuntimeError, 'Há controles'):
                module.downgrade()
            connection.execute(sa.text('DELETE FROM controles_remotos'))
            module.downgrade()
            assert 'controles_remotos' not in sa.inspect(connection).get_table_names()
    engine.dispose()
