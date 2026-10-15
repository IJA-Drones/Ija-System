"""Real HTTP workflows, competing sessions and migration on disposable databases."""
import importlib.util
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import Flask, request
from flask_login import LoginManager, current_user
from jinja2 import ChoiceLoader, DictLoader
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.extensions import db
from app.models import (Prefeitura, Usuario, Solicitacao, Denuncia, Equipe, OrdemServico,
                        EdicaoReserva, AuditoriaUsuario, CentralTiPerfilConfiguracao, CentralTiSelecao)
from app.shared.edit_control import register_edit_control, _ticket, now, EditConflict
from app.modules.auditoria.recorder import register_audit

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app(tmp_path):
    app = Flask(__name__, template_folder=str(ROOT/'app/templates'), static_folder=str(ROOT/'app/static'))
    app.config.update(TESTING=True, SECRET_KEY='isolated-edit-test-key', SQLALCHEMY_DATABASE_URI='sqlite:///'+str(tmp_path/'edit.sqlite'),
                      AUDIT_SKYBOX_ENABLED=False, CENTRAL_TI_ENABLED=False, SECURITY_CONTROLS_ENABLED=False,
                      SKYBOX_ENABLED=False, UPLOAD_FOLDER=str(tmp_path), EDIT_LEASE_SECONDS=120)
    db.init_app(app)
    manager = LoginManager(app)
    manager.user_loader(lambda uid: db.session.get(Usuario, int(uid)))
    from app.routes import bp
    from app.modules.auth.routes import bp as auth
    with patch('app.modules.backup.routes.start_daily_backup_scheduler'):
        app.register_blueprint(bp)
    app.register_blueprint(auth)
    app.jinja_loader = ChoiceLoader([DictLoader({'base.html': '{% block content %}{% endblock %}'}), app.jinja_loader])
    app.jinja_env.globals['brazil_datetime'] = lambda value: value
    register_audit(app)
    register_edit_control(app)
    with app.app_context():
        db.create_all()
        db.session.add_all([Prefeitura(id=1,nome='A',slug='a'), Prefeitura(id=2,nome='B',slug='b')])
        for uid, role, tenant in [(1,'dev',None),(2,'admin',None),(3,'prefeitura_admin',1),(4,'prefeitura_admin',2),(5,'uvis',1),(6,'regional',1)]:
            db.session.add(Usuario(id=uid, nome_uvis=f'Editor {uid}', login=f'u{uid}', senha_hash='test',
                                  tipo_usuario=role, prefeitura_id=tenant, regiao='NORTE'))
        db.session.add(Equipe(id=1,nome_equipe='Equipe',prefeitura_id=1,regiao='NORTE',ativa=True))
        db.session.flush()
        for oid, tenant in [(1,1),(2,2)]:
            db.session.add(Solicitacao(id=oid,prefeitura_id=tenant,usuario_id=5,equipe_id=1,
                data_agendamento=date.today(),hora_agendamento=time(9),foco='Corrego',tipo_visita='Culex',
                cep='00000000',logradouro='Rua',numero='1',bairro='Centro',cidade='Teste',uf='SP',status='APROVADO'))
            db.session.add(Denuncia(id=oid,prefeitura_id=tenant,protocolo=f'D{oid}',tipo_visita='Culex',foco='Corrego',
                logradouro='Rua',numero='1',bairro='Centro',cidade='Teste',uf='SP',cidadao_nome='Cidadão',
                cidadao_cpf='00000000000',cidadao_rg='',cidadao_telefone='000',consentimento=True))
        db.session.commit()

    # Test-only ticket endpoint avoids dependencies on dashboard charts; production tickets originate in rendered forms.
    @app.get('/fixture/ticket/<kind>/<int:oid>')
    def ticket(kind,oid):
        model = Solicitacao if kind == 'solicitacao' else Denuncia
        return _ticket(db.session.get(model,oid),request.args.get('endpoint','main.atualizar'))

    @app.post('/fixture/unprotected/<int:oid>')
    def unprotected(oid):
        obj=db.session.get(Solicitacao,oid);obj.protocolo='outside-form';db.session.commit();return 'ok'

    @app.post('/fixture/rollback')
    def rollback():
        obj=db.session.get(Solicitacao,1);obj.protocolo='must-rollback';db.session.flush();db.session.rollback();return 'no',400

    yield app
    with app.app_context():
        db.session.remove();db.engine.dispose()


