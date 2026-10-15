"""Exercise real login routes, persistent counters, isolation and manual release."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from flask import Flask
from flask_login import LoginManager
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import LoginBloqueio, LoginEvento, PilotoAgro, Usuario
from app.modules.auth.routes import bp as auth_bp
from app.routes import bp as main_bp
from app.shared import login_protection as protection
from app.shared.csrf_security import CSRF_SESSION_KEY, register_csrf_security

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'Senha de homologação 7!'


@pytest.fixture
def app(tmp_path, request):
    app = Flask(__name__, template_folder=str(ROOT/'app/templates'), static_folder=str(ROOT/'app/static'))
    app.config.update(TESTING=True, SECRET_KEY='login-protection-isolated-test-key-12345',
                      SQLALCHEMY_DATABASE_URI='sqlite:///'+str(tmp_path/'login.sqlite'),
                      SQLALCHEMY_ENGINE_OPTIONS={'pool_size':getattr(request, 'param', 1), 'max_overflow':0, 'pool_timeout':5},
                      LOGIN_PROTECTION_ENABLED=True, LOGIN_MAX_FAILURES=3, LOGIN_IP_MAX_FAILURES=8,
                      LOGIN_FAILURE_WINDOW_MINUTES=10, LOGIN_LOCKOUT_MINUTES=15)
    db.init_app(app)
    manager = LoginManager(app)
    manager.login_view = 'auth.login'
    manager.user_loader(lambda key: db.session.get(Usuario, int(key)))
    register_csrf_security(app)
    with patch('app.modules.backup.routes.start_daily_backup_scheduler'):
        app.register_blueprint(auth_bp)
        app.register_blueprint(main_bp)
    from zoneinfo import ZoneInfo
    from datetime import timezone
    app.jinja_env.globals['brazil_datetime'] = lambda value: value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/Sao_Paulo'))
    with app.app_context():
        db.create_all()
        db.session.add(PilotoAgro(id=1, nome='Piloto teste', ativo=True))
        db.session.add_all([
            Usuario(id=key, login=login, nome_uvis=login, senha_hash=generate_password_hash(PASSWORD),
                    tipo_usuario=role, piloto_agro_id=1 if role=='piloto_agro' else None)
            for key, login, role in [(1,'unidade','uvis'), (2,'piloto','piloto_agro'),
                                     (3,'dev','dev'), (4,'covisa','covisa'), (5,'admin','admin'), (6,'gestor','gestor_ti')]
        ])
        db.session.commit()
    with patch('app.modules.auth.routes.record_user_presence'):
        yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def post(app, path='/login', login='unidade', password='wrong', ip='192.0.2.1', **kwargs):
    return app.test_client().post(path, data={'login':login,'senha':password},
                                 environ_overrides={'REMOTE_ADDR':ip}, **kwargs)


def bucket(scope='conta', value='unidade'):
    return db.session.get(LoginBloqueio, protection.bucket_key(scope,value))


@pytest.mark.parametrize('path,login', [('/login','unidade'),('/uvis-operacional/login','unidade'),('/agro/login','piloto')])
def test_three_routes_block_and_persist_without_authenticating(app,path,login):
    assert post(app,path,login).status_code==200
    assert post(app,path,login).status_code==200
    response=post(app,path,login)
    assert response.status_code==429
    assert response.headers['Retry-After']=='900'
    assert response.headers['Cache-Control']=='private, no-store'
    html = response.get_data(as_text=True)
    assert 'Acesso temporariamente bloqueado' in html
    assert 'data-retry-after="900"' in html
    assert 'role="alert" tabindex="-1"' in html
    assert 'Aguarde cerca de 15 minutos' in html
    assert 'fale com o suporte do sistema' in html
    assert f'name="login" value="{login}"' in html
    assert 'const flashMessage =' not in html
    with patch.object(Usuario,'check_senha', side_effect=AssertionError('Blocked passwords must not be checked')):
        response=post(app,path,login,password=PASSWORD)
        assert response.status_code==429
    with app.app_context():
        assert bucket(value=login).falhas==3
        assert [e.resultado for e in LoginEvento.query.order_by(LoginEvento.id)]==['falha','falha','limite_atingido','bloqueado']
        assert all(PASSWORD not in str(e.__dict__) and 'wrong' not in str(e.__dict__) for e in LoginEvento.query)


def test_counter_shared_across_portals_and_source_addresses(app):
    assert post(app,'/login').status_code==200
    assert post(app,'/uvis-operacional/login',ip='192.0.2.2').status_code==200
    assert post(app,'/agro/login',ip='192.0.2.3').status_code==429
    assert post(app,password=PASSWORD,ip='192.0.2.4').status_code==429


def test_unknown_account_same_limit_and_case_variants(app):
    for name, status in [('missing',200),('MISSING',200),(' missing ',429)]:
        assert post(app,login=name).status_code==status
    with app.app_context():
        assert LoginBloqueio.query.filter_by(escopo='conta').count()==1


def test_success_resets_account_but_not_source_and_records_user(app):
    post(app)
    assert post(app,password=PASSWORD).status_code==302
    with app.app_context():
        assert bucket().falhas==0
        assert bucket('origem','192.0.2.1').falhas==1
        event=LoginEvento.query.order_by(LoginEvento.id.desc()).first()
        assert (event.resultado,event.usuario_id)==('sucesso',1)
    assert post(app).status_code==200
    assert post(app).status_code==200
    assert post(app).status_code==429


def test_ip_limit_covers_unknown_names_and_does_not_create_accounts_while_blocked(app):
    app.config['LOGIN_IP_MAX_FAILURES']=2
    assert post(app,login='unknown1').status_code==200
    assert post(app,login='unknown2').status_code==429
    assert post(app,login='unknown3').status_code==429
    with app.app_context():
        assert bucket('conta','unknown3') is None
        assert bucket('origem','192.0.2.1').falhas==2
    assert post(app,password=PASSWORD,ip='192.0.2.2').status_code==302


def test_block_has_fixed_expiry_and_new_window(app):
    start=datetime(2026,10,15,12)
    with patch.object(protection,'utcnow',return_value=start):
        for _ in range(3): post(app)
    with patch.object(protection,'utcnow',return_value=start+timedelta(minutes=14)):
        response=post(app,password=PASSWORD)
        assert response.status_code==429 and response.headers['Retry-After']=='60'
    with patch.object(protection,'utcnow',return_value=start+timedelta(minutes=15)):
        assert post(app,password=PASSWORD).status_code==302
    with app.app_context():
        assert bucket().falhas==0 and bucket().bloqueado_ate is None


def test_failure_window_expires_without_reaching_threshold(app):
    start=datetime(2026,10,15,12)
    with patch.object(protection,'utcnow',return_value=start):
        post(app); post(app)
    with patch.object(protection,'utcnow',return_value=start+timedelta(minutes=10)):
        assert post(app).status_code==200
    with app.app_context(): assert bucket().falhas==1


def test_forwarded_header_requires_explicit_trusted_proxy(app):
    with app.test_request_context('/', environ_base={'REMOTE_ADDR':'192.0.2.1'}, headers={'X-Forwarded-For':'203.0.113.9'}):
        assert protection.client_ip()=='192.0.2.1'
    app.config['LOGIN_TRUSTED_PROXY_CIDRS']='192.0.2.0/24'
    with app.test_request_context('/', environ_base={'REMOTE_ADDR':'192.0.2.1'}, headers={'X-Forwarded-For':'198.51.100.8, 203.0.113.9'}):
        assert protection.client_ip()=='203.0.113.9'
    with app.test_request_context('/', environ_base={'REMOTE_ADDR':'192.0.2.1'}, headers={'X-Forwarded-For':'malformed'}):
        assert protection.client_ip()=='192.0.2.1'


def test_persistence_failure_denies_login_and_keeps_no_browser_session(app):
    client=app.test_client()
    with patch.object(protection,'_event',side_effect=SQLAlchemyError('simulated')):
        response=client.post('/login',data={'login':'unidade','senha':PASSWORD})
    assert response.status_code==503
    with client.session_transaction() as state: assert '_user_id' not in state
    with app.app_context():
        assert LoginEvento.query.count()==0 and LoginBloqueio.query.count()==0


@pytest.mark.parametrize('app', [6], indirect=True)
def test_parallel_requests_do_not_lose_failures(app):
    # File-backed SQLite serializes the writes. PostgreSQL uses row locks/upsert.
    checked=[]
    @protection.protect_login('principal')
    def reject(login,password, *, auth_session=None):
        checked.append(login)
        return None
    def attempt(_):
        with app.test_request_context('/',environ_base={'REMOTE_ADDR':'192.0.2.1'}):
            try:
                reject('parallel','wrong')
                return 'falha'
            except protection.LoginBlocked:
                return 'bloqueado'
    with ThreadPoolExecutor(max_workers=6) as executor:
        results=list(executor.map(attempt,range(6)))
    assert len(checked)==3 and results.count('bloqueado')==4
    with app.app_context():
        assert bucket(value='parallel').falhas==3
        assert LoginEvento.query.count()==6


def authorized_client(app,key):
    client=app.test_client()
    with client.session_transaction() as state:
        state['_user_id']=str(key); state['_fresh']=True
        state[CSRF_SESSION_KEY]='known-csrf'
    return client


def test_dev_release_requires_csrf_reason_and_keeps_audit(app):
    for _ in range(3): post(app)
    key=protection.bucket_key('conta','unidade')
    client=authorized_client(app,3)
    page=client.get('/dev/seguranca-login')
    assert page.status_code==200 and 'unidade' in page.text
    path=f'/dev/seguranca-login/{key}/desbloquear'
    assert client.post(path,data={'motivo':'Conferido pelo suporte'}).status_code==403
    assert client.post(path,data={'_csrf_token':'known-csrf','motivo':'x'}).status_code==400
    assert client.post(path,data={'_csrf_token':'known-csrf','motivo':'Conferido pelo suporte'}).status_code==303
    assert post(app,password=PASSWORD).status_code==302
    with app.app_context():
        events=LoginEvento.query.all()
        released=next(e for e in events if e.resultado=='desbloqueio')
        assert released.responsavel_id==3 and 'Conferido pelo suporte' in released.motivo
        assert len(events)==5


@pytest.mark.parametrize('user_id',[1,4,5,6])
def test_only_dev_can_view_or_release_even_with_delegated_permissions(app,user_id):
    client=authorized_client(app,user_id)
    assert client.get('/dev/seguranca-login').status_code==403
    assert client.post('/dev/seguranca-login/key/desbloquear', data={'_csrf_token':'known-csrf','motivo':'Teste autorizado'}).status_code==403


def test_global_csrf_and_new_route_policy(app):
    from app.modules.gestao_ti.permissions import validate_route_policy
    validate_route_policy(app)
    app.config['CSRF_PROTECTION_ENABLED']=True
    for route in ['/login','/agro/login','/uvis-operacional/login']:
        assert post(app,route).status_code==403
    with app.app_context(): assert LoginEvento.query.count()==0


def test_wrong_portal_does_not_authenticate_or_reset_counter(app):
    assert post(app,'/uvis-operacional/login',login='dev',password=PASSWORD).status_code==200
    with app.app_context(): assert bucket(value='dev').falhas==1
    assert post(app,'/agro/login',login='dev',password=PASSWORD).status_code==200
    assert post(app,'/login',login='dev',password=PASSWORD).status_code==302


def test_migration_tables_foreign_keys_and_downgrade():
    spec=spec_from_file_location('login_migration',ROOT/'migrations/versions/b82e0d5f314c_login_protection.py')
    migration=module_from_spec(spec); spec.loader.exec_module(migration)
    engine=create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('PRAGMA foreign_keys=ON'))
        conn.execute(text('CREATE TABLE usuarios (id INTEGER PRIMARY KEY)'))
        conn.execute(text('INSERT INTO usuarios VALUES (1)'))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            assert set(inspect(conn).get_table_names())=={'usuarios','login_bloqueios','login_eventos'}
            conn.execute(text("INSERT INTO login_eventos (criado_em,login,ip,canal,resultado,usuario_id,responsavel_id) VALUES (CURRENT_TIMESTAMP,'test','127.0.0.1','principal','sucesso',1,1)"))
            conn.execute(text('DELETE FROM usuarios WHERE id=1'))
            assert tuple(conn.execute(text('SELECT usuario_id,responsavel_id FROM login_eventos')).one())==(None,None)
            migration.downgrade()
            assert inspect(conn).get_table_names()==['usuarios']
    graph=ScriptDirectory(str(ROOT/'migrations'))
    assert len(graph.get_heads()) == 1
    assert migration.revision in {rev.revision for rev in graph.walk_revisions()}
    assert migration.down_revision=='c1a0f8b6d2e4'


@pytest.mark.parametrize('path,login',[('/login','unidade'),('/uvis-operacional/login','unidade'),('/agro/login','piloto')])
def test_valid_credentials_still_start_session_in_each_portal(app,path,login):
    client=app.test_client()
    response=client.post(path,data={'login':login,'senha':PASSWORD})
    assert response.status_code==302
    with client.session_transaction() as state: assert state.get('_user_id')
    with app.app_context():
        assert LoginEvento.query.one().resultado=='sucesso'


def test_dev_permissions_from_central_ti_are_respected(app):
    from app.models import CentralTiPerfilConfiguracao, CentralTiSelecao
    app.config.update(CENTRAL_TI_ENABLED=True,CENTRAL_TI_ENFORCE_PERMISSIONS=True)
    for _ in range(3): post(app)
    with app.app_context():
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='dev',versao=2,atualizado_por_id=3))
        db.session.commit()
    client=authorized_client(app,3)
    key=protection.bucket_key('conta','unidade')
    path=f'/dev/seguranca-login/{key}/desbloquear'
    assert client.get('/dev/seguranca-login').status_code==403
    with app.app_context():
        for code in ['area:sistema','sistema.tecnico.consultar']:
            db.session.add(CentralTiSelecao(perfil_codigo='dev',codigo=code))
        db.session.commit()
    assert client.get('/dev/seguranca-login').status_code==200
    assert client.post(path,data={'_csrf_token':'known-csrf','motivo':'Solicitação conferida'}).status_code==403
    with app.app_context():
        db.session.add(CentralTiSelecao(perfil_codigo='dev',codigo='sistema.tecnico.operar'))
        db.session.commit()
    assert client.post(path,data={'_csrf_token':'known-csrf','motivo':'Solicitação conferida'}).status_code==303


def test_failed_commit_cannot_create_login_session_or_erase_previous_failures(app):
    post(app)
    client=app.test_client()
    with patch.object(db.session,'commit',side_effect=SQLAlchemyError('simulated commit failure')):
        response=client.post('/login',data={'login':'unidade','senha':PASSWORD})
    assert response.status_code==503
    with client.session_transaction() as state: assert '_user_id' not in state
    with app.app_context():
        assert bucket().falhas==1
        assert LoginEvento.query.count()==1


def test_failed_manual_release_rolls_back_counter_and_event(app):
    for _ in range(3): post(app)
    client=authorized_client(app,3)
    key=protection.bucket_key('conta','unidade')
    with patch.object(db.session,'commit',side_effect=SQLAlchemyError('simulated commit failure')):
        response=client.post(f'/dev/seguranca-login/{key}/desbloquear',data={'_csrf_token':'known-csrf','motivo':'Solicitação conferida'})
    assert response.status_code==503
    with app.app_context():
        assert bucket().bloqueado_ate is not None
        assert LoginEvento.query.count()==3
