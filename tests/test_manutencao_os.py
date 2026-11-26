"""Maintenance OS workflow for Fernando's role, isolated from production data."""
from datetime import date
from io import BytesIO
from pathlib import Path
import unittest

from flask import g
from openpyxl import load_workbook
from pypdf import PdfReader

from app.extensions import db
from app.models import Drones, EstoquePeca, ManutencaoEquipamento, ManutencaoPecaUso, Prefeitura, Usuario
from app.modules.equipamentos.exporters import build_manutencao_pdf
from app.modules.gestao_ti.permissions import validate_route_policy
from app.modules.gestao_ti.service import save_configurations
from tests import test_central_ti as fixture


class ManutencaoOsTests(unittest.TestCase):
    tearDown = fixture.CentralTiTests.tearDown
    login = fixture.CentralTiTests.login

    def setUp(self):
        fixture.CentralTiTests.setUp(self)
        self.app.config['CENTRAL_TI_ENFORCE_PERMISSIONS'] = True
        db.session.add_all([Prefeitura(id=i, nome=f'Município {i}', slug=f'municipio-{i}') for i in (1, 2)])
        self.user = Usuario(nome_uvis='Fernando teste', login='fernando.almeida.teste', senha_hash='test-only',
                            tipo_usuario='manutencao', prefeitura_id=1)
        db.session.add(self.user)
        self.users['manutencao'] = self.user
        self.drones = []
        for tenant in (1, 2):
            drone = Drones(modelo='Matrice teste', renomacao=f'Drone {tenant}', numero_serie=f'DRONE-{tenant}',
                           registro_anatel='teste', registro_anac=f'ANAC-{tenant}', pmd_kg=1,
                           prefeitura_id=tenant, ultima_manutencao=date(2026, 1, 1))
            db.session.add(drone)
            self.drones.append(drone)
        self.peca = EstoquePeca(prefeitura_id=1, modelo_peca='Hélice', modelos_compativeis='Matrice teste', quantidade=3)
        db.session.add(self.peca)
        db.session.commit()
        self.permissions = ['prefeitura.equipamentos.consultar', 'prefeitura.equipamentos.editar',
                            'prefeitura.equipamentos.exportar']
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

    def open_os(self, drone=None, **extra):
        data = {'drone_id': (drone or self.drones[0]).id, 'avarias_identificadas': 'Hélice danificada',
                'responsavel_manutencao': 'Fernando teste', **extra}
        return self.client.post('/equipamentos/manutencoes/nova', data=data)

    def test_complete_workflow_with_stock_history_and_separate_os_number(self):
        validate_route_policy(self.app)
        for path in ('/equipamentos/em-manutencao', '/equipamentos/drones', '/equipamentos/manutencoes/nova'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn('Abrir OS de manutenção', response.text)
        self.assertEqual(self.open_os().status_code, 302)
        os = ManutencaoEquipamento.query.one()
        self.assertEqual(os.numero_os, f'OSM-{os.id:06d}')
        self.assertEqual(os.aberta_por_id, self.user.id)
        self.assertEqual(os.prefeitura_id, 1)
        self.assertIsNotNone(os.aberta_em)
        self.assertEqual(self.drones[0].ultima_manutencao, date(2026, 1, 1))
        self.assertIn(os.numero_os, self.client.get('/equipamentos/em-manutencao').text)
        path = f'/equipamentos/{self.drones[0].id}/manutencao/pecas'
        self.assertIn(os.numero_os, self.client.get(path).text)
        response = self.client.post(path, data={'peca_id': str(self.peca.id), f'quantidade_{self.peca.id}': '2',
            'avarias_identificadas': os.avarias_identificadas, 'responsavel_manutencao': 'Fernando teste',
            'drone_testado': '1', 'observacoes_teste': 'Teste aprovado'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.peca.quantidade, 1)
        uso = ManutencaoPecaUso.query.one()
        self.assertEqual((uso.manutencao_id, uso.usuario_id, uso.prefeitura_id), (os.id, self.user.id, 1))
        self.assertEqual(self.client.post(f'/equipamentos/{self.drones[0].id}/manutencao/encerrar').status_code, 302)
        self.assertEqual(os.status, 'encerrada')
        self.assertIsNotNone(os.encerrada_em)
        self.assertEqual(os.encerrada_por_id, self.user.id)
        self.assertEqual(self.drones[0].status, 'Ativo')
        self.assertEqual(self.drones[0].ultima_manutencao, date.today())
        self.assertIn(os.numero_os, self.client.get('/equipamentos/manutencoes/historico').text)
        self.assertIn(os.numero_os, self.client.get(f'/equipamentos/manutencoes/{os.id}').text)
        response = self.client.get('/equipamentos/manutencoes/historico/excel')
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.data))
        self.assertEqual(workbook.active.cell(3, 1).value, os.numero_os)
        path = build_manutencao_pdf(os.drone, os.pecas_usadas, manutencao=os)
        try:
            text = '\n'.join(page.extract_text() for page in PdfReader(path).pages)
            self.assertIn('OS de manutenção', text)
            self.assertIn(os.numero_os, text)
        finally:
            Path(path).unlink()

    def test_legacy_maintenance_can_open_and_send_drone(self):
        self.app.config['CENTRAL_TI_ENFORCE_PERMISSIONS'] = False
        self.assertIn('Abrir OS de manutenção', self.client.get('/equipamentos/drones').text)
        self.assertEqual(self.open_os().status_code, 302)
        self.client.post(f'/equipamentos/{self.drones[0].id}/manutencao/encerrar')
        response = self.client.post(f'/drones/{self.drones[0].id}/manutencao')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ManutencaoEquipamento.query.filter_by(status='aberta').count(), 1)

    def test_repeat_open_preserves_existing_os_and_report(self):
        self.open_os()
        self.open_os(avarias_identificadas='Outro motivo')
        self.assertEqual(ManutencaoEquipamento.query.count(), 1)
        self.assertEqual(ManutencaoEquipamento.query.one().avarias_identificadas, 'Hélice danificada')

    def test_global_admin_opens_os_in_drone_municipality(self):
        self.login('admin')
        self.assertEqual(self.open_os().status_code, 302)
        os = ManutencaoEquipamento.query.one()
        self.assertEqual(os.prefeitura_id, self.drones[0].prefeitura_id)
        path = f'/equipamentos/{self.drones[0].id}/manutencao/pecas'
        self.assertEqual(self.client.post(path, data={'peca_id': self.peca.id}).status_code, 302)
        self.assertEqual(ManutencaoPecaUso.query.one().prefeitura_id, 1)
        self.login('manutencao')
        self.assertIn(os.numero_os, self.client.get('/equipamentos/em-manutencao').text)
        self.assertEqual(self.client.get(f'/equipamentos/manutencoes/{os.id}').status_code, 200)

    def test_opening_requires_authentication_and_csrf(self):
        self.app.config['CSRF_PROTECTION_ENABLED'] = True
        response = self.client.get('/equipamentos/manutencoes/nova')
        self.assertIn('name="_csrf_token"', response.text)
        self.assertEqual(self.open_os().status_code, 403)
        with self.client.session_transaction() as stored:
            token = stored['_ija_csrf']
        self.assertEqual(self.open_os(_csrf_token=token).status_code, 302)
        with self.client.session_transaction() as stored:
            stored.clear()
        self.assertEqual(self.client.get('/equipamentos/manutencoes/nova').status_code, 302)

    def test_requires_drone_and_reason_without_changing_equipment(self):
        response = self.client.post('/equipamentos/manutencoes/nova', data={})
        self.assertIn('Selecione o drone.', response.text)
        self.assertIn('Informe o motivo', response.text)
        self.assertEqual(ManutencaoEquipamento.query.count(), 0)
        self.assertEqual(self.drones[0].status, 'Ativo')

    def test_other_municipality_is_never_mutated(self):
        response = self.client.get('/equipamentos/manutencoes/nova')
        self.assertNotIn('DRONE-2', response.text)
        self.assertEqual(self.open_os(self.drones[1]).status_code, 404)
        for path in (f'/drones/{self.drones[1].id}/manutencao',
                     f'/equipamentos/{self.drones[1].id}/manutencao/encerrar',
                     f'/equipamentos/{self.drones[1].id}/manutencao/pecas'):
            self.assertEqual(self.client.post(path).status_code, 404)
        self.assertEqual(self.drones[1].status, 'Ativo')

    def test_consultation_does_not_allow_open_consumption_or_closure(self):
        self.open_os()
        self.configure(['prefeitura.equipamentos.consultar'])
        self.assertNotIn('Abrir OS de manutenção', self.client.get('/equipamentos/em-manutencao').text)
        self.assertEqual(self.client.get('/equipamentos/manutencoes/nova').status_code, 403)
        for path in ('/equipamentos/manutencoes/nova', f'/drones/{self.drones[0].id}/manutencao',
                     f'/equipamentos/{self.drones[0].id}/manutencao/pecas',
                     f'/equipamentos/{self.drones[0].id}/manutencao/encerrar'):
            self.assertEqual(self.client.post(path).status_code, 403)
        self.assertEqual(self.peca.quantidade, 3)
        self.assertEqual(ManutencaoEquipamento.query.one().status, 'aberta')

    def test_insufficient_stock_does_not_consume_parts(self):
        self.open_os()
        response = self.client.post(f'/equipamentos/{self.drones[0].id}/manutencao/pecas',
            data={'peca_id': self.peca.id, f'quantidade_{self.peca.id}': 4})
        self.assertIn('Quantidade maior que o estoque', response.text)
        self.assertEqual(self.peca.quantidade, 3)
        self.assertEqual(ManutencaoPecaUso.query.count(), 0)
