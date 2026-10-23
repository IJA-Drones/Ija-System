"""Public directory, publication boundaries and municipal editing; isolated DB only."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest
from flask import Flask
from flask_login import LoginManager
from sqlalchemy import create_engine, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.extensions import db
from app.models import Prefeitura, Usuario, PrefeituraContatoPublico, PrefeituraContatoHistorico, PrefeituraEmailConfig, CentralTiPerfilConfiguracao, CentralTiSelecao
from app.routes import bp
from app.modules.auth.routes import bp as auth_bp
from app.modules.contatos_publicos.service import public_directory, validate
from app.modules.portal_cidadao.chatbot import public_instructions
from app.shared.csrf_security import CSRF_SESSION_KEY

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def app():
    a=Flask(__name__,template_folder=str(ROOT/'app/templates'),static_folder=str(ROOT/'app/static'))
    a.config.update(TESTING=True,SECRET_KEY='isolated-contact-tests',SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',SESSION_PROTECTION=None)
    db.init_app(a);login=LoginManager(a);login.login_view='auth.login';login.user_loader(lambda uid:db.session.get(Usuario,int(uid)))
    a.register_blueprint(auth_bp);a.register_blueprint(bp)
    with a.app_context():
        db.create_all()
        db.session.add_all([Prefeitura(id=1,nome='Alfa',slug='alfa'),Prefeitura(id=2,nome='Beta',slug='beta'),Prefeitura(id=3,nome='Inativa',slug='inativa',ativa=False)])
        for uid,role,city,region in [(1,'covisa',1,'COVISA'),(2,'covisa',2,'COVISA'),(3,'dev',None,None),(4,'diretor',None,None),(5,'uvis',1,None),(6,'covisa',None,'COVISA'),(7,'visualizar',1,'COVISA')]:
            db.session.add(Usuario(id=uid,login=f'contacts{uid}',senha_hash='unused',nome_uvis=f'Usuário {uid}',tipo_usuario=role,prefeitura_id=city,regiao=region))
        db.session.add(PrefeituraEmailConfig(prefeitura_id=1,destinatario='privado@example.org',atualizado_por_id=1))
        db.session.commit()
    yield a
    with a.app_context():db.session.remove();db.drop_all();db.engine.dispose()


def client(a,uid=1):
    c=a.test_client()
    if uid:
        with c.session_transaction() as s:s['_user_id']=str(uid);s['_fresh']=True;s[CSRF_SESSION_KEY]='token'
    return c


def payload(**kw):
    return dict(dict(_csrf_token='token',versao='0',publicado='1',telefone='(11) 3000-1234',whatsapp='+55 11 99999-1234',instagram='@prefeitura_alfa',email='publico@example.org',horario='Segunda a sexta, 8h às 17h',servicos='Orientações da vigilância municipal.'),**kw)


def test_tenant_permissions_csrf_and_version(app):
    c=client(app)
    assert c.post('/configuracoes/contatos/2',data=payload()).status_code==404
    assert c.post('/configuracoes/contatos/1',data=payload(_csrf_token='wrong')).status_code==403
    assert c.post('/configuracoes/contatos/1',data=payload(prefeitura_id='2')).status_code==403
    assert c.post('/configuracoes/contatos/1',data=payload()).status_code==303
    assert c.post('/configuracoes/contatos/1',data=payload()).status_code==409
    assert client(app,5).get('/configuracoes/contatos/1').status_code==403
    assert client(app,6).get('/configuracoes/contatos/1').status_code==404
    assert client(app,4).get('/configuracoes/contatos/2').status_code==200
    assert client(app,4).post('/configuracoes/contatos/2',data=payload()).status_code==403
    assert client(app,3).post('/configuracoes/contatos/2',data=payload()).status_code==303
    assert client(app,7).post('/configuracoes/contatos/1',data=payload(versao='1')).status_code==303
    with app.app_context():
        assert PrefeituraContatoHistorico.query.count()==3
        assert db.session.get(PrefeituraEmailConfig,1).destinatario=='privado@example.org'


def test_publication_and_azul_share_current_allowlist(app):
    c=client(app)
    c.post('/configuracoes/contatos/1',data=payload(publicado='0'))
    anon=client(app,None)
    html=anon.get('/portal-cidadao/contatos').text
    assert 'Alfa' in html and 'Beta' in html and 'Inativa' not in html
    assert 'publico@example.org' not in html and 'privado@example.org' not in html
    with app.app_context():assert 'publico@example.org' not in public_instructions()
    assert c.post('/configuracoes/contatos/1',data=payload(versao='1')).status_code==303
    html=anon.get('/portal-cidadao/contatos?prefeitura=1').text
    assert 'https://wa.me/5511999991234' in html and 'https://www.instagram.com/prefeitura_alfa/' in html
    assert 'mailto:publico@example.org' in html
    with app.app_context():
        ctx=public_instructions();assert 'publico@example.org' in ctx and 'privado@example.org' not in ctx
        assert 'senha_hash' not in ctx and 'atualizado_por_id' not in ctx
    assert c.post('/configuracoes/contatos/1',data=payload(versao='2',publicado='0')).status_code==303
    with app.app_context():assert 'publico@example.org' not in public_instructions()
    with app.app_context():
        db.session.get(PrefeituraContatoPublico,1).publicado=True
        db.session.get(Prefeitura,1).ativa=False;db.session.commit()
        assert 'publico@example.org' not in public_instructions()


@pytest.mark.parametrize('changes',[
 {'instagram':'https://instagram.com.evil.test/abc'}, {'instagram':'javascript:alert(1)'},
 {'instagram':'https://www.instagram.com/a?next=evil'}, {'instagram':'https://evil@instagram.com/a'},
 {'instagram':'https://instagram.com/p/123/'}, {'telefone':'123'}, {'whatsapp':'11<script>123456789'},
 {'email':'a@example.org\nBcc:x@example.org'}, {'email':'a@example.org?bcc=x@evil.org'},
 {'telefone':'','whatsapp':'','instagram':'','email':''}, {'servicos':'x'*6001}])
def test_reject_unsafe_or_invalid_contact(changes):
    with pytest.raises(ValueError):validate(payload(**changes))


def test_html_escaped_and_mailto_encoded(app):
    c=client(app);assert c.post('/configuracoes/contatos/1',data=payload(servicos='<script>alert(1)</script>',email='a?b@example.org')).status_code==303
    response=client(app,None).get('/portal-cidadao/contatos')
    assert '<script>alert(1)</script>' not in response.text
    assert '&lt;script&gt;' in response.text and 'mailto:a%3Fb@example.org' in response.text
    assert response.headers['Cache-Control']=='no-store'


def test_revoked_config_permission_denies(app):
    app.config.update(CENTRAL_TI_ENABLED=True,CENTRAL_TI_ENFORCE_PERMISSIONS=True)
    with app.app_context():
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='covisa',versao=2))
        db.session.add_all([CentralTiSelecao(perfil_codigo='covisa',codigo=c) for c in ('area:prefeitura','prefeitura.documentos.consultar')]);db.session.commit()
    c=client(app)
    assert c.get('/configuracoes/contatos/1').status_code==200
    assert c.post('/configuracoes/contatos/1',data=payload()).status_code==403


def test_missing_schema_is_explicit_and_not_exposed(app):
    with app.app_context():
        PrefeituraContatoHistorico.__table__.drop(db.engine)
        PrefeituraContatoPublico.__table__.drop(db.engine)
        assert public_directory()=={'disponivel':False,'prefeituras':[]}
    assert client(app,None).get('/portal-cidadao/contatos').status_code==503
    assert client(app).get('/configuracoes/contatos/1').status_code==503


def test_migration_roundtrip():
    path=ROOT/'migrations/versions/d82b46fa910c_contatos_publicos_prefeitura.py'
    spec=importlib.util.spec_from_file_location('contacts_migration',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    engine=create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            mod.upgrade();assert inspect(conn).has_table('prefeitura_contatos_publicos')
            mod.downgrade();assert not inspect(conn).has_table('prefeitura_contatos_publicos')
            mod.upgrade();assert inspect(conn).has_table('prefeitura_contatos_historico')
    engine.dispose()
