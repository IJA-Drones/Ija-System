from datetime import date, time
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from flask import Flask, Blueprint, g
from flask_login import LoginManager
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import MultiDict
from app.extensions import db
from app.models import Prefeitura, Usuario, Solicitacao, Equipe, OrdemServico, PrefeituraEmailConfig, ConsultaEmailEnvio
from app.modules.consultas import service, exporters, mail
from app.modules.consultas.routes import register_routes
from app.modules.gestao_ti.permissions import register_permission_security


@pytest.fixture
def app():
    app=Flask(__name__)
    app.config.update(TESTING=True,SECRET_KEY='isolated-only',SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',CENTRAL_TI_ENABLED=False)
    db.init_app(app);manager=LoginManager(app);manager.user_loader(lambda uid:db.session.get(Usuario,int(uid)))
    bp=Blueprint('main',__name__);register_permission_security(bp);register_routes(bp)
    from app.modules.configuracoes.routes import register_routes as config_routes
    config_routes(bp);app.register_blueprint(bp)
    @app.before_request
    def clear_user(): g.pop('_login_user', None)
    with app.app_context():
        db.create_all()
        cities=[Prefeitura(nome='Cidade A',slug='a'),Prefeitura(nome='Cidade B',slug='b')];db.session.add_all(cities);db.session.flush()
        users=[Usuario(nome_uvis='A',login='a',senha_hash='unused',tipo_usuario='prefeitura_admin',prefeitura_id=cities[0].id),
               Usuario(nome_uvis='B',login='b',senha_hash='unused',tipo_usuario='prefeitura_admin',prefeitura_id=cities[1].id)]
        db.session.add_all(users);db.session.flush()
        team=Equipe(nome_equipe='Equipe A',regiao='NORTE',prefeitura_id=cities[0].id);db.session.add(team);db.session.flush()
        for i,(owner,bairro,status) in enumerate([(users[0],'Centro','APROVADO'),(users[0],'Jardim','PENDENTE'),(users[1],'Secreto','APROVADO')]):
            row=Solicitacao(usuario_id=owner.id,prefeitura_id=owner.prefeitura_id,data_agendamento=date(2026,10,17),hora_agendamento=time(10),
                foco='Piscina',tipo_visita='Aedes',cep='01000000',logradouro='Rua Teste',bairro=bairro,cidade='Cidade',uf='SP',status=status,
                latitude='-23' if i==0 else None,longitude='-46' if i==0 else None)
            db.session.add(row);db.session.flush()
            if i==0:db.session.add(OrdemServico(solicitacao_id=row.id,equipe_id=team.id,quantidade_imagens_registradas=4,quantidade_videos_registradas=2))
        db.session.commit()
    yield app
    with app.app_context():db.session.remove();db.drop_all()


def spec(**kwargs):return dict({'columns':['id','bairro','status','imagens','videos'],'source':'solicitacoes'},**kwargs)
def user():return db.session.get(Usuario,1)
def client(app,uid=1):
    c=app.test_client()
    with c.session_transaction() as s:s['_user_id']=str(uid);s['_fresh']=True
    return c


def test_scope_consistent_views_and_filters(app):
    with app.app_context():
        result=service.execute(user(),spec())
        assert result['total']==2 and sum(result['chart'].values())==2
        assert len(result['points'])==1 and result['unmapped']==1
        assert service.facets(user())['bairro']==['Centro','Jardim']
        filtered=service.execute(user(),spec(filters={'bairro':'Centro','categoria':'Aedes','status':'APROVADO','inicio':'2026-10-17','fim':'2026-10-17'}))
        assert filtered['total']==len(filtered['points'])==1
        assert filtered['rows'][0][1]=='Centro'
        assert service.execute(user(),spec(filters={'bairro':'Secreto'}))['total']==0


def test_conditions_exceptions_and_formulas(app):
    with app.app_context():
        result=service.execute(user(),spec(formulas=[{'label':'Mídias','expression':'imagens + videos'},{'label':'Zero','expression':'imagens / 0'}],group='bairro',
            exclusions=[{'field':'status','op':'eq','value':'PENDENTE'}]))
        assert result['total']==1 and result['rows'][0][-2:]==['6.0','Não informado']
        assert result['groups'][0]['totals']['formula_0']==6
        result=service.execute(user(),spec(exclusions=[{'field':'imagens','op':'eq','value':4}]))
        assert result['total']==1  # NULL does not match exclusion
        assert service.execute(user(),spec(source='ordens_servico'))['total']==1


@pytest.mark.parametrize('expression',["__import__('os')",'imagens.__class__','[1][0]','imagens ** 999','imagens % 2','sum(imagens)','bairro + 1','1e999','True',''])
def test_formula_rejects_execution_and_unsafe_operations(expression):
    with pytest.raises(service.QueryError):service.formula(expression)


@pytest.mark.parametrize('bad',[{'source':[]},{'columns':['senha_hash']},{'columns':['id','id']},{'columns':[]},
    {'conditions':[{'field':{},'op':'eq','value':'x'}]},{'filters':{'inicio':'not-a-date'}},
    {'filters':{'inicio':'2026-11-01','fim':'2026-10-01'}},{'conditions':[{'field':'imagens','op':'contains','value':'x'}]},
    {'formats':{'id':{}}},{'group':'senha_hash'}])
def test_bad_payload_is_validation_error(bad):
    with pytest.raises(service.QueryError):service.validate(spec(**bad))


def test_limit_refuses_truncated_results(app,monkeypatch):
    with app.app_context():
        monkeypatch.setattr(service,'MAX_ROWS',1)
        with pytest.raises(service.QueryError,match='nenhum resultado foi cortado'):service.execute(user(),spec())


def test_missing_tenant_fails_closed(app):
    with app.app_context():
        u=user();u.prefeitura_id=None
        assert service.execute(u,spec())['total']==0


def test_catalog_private_and_versioned(app):
    c=client(app);created=c.post('/relatorios/consultas/catalogo',json={'nome':'Minha consulta','definicao':spec()})
    assert created.status_code==200
    key=created.json['id'];version=created.json['versao']
    assert len(c.get('/relatorios/consultas/catalogo').json['items'])==1
    other=client(app,2)
    assert other.get('/relatorios/consultas/catalogo').json['items']==[]
    assert other.delete(f'/relatorios/consultas/catalogo/{key}').status_code==404
    assert c.post('/relatorios/consultas/catalogo',json={'id':key,'versao':version,'nome':'Nova','definicao':spec()}).status_code==200
    assert c.post('/relatorios/consultas/catalogo',json={'id':key,'versao':version,'nome':'Antiga','definicao':spec()}).status_code==409


def test_export_pdf_excel_and_formula_injection(app):
    import openpyxl
    from pypdf import PdfReader
    with app.app_context():
        row=db.session.get(Solicitacao,1);row.bairro='=HYPERLINK("https://invalid")';db.session.commit()
        result=service.execute(user(),spec())
        book=openpyxl.load_workbook(exporters.excel(result))
        assert book.active['B2'].data_type=='s' and book.active['B2'].value.startswith("'=")
        pdf=exporters.pdf(result,user());text=''.join(p.extract_text() for p in PdfReader(pdf).pages)
        assert 'Consulta personalizada' in text and 'Secreto' not in text
        result['total']=2001
        with pytest.raises(service.QueryError):exporters.pdf(result,user())


def test_preview_failure_can_be_retried(app):
    c=client(app)
    with patch.object(service,'execute',side_effect=OperationalError('query',{},Exception())):
        response=c.post('/relatorios/consultas/executar',json=spec())
        assert response.status_code==503 and 'não foi concluída' in response.json['error']
    assert c.post('/relatorios/consultas/executar',json=spec()).json['total']==2


def test_email_disabled_and_no_accidental_delivery(app):
    with patch.object(mail.smtplib,'SMTP') as smtp:
        assert client(app).post('/relatorios/consultas/email',json={'definicao':spec(),'destinatario':'a@example.org'}).status_code==503
        smtp.assert_not_called()


def test_smtp_message_tls_and_uncertain_failure(app):
    with app.app_context():
        app.config.update(REPORT_SMTP_HOST='smtp.invalid',REPORT_SMTP_FROM='reports@example.org')
        with patch.object(mail.smtplib,'SMTP') as factory:
            smtp=factory.return_value.__enter__.return_value;smtp.send_message.return_value={}
            mail.send_report('to@example.org',b'%PDF-test')
            smtp.starttls.assert_called_once();message=smtp.send_message.call_args.args[0]
            assert message['To']=='to@example.org' and len(list(message.iter_attachments()))==1
            with pytest.raises(ValueError):mail.send_report('to@example.org\nBcc: other@example.org',b'x')
        with patch.object(mail.smtplib,'SMTP',side_effect=OSError('timeout')):
            db.session.add(PrefeituraEmailConfig(prefeitura_id=1,destinatario='to@example.org',atualizado_por_id=1));db.session.commit()
            c=client(app)
            from uuid import uuid4
            payload={'definicao':spec(filters={'prefeitura':'1'}),'prefeitura_id':1,'versao':1,'destinatario':'to@example.org','envio_id':str(uuid4())}
            assert c.post('/relatorios/consultas/email',json=payload).status_code==502
            assert db.session.get(ConsultaEmailEnvio,payload['envio_id']).estado=='incerto'


def test_migration_additive_roundtrip():
    import importlib.util
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path=Path(__file__).parents[1]/'migrations/versions/a12f07c98e43_saved_queries.py'
    spec_=importlib.util.spec_from_file_location('migration_queries',path);mod=importlib.util.module_from_spec(spec_);spec_.loader.exec_module(mod)
    engine=sa.create_engine('sqlite://')
    with engine.begin() as conn:
        mod.op=Operations(MigrationContext.configure(conn));mod.upgrade()
        assert sa.inspect(conn).has_table('consultas_salvas')
        mod.downgrade();assert not sa.inspect(conn).has_table('consultas_salvas')
