"""Audit transactions, access controls and durable archives in disposable SQLite."""
import hashlib
import importlib.util
import json
import threading
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import Blueprint, Flask, Response, abort, request
from flask_login import LoginManager, current_user, login_required
from jinja2 import ChoiceLoader, DictLoader
from sqlalchemy import create_engine, inspect, update

from app.extensions import db
from app.models import AuditoriaArquivo, AuditoriaInstalacao, AuditoriaUsuario, Prefeitura, Usuario
from app.modules.auditoria.archive import prepare_batch, deliver_batch, process_archive
from app.modules.auditoria.recorder import event_values, register_audit, utcnow

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app(tmp_path):
    app = Flask(__name__, template_folder=str(ROOT/'app/templates'), static_folder=str(ROOT/'app/static'))
    app.config.update(TESTING=True, SECRET_KEY='audit-tests-only-long-key-at-least-32-characters', SQLALCHEMY_DATABASE_URI='sqlite:///'+str(tmp_path/'audit.sqlite'),
                      AUDIT_SKYBOX_ENABLED=True, LOGIN_PROTECTION_ENABLED=True, LOGIN_MAX_FAILURES=3,
                      LOGIN_IP_MAX_FAILURES=30, LOGIN_FAILURE_WINDOW_MINUTES=10, LOGIN_LOCKOUT_MINUTES=15,
                      CENTRAL_TI_ENABLED=False, SECURITY_CONTROLS_ENABLED=False)
    db.init_app(app)
    manager = LoginManager(app)
    manager.user_loader(lambda uid: db.session.get(Usuario, int(uid)))
    app.jinja_loader = ChoiceLoader([DictLoader({'base.html': '{% block content %}{% endblock %}'}), app.jinja_loader])
    app.jinja_env.globals['brazil_datetime'] = lambda value: value
    with app.app_context():
        db.create_all()
        db.session.add_all([Prefeitura(id=1, nome='Prefeitura A', slug='a'), Prefeitura(id=2, nome='Prefeitura B', slug='b'),
                            AuditoriaInstalacao(id=1, identificador=str(uuid4()))])
        for uid, role, tenant in [(1,'dev',None), (2,'covisa',1), (3,'uvis',2), (4,'admin',None)]:
            user = Usuario(id=uid, nome_uvis=role, login=role, tipo_usuario=role, prefeitura_id=tenant)
            user.set_senha('Senha segura 7!')
            db.session.add(user)
        db.session.commit()
    register_audit(app)
    from app.modules.auth.routes import bp as auth
    app.register_blueprint(auth)
    from app.modules.auditoria.routes import register_routes
    main = Blueprint('main', __name__)
    register_routes(main)
    for endpoint in ('admin_dashboard','dev_dashboard','dashboard','agro_piloto_dashboard','dashboard_equipe_uvis'):
        main.add_url_rule('/test/'+endpoint, endpoint, lambda: 'ok')
    app.register_blueprint(main)

    @app.post('/test/mudar/<int:uid>')
    @login_required
    def change(uid):
        user = db.session.get(Usuario, uid)
        user.regiao = 'NORTE'
        user.senha_hash = 'NEVER-STORE-THIS-HASH'
        user.nome_uvis = '<script>private-name</script>'
        if request.args.get('rollback'):
            db.session.flush()
            db.session.rollback()
            return 'not saved', 400
        if request.args.get('uncommitted'):
            db.session.flush()
            return 'not committed', 200
        db.session.commit()
        return 'saved', 200

    @app.post('/test/criar')
    def create():
        tenant = Prefeitura(nome='Nova', slug='nova')
        db.session.add(tenant)
        db.session.commit()
        return 'created', 201

    @app.post('/test/excluir')
    def delete():
        db.session.delete(db.session.get(Usuario, 3))
        db.session.commit()
        return 'deleted'

    @app.post('/test/bulk')
    def bulk():
        db.session.execute(update(Usuario).where(Usuario.id == 3).values(regiao='SUL'))
        if request.args.get('rollback'):
            db.session.rollback()
            return 'no', 400
        db.session.commit()
        return 'yes'

    @app.post('/test/vinculo')
    def link():
        user = db.session.get(Usuario, 3)
        user.prefeitura = db.session.get(Prefeitura, 1)
        db.session.commit()
        return 'changed'

    @app.get('/test/sensivel/<int:uid>')
    def sensitive(uid):
        if current_user.id != 1:
            abort(403)
        return Response('private', headers={'Content-Disposition': 'attachment; filename=x.pdf'})

    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def login(app, uid=1):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(uid)
        session['_fresh'] = True
    return client