def client(app, uid=1):
    c=app.test_client()
    with c.session_transaction() as s:
        s['_user_id']=str(uid);s['_fresh']=True
    return c


def ticket(c,oid=1,kind='solicitacao',endpoint='main.atualizar'):
    r=c.get(f'/fixture/ticket/{kind}/{oid}',query_string={'endpoint':endpoint})
    assert r.status_code==200,r.data
    return r.get_data(as_text=True)


def reserve(c,t):
    return c.post('/api/edicao/reservar',json={'ticket':t})


def save(c,t,token,**extra):
    return c.post('/admin/atualizar/1',data={'_edit_ticket':t,'_edit_token':token,
        'status':'APROVADO','equipe_id':'1','protocolo':'new',**extra},headers={'X-Requested-With':'XMLHttpRequest'})


def test_save_requires_reservation_and_releases_with_audit(app):
    c=client(app);t=ticket(c)
    assert save(c,t,'').status_code==409
    r=reserve(c,t);assert r.status_code==200,r.json
    result=save(c,t,r.json['token']);assert result.status_code==200,result.data
    assert result.headers['X-Edit-Released']=='1'
    with app.app_context():
        assert db.session.get(Solicitacao,1).protocolo=='new'
        assert db.session.get(EdicaoReserva,('solicitacao',1)).token_hash is None
        assert AuditoriaUsuario.query.filter_by(tipo_evento='EDICAO_RESERVADA').count()==1
        assert AuditoriaUsuario.query.filter_by(tipo_evento='EDICAO_LIBERADA').count()==1
        assert AuditoriaUsuario.query.filter_by(tipo_evento='EDICAO',objeto_tipo='solicitacoes').count()==1


def test_two_editors_and_same_user_second_tab_cannot_take_active_lease(app):
    a,b=client(app),client(app,2);ta,tb=ticket(a),ticket(b)
    token=reserve(a,ta).json['token']
    for c,t in [(a,ta),(b,tb)]:
        r=reserve(c,t);assert r.status_code==409
        assert r.json['owner']=='Editor 1'
    assert save(b,tb,token).status_code==409
    assert b.post('/api/edicao/liberar',json={'ticket':tb,'token':token}).status_code==409
    assert a.post('/api/edicao/liberar',json={'ticket':ta,'token':token}).status_code==200
    assert reserve(b,tb).status_code==200


def test_stale_tab_after_another_editor_saved_is_rejected(app):
    a,b=client(app),client(app,2);ta,tb=ticket(a),ticket(b)
    token=reserve(b,tb).json['token'];assert save(b,tb,token).status_code==200
    r=reserve(a,ta);assert r.status_code==409 and r.json['code']=='stale'
    assert save(b,tb,token).status_code==409


def test_expiry_and_dev_release_revoke_old_editor(app):
    a,dev=client(app,2),client(app);ta,td=ticket(a),ticket(dev)
    token=reserve(a,ta).json['token']
    assert a.post('/api/edicao/liberar-dev',json={'ticket':ta,'motivo':'Solicitação do suporte'}).status_code==403
    assert dev.post('/api/edicao/liberar-dev',json={'ticket':td,'motivo':'curto'}).status_code==400
    assert dev.post('/api/edicao/liberar-dev',json={'ticket':td,'motivo':'Editor saiu do atendimento'}).status_code==200
    assert save(a,ta,token).status_code==409
    newtoken=reserve(dev,td).json['token']
    with app.app_context():
        row=db.session.get(EdicaoReserva,('solicitacao',1));row.expira_em=now()-timedelta(seconds=1);db.session.commit()
    assert dev.post('/api/edicao/renovar',json={'ticket':td,'token':newtoken}).status_code==409
    assert save(dev,td,newtoken).status_code==409
    assert reserve(a,ta).status_code==200
    with app.app_context():
        row=AuditoriaUsuario.query.filter_by(tipo_evento='EDICAO_LIBERADA_DEV').one()
        assert row.usuario_id==1 and row.detalhes['editor_anterior_id']==2


