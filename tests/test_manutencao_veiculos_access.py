"""Vehicle consultation for maintenance, using disposable SQLite only."""
import unittest
from datetime import datetime

from flask import g

from app.extensions import db
from app.models import LogVeiculo, Prefeitura, Usuario, Veiculos
from app.modules.gestao_ti.service import save_configurations
from tests import test_central_ti as central_fixture


class ManutencaoVeiculosAccessTests(unittest.TestCase):
    tearDown = central_fixture.CentralTiTests.tearDown
    login = central_fixture.CentralTiTests.login

    def setUp(self):
        central_fixture.CentralTiTests.setUp(self)
        self.app.config.update(CENTRAL_TI_ENFORCE_PERMISSIONS=True, REDGPS_SYNC_ENABLED=False)
        db.session.add_all([
            Prefeitura(id=1, nome='Município teste', slug='municipio-teste'),
            Prefeitura(id=2, nome='Outro município', slug='outro-municipio'),
        ])
        user = Usuario(nome_uvis='Manutenção teste', login='maintenance-test', senha_hash='test-only',
                       tipo_usuario='manutencao', prefeitura_id=1, trabalha_oceano_azul=True)
        db.session.add(user)
        self.users['manutencao'] = user
        self.vehicles = []
        for tenant in (1, 2):
            vehicle = Veiculos(modelo=f'Veículo teste {tenant}', renomacao=f'Veículo teste {tenant}',
                               placa=f'TST{tenant}A11',
                               prefeitura_id=tenant, status='Ativo', operacao='PMSP', frota='PROPRIA')
            db.session.add(vehicle)
            db.session.flush()
            db.session.add(LogVeiculo(veiculo_id=vehicle.id, km_inicial=100,
                                      data_registro=datetime(2026, 11, 24)))
            self.vehicles.append(vehicle)
        db.session.commit()
        self.permissions = ['prefeitura.veiculos.consultar', 'prefeitura.veiculos.exportar',
                            'prefeitura.logs_veiculos.consultar', 'prefeitura.logs_veiculos.exportar',
                            'prefeitura.checklists.consultar']
        self.configure(self.permissions)
        self.login('manutencao')

    def configure(self, permissions):
        from app.models import CentralTiPerfilConfiguracao
        row = db.session.get(CentralTiPerfilConfiguracao, 'manutencao')
        save_configurations(self.users['dev'], {'profiles': [{
            'id': 'manutencao', 'version': row.versao if row else 0,
            'areas': ['prefeitura'], 'permissions': permissions,
        }]})
        g.pop('_central_ti_permissions', None)

    def test_vehicle_menu_shows_all_authorized_admin_consultations(self):
        response = self.client.get('/veiculos/menu')
        self.assertEqual(response.status_code, 200)
        for path in ('/veiculos', '/veiculos/logs', '/veiculos/limpezas', '/veiculos/rastreamento',
                     '/veiculos/limpeza/alertas', '/admin/checklists/semanais'):
            self.assertIn(f'href="{path}"', response.text)

    def test_consultations_and_exports_open_without_admin_identity(self):
        for path in ('/veiculos', '/veiculos/logs', '/veiculos/limpezas', '/veiculos/rastreamento?cached=1',
                     '/veiculos/rastreamento/dados?cached=1', '/veiculos/limpeza/alertas',
                     '/admin/checklists/semanais', '/veiculos?export=xlsx', '/veiculos/logs/exportar'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_vehicle_and_log_details_remain_inside_the_municipality(self):
        response = self.client.get('/veiculos')
        self.assertIn(self.vehicles[0].placa, response.text)
        self.assertNotIn(self.vehicles[1].placa, response.text)
        self.assertEqual(self.client.get(f'/veiculos/logs/veiculo/{self.vehicles[0].id}').status_code, 200)
        self.assertEqual(self.client.get(f'/veiculos/logs/veiculo/{self.vehicles[1].id}').status_code, 403)

    def test_revoked_checklists_disappear_from_vehicle_menu(self):
        self.configure([p for p in self.permissions if p != 'prefeitura.checklists.consultar'])
        response = self.client.get('/veiculos/menu')
        self.assertNotIn('href="/admin/checklists/semanais"', response.text)
        self.assertEqual(self.client.get('/admin/checklists/semanais').status_code, 403)

    def test_revoked_logs_disappear_from_vehicle_menu(self):
        self.configure([p for p in self.permissions if not p.startswith('prefeitura.logs_veiculos.')])
        response = self.client.get('/veiculos/menu')
        self.assertNotIn('href="/veiculos/logs"', response.text)
        self.assertEqual(self.client.get('/veiculos/logs').status_code, 403)

    def test_consultation_does_not_grant_administrative_mutations(self):
        for path in ('/veiculos/cadastrar', f'/veiculos/{self.vehicles[0].id}/editar',
                     '/admin/veiculos/logs-excluidos'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)


if __name__ == '__main__':
    unittest.main()
