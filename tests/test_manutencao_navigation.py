"""Maintenance links follow the existing route grants; no accounts are changed."""
import unittest
from flask import g
from app.modules.gestao_ti.service import save_configurations
from tests import test_manutencao_os as fixture


class MaintenanceNavigationTests(unittest.TestCase):
    setUp = fixture.ManutencaoOsTests.setUp
    tearDown = fixture.ManutencaoOsTests.tearDown
    login = fixture.ManutencaoOsTests.login
    configure = fixture.ManutencaoOsTests.configure

    def sidebar(self, response):
        self.assertEqual(response.status_code, 200)
        return response.text.split('id="appSidebar"', 1)[1].split('id="appContent"', 1)[0]

    def test_maintenance_history_is_visible_and_active_for_consultation(self):
        self.configure(['prefeitura.equipamentos.consultar'])
        sidebar = self.sidebar(self.client.get('/equipamentos/manutencoes/historico'))
        self.assertIn('id="menuManutencao" class="collapse show"', sidebar)
        self.assertIn('href="/equipamentos/em-manutencao"', sidebar)
        self.assertIn('href="/equipamentos/manutencoes/historico" aria-current="page"', sidebar)
        self.assertIn('Histórico de OS', sidebar)
        self.assertIn('href="/equipamentos/preventivas"', sidebar)
        self.assertNotIn('href="/admin/historico-os"', sidebar)
        self.assertEqual(self.client.post('/equipamentos/manutencoes/nova').status_code, 403)

    def test_removing_equipment_access_hides_history_without_changing_grants(self):
        self.configure([])
        sidebar = self.sidebar(self.client.get('/treinamentos'))
        self.assertNotIn('id="menuManutencao"', sidebar)
        self.assertNotIn('href="/equipamentos/manutencoes/historico"', sidebar)
        self.assertEqual(self.client.get('/equipamentos/manutencoes/historico').status_code, 403)

    def test_customized_user_sees_navigation_without_maintenance_user_type(self):
        save_configurations(self.users['dev'], {'profiles': [{
            'id': 'piloto', 'version': 0, 'areas': ['prefeitura'],
            'permissions': ['prefeitura.equipamentos.consultar'],
        }]})
        g.pop('_central_ti_permissions', None)
        self.login('piloto')
        sidebar = self.sidebar(self.client.get('/equipamentos/manutencoes/historico'))
        self.assertIn('href="/equipamentos/manutencoes/historico" aria-current="page"', sidebar)
        self.assertEqual(self.client.post('/equipamentos/manutencoes/nova').status_code, 403)
