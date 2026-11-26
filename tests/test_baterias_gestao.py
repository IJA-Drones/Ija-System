"""Manual battery management and allocation, with disposable SQLite databases."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import g

from app.extensions import db
from app.models import Baterias, BateriaAtualizacao, CentralTiSelecao, Veiculos
from app.modules.equipamentos.baterias import battery_inventory
from app.modules.equipamentos.service import validate_bateria_form
from app.modules.gestao_ti.permissions import validate_route_policy
from tests import test_equipamentos_busca as fixture


class BatteryManagementTests(unittest.TestCase):
    setUp = fixture.EquipmentLookupTests.setUp
    tearDown = fixture.EquipmentLookupTests.tearDown
    login = fixture.EquipmentLookupTests.login
    make_team = fixture.EquipmentLookupTests.make_team

    def payload(self, **extra):
        data = dict(modelo='TB 65', renomacao='Bateria conferida', numero_serie='BAT-NOVA', status='Ativo',
                    drone_id=str(self.drones[0].id), ciclo='', ano_fabricacao='', ultima_manutencao='', categoria='')
        data.update(extra)
        return data

    def allow_create(self):
        db.session.add(CentralTiSelecao(perfil_codigo='manutencao', codigo='prefeitura.equipamentos.criar'))
        db.session.commit()
        g.pop('_central_ti_permissions', None)

    def test_family_allocation_filters_are_scoped_and_counts_are_stable(self):
        team, pilot = self.make_team('Matrice')
        foreign, _ = self.make_team('Sigilo', tenant=2)
        self.drones[0].equipe_id = team.id
        self.drones[3].equipe_id = foreign.id
        self.battery.drone_id = self.drones[0].id
        agras = Baterias(modelo='Agras T10', renomacao='Bateria Agras', numero_serie='AG-001',
                        prefeitura_id=1, drone_id=self.drones[1].id)
        hidden = Baterias(modelo='Matrice Sigilosa', renomacao='Bateria sigilosa', numero_serie='SEGREDO',
                         prefeitura_id=2, drone_id=self.drones[3].id)
        db.session.add_all([agras, hidden]);db.session.commit()
        vehicle = Veiculos.query.filter_by(equipe_id=team.id).one()
        for filters in ({'familia':'matrice'}, {'equipe_id':str(team.id)}, {'responsavel_id':str(pilot.id)},
                        {'veiculo_id':str(vehicle.id)}, {'drone_id':str(self.drones[0].id)}):
            inventory = battery_inventory(self.user, filters)
            self.assertEqual(inventory['baterias'], [self.battery])
            self.assertEqual(inventory['counters']['total'], 2)
            self.assertNotIn('Sigilo', str([t.nome_equipe for t in inventory['filter_equipes']]))
        self.assertEqual(battery_inventory(self.user, {'familia':'agras_t10'})['baterias'], [agras])
        self.assertEqual(battery_inventory(self.user, {'q':'SEGREDO'})['baterias'], [])
        page = self.client.get('/equipamentos/baterias?familia=matrice')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('Bateria sigilosa', page.text)
        self.assertIn('Piloto Matrice', page.text)
        self.assertIn('Sem conferência registrada', page.text)
        self.assertNotIn('id="progresso', page.text)

    def test_pagination_preserves_filters_and_invalid_foreign_choices_match_nothing(self):
        for i in range(31):
            db.session.add(Baterias(modelo='MATRICE RESERVA', renomacao=f'Reserva {i:02}', prefeitura_id=1))
        db.session.commit()
        inventory = battery_inventory(self.user, {'familia':'matrice','page':'2'})
        self.assertEqual(len(inventory['baterias']), 15)
        self.assertEqual(inventory['total'], 31)
        page = self.client.get('/equipamentos/baterias?familia=matrice&page=2')
        self.assertIn('Página 2 de 3', page.text)
        self.assertIn('familia=matrice', page.text)
        self.assertEqual(battery_inventory(self.user, {'responsavel_id':'999999'})['baterias'], [])
        self.assertEqual(battery_inventory(self.user, {'veiculo_id':'999999'})['baterias'], [])

    def test_create_optional_cycles_and_recorded_actor(self):
        self.allow_create()
        response = self.client.post('/baterias/cadastrar', data=self.payload())
        self.assertEqual(response.status_code, 302)
        battery = Baterias.query.filter_by(numero_serie='BAT-NOVA').one()
        self.assertIsNone(battery.ciclo)
        self.assertIsNone(battery.ciclos_atualizados_em)
        self.assertEqual(battery.atualizado_por_id, self.user.id)
        self.assertEqual(battery.prefeitura_id, 1)
        event = BateriaAtualizacao.query.filter_by(bateria_id=battery.id).one()
        self.assertEqual(event.usuario_id, self.user.id)
        self.assertEqual(event.tipo, 'cadastro')
        self.assertEqual(event.alteracoes['numero_serie']['depois'], 'BAT-NOVA')

    def test_conference_keeps_legacy_cycles_and_does_not_invent_cycle_confirmation(self):
        self.battery.ciclo = 97
        db.session.commit()
        page = self.client.get(f'/equipamentos/baterias/{self.battery.id}')
        self.assertIn('Sem atualização registrada', page.text)
        response = self.client.post(f'/baterias/{self.battery.id}/conferir')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.battery.ciclo, 97)
        self.assertIsNone(self.battery.ciclos_atualizados_em)
        event = BateriaAtualizacao.query.one()
        self.assertEqual(event.tipo, 'conferencia')
        self.assertEqual(event.alteracoes, {})
        self.assertEqual(event.usuario_nome, self.user.nome_uvis)
        self.assertEqual(event.prefeitura_id, 1)

    def test_manual_cycles_capture_before_after_and_confirm_same_value(self):
        self.battery.ciclo = 97
        db.session.commit()
        for reading in ('18', '18', '0'):
            response = self.client.post(f'/baterias/{self.battery.id}/ciclos', data={'ciclo':reading})
            self.assertEqual(response.status_code, 302)
        events = BateriaAtualizacao.query.order_by(BateriaAtualizacao.id).all()
        self.assertEqual(events[0].alteracoes['ciclo'], {'antes':97, 'depois':18})
        self.assertEqual(events[1].alteracoes, {})
        self.assertEqual(events[2].alteracoes['ciclo'], {'antes':18, 'depois':0})
        self.assertEqual(self.battery.ciclo, 0)
        self.assertIsNotNone(self.battery.ciclos_atualizados_em)
        self.assertTrue(all(event.usuario_id==self.user.id for event in events))

    def test_dji_cycles_use_serial_timestamp_and_municipality(self):
        from app.modules.equipamentos.dji_battery_sync import sync_battery_cycles

        self.battery.numero_serie = 'BAT-DJI-1'
        self.battery.ciclo = 180
        self.drones[0].numero_serie = 'M30T-1'
        foreign = Baterias(modelo='TB', renomacao='Bateria externa', numero_serie='BAT-DJI-2', prefeitura_id=2)
        db.session.add(foreign)
        db.session.commit()
        now = datetime(2026, 11, 26, 15)

        def osd(at, count):
            return json.dumps({'timestamp': int(at.replace(tzinfo=timezone.utc).timestamp() * 1000),
                'data': {'battery': {'batteries': [
                    {'sn': 'bat-dji-1', 'loop_times': count}, {'sn': 'BAT-DJI-2', 'loop_times': 88},
                    {'sn': 'BAT-INEXISTENTE', 'loop_times': 1},
                ]}}}).encode()

        self.assertEqual(sync_battery_cycles('INEXISTENTE', osd(now, 181), now=now), 0)
        self.assertEqual(sync_battery_cycles('M30T-1', osd(now, 181), now=now), 1)
        self.assertEqual(self.battery.ciclo, 181)
        self.assertEqual(self.battery.ciclos_atualizados_em, now)
        self.assertIsNone(foreign.ciclo)
        self.assertEqual(sync_battery_cycles('M30T-1', osd(now, 181), now=now), 0)
        self.assertEqual(sync_battery_cycles('M30T-1', osd(now - timedelta(seconds=1), 182), now=now), 0)
        self.assertEqual(sync_battery_cycles('M30T-1', osd(now + timedelta(seconds=1), 179), now=now), 0)
        event = BateriaAtualizacao.query.one()
        self.assertEqual(event.alteracoes['ciclo'], {'antes': 180, 'depois': 181})
        self.assertEqual(event.usuario_nome, 'DJI')
        self.assertIn('Sincronização DJI', self.client.get(f'/equipamentos/baterias/{self.battery.id}').text)

    def test_invalid_cycles_do_not_write_or_silently_change_numbers(self):
        self.battery.ciclo = 5
        db.session.commit()
        for value in (-1, 2.5, True, '13+5', '1.5', '', 2147483648):
            response = self.client.post(f'/equipamentos/baterias/update_ciclos/{self.battery.id}',
                                        json={'operacao':'add','quantidade':value})
            self.assertEqual(response.status_code, 400, str(value))
        self.assertEqual(self.battery.ciclo, 5)
        self.assertEqual(BateriaAtualizacao.query.count(), 0)
        response = self.client.post(f'/equipamentos/baterias/update_ciclos/{self.battery.id}', json={'operacao':'surpresa','quantidade':1})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.battery.ciclo, 5)
        self.battery.ciclo = None
        db.session.commit()
        response = self.client.post(f'/equipamentos/baterias/update_ciclos/{self.battery.id}', json={'operacao':'add','quantidade':1})
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.battery.ciclo)

    def test_edit_tracking_noop_and_clearing_optional_cycles(self):
        self.battery.ciclo = 12
        db.session.commit()
        response = self.client.post(f'/baterias/{self.battery.id}/editar',data=self.payload(numero_serie=self.battery.numero_serie, ciclo='12'))
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.battery.ciclos_atualizados_em)  # Editing the name does not confirm an old reading.
        self.assertEqual(BateriaAtualizacao.query.count(), 1)
        response = self.client.post(f'/baterias/{self.battery.id}/editar',data=self.payload(numero_serie=self.battery.numero_serie, ciclo='12'))
        self.assertEqual(BateriaAtualizacao.query.count(), 1)
        self.client.post(f'/baterias/{self.battery.id}/editar',data=self.payload(numero_serie=self.battery.numero_serie, ciclo=''))
        self.assertIsNone(self.battery.ciclo)
        self.assertEqual(BateriaAtualizacao.query.order_by(BateriaAtualizacao.id.desc()).first().alteracoes['ciclo'], {'antes':12,'depois':None})

    def test_history_timestamps_are_sao_paulo_and_foreign_records_are_hidden(self):
        self.client.post(f'/baterias/{self.battery.id}/conferir')
        event = BateriaAtualizacao.query.one()
        event.criado_em = datetime(2026,11,26,1,12)
        self.battery.atualizado_em = event.criado_em
        hidden = Baterias(modelo='Oculta',renomacao='Oculta',prefeitura_id=2)
        db.session.add(hidden);db.session.commit()
        response = self.client.get(f'/equipamentos/baterias/{self.battery.id}')
        self.assertIn('25/11/2026 22:12', response.text)
        self.assertEqual(self.client.get(f'/equipamentos/baterias/{hidden.id}').status_code, 404)
        self.assertEqual(self.client.post(f'/baterias/{hidden.id}/conferir').status_code, 404)
        self.assertEqual(self.client.post(f'/baterias/{hidden.id}/ciclos', data={'ciclo':'4'}).status_code, 404)

    def test_legacy_parent_resolves_root_but_global_editor_cannot_cross_prefeitura(self):
        team, _ = self.make_team('Legado')
        self.drones[0].equipe_id = team.id
        self.drones[0].prefeitura_id = None
        self.battery.prefeitura_id = None
        self.battery.drone_id = self.drones[0].id
        db.session.commit()
        data=self.payload(numero_serie=self.battery.numero_serie)
        _, _, errors=validate_bateria_form(data, existing_bateria=self.battery, user=self.user)
        self.assertFalse(errors)
        data['drone_id']=str(self.drones[3].id)
        _, _, errors=validate_bateria_form(data, existing_bateria=self.battery, user=self.users['dev'])
        self.assertIn('drone_id',errors)
        self.client.post(f'/baterias/{self.battery.id}/conferir')
        self.assertEqual(BateriaAtualizacao.query.one().prefeitura_id,1)

    def test_audit_cannot_be_deleted_and_read_only_user_cannot_write(self):
        self.client.post(f'/baterias/{self.battery.id}/conferir')
        db.session.add(CentralTiSelecao(perfil_codigo='manutencao',codigo='prefeitura.equipamentos.excluir'))
        db.session.commit();g.pop('_central_ti_permissions',None)
        response=self.client.post(f'/baterias/{self.battery.id}/deletar')
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(Baterias,self.battery.id))
        self.assertEqual(BateriaAtualizacao.query.count(),1)
        CentralTiSelecao.query.filter_by(perfil_codigo='manutencao',codigo='prefeitura.equipamentos.editar').delete()
        db.session.commit();g.pop('_central_ti_permissions',None)
        self.assertEqual(self.client.get(f'/equipamentos/baterias/{self.battery.id}').status_code,200)
        self.assertEqual(self.client.post(f'/baterias/{self.battery.id}/conferir').status_code,403)
        self.assertEqual(self.client.post(f'/baterias/{self.battery.id}/ciclos',data={'ciclo':'4'}).status_code,403)
        self.assertFalse(validate_route_policy(self.app))


def test_migration_preserves_old_cycles_and_leaves_old_dates_unknown():
    path=Path(__file__).resolve().parents[1]/'migrations/versions/b7d3e91a6204_baterias_historico.py'
    spec=importlib.util.spec_from_file_location('battery_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as c:
        for table in ('equipamentos','usuarios','prefeituras'):
            c.execute(sa.text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY)'))
        c.execute(sa.text('CREATE TABLE baterias (id INTEGER PRIMARY KEY, ciclo INTEGER)'))
        c.execute(sa.text('INSERT INTO baterias (id,ciclo) VALUES (1,97),(2,0),(3,NULL)'))
        with patch.object(module,'op',Operations(MigrationContext.configure(c))):
            module.upgrade()
            rows=c.execute(sa.text('SELECT ciclo,atualizado_em,ciclos_atualizados_em FROM baterias ORDER BY id')).all()
            assert rows==[(97,None,None),(0,None,None),(None,None,None)]
            module.downgrade()
            assert c.execute(sa.text('SELECT ciclo FROM baterias ORDER BY id')).scalars().all()==[97,0,None]
    engine.dispose()
