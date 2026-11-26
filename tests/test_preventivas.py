from datetime import date, timedelta
import unittest
from unittest.mock import patch
from flask import g
from app.extensions import db
from app.models import CentralTiSelecao, PreventivaPlano, PreventivaRegistro, ManutencaoEquipamento
from app.modules.equipamentos.preventivas import situation
from app.modules.gestao_ti.permissions import can_access_endpoint, validate_route_policy
from tests import test_equipamentos_busca as fixture

TODAY=date(2026,11,26)
class PreventivaTests(unittest.TestCase):
    tearDown=fixture.EquipmentLookupTests.tearDown
    login=fixture.EquipmentLookupTests.login
    make_team=fixture.EquipmentLookupTests.make_team
    def setUp(self):
        fixture.EquipmentLookupTests.setUp(self)
        self.clock=patch('app.modules.equipamentos.preventivas.today_local',return_value=TODAY);self.clock.start();self.addCleanup(self.clock.stop)
    def config(self,equipment=None,**extra):
        data={'acao':'configurar','versao':'0','intervalo':'60','ultima_realizada_em':(TODAY-timedelta(days=61)).isoformat()};data.update(extra)
        return self.client.post(f'/equipamentos/preventivas/{(equipment or self.drones[0]).id}',data=data)
    def test_states_and_boundaries(self):
        self.assertEqual(situation(None,TODAY)['status'],'sem_configuracao')
        for delta,status in [(-1,'atrasada'),(0,'hoje'),(1,'proxima'),(7,'proxima'),(8,'em_dia')]:
            plan=PreventivaPlano(intervalo_dias=60,ultima_realizada_em=TODAY+timedelta(days=delta-60))
            self.assertEqual(situation(plan,TODAY)['status'],status)
        self.assertEqual(situation(PreventivaPlano(intervalo_dias=90,ultima_realizada_em=TODAY),TODAY)['vencimento'],TODAY+timedelta(days=90))
    def test_configure_complete_history_and_stale_tab(self):
        self.assertEqual(self.config().status_code,302)
        plan=PreventivaPlano.query.one()
        self.assertEqual(plan.prefeitura_id,1)
        self.assertEqual(plan.versao,1)
        page=self.client.get('/equipamentos/preventivas?situacao=atrasada')
        self.assertIn('Drone 0',page.text)
        self.assertIn('Atrasada',page.text)
        result=self.client.post(f'/equipamentos/preventivas/{self.drones[0].id}',data={'acao':'concluir','versao':'1','realizada_em':TODAY.isoformat(),'descricao':'Revisão de braços, hélices e conexões.'})
        self.assertEqual(result.status_code,302)
        self.assertEqual(plan.ultima_realizada_em,TODAY)
        self.assertEqual(PreventivaRegistro.query.count(),2)
        self.assertEqual(PreventivaRegistro.query.order_by(PreventivaRegistro.id.desc()).first().usuario_nome,self.user.nome_uvis)
        self.config(versao='1',intervalo='90')
        self.assertEqual(plan.intervalo_dias,60)
        self.assertEqual(PreventivaRegistro.query.count(),2)
        # After an actual conclusion, configuration cannot erase the reference.
        self.config(versao='2',ultima_realizada_em='')
        self.assertEqual(plan.ultima_realizada_em,TODAY)
    def test_unknown_reference_can_be_completed_without_inventing_past_date(self):
        self.config(ultima_realizada_em='',intervalo='90')
        plan=PreventivaPlano.query.one();self.assertIsNone(plan.ultima_realizada_em)
        self.assertEqual(situation(plan,TODAY)['status'],'sem_configuracao')
        response=self.client.post(f'/equipamentos/preventivas/{self.drones[0].id}',data={'acao':'concluir','versao':'1','realizada_em':TODAY.isoformat(),'descricao':'Primeira preventiva documentada.'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(situation(plan,TODAY)['dias'],90)
    def test_invalid_dates_intervals_and_description_do_not_write(self):
        for extra in ({'intervalo':'30'},{'ultima_realizada_em':'amanha'},{'ultima_realizada_em':(TODAY+timedelta(days=1)).isoformat()}):
            self.config(**extra)
            self.assertEqual(PreventivaPlano.query.count(),0)
        self.config()
        for values in ({'realizada_em':'2020-01-01','descricao':'teste'},{'realizada_em':TODAY.isoformat(),'descricao':''},{'realizada_em':(TODAY+timedelta(days=1)).isoformat(),'descricao':'teste'}):
            self.client.post(f'/equipamentos/preventivas/{self.drones[0].id}',data={'acao':'concluir','versao':'1',**values})
        self.assertEqual(PreventivaRegistro.query.count(),1)
    def test_foreign_scope_readonly_and_independent_vehicle_permissions(self):
        self.assertEqual(self.config(self.drones[3]).status_code,404)
        self.assertEqual(self.client.get(f'/equipamentos/preventivas/{self.drones[3].id}').status_code,404)
        team,_=self.make_team('Carro')
        from app.models import Veiculos
        vehicle=Veiculos.query.filter_by(equipe_id=team.id).one()
        self.assertEqual(self.config(vehicle).status_code,404)
        db.session.add_all([CentralTiSelecao(perfil_codigo='manutencao',codigo=c) for c in ('prefeitura.veiculos.consultar','prefeitura.veiculos.editar')]);db.session.commit();g.pop('_central_ti_permissions',None)
        self.assertEqual(self.config(vehicle,intervalo='90').status_code,302)
        CentralTiSelecao.query.filter_by(perfil_codigo='manutencao',codigo='prefeitura.veiculos.editar').delete();db.session.commit();g.pop('_central_ti_permissions',None)
        self.assertEqual(self.client.get(f'/equipamentos/preventivas/{vehicle.id}').status_code,200)
        self.assertEqual(self.config(vehicle,versao='1').status_code,403)
        self.assertFalse(validate_route_policy(self.app))
    def test_corrective_order_does_not_reset_and_os_must_match_drone(self):
        self.config();plan=PreventivaPlano.query.one();before=plan.ultima_realizada_em
        from app.modules.equipamentos.service import send_drone_to_manutencao,encerrar_manutencao_drone
        send_drone_to_manutencao(self.drones[0],user=self.user)
        from tests.maintenance_helpers import worksheet_data
        from app.modules.equipamentos.manutencao import salvar_atendimento_manutencao
        order = ManutencaoEquipamento.query.filter_by(drone_id=self.drones[0].id, status='aberta').one()
        salvar_atendimento_manutencao(self.drones[0], worksheet_data(order, complete=True), user=self.user)
        self.assertEqual(plan.ultima_realizada_em,before)
        order=ManutencaoEquipamento.query.one()
        self.client.post(f'/equipamentos/preventivas/{self.drones[0].id}',data={'acao':'concluir','versao':'1','realizada_em':TODAY.isoformat(),'descricao':'Preventiva com OS','manutencao_id':str(order.id)})
        self.assertEqual(PreventivaRegistro.query.order_by(PreventivaRegistro.id.desc()).first().manutencao_id,order.id)

    def test_team_scope_limits_dashboard_details_and_writes(self):
        north, _ = self.make_team('Norte')
        south, _ = self.make_team('Sul')
        self.drones[0].equipe_id = north.id
        self.drones[1].equipe_id = south.id
        db.session.commit()
        self.config(self.drones[1])
        with patch('app.shared.access.central_ti_team_ids', return_value=[north.id]):
            page = self.client.get('/equipamentos/preventivas')
            self.assertIn('Drone 0', page.text)
            self.assertIn('Piloto Norte', page.text)
            self.assertNotIn('Drone 1', page.text)
            self.assertNotIn('Piloto Sul', page.text)
            self.assertEqual(self.client.get(f'/equipamentos/preventivas/{self.drones[1].id}').status_code, 404)
            self.assertEqual(self.config(self.drones[1], versao='1').status_code, 404)

    def test_reassignment_cannot_reveal_or_overwrite_previous_tenants_history(self):
        self.config()
        plan = PreventivaPlano.query.one()
        plan.prefeitura_id = 2
        record = PreventivaRegistro.query.one()
        record.descricao = 'Histórico reservado da prefeitura anterior'
        db.session.commit()
        self.assertEqual(self.client.get(f'/equipamentos/preventivas/{self.drones[0].id}').status_code, 404)
        self.assertEqual(self.config(versao='1').status_code, 404)
        self.assertEqual(PreventivaRegistro.query.count(), 1)
        dashboard = self.client.get('/equipamentos/preventivas')
        self.assertNotIn('Histórico reservado', dashboard.text)
        self.assertNotIn('25/11/2026', dashboard.text)

    def test_only_dev_and_maintenance_stock_can_access_even_with_equipment_grants(self):
        grants = frozenset({'area:prefeitura', 'prefeitura.equipamentos.consultar',
                            'prefeitura.equipamentos.editar', 'prefeitura.veiculos.consultar',
                            'prefeitura.veiculos.editar'})
        with patch('app.modules.gestao_ti.permissions.active_configuration', return_value=grants):
            for role in ('diretor', 'admin', 'prefeitura_admin', 'operario', 'piloto', 'sup_veiculos', 'gestor_ti'):
                with self.subTest(role=role):
                    self.user.tipo_usuario = role
                    db.session.commit()
                    self.assertFalse(can_access_endpoint(self.user, 'main.preventivas'))
                    self.assertEqual(self.client.get('/equipamentos/preventivas').status_code, 403)
                    self.assertEqual(self.client.get(f'/equipamentos/preventivas/{self.drones[0].id}').status_code, 403)
                    self.assertEqual(self.config().status_code, 403)
                    self.assertNotIn('href="/equipamentos/preventivas"', self.client.get('/equipamentos').text)
            self.user.tipo_usuario = 'manutencao'
            db.session.commit()
            self.assertEqual(self.client.get('/equipamentos/preventivas').status_code, 200)
            self.assertIn('href="/equipamentos/preventivas"', self.client.get('/equipamentos').text)
            self.login('dev')
            self.assertEqual(self.client.get('/equipamentos/preventivas').status_code, 200)
        self.assertEqual(PreventivaPlano.query.count(), 0)

    def test_role_restriction_also_applies_without_central_ti_enforcement(self):
        self.app.config['CENTRAL_TI_ENFORCE_PERMISSIONS'] = False
        self.user.tipo_usuario = 'admin'
        db.session.commit()
        self.assertEqual(self.client.get('/equipamentos/preventivas').status_code, 403)
        self.assertEqual(self.config().status_code, 403)
        self.assertNotIn('href="/equipamentos/preventivas"', self.client.get('/equipamentos').text)