def test_cross_municipality_and_ticket_tampering_never_reveal_holder(app):
    a,b=client(app),client(app,4);ta=ticket(a);reserve(a,ta)
    # Even a signed ticket cannot substitute for live municipal authorization.
    tb=ticket(b)
    r=reserve(b,tb);assert r.status_code in (403,404) and b'Editor 1' not in r.data
    assert reserve(b,ta).status_code==403
    assert reserve(a,ta+'bad').status_code==409


def test_permissions_are_rechecked_after_ticket_issued(app):
    c=client(app,3);t=ticket(c)
    with app.app_context():
        app.config.update(CENTRAL_TI_ENABLED=True,CENTRAL_TI_ENFORCE_PERMISSIONS=True)
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='prefeitura_admin',versao=2))
        db.session.commit()
    assert reserve(c,t).status_code==403


def test_os_and_solicitation_share_lease(app):
    a,b=client(app),client(app,2)
    ta=ticket(a,endpoint='main.admin_os_formulario_view');tb=ticket(b)
    assert reserve(a,ta).status_code==200
    assert reserve(b,tb).status_code==409
    # Other mutation paths cannot silently bypass an active lease.
    r=b.post('/fixture/unprotected/1',headers={'X-Requested-With':'XMLHttpRequest'})
    assert r.status_code==409
    with app.app_context():assert db.session.get(Solicitacao,1).protocolo is None


def test_denuncia_real_form_triage_reserves_and_releases(app):
    c=client(app)
    page=c.get('/denuncias/1');assert page.status_code==200,page.data
    tickets=re.findall(r'name="_edit_ticket" value="([^"]+)"',page.get_data(as_text=True))
    assert len(tickets)==2
    token=reserve(c,tickets[0]).json['token']
    response=c.post('/denuncias/1/encaminhar-coordenadoria',data={
        '_edit_ticket':tickets[0],'_edit_token':token,'coordenadoria':'NORTE'})
    assert response.status_code==302,response.data
    with app.app_context():
        assert db.session.get(Denuncia,1).coordenadoria=='NORTE'
        assert not db.session.get(EdicaoReserva,('denuncia',1)).token_hash


def test_failed_validation_does_not_release_or_commit_partial_changes(app):
    c=client(app);t=ticket(c);token=reserve(c,t).json['token']
    assert save(c,t,token,equipe_id='invalid').status_code==400
    with app.app_context():
        assert db.session.get(Solicitacao,1).protocolo is None
        assert db.session.get(EdicaoReserva,('solicitacao',1)).token_hash
    assert save(c,t,token).status_code==200


def test_optimistic_version_rejects_stale_database_session(app):
    with app.app_context():
        with Session(db.engine) as a, Session(db.engine) as b:
            first=a.get(Solicitacao,1);second=b.get(Solicitacao,1)
            first.protocolo='first';a.commit()
            second.protocolo='second'
            with pytest.raises(StaleDataError):b.commit()
            b.rollback()
        assert db.session.get(Solicitacao,1).protocolo=='first'


def test_simultaneous_reservations_have_one_winner(app):
    a,b=client(app),client(app,2);ta,tb=ticket(a),ticket(b)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(reserve,c,t) for c,t in [(a,ta),(b,tb)]]
        codes=sorted(f.result().status_code for f in futures)
    assert codes==[200,409]


def test_read_only_os_view_does_not_acquire_lease(app):
    c=client(app);response=c.get('/admin/os/1/formulario')
    assert response.status_code==200,response.data
    assert b'Iniciar edi' in response.data
    with app.app_context():assert EdicaoReserva.query.count()==0