def test_committed_change_has_actor_tenant_object_and_redacted_before_after(app):
    response = login(app).post('/test/mudar/3?secret=QUERY-SECRET', data={'senha':'BODY-SECRET'},
                               headers={'Referer':'https://example.invalid/?token=TOKEN-SECRET', 'X-Forwarded-For':'1.2.3.4'})
    assert response.status_code == 200
    with app.app_context():
        rows = AuditoriaUsuario.query.order_by(AuditoriaUsuario.id).all()
        mutation = next(r for r in rows if r.tipo_evento == 'EDICAO')
        assert (mutation.usuario_id, mutation.prefeitura_id, mutation.objeto_tipo, mutation.objeto_id) == (1,2,'usuarios','3')
        assert mutation.resultado == 'CONFIRMADO'
        assert mutation.detalhes['campos']['regiao'] == {'antes':None, 'depois':'NORTE'}
        assert mutation.detalhes['campos']['senha_hash']['depois'] == '[conteúdo protegido]'
        assert rows[-1].requisicao_id == mutation.requisicao_id
        assert rows[-1].ip != '1.2.3.4'
        serialized = json.dumps([r.detalhes for r in rows]) + str([(r.query_string,r.referrer) for r in rows])
        for secret in ('NEVER-STORE', 'QUERY-SECRET', 'BODY-SECRET', 'TOKEN-SECRET','private-name'):
            assert secret not in serialized


@pytest.mark.parametrize('mode', ['rollback','uncommitted'])
def test_rolled_back_or_uncommitted_changes_are_never_reported_as_saved(app, mode):
    login(app).post('/test/mudar/3?'+mode+'=1')
    with app.app_context():
        assert db.session.get(Usuario,3).regiao is None
        assert AuditoriaUsuario.query.filter_by(tipo_evento='EDICAO').count() == 0
        assert AuditoriaUsuario.query.filter_by(tipo_evento='REQUISICAO').count() == 1


def test_create_and_delete_keep_generated_and_deleted_object_ids(app):
    client = login(app)
    assert client.post('/test/criar').status_code == 201
    assert client.post('/test/excluir').status_code == 200
    with app.app_context():
        created = AuditoriaUsuario.query.filter_by(tipo_evento='CRIACAO', objeto_tipo='prefeituras').one()
        assert created.objeto_id == '3' and created.prefeitura_id == 3
        deleted = AuditoriaUsuario.query.filter_by(tipo_evento='EXCLUSAO', objeto_tipo='usuarios').one()
        assert deleted.objeto_id == '3' and deleted.prefeitura_id == 2


def test_bulk_change_is_transactional_and_does_not_invent_individual_values(app):
    client = login(app)
    client.post('/test/bulk?rollback=1')
    with app.app_context():
        assert AuditoriaUsuario.query.filter_by(tipo_evento='ALTERACAO_LOTE').count() == 0
    client.post('/test/bulk')
    with app.app_context():
        row = AuditoriaUsuario.query.filter_by(tipo_evento='ALTERACAO_LOTE').one()
        assert row.detalhes['quantidade'] == 1
        assert 'campos' not in row.detalhes


def test_relationship_changes_capture_final_foreign_key(app):
    assert login(app).post('/test/vinculo').status_code == 200
    with app.app_context():
        row = AuditoriaUsuario.query.filter_by(tipo_evento='EDICAO', objeto_tipo='usuarios').one()
        assert row.prefeitura_id == 1
        assert row.detalhes['campos']['prefeitura_id'] == {'antes':2,'depois':1}


def test_login_failure_lockout_success_and_logout_are_recorded(app):
    with patch('app.modules.auth.routes.record_user_presence'):
        client = app.test_client()
        for _ in range(3):
            response = client.post('/login',data={'login':'uvis','senha':'wrong'})
        assert response.status_code == 429
        ok = app.test_client()
        assert ok.post('/login',data={'login':'dev','senha':'Senha segura 7!'}).status_code == 302
        assert ok.get('/logout').status_code == 302
    with app.app_context():
        events = [(r.tipo_evento,r.resultado) for r in AuditoriaUsuario.query.all()]
        assert ('LOGIN','FALHA') in events and ('LOGIN','BLOQUEADO') in events
        assert ('LOGIN','SUCESSO') in events and ('LOGOUT','SUCESSO') in events


