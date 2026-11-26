"""Shared inventory and compatible equipment, using disposable databases only."""
import importlib.util
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import g
from openpyxl import load_workbook
import sqlalchemy as sa
from sqlalchemy.orm.attributes import set_committed_value
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Baterias, Drones, EstoquePeca, ManutencaoPecaUso, Prefeitura, Usuario
from app.modules.estoque.service import build_peca_form, validate_peca_form
from app.modules.estoque.service import list_pecas
from app.modules.equipamentos.service import list_pecas_disponiveis_manutencao, registrar_pecas_usadas_manutencao, send_drone_to_manutencao
from app.modules.gestao_ti.service import save_configurations
from tests import test_central_ti as fixture


class EstoqueCompatibilidadeTests(unittest.TestCase):
    tearDown = fixture.CentralTiTests.tearDown
    login = fixture.CentralTiTests.login

    def setUp(self):
        fixture.CentralTiTests.setUp(self)
        self.app.config['CENTRAL_TI_ENFORCE_PERMISSIONS'] = True
        db.session.add_all([Prefeitura(id=i, nome=f'Prefeitura {i}', slug=f'prefeitura-{i}') for i in (1, 2)])
        self.user = Usuario(nome_uvis='Manutenção', login='manutencao', senha_hash='test-only', tipo_usuario='manutencao', prefeitura_id=1)
        self.users['manutencao'] = self.user
        db.session.add(self.user)
        self.drones = []
        for i, (tenant, model) in enumerate([(1, 'MATRICE 4E'), (1, 'AGRAS T10'), (1, 'MATRICE 4E'), (2, 'MATRICE 4E')]):
            drone = Drones(modelo=model, renomacao=f'Drone {i}', numero_serie=f'DRONE-{i}',
                           registro_anatel='teste', registro_anac=f'ANAC-{i}', pmd_kg=1, prefeitura_id=tenant)
            db.session.add(drone)
            self.drones.append(drone)
        self.battery = Baterias(modelo='TB TESTE', renomacao='Bateria compatível', numero_serie='BAT-TESTE', prefeitura_id=1)
        db.session.add(self.battery)
        db.session.commit()
        permissions = ['sistema.estoque.consultar', 'sistema.estoque.criar', 'sistema.estoque.editar', 'sistema.estoque.exportar',
                       'prefeitura.equipamentos.consultar', 'prefeitura.equipamentos.editar']
        save_configurations(self.users['dev'], {'profiles': [{'id': 'manutencao', 'version': 0,
                            'areas': ['prefeitura', 'sistema'], 'permissions': permissions}]})
        g.pop('_central_ti_permissions', None)
        self.login('manutencao')

    def payload(self, ids=(), models=(), **extra):
        data = MultiDict({'modelo_peca': 'Peça compartilhada', 'quantidade': '5', 'status': 'disponivel_manutencao',
                          'prefeitura_id': '1', 'compatibilidade_multipla': '1', 'prateleira_local': 'Armário A'})
        data.setlist('equipamento_ids', [str(i) for i in ids])
        data.setlist('modelos_compativeis', models)
        for key, value in extra.items():
            data[key] = value
        return data

    def create(self, ids=(), models=()):
        response = self.client.post('/estoque/novo', data=self.payload(ids, models))
        self.assertEqual(response.status_code, 302, response.text[:200])
        return EstoquePeca.query.one()

    def available(self, drone, user=None):
        return list_pecas_disponiveis_manutencao(drone, user=user or self.user)

    def test_multiple_models_and_equipment_roundtrip_and_export(self):
        peca = self.create([self.drones[0].id, self.battery.id], ['MATRICE 4E', 'AGRAS T10'])
        form = build_peca_form(peca)
        self.assertEqual(set(form['equipamento_ids']), {str(self.drones[0].id), str(self.battery.id)})
        self.assertEqual(set(form['modelos_compativeis']), {'MATRICE 4E', 'AGRAS T10'})
        self.assertEqual(peca.quantidade, 5)
        for drone in self.drones[:3]:
            self.assertIn(peca, self.available(drone))
        self.assertNotIn(peca, self.available(self.drones[3], self.users['dev']))
        page = self.client.get(f'/estoque/{peca.id}/editar')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Equipamentos compatíveis', page.text)
        self.assertIn('type="checkbox"', page.text)
        response = self.client.get('/estoque/export/excel')
        self.assertEqual(response.status_code, 200)
        values = list(load_workbook(BytesIO(response.data)).active.values)
        self.assertIn('Modelos compatíveis', values[1])
        self.assertIn('MATRICE 4E, AGRAS T10', values[2])
        self.assertTrue(any('Bateria compatível' in str(cell) and 'Drone 0' in str(cell) for cell in values[2]))
        self.assertIn('Armário A', values[2])

    def test_specific_equipment_does_not_grant_compatibility_to_its_entire_model(self):
        peca = self.create([self.drones[0].id, self.drones[1].id])
        self.assertIn(peca, self.available(self.drones[0]))
        self.assertIn(peca, self.available(self.drones[1]))
        self.assertNotIn(peca, self.available(self.drones[2]))
        self.assertIsNone(peca.modelos_compativeis)

    def test_shared_stock_consumption_records_each_drone_and_os(self):
        peca = self.create([self.drones[0].id, self.drones[1].id])
        for drone, amount in ((self.drones[0], 2), (self.drones[1], 1)):
            send_drone_to_manutencao(drone, user=self.user)
            response = self.client.post(f'/equipamentos/{drone.id}/manutencao/pecas',
                data={'peca_id': peca.id, f'quantidade_{peca.id}': amount, 'observacoes': 'Uso de estoque compartilhado'})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(EstoquePeca.query.count(), 1)
        self.assertEqual(peca.quantidade, 2)
        usos = ManutencaoPecaUso.query.order_by(ManutencaoPecaUso.id).all()
        self.assertEqual([u.drone_id for u in usos], [self.drones[0].id, self.drones[1].id])
        self.assertEqual([u.quantidade_usada for u in usos], [2, 1])
        self.assertNotEqual(usos[0].manutencao_id, usos[1].manutencao_id)
        self.assertTrue(all(u.manutencao.drone_id == u.drone_id and u.usuario_id == self.user.id for u in usos))
        send_drone_to_manutencao(self.drones[2], user=self.user)
        denied = self.client.post(f'/equipamentos/{self.drones[2].id}/manutencao/pecas', data={'peca_id': peca.id})
        self.assertIn('nao esta disponivel', denied.text)
        self.assertEqual(peca.quantidade, 2)

    def test_removing_compatibility_clears_all_legacy_references(self):
        peca = self.create([self.drones[0].id, self.drones[1].id], ['MATRICE 4E'])
        response = self.client.post(f'/estoque/{peca.id}/editar', data=self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(peca.equipamentos_compativeis, [])
        self.assertIsNone(peca.equipamento_id)
        self.assertIsNone(peca.drone_id)
        self.assertIsNone(peca.modelos_compativeis)
        self.assertNotIn(peca, self.available(self.drones[0]))

    def test_model_only_balance_is_exhausted_for_every_compatible_drone(self):
        peca = self.create(models=['MATRICE 4E', 'AGRAS T10'])
        self.assertEqual(peca.equipamentos_compativeis, [])
        for drone, amount in ((self.drones[0], 3), (self.drones[1], 2)):
            send_drone_to_manutencao(drone, user=self.user)
            response = self.client.post(f'/equipamentos/{drone.id}/manutencao/pecas',
                data={'peca_id': peca.id, f'quantidade_{peca.id}': amount})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(peca.quantidade, 0)
        self.assertEqual(peca.status, 'baixada')
        self.assertTrue(all(peca not in self.available(d) for d in self.drones[:3]))
        self.assertEqual(EstoquePeca.query.count(), 1)
        self.assertEqual(ManutencaoPecaUso.query.count(), 2)

    def test_tenant_and_model_injection_are_rejected_even_for_global_admin(self):
        _, _, errors = validate_peca_form(self.payload([self.drones[3].id]), user=self.user)
        self.assertIn('equipamento_ids', errors)
        _, _, errors = validate_peca_form(self.payload([self.drones[0].id, self.drones[3].id]), user=self.users['dev'])
        self.assertIn('equipamento_ids', errors)
        _, _, errors = validate_peca_form(self.payload(models=['Modelo inventado']), user=self.user)
        self.assertIn('modelos_compativeis', errors)
        _, _, errors = validate_peca_form(self.payload([self.drones[0].id], prefeitura_id='2'), user=self.user)
        self.assertIn('prefeitura_id', errors)
        self.assertEqual(EstoquePeca.query.count(), 0)

    def test_legacy_links_and_model_names_survive_editing(self):
        peca = EstoquePeca(modelo_peca='Peça legada', quantidade=3, prefeitura_id=1,
                          equipamento=self.drones[0], drone=self.drones[0], modelos_compativeis='Modelo legado')
        db.session.add(peca)
        db.session.commit()
        form = build_peca_form(peca)
        self.assertEqual(form['equipamento_ids'], [str(self.drones[0].id)])
        self.assertIn(peca, self.available(self.drones[0]))
        page = self.client.get(f'/estoque/{peca.id}/editar')
        self.assertIn('value="Modelo legado" checked', page.text)
        response = self.client.post(f'/estoque/{peca.id}/editar', data=self.payload([self.drones[0].id], ['Modelo legado']))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(peca.modelos_compativeis, 'Modelo legado')
        self.assertEqual([e.id for e in peca.equipamentos_compativeis], [self.drones[0].id])

    def test_duplicate_piece_selection_cannot_spend_twice(self):
        peca = self.create([self.drones[0].id])
        send_drone_to_manutencao(self.drones[0], user=self.user)
        form = MultiDict([('peca_id', str(peca.id)), ('peca_id', str(peca.id)), (f'quantidade_{peca.id}', '4')])
        usos, errors = registrar_pecas_usadas_manutencao(self.drones[0], form, user=self.user)
        self.assertIsNone(usos)
        self.assertIn('pecas', errors)
        self.assertEqual(peca.quantidade, 5)
        self.assertEqual(ManutencaoPecaUso.query.count(), 0)

    def test_changed_shared_balance_rolls_back_all_requested_parts(self):
        peca = self.create([self.drones[0].id])
        other = EstoquePeca(modelo_peca='Outra peça', quantidade=2, prefeitura_id=1, equipamentos_compativeis=[self.drones[0]])
        db.session.add(other)
        db.session.commit()
        send_drone_to_manutencao(self.drones[0], user=self.user)
        # Emulate a second OS spending the balance after this form loaded.
        db.session.execute(sa.update(EstoquePeca).where(EstoquePeca.id == other.id).values(quantidade=0))
        db.session.commit()
        set_committed_value(other, 'quantidade', 2)
        with patch('app.modules.equipamentos.service.list_pecas_disponiveis_manutencao', return_value=[peca, other]):
            usos, errors = registrar_pecas_usadas_manutencao(self.drones[0],
                MultiDict([('peca_id', str(peca.id)), ('peca_id', str(other.id))]), user=self.user)
        self.assertIsNone(usos)
        self.assertIn('saldo', errors['pecas'])
        self.assertEqual(peca.quantidade, 5)
        self.assertEqual(other.quantidade, 0)
        self.assertEqual(ManutencaoPecaUso.query.count(), 0)

    def test_inventory_search_finds_linked_equipment_and_combines_filters(self):
        peca = self.create([self.drones[0].id, self.battery.id], ['AGRAS T10'])
        self.assertIn(peca, list_pecas(user=self.user, q='BAT-TESTE', local='Armário', status='disponivel_manutencao'))
        self.assertIn(peca, list_pecas(user=self.user, q='AGRAS T10'))
        self.assertNotIn(peca, list_pecas(user=self.user, q='DRONE-1'))
        self.assertNotIn(peca, list_pecas(user=self.user, q='BAT-TESTE', status='reservada'))
        response = self.client.get('/estoque?q=BAT-TESTE&local=Armário&status=disponivel_manutencao')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Peça compartilhada', response.text)
        self.assertIn('Limpar', response.text)

    def test_inventory_overview_and_search_never_include_other_municipality(self):
        self.create([self.drones[0].id])
        db.session.add(EstoquePeca(modelo_peca='Peça de outra prefeitura', prefeitura_id=2, quantidade=987))
        db.session.commit()
        self.assertEqual(len(list_pecas(user=self.user)), 1)
        self.assertEqual(list_pecas(user=self.user, q='outra prefeitura'), [])
        response = self.client.get('/estoque')
        self.assertIn('Unidades disponíveis', response.text)
        self.assertNotIn('987', response.text)
        self.assertNotIn('Peça de outra prefeitura', response.text)


class EstoqueCompatibilidadeMigrationTests(unittest.TestCase):
    def test_backfill_preserves_links_and_stock_without_duplicate_balances(self):
        path = Path(__file__).resolve().parents[1] / 'migrations/versions/d92e4f6a8b10_estoque_equipamentos_compativeis.py'
        spec = importlib.util.spec_from_file_location('compatibility_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = sa.create_engine('sqlite:///:memory:')
        try:
            with engine.begin() as conn:
                conn.execute(sa.text('CREATE TABLE equipamentos (id INTEGER PRIMARY KEY)'))
                conn.execute(sa.text('CREATE TABLE estoque_pecas (id INTEGER PRIMARY KEY, equipamento_id INTEGER, drone_id INTEGER, quantidade INTEGER)'))
                conn.execute(sa.text('INSERT INTO equipamentos VALUES (1), (2)'))
                conn.execute(sa.text('INSERT INTO estoque_pecas VALUES (1,1,1,8), (2,2,1,4), (3,NULL,NULL,10)'))
                with Operations.context(MigrationContext.configure(conn)):
                    migration.upgrade()
                links = conn.execute(sa.text('SELECT peca_id,equipamento_id FROM estoque_peca_equipamentos ORDER BY 1,2')).all()
                self.assertEqual(links, [(1,1), (2,1), (2,2)])
                self.assertEqual(conn.execute(sa.text('SELECT quantidade FROM estoque_pecas ORDER BY id')).scalars().all(), [8,4,10])
                with Operations.context(MigrationContext.configure(conn)):
                    migration.downgrade()
                self.assertNotIn('estoque_peca_equipamentos', sa.inspect(conn).get_table_names())
        finally:
            engine.dispose()
