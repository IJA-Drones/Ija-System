"""Citizen -> COVISA -> UVIS workflow, in-memory database only."""
import importlib.util
import re
import unittest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from flask import Flask, g
from flask_login import LoginManager
from pypdf import PdfReader
from sqlalchemy import inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.extensions import db
from app.models import Prefeitura, Usuario, RelatoSaude, RelatoSaudeEvento, Notificacao, Denuncia, Solicitacao, CentralTiPerfilConfiguracao, CentralTiSelecao
from app.routes import bp
from app.modules.auth.routes import bp as auth_bp
from app.shared.csrf_security import register_csrf_security
from app.modules.gestao_ti.permissions import validate_route_policy

ROOT=Path(__file__).resolve().parents[1]

class HealthReportsTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__, template_folder=str(ROOT/'app/templates'),static_folder=str(ROOT/'app/static'))
        self.app.config.update(TESTING=True,SECRET_KEY='isolated-health-tests-long-secret',SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            CSRF_PROTECTION_ENABLED=False, CENTRAL_TI_ENABLED=True, SESSION_PROTECTION=None)
        db.init_app(self.app)
        login=LoginManager(self.app);login.user_loader(lambda uid:db.session.get(Usuario,int(uid)))
        register_csrf_security(self.app)
        @self.app.before_request
        def clear():
            g.pop('_login_user',None);g.pop('_central_ti_permissions',None)
        self.app.register_blueprint(auth_bp);self.app.register_blueprint(bp)
        self.ctx=self.app.app_context();self.ctx.push();db.create_all()
        db.session.add_all([Prefeitura(id=1,nome='Prefeitura A',slug='a'),Prefeitura(id=2,nome='Prefeitura B',slug='b'),Prefeitura(id=3,nome='Inativa',slug='c',ativa=False)])
        specs=[(1,'visualizar',1,'COVISA'),(2,'uvis',1,'SUL'),(3,'uvis',1,'NORTE'),(4,'covisa',2,'COVISA'),(5,'uvis',2,'SUL'),(6,'dev',None,None),(7,'equipe_oceano',1,None),(8,'regional',1,'SUL'),(9,'covisa',None,'COVISA')]
        for uid,role,tenant,region in specs:
            db.session.add(Usuario(id=uid,login=f'health{uid}',senha_hash='test',nome_uvis=f'Unidade {uid}',tipo_usuario=role,prefeitura_id=tenant,regiao=region))
        db.session.commit();self.client=self.app.test_client()

    def tearDown(self):
        db.session.remove();db.drop_all();db.engine.dispose();self.ctx.pop()

    def login(self,uid):
        g.pop('_login_user',None)
        with self.client.session_transaction() as s:
            s.clear();s['_user_id']=str(uid);s['_fresh']=True

    def form(self):
        r=self.client.get('/portal-cidadao/relato-saude');self.assertEqual(r.status_code,200)
        with self.client.session_transaction() as s:
            csrf=s['_saude_csrf'];envio=s['_saude_envio']
        return dict(saude_csrf=csrf,envio_id=envio,prefeitura_id='1',nome='Nome Sigiloso',telefone='11999999999',
                    logradouro='Rua Privada',numero='10',bairro='Centro',descricao='Sintoma privado informado',consentimento='1')

    def create(self):
        self.payload=self.form()
        r=self.client.post('/portal-cidadao/relato-saude',data=self.payload)
        self.assertEqual(r.status_code,303,r.get_data(as_text=True)[:1000])
        return RelatoSaude.query.order_by(RelatoSaude.id.desc()).first()

    def action(self,uid,row,acao,expected=303,**extra):
        self.login(uid)
        r=self.client.get(f'/relatos-saude/{row.id}');self.assertEqual(r.status_code,200)
        with self.client.session_transaction() as s:csrf=s['_saude_csrf']
        data=dict(saude_csrf=csrf,versao=str(row.versao),acao=acao,**extra)
        response=self.client.post(f'/relatos-saude/{row.id}',data=data)
        self.assertEqual(response.status_code,expected,response.get_data(as_text=True)[:1000])
        db.session.refresh(row)
        return response

    def test_complete_workflow_notifications_and_no_focus_records(self):
        row=self.create()
        self.assertEqual(row.status,'RECEBIDO');self.assertIsNone(row.uvis_usuario_id)
        self.assertEqual([n.usuario_id for n in Notificacao.query.all()],[1])
        receipt=self.client.get('/portal-cidadao/relato-saude/recebido')
        self.assertIn(row.protocolo,receipt.text);self.assertNotIn('Sintoma privado',receipt.text)
        self.assertIn('no-store',receipt.headers['Cache-Control'])
        self.action(1,row,'ciencia');self.assertEqual(row.status,'EM_ANALISE')
        self.action(1,row,'encaminhar',uvis_usuario_id='2',observacao='Avaliar território.')
        self.action(2,row,'ciencia');self.assertEqual(row.status,'EM_ATENDIMENTO')
        self.action(2,row,'acompanhamento',observacao='Contato realizado e encaminhado ao serviço local.')
        self.action(2,row,'concluir',observacao='Providências registradas pela unidade.')
        self.assertEqual(row.status,'CONCLUIDO')
        self.assertEqual(RelatoSaudeEvento.query.count(),6)
        self.assertEqual(Notificacao.query.count(),2)
        self.assertEqual(Denuncia.query.count(),0);self.assertEqual(Solicitacao.query.count(),0)
        self.action(1,row,'acompanhamento',expected=400,observacao='Não alterar encerrado')

    def test_tenant_uvis_and_role_isolation(self):
        row=self.create()
        for uid in (2,3,4,5,7,8,9):
            self.login(uid)
            self.assertIn(self.client.get(f'/relatos-saude/{row.id}').status_code,(403,404))
            pdf=self.client.get('/relatos-saude/relatorio.pdf')
            if pdf.status_code==200:
                self.assertNotIn(row.protocolo, ''.join(p.extract_text() for p in PdfReader(BytesIO(pdf.data)).pages))
            else:self.assertEqual(pdf.status_code,403)
        self.action(1,row,'ciencia')
        self.action(1,row,'encaminhar',expected=400,uvis_usuario_id='5',observacao='Outra prefeitura')
        self.action(1,row,'encaminhar',uvis_usuario_id='2',observacao='Encaminhar')
        self.action(2,row,'encaminhar',expected=403,uvis_usuario_id='3',observacao='Não permitido')
        self.action(1,row,'encaminhar',uvis_usuario_id='3',observacao='Redirecionar')
        self.login(2);self.assertEqual(self.client.get(f'/relatos-saude/{row.id}').status_code,404)
        result=self.action(3,row,'devolver',observacao='Território precisa de revisão')
        self.assertEqual(result.headers['Location'],'/relatos-saude')
        self.assertEqual(self.client.get(result.headers['Location']).status_code,200)
        self.assertIsNone(row.uvis_usuario_id)
        self.login(3);self.assertEqual(self.client.get(f'/relatos-saude/{row.id}').status_code,404)

    def test_public_validation_csrf_idempotency_and_rate(self):
        payload=self.form()
        self.assertEqual(self.client.post('/portal-cidadao/relato-saude',data={**payload,'saude_csrf':'bad'}).status_code,403)
        for override in [{'prefeitura_id':'3'},{'prefeitura_id':'bad'},{'inicio_sintomas':'2999-01-01'}, {'inicio_sintomas':'bad'}, {'descricao':'x'*2001},{'consentimento':'0'},{'telefone':'2'},{'website':'spam'}]:
            self.assertEqual(self.client.post('/portal-cidadao/relato-saude',data={**payload,**override}).status_code,400)
        self.assertEqual(RelatoSaude.query.count(),0)
        self.assertEqual(self.client.post('/portal-cidadao/relato-saude',data=payload).status_code,303)
        self.assertEqual(self.client.post('/portal-cidadao/relato-saude',data=payload).status_code,303)
        self.assertEqual(RelatoSaude.query.count(),1);self.assertEqual(Notificacao.query.count(),1)
        self.app.config['RELATOS_SAUDE_MAX_HORA']=1
        other=self.form();self.assertEqual(self.client.post('/portal-cidadao/relato-saude',data=other).status_code,429)
        outsider=self.app.test_client();self.assertEqual(outsider.get('/portal-cidadao/relato-saude/recebido').status_code,302)

    def test_public_form_for_authenticated_user_and_global_csrf(self):
        self.login(1)
        self.app.config['CSRF_PROTECTION_ENABLED']=True
        payload=self.form()
        self.assertIn('Relatar suspeita de adoecimento',self.client.get('/portal-cidadao/relato-saude').text)
        self.assertEqual(self.client.post('/portal-cidadao/relato-saude',data=payload).status_code,403)
        with self.client.session_transaction() as s: payload['_csrf_token']=s['_ija_csrf']
        self.assertEqual(self.client.post('/portal-cidadao/relato-saude',data={**payload,'envio_id':'inválido'}).status_code,400)
        self.assertEqual(self.client.post('/portal-cidadao/relato-saude',data=payload).status_code,303)

    def test_stale_edits_and_explicit_science(self):
        row=self.create()
        self.action(1,row,'concluir',expected=400,observacao='Prematuro')
        self.action(1,row,'ciencia')
        self.action(1,row,'ciencia',expected=400)
        self.login(1);self.client.get(f'/relatos-saude/{row.id}')
        with self.client.session_transaction() as s:csrf=s['_saude_csrf']
        response=self.client.post(f'/relatos-saude/{row.id}',data={'saude_csrf':csrf,'versao':'1','acao':'concluir','observacao':'Stale'})
        self.assertEqual(response.status_code,409);self.assertEqual(row.status,'EM_ANALISE')
        self.assertEqual(RelatoSaudeEvento.query.count(),2)

    def test_transaction_failure_rolls_back_report_history_and_notifications(self):
        payload=self.form()
        with patch.object(db.session,'commit',side_effect=RuntimeError('test')):
            self.assertEqual(self.client.post('/portal-cidadao/relato-saude',data=payload).status_code,500)
        self.assertEqual(RelatoSaude.query.count(),0);self.assertEqual(RelatoSaudeEvento.query.count(),0);self.assertEqual(Notificacao.query.count(),0)

    def test_consistent_filters_and_pdf_without_health_data(self):
        row=self.create();row.criado_em=datetime(2026,10,17,2,30);db.session.commit()
        self.login(1)
        response=self.client.get('/relatos-saude?inicio=2026-10-16&fim=2026-10-16')
        self.assertEqual(response.status_code,200);self.assertIn(row.protocolo,response.text)
        self.assertNotIn('Nome Sigiloso',response.text)
        pdf=self.client.get('/relatos-saude/relatorio.pdf?inicio=2026-10-16&fim=2026-10-16')
        self.assertEqual(pdf.status_code,200)
        text=''.join(p.extract_text() for p in PdfReader(BytesIO(pdf.data)).pages)
        self.assertIn(row.protocolo,text);self.assertIn('Total: 1',text)
        for private in ('Nome Sigiloso','Rua Privada','Sintoma privado','99999'):self.assertNotIn(private,text)
        for url in ['/relatos-saude?inicio=2026-10-17','/relatos-saude?prefeitura_id=2','/relatos-saude?status=CONCLUIDO']:
            self.assertNotIn(row.protocolo,self.client.get(url).text)
        for query in ['inicio=invalid','inicio=2026-10-18&fim=2026-10-16','status=bad','prefeitura_id=x']:
            self.assertEqual(self.client.get('/relatos-saude?'+query).status_code,400)

    def test_active_central_permissions_and_fixed_role_boundary(self):
        row=self.create();self.app.config['CENTRAL_TI_ENFORCE_PERMISSIONS']=True
        for role in ('covisa','equipe_oceano'):
            db.session.add(CentralTiPerfilConfiguracao(perfil_codigo=role,versao=2))
            for code in ('area:prefeitura','prefeitura.relatos_saude.consultar','prefeitura.relatos_saude.exportar'):
                db.session.add(CentralTiSelecao(perfil_codigo=role,codigo=code))
        db.session.commit()
        self.login(1);self.assertEqual(self.client.get(f'/relatos-saude/{row.id}').status_code,200)
        with self.client.session_transaction() as s:csrf=s['_saude_csrf']
        self.assertEqual(self.client.post(f'/relatos-saude/{row.id}',data={'saude_csrf':csrf,'versao':'1','acao':'ciencia'}).status_code,403)
        self.login(7);self.assertEqual(self.client.get('/relatos-saude').status_code,403)
        validate_route_policy(self.app)

    def test_new_migration_roundtrip(self):
        db.session.remove()
        RelatoSaudeEvento.__table__.drop(db.engine);RelatoSaude.__table__.drop(db.engine)
        path=ROOT/'migrations/versions/c94a820d173b_relatos_saude.py'
        spec=importlib.util.spec_from_file_location('health_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                self.assertIn('relatos_saude',inspect(connection).get_table_names())
                module.downgrade()
                self.assertNotIn('relatos_saude',inspect(connection).get_table_names())
                module.upgrade()
        self.create()

if __name__=='__main__':unittest.main()