@pytest.mark.parametrize('channel', ['/uvis-operacional/login', '/agro/login'])
def test_other_login_channels_and_expired_password_are_audited(app, channel):
    from app.models import PilotoAgro
    with app.app_context():
        user = db.session.get(Usuario, 3)
        if channel == '/agro/login':
            pilot = PilotoAgro(nome='Piloto teste', ativo=True)
            db.session.add(pilot); db.session.flush()
            user.tipo_usuario='piloto_agro'; user.piloto_agro_id=pilot.id
        user.senha_alterada_em=utcnow()-timedelta(days=100)
        db.session.commit()
    with patch('app.modules.auth.routes.record_user_presence'):
        response = app.test_client().post(channel, data={'login':'uvis','senha':'Senha segura 7!'})
    assert response.status_code == 303 and '/renovar-senha' in response.location
    with app.app_context():
        row = AuditoriaUsuario.query.filter_by(tipo_evento='LOGIN').one()
        assert row.resultado == 'SENHA_VENCIDA' and row.usuario_id == 3 and row.prefeitura_id == 2


def test_expired_session_preserves_actor_in_event(app):
    import time
    from app.shared.session_security import register_session_security
    app.config.update(SECURITY_CONTROLS_ENABLED=True, SESSION_IDLE_TIMEOUT_SECONDS=5)
    register_session_security(app)
    client=login(app)
    with client.session_transaction() as session:
        session['_ija_security']={'last_activity':time.time()-100,'created_at':time.time()-100,
                                  'csrf':'test-token','login_endpoint':'auth.login'}
    assert client.get('/test/dev_dashboard').status_code == 303
    with app.app_context():
        row = AuditoriaUsuario.query.filter_by(tipo_evento='SESSAO_EXPIRADA').one()
        assert row.usuario_id == 1 and row.resultado == 'ENCERRADA'


def test_denied_access_export_filters_and_dev_only_archive(app):
    assert login(app,2).get('/test/sensivel/3').status_code == 403
    assert login(app).get('/test/sensivel/3').status_code == 200
    for uid in (2,3,4):
        assert login(app,uid).get('/admin/logs-usuarios').status_code == 403
        assert login(app,uid).get('/admin/logs-usuarios/arquivo/nonexistent').status_code == 403
    response = login(app).get('/admin/logs-usuarios?prefeitura_id=1&resultado=NEGADO')
    assert response.status_code == 200
    assert b'Arquivo de auditoria no Skybox' in response.data
    with app.app_context():
        from app.modules.auditoria.service import build_auditoria_query
        assert build_auditoria_query(prefeitura_id='1',resultado='NEGADO').count() >= 1
        assert AuditoriaUsuario.query.filter_by(tipo_evento='EXPORTACAO').count() == 1


def seed_events(count=3, tenant=1):
    with db.engine.begin() as conn:
        for i in range(count):
            row=event_values('EDICAO','CONFIRMADO',objeto_tipo='solicitacoes',objeto_id=str(i))
            row['prefeitura_id']=tenant
            conn.execute(AuditoriaUsuario.__table__.insert().values(**row))


def test_skybox_batch_is_separated_verified_and_pending_records_are_never_trimmed(app):
    from app.modules.auditoria.service import trim_auditoria_usuarios
    with app.app_context():
        seed_events(3,1); seed_events(1,2)
        with db.engine.begin() as conn:
            assert trim_auditoria_usuarios(conn,1)==0
        batch_id=prepare_batch()
        batch=db.session.get(AuditoriaArquivo,batch_id)
        payload=batch.conteudo.encode()
        assert '/prefeitura-1/' in batch.caminho and batch.caminho.startswith('auditoria_sistema/')
        assert len(payload.splitlines())==3
        assert all(json.loads(line)['prefeitura_id']==1 for line in payload.splitlines())
        db.session.remove()
        with patch('app.modules.auditoria.archive.upload_file_to_skybox',return_value='skybox://test') as upload, \
             patch('app.modules.auditoria.archive.download_skybox_bytes',return_value=payload):
            assert deliver_batch() is True
            assert upload.call_args.args[0].stream.getvalue()==payload
        batch=db.session.get(AuditoriaArquivo,batch_id)
        assert batch.enviado_em and batch.conteudo is None
        assert batch.sha256 == hashlib.sha256(payload).hexdigest()
        db.session.remove()
        with db.engine.begin() as conn:
            assert trim_auditoria_usuarios(conn,1)==3
        assert AuditoriaUsuario.query.count()==1
        assert AuditoriaUsuario.query.one().prefeitura_id==2


