"""OS de origem, confirmação explícita da inspeção e persistência municipal."""

from datetime import date, time
import unittest

from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Equipe, OrdemServico, Prefeitura, Solicitacao
from app.modules.vigilancia.field_models import CampoOsReferencia
from app.modules.vigilancia.field_store import FieldStore
from tests import test_central_ti as base
from tests import test_central_ti_permissions as permissions


class VigilanciaOsTests(unittest.TestCase):
    tearDown = base.CentralTiTests.tearDown
    login = base.CentralTiTests.login
    def setUp(self):
        base.CentralTiTests.setUp(self)
        self.app.config.update(VIGILANCIA_IMPORT_ENABLED=True)
        self.configure = permissions.CentralTiPermissionsTests.configure.__get__(self)
        db.session.add_all([Prefeitura(id=7, nome='Sete', slug='sete'), Prefeitura(id=8, nome='Oito', slug='oito')])
        self.users['prefeitura_admin'].prefeitura_id = 7
        self.users['uvis'].prefeitura_id = 7
        team = Equipe(id=701, prefeitura_id=7, nome_equipe='Equipe de teste')
        db.session.add(team)
        db.session.flush()
        for oid, prefeitura in ((701, 7), (702, 8), (703, 7)):
            db.session.add(Solicitacao(id=oid, prefeitura_id=prefeitura, usuario_id=self.users['uvis'].id,
                data_agendamento=date(2026, 10, 19), hora_agendamento=time(9), foco='Pneu',
                cep='00000-000', logradouro='Rua Sintética', numero='10', bairro='Bairro da OS',
                cidade='Cidade de teste', uf='PE', latitude='-8.35', longitude='-36.69', equipe_id=701))
        db.session.add(OrdemServico(solicitacao_id=701, equipe_id=701, larva_visualizada='SIM',
            nome_rf_ace_responsavel_os='Agente de teste', data_aplicacao=date(2026, 10, 18)))
        db.session.commit()
        self.login('prefeitura_admin')

    def field_data(self, **changes):
        self.client.get('/vigilancia/campo')
        with self.client.session_transaction() as session:
            csrf = session['_ija_csrf']
        return dict(os_id='701', demo='false', autorizado='sim', _csrf_token=csrf,
            origem='LIRAA', levantamento_codigo='L-01', estrato_codigo='E-01',
            imovel_codigo='IM-01', inspecao_codigo='VIS-01', data_inspecao='2026-10-19',
            bairro='Bairro da OS', area_codigo='A-01', situacao='INSPECIONADO', positivo_aedes='NAO',
            latitude='-8.35', longitude='-36.69', responsavel_inspecao='Agente de teste', amostra_liraa='sim') | changes

    def test_prefill_never_deduces_inspection_result_date_or_property_identity(self):
        response = self.client.get('/vigilancia/campo?os_id=701&demo=false')
        self.assertEqual(response.status_code, 200)
        self.assertIn('value="Bairro da OS"', response.text)
        self.assertIn('value="Agente de teste"', response.text)
        self.assertIn('Equipe de teste', response.text)
        self.assertIn('Selecione a situação da visita', response.text)
        self.assertNotIn('value="INSPECIONADO" selected', response.text)
        self.assertNotIn('value="SIM" selected', response.text)
        self.assertNotIn('value="2026-10-18"', response.text)

    def test_confirm_preserves_reference_and_counts_negative_inspection(self):
        response = self.client.post('/vigilancia/campo', data=self.field_data())
        self.assertEqual(response.status_code, 303)
        store = FieldStore()
        batch = store.history(7)[0]
        self.assertEqual(db.session.get(CampoOsReferencia, batch['id']).solicitacao_id, 701)
        self.assertEqual(store.records(7, demo=False), [])
        with self.client.session_transaction() as session:
            csrf = session['_ija_csrf']
        response = self.client.post('/vigilancia/importacoes', data=dict(acao='confirmar', lote=batch['id'], _csrf_token=csrf))
        self.assertEqual(response.status_code, 303)
        saved = store.get(batch['id'], 7)
        self.assertEqual(saved['report']['vinculo_os']['responsavel'], 'Agente de teste')
        self.assertEqual(saved['report']['indicadores'][0]['iip'], 0)
        self.assertEqual(db.session.get(Solicitacao, 701).bairro, 'Bairro da OS')
        self.assertEqual(self.client.post('/vigilancia/campo', data=self.field_data()).status_code, 303)
        self.assertEqual(len(store.history(7)), 1)

    def test_scope_repeated_ids_demo_and_sample_must_be_valid(self):
        self.assertEqual(self.client.get('/vigilancia/campo?os_id=702&demo=false').status_code, 404)
        self.assertEqual(self.client.post('/vigilancia/campo', data=self.field_data(os_id='702')).status_code, 404)
        self.assertEqual(self.client.get('/vigilancia/campo?os_id=701&os_id=703&demo=false').status_code, 400)
        self.assertEqual(self.client.get('/vigilancia/campo?os_id=701&demo=true').status_code, 400)
        self.assertEqual(self.client.post('/vigilancia/campo', data=self.field_data(amostra_liraa='')).status_code, 400)
        self.assertEqual(self.client.post('/vigilancia/campo', data=self.field_data(responsavel_inspecao='')).status_code, 400)
        self.assertEqual(self.client.post('/vigilancia/campo', data=self.field_data(_csrf_token='invalid')).status_code, 403)
        self.assertEqual(FieldStore().history(7), [])

    def test_not_inspected_has_no_positive_result_or_iip_denominator(self):
        response = self.client.post('/vigilancia/campo', data=self.field_data(situacao='NAO_INSPECIONADO', positivo_aedes=''))
        self.assertEqual(response.status_code, 303)
        store = FieldStore()
        saved = store.confirm(store.history(7)[0]['id'], prefeitura=7, actor=str(self.users['prefeitura_admin'].id))
        self.assertEqual(saved['report']['indicadores'][0]['imoveis_inspecionados'], 0)
        self.assertIsNone(saved['report']['indicadores'][0]['iip'])

    def test_confirmation_rechecks_os_scope_and_prevents_cross_os_reuse(self):
        self.client.post('/vigilancia/campo', data=self.field_data())
        store = FieldStore()
        first = store.history(7)[0]
        store.confirm(first['id'], prefeitura=7, actor=str(self.users['prefeitura_admin'].id))
        self.assertEqual(self.client.post('/vigilancia/campo', data=self.field_data(os_id='703')).status_code, 303)
        pending = store.history(7)[0]
        with self.client.session_transaction() as session:
            csrf = session['_ija_csrf']
        response = self.client.post('/vigilancia/importacoes', data=dict(acao='confirmar', lote=pending['id'], _csrf_token=csrf))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(store.records(7, demo=False)), 1)

    def test_delegated_uvis_can_only_select_its_own_os(self):
        self.app.config['CENTRAL_TI_ENFORCE_PERMISSIONS'] = True
        self.configure('uvis', ['prefeitura.vigilancia.consultar', 'prefeitura.vigilancia.editar'])
        self.login('uvis')
        self.assertEqual(self.client.get('/vigilancia/campo?os_id=701&demo=false').status_code, 200)
        db.session.get(Solicitacao, 703).usuario_id = self.users['admin'].id
        db.session.commit()
        self.assertEqual(self.client.get('/vigilancia/campo?os_id=703&demo=false').status_code, 404)

    def test_municipality_changed_after_review_blocks_confirmation(self):
        self.client.post('/vigilancia/campo', data=self.field_data())
        store = FieldStore()
        batch = store.history(7)[0]
        db.session.get(Solicitacao, 701).prefeitura_id = 8
        db.session.commit()
        with self.client.session_transaction() as session:
            csrf = session['_ija_csrf']
        response = self.client.post('/vigilancia/importacoes', data=dict(acao='confirmar', lote=batch['id'], _csrf_token=csrf))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(store.get(batch['id'], 7)['status'], 'VALIDADO')
        self.assertEqual(store.records(7, demo=False), [])