def test_migration_backfills_versions_and_preserves_data(tmp_path):
    path=ROOT/'migrations/versions/b7f2c9d41e60_edit_reservations.py'
    spec=importlib.util.spec_from_file_location('migration',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    engine=create_engine('sqlite:///'+str(tmp_path/'migration.sqlite'))
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE usuarios (id INTEGER PRIMARY KEY)'))
        for table in m.TABLES:
            conn.execute(text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, valor TEXT)'))
            conn.execute(text(f"INSERT INTO {table} VALUES (1, 'preservado')"))
        with Operations.context(MigrationContext.configure(conn)):
            m.upgrade()
            for table in m.TABLES:
                assert conn.execute(text(f'SELECT valor, versao_edicao FROM {table}')).one()==('preservado',1)
            m.downgrade()
            for table in m.TABLES:
                assert conn.execute(text(f'SELECT valor FROM {table}')).scalar()=='preservado'
    engine.dispose()


def test_background_video_can_finish_for_owner_and_refresh_only_its_exact_snapshot(app):
    from app.shared.edit_control import (_digest, prepare_background_media, background_media_versions,
                                         publish_media_transition)
    # Create the media row before loading the form, as the upload initialization does.
    with app.app_context():
        db.session.add(OrdemServico(solicitacao_id=1,equipe_id=1));db.session.commit()

    jobs={}
    @app.get('/fixture/job')
    def job_status():
        publish_media_transition(jobs['job']);return {'ok':True}

    c=client(app);t=ticket(c);token=reserve(c,t).json['token']
    job={'os_id':1,'user_id':1,'edit_token_hash':_digest(token)}
    with app.app_context():
        before=prepare_background_media(job)
        order=OrdemServico.query.filter_by(solicitacao_id=1).one()
        order.video='skybox://video.mp4';order.quantidade_videos_registradas=1
        db.session.commit()
        after=background_media_versions(1)
        db.session.info.pop('_edit_background_media',None)
    jobs['job']={**job,'status':'success','edit_versions_before':before,'edit_versions_after':after}
    # Heartbeats keep the reservation alive while the job completion is being polled.
    assert c.post('/api/edicao/renovar',json={'ticket':t,'token':token}).status_code==200
    r=c.get('/fixture/job',headers={'X-Edit-Token':token,'X-Edit-Ticket':t})
    assert r.headers.get('X-Edit-Ticket') and r.headers['X-Edit-Ticket']!=t
    assert save(c,r.headers['X-Edit-Ticket'],token).status_code==200


def test_background_job_cannot_overwrite_another_reservation_or_edit_business_fields(app):
    from app.shared.edit_control import _digest, prepare_background_media
    with app.app_context():
        db.session.add(OrdemServico(solicitacao_id=1,equipe_id=1));db.session.commit()
    a,b=client(app),client(app,2);ta,tb=ticket(a),ticket(b)
    oldtoken=reserve(a,ta).json['token']
    a.post('/api/edicao/liberar',json={'ticket':ta,'token':oldtoken})
    reserve(b,tb)
    job={'os_id':1,'user_id':1,'edit_token_hash':_digest(oldtoken)}
    with app.app_context():
        with pytest.raises(EditConflict):prepare_background_media(job)
        db.session.rollback()
    # A worker grant is limited to the video fields, even with the correct owner.
    a.post('/api/edicao/liberar-dev',json={'ticket':ta,'motivo':'Conferência de atendimento'})
    token=reserve(a,ta).json['token']
    with app.app_context():
        prepare_background_media({**job,'edit_token_hash':_digest(token)})
        order=OrdemServico.query.filter_by(solicitacao_id=1).one();order.identificador_os='forbidden'
        with pytest.raises(EditConflict):db.session.commit()
        db.session.rollback();db.session.info.pop('_edit_background_media',None)


def test_active_lease_does_not_prevent_other_authorized_readers(app):
    a,b=client(app),client(app,2);t=ticket(a);reserve(a,t)
    assert b.get('/admin/os/1/formulario').status_code==200
    assert b.get('/solicitacao/editar/1').status_code==200


def test_cross_object_or_endpoint_ticket_is_rejected(app):
    c=client(app);t=ticket(c,oid=2);token=reserve(c,t).json['token']
    assert save(c,t,token).status_code==403
    t=ticket(c,endpoint='main.admin_os_formulario_view');token=reserve(c,t).json['token']
    assert save(c,t,token).status_code==403


def test_delete_does_not_report_success_when_blocked(app):
    a,b=client(app),client(app,2);t=ticket(a);reserve(a,t)
    response=b.post('/admin/deletar/1',headers={'X-Requested-With':'XMLHttpRequest'})
    assert response.status_code==409
    with app.app_context():assert db.session.get(Solicitacao,1) is not None


def test_csrf_is_required_when_security_is_enabled(app):
    from app.shared.csrf_security import register_csrf_security
    app.config.update(CSRF_PROTECTION_ENABLED=True,SECRET_KEY='test-only-secret-key-long-enough-for-csrf-32')
    register_csrf_security(app)
    c=client(app)
    with c.session_transaction() as s:s['_ija_csrf']='test-csrf'
    t=ticket(c)
    assert reserve(c,t).status_code==403
    r=c.post('/api/edicao/reservar',json={'ticket':t},headers={'X-CSRFToken':'test-csrf'})
    assert r.status_code==200


@pytest.mark.parametrize('body',[[],{'ticket':1},{'ticket':'x','token':{}},{'ticket':'x','motivo':[]},None])
def test_malformed_lease_requests_fail_without_server_error(app,body):
    c=client(app)
    r=c.post('/api/edicao/reservar',json=body)
    assert r.status_code in (400,409)


def test_new_return_os_is_allowed_inside_parent_reservation(app):
    from flask import g
    from app.shared.edit_control import _require_form
    c=client(app);t=ticket(c);token=reserve(c,t).json['token']
    with c.session_transaction() as saved_session:cookie_session=dict(saved_session)
    with app.test_request_context('/admin/atualizar/1',method='POST',data={'_edit_token':token,'_edit_ticket':t}):
        from flask import session
        session.update(cookie_session)
        _require_form()
        new=Solicitacao(prefeitura_id=1,usuario_id=5,equipe_id=1,data_agendamento=date.today(),hora_agendamento=time(9),
            foco='Corrego',tipo_visita='Culex',cep='00000000',logradouro='Retorno',numero='1',bairro='Centro',cidade='Teste',uf='SP',status='APROVADO')
        db.session.add(new);db.session.flush()
        db.session.add(OrdemServico(solicitacao_id=new.id,equipe_id=1));db.session.commit()
        assert g.edit_saved and not db.session.get(EdicaoReserva,('solicitacao',1)).token_hash


def test_real_factory_presence_commit_does_not_release_the_form_early(app):
    from config import Config
    from app import create_app
    settings=dict(SQLALCHEMY_DATABASE_URI=app.config['SQLALCHEMY_DATABASE_URI'],
        SECRET_KEY='factory-test-only-fixed-secret-long-enough',DEBUG=True,TESTING=True,
        AUDIT_SKYBOX_ENABLED=False,SECURITY_CONTROLS_ENABLED=False,CSRF_PROTECTION_ENABLED=False,
        CENTRAL_TI_ENABLED=False,USER_PRESENCE_UPDATE_INTERVAL_SECONDS=0)
    with patch.multiple(Config,create=True,**settings),patch('app.modules.backup.routes.start_daily_backup_scheduler'):
        factory=create_app()
    @factory.get('/fixture/ticket/<kind>/<int:oid>')
    def fixture_ticket(kind,oid):
        return _ticket(db.session.get(Solicitacao,oid),'main.atualizar')
    c=client(factory);t=ticket(c);r=reserve(c,t)
    assert r.status_code==200,r.data
    result=save(c,t,r.json['token'])
    assert result.status_code==200,result.data
    with factory.app_context():
        assert db.session.get(Solicitacao,1).protocolo=='new'
        assert db.session.get(EdicaoReserva,('solicitacao',1)).token_hash is None
        db.session.remove();db.engine.dispose()