@pytest.mark.parametrize('failure',['upload','checksum'])
def test_retry_preserves_same_payload_and_path_without_acknowledging_failed_copy(app,failure):
    with app.app_context():
        seed_events()
        batch_id=prepare_batch()
        batch=db.session.get(AuditoriaArquivo,batch_id)
        payload,path=batch.conteudo.encode(),batch.caminho
        db.session.remove()
        with patch('app.modules.auditoria.archive.upload_file_to_skybox',side_effect=RuntimeError('secret') if failure=='upload' else None,return_value='skybox://test'), \
             patch('app.modules.auditoria.archive.download_skybox_bytes',return_value=b'bad'):
            assert deliver_batch() is False
        batch=db.session.get(AuditoriaArquivo,batch_id)
        assert batch.enviado_em is None and batch.conteudo.encode()==payload
        assert 'secret' not in batch.ultimo_erro
        assert AuditoriaUsuario.query.filter(AuditoriaUsuario.arquivado_em.isnot(None)).count()==0
        batch.proxima_tentativa=utcnow()-timedelta(seconds=1)
        db.session.commit(); db.session.remove()
        with patch('app.modules.auditoria.archive.upload_file_to_skybox',return_value='skybox://test') as upload, \
             patch('app.modules.auditoria.archive.download_skybox_bytes',return_value=payload):
            assert deliver_batch() is True
            assert upload.call_args.args[1]==path
        assert db.session.get(AuditoriaArquivo,batch_id).tentativas==2


def test_concurrent_delivery_respects_lease_and_recovers_expired_worker(app):
    with app.app_context():
        seed_events(); batch_id=prepare_batch()
        batch=db.session.get(AuditoriaArquivo,batch_id)
        payload=batch.conteudo.encode()
        batch.lease_token='abandoned'; batch.lease_ate=utcnow()-timedelta(seconds=1)
        db.session.commit()
    started,release=threading.Event(),threading.Event()
    results=[]
    def upload(*args):
        started.set(); assert release.wait(5)
        return 'skybox://test'
    def worker():
        with app.app_context(): results.append(deliver_batch())
    with patch('app.modules.auditoria.archive.upload_file_to_skybox',side_effect=upload) as send, \
         patch('app.modules.auditoria.archive.download_skybox_bytes',return_value=payload):
        thread=threading.Thread(target=worker); thread.start()
        try:
            assert started.wait(5)
            with app.app_context(): assert deliver_batch() is None
        finally:
            release.set(); thread.join(5)
        assert results==[True] and send.call_count==1


def test_archive_disabled_preserves_pending_events(app):
    with app.app_context():
        seed_events()
        app.config['AUDIT_SKYBOX_ENABLED']=False
        assert process_archive()=={'enviados':0,'disponivel':False}
        assert AuditoriaUsuario.query.count()==3


def test_migration_preserves_legacy_rows_and_has_reversible_schema(tmp_path):
    spec=importlib.util.spec_from_file_location('audit_migration',ROOT/'migrations/versions/a6e3f8129c40_audit_trail_skybox.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine=create_engine('sqlite:///'+str(tmp_path/'migration.sqlite'))
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE auditoria_usuarios (id INTEGER PRIMARY KEY, usuario_nome VARCHAR(100))')
        conn.exec_driver_sql("INSERT INTO auditoria_usuarios VALUES (1, 'Legado')")
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            assert conn.exec_driver_sql('SELECT usuario_nome, detalhes FROM auditoria_usuarios').one()==('Legado',None)
            assert conn.exec_driver_sql('SELECT count(*) FROM auditoria_instalacao').scalar()==1
            assert 'auditoria_arquivos' in inspect(conn).get_table_names()
            module.downgrade()
            assert conn.exec_driver_sql('SELECT usuario_nome FROM auditoria_usuarios').scalar()=='Legado'
            assert 'auditoria_arquivos' not in inspect(conn).get_table_names()
    engine.dispose()
