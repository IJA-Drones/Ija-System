"""Independent vehicle screens, legacy compatibility and real server guards."""
import unittest
from datetime import datetime
from unittest.mock import patch

from flask import g

from app.extensions import db
from app.models import (Usuario, Prefeitura, Veiculos, LogVeiculo, CentralTiPerfilConfiguracao,
                        CentralTiSelecao, CentralTiUsuarioConfiguracao, CentralTiUsuarioSelecao)
from app.modules.gestao_ti.permission_versions import (PERMISSION_SCHEMA_VERSION, VEHICLE_MARKER,
                                                     VEHICLE_BASE, VEHICLE_DETAILS)
from app.modules.gestao_ti.permissions import active_configuration
from app.modules.gestao_ti.service import save_configurations
from app.modules.gestao_ti.user_permissions import save_user_configuration
from tests import test_central_ti_users as individual_fixture


class VehicleGranularTests(unittest.TestCase):
    tearDown = individual_fixture.CentralTiUserTests.tearDown
    login = individual_fixture.CentralTiUserTests.login

    def setUp(self):
        individual_fixture.CentralTiUserTests.setUp(self)
        db.session.add_all([Prefeitura(id=1, nome='Cidade teste', slug='cidade-teste'),
                            Prefeitura(id=2, nome='Outra cidade', slug='outra-cidade')])
        self.first = self.users['uvis']; self.second = self.users['second']
        for user in (self.first, self.second):
            user.tipo_usuario = 'manutencao'; user.prefeitura_id = 1; user.trabalha_oceano_azul = True
        self.vehicles = []
        for city in (1, 2):
            vehicle = Veiculos(modelo='Veículo de teste', renomacao=f'Teste {city}', placa=f'TST{city}A11',
                               frota='PROPRIA', operacao='PMSP', status='Ativo', prefeitura_id=city)
            db.session.add(vehicle); db.session.flush(); self.vehicles.append(vehicle)
            db.session.add(LogVeiculo(veiculo_id=vehicle.id, km_inicial=100,
                data_registro=datetime(2026, 11, 25), condutor_nome='Condutor restrito do log'))
        db.session.commit()

    def grant(self, user, permissions, schema=PERMISSION_SCHEMA_VERSION):
        row = db.session.get(CentralTiUsuarioConfiguracao, user.id)
        result = save_user_configuration(self.actor, user.id, {
            'version': row.versao if row else 0, 'areas': ['prefeitura'],
            'permissions': permissions, 'nome_acesso': 'Teste granular',
        }, permission_schema_version=schema)
        g.pop('_central_ti_permissions', None)
        return result

    def test_each_vehicle_screen_opens_independently_and_hides_other_cards(self):
        screens = {
            VEHICLE_BASE: '/veiculos',
            'prefeitura.rastreamento_veiculos.consultar': '/veiculos/rastreamento',
            'prefeitura.limpezas_veiculos.consultar': '/veiculos/limpezas',
            'prefeitura.alertas_limpeza_veiculos.consultar': '/veiculos/limpeza/alertas',
            'prefeitura.logs_veiculos.consultar': '/veiculos/logs',
            'prefeitura.checklists.consultar': '/admin/checklists/semanais',
        }
        self.login('uvis')
        for permission, allowed in screens.items():
            self.grant(self.first, [permission])
            menu = self.client.get('/veiculos/menu')
            self.assertEqual(menu.status_code, 200)
            for target in screens.values():
                with self.subTest(permission=permission, target=target):
                    self.assertEqual(self.client.get(target).status_code, 200 if target == allowed else 403)
                    if target == allowed: self.assertIn(f'href="{target}"', menu.text)
                    else: self.assertNotIn(f'href="{target}"', menu.text)

    def test_two_users_with_same_role_can_have_different_vehicle_screens(self):
        self.grant(self.first, ['prefeitura.limpezas_veiculos.consultar'])
        self.grant(self.second, ['prefeitura.rastreamento_veiculos.consultar'])
        for role, allowed, denied in [('uvis', '/veiculos/limpezas', '/veiculos/rastreamento'),
                                     ('second', '/veiculos/rastreamento', '/veiculos/limpezas')]:
            self.login(role)
            self.assertEqual(self.client.get(allowed).status_code, 200)
            self.assertEqual(self.client.get(denied).status_code, 403)

    def test_fleet_permission_does_not_regrant_a_revoked_tracking_permission(self):
        self.grant(self.first, [VEHICLE_BASE, 'prefeitura.rastreamento_veiculos.consultar'])
        self.grant(self.first, [VEHICLE_BASE])
        raw = {row.codigo for row in CentralTiUsuarioSelecao.query.filter_by(usuario_id=self.first.id)}
        self.assertIn(VEHICLE_MARKER, raw)
        self.assertEqual(active_configuration(self.first), frozenset({'area:prefeitura', VEHICLE_BASE}))
        self.login('uvis')
        self.assertEqual(self.client.get('/veiculos').status_code, 200)
        self.assertEqual(self.client.get('/veiculos/rastreamento/dados').status_code, 403)
        with patch('app.modules.veiculos.routes.import_redgps_history') as provider:
            self.assertEqual(self.client.post('/veiculos/rastreamento/historico', json={}).status_code, 403)
            provider.assert_not_called()

    def test_tracking_does_not_expose_log_data_without_history_permission(self):
        self.grant(self.first, ['prefeitura.rastreamento_veiculos.consultar'])
        self.login('uvis')
        response = self.client.get('/veiculos/rastreamento/dados?cached=1&date=2026-11-25')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Condutor restrito do log', response.text)
        self.assertNotIn('TST2A11', response.text)
        self.grant(self.first, ['prefeitura.rastreamento_veiculos.consultar', 'prefeitura.logs_veiculos.consultar'])
        response = self.client.get('/veiculos/rastreamento/dados?cached=1&date=2026-11-25')
        self.assertIn('Condutor restrito do log', response.text)

    def test_direct_tracking_history_and_exports_respect_permission_and_municipality(self):
        self.grant(self.first, ['prefeitura.rastreamento_veiculos.consultar'])
        self.login('uvis')
        self.assertEqual(self.client.get('/veiculos/logs/exportar').status_code, 403)
        self.assertEqual(self.client.get('/veiculos?export=xlsx').status_code, 403)
        self.assertEqual(self.client.post('/veiculos/equipes', data={}).status_code, 403)
        self.assertEqual(self.client.get(f'/veiculos/rastreamento/dados?cached=1&vehicle_id={self.vehicles[1].id}').status_code, 403)
        with patch('app.modules.veiculos.routes.import_redgps_history') as provider:
            response = self.client.post('/veiculos/rastreamento/historico', json={
                'vehicle_id': self.vehicles[1].id, 'date': '2026-11-25'})
            self.assertEqual(response.status_code, 404)
            provider.assert_not_called()

    def test_legacy_profile_and_user_selections_keep_bundle_without_database_writes(self):
        profile = CentralTiPerfilConfiguracao(perfil_codigo='manutencao', versao=3)
        personal = CentralTiUsuarioConfiguracao(usuario_id=self.second.id, versao=2, nome_acesso='Anterior')
        db.session.add_all([profile, personal]); db.session.flush()
        for code in ('area:prefeitura', VEHICLE_BASE):
            db.session.add(CentralTiSelecao(perfil_codigo='manutencao', codigo=code))
            db.session.add(CentralTiUsuarioSelecao(usuario_id=self.second.id, codigo=code))
        db.session.commit()
        for user in (self.first, self.second):
            self.assertEqual(active_configuration(user), frozenset({'area:prefeitura', VEHICLE_BASE, *VEHICLE_DETAILS}))
        self.assertEqual((profile.versao, personal.versao), (3, 2))
        self.assertEqual(CentralTiSelecao.query.count(), 2)
        self.assertEqual(CentralTiUsuarioSelecao.query.count(), 2)

    def test_legacy_editor_submission_preserves_bundle_and_current_editor_can_split_it(self):
        legacy = self.grant(self.first, [VEHICLE_BASE], schema=None)
        self.assertTrue(VEHICLE_DETAILS <= set(legacy['permissions']))
        current = self.grant(self.first, [VEHICLE_BASE])
        self.assertEqual(current['permissions'], [VEHICLE_BASE])
        with self.assertRaises(ValueError): self.grant(self.first, [VEHICLE_BASE], schema='unknown-schema')

    def test_profile_editor_can_restrict_new_permissions_too(self):
        payload = {'profiles': [{'id': 'manutencao', 'version': 0, 'areas': ['prefeitura'], 'permissions': [VEHICLE_BASE]}]}
        save_configurations(self.actor, payload, permission_schema_version=PERMISSION_SCHEMA_VERSION)
        self.assertFalse(VEHICLE_DETAILS & active_configuration(self.first))
        self.login('uvis')
        self.assertEqual(self.client.get('/veiculos/limpezas').status_code, 403)

    def test_guides_and_downloads_follow_tracking_permission_independently_of_fleet(self):
        self.login('uvis')
        self.grant(self.first, [VEHICLE_BASE])
        self.assertNotIn('guia-rastreamento-veiculos', self.client.get('/treinamentos').text)
        self.assertEqual(self.client.get('/treinamentos/arquivos/guia-rastreamento-veiculos').status_code, 403)
        self.grant(self.first, ['prefeitura.rastreamento_veiculos.consultar'])
        self.assertIn('guia-rastreamento-veiculos', self.client.get('/treinamentos').text)
        self.assertEqual(self.client.get('/treinamentos/arquivos/guia-rastreamento-veiculos').status_code, 200)

    def test_user_api_uses_catalog_version_when_saving_precise_access(self):
        self.login('dev'); page = self.client.get('/central-ti/usuarios')
        self.assertEqual(page.status_code, 200)
        with self.client.session_transaction() as stored:
            token = stored['_ija_central_ti_csrf']['token']
        result = self.client.post(f'/central-ti/usuarios/{self.first.id}/permissoes', json={
            'version': 0, 'areas': ['prefeitura'], 'permissions': [VEHICLE_BASE], 'nome_acesso': 'Somente frota'},
            headers={'X-Central-TI-CSRF': token, 'X-Central-TI-Permission-Schema': PERMISSION_SCHEMA_VERSION})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['configuration']['permissions'], [VEHICLE_BASE])

    def test_practical_tutorials_follow_exact_vehicle_screen_permissions(self):
        from app.modules.chatbot.practical import catalog
        self.grant(self.first, ['prefeitura.rastreamento_veiculos.consultar'])
        with self.app.test_request_context('/treinamentos'):
            functions = {item['id'] for group in catalog(self.first) for item in group['functions']}
        self.assertIn('veiculos_rastreamento', functions)
        self.assertNotIn('veiculos_limpezas', functions)
        self.assertNotIn('veiculos_alertas_limpeza', functions)
        self.assertNotIn('listar_veiculos', functions)
        self.assertNotIn('veiculos_logs', functions)

    def test_legacy_practical_tutorial_does_not_offer_unavailable_cleaning_alerts(self):
        from app.modules.chatbot.practical import catalog
        self.first.trabalha_oceano_azul = False; db.session.commit()
        with self.app.test_request_context('/treinamentos'):
            functions = {item['id'] for group in catalog(self.first) for item in group['functions']}
        self.assertIn('veiculos_rastreamento', functions)
        self.assertIn('veiculos_limpezas', functions)
        self.assertNotIn('veiculos_alertas_limpeza', functions)
