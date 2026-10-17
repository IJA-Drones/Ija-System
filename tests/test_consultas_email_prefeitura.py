"""Tenant isolation, destination confirmation and delivery auditing."""
from uuid import uuid4
from unittest.mock import patch
from flask import jsonify
from app.extensions import db
from app.models import Usuario, PrefeituraEmailConfig, ConsultaEmailEnvio, CentralTiPerfilConfiguracao, CentralTiSelecao
from app.modules.consultas import service, mail
from app.modules.consultas import email_settings
from app.shared.csrf_security import CSRF_SESSION_KEY
from test_consultas import app, client, spec


def setup_config(app):
    with app.app_context():
        db.session.get(Usuario,1).tipo_usuario='covisa'
        db.session.get(Usuario,2).tipo_usuario='covisa'
        db.session.add(PrefeituraEmailConfig(prefeitura_id=1,destinatario='a@example.org',atualizado_por_id=1))
        db.session.add(PrefeituraEmailConfig(prefeitura_id=2,destinatario='b@example.org',atualizado_por_id=2))
        db.session.commit()


def send_payload(**overrides):
    return dict(dict(definicao=spec(filters={'prefeitura':'1'}),prefeitura_id=1,
        destinatario='a@example.org',versao=1,envio_id=str(uuid4())),**overrides)


def test_covisa_only_own_settings_and_data(app):
    setup_config(app);c=client(app)
    assert c.get('/configuracoes/email/2').status_code==404
    assert c.get('/relatorios/consultas/email-destino?prefeitura_id=2').status_code==404
    assert c.get('/relatorios/consultas/email-destino?prefeitura_id=1').json['destinatario']=='a@example.org'
    assert c.post('/relatorios/consultas/executar',json=spec()).json['total']==2
    assert c.post('/relatorios/consultas/executar',json=spec(filters={'prefeitura':'2'})).json['total']==0
    assert c.post('/configuracoes/email/1',data={'destinatario':'new@example.org','versao':1}).status_code==403
    with c.session_transaction() as s:s[CSRF_SESSION_KEY]='test-token'
    data={'_csrf_token':'test-token','destinatario':'new@example.org','versao':1}
    assert c.post('/configuracoes/email/1',data=data).status_code==303
    assert c.post('/configuracoes/email/2',data=data).status_code==404
    with patch.object(email_settings,'render_template',return_value='form'):
        assert c.post('/configuracoes/email/1',data=data).status_code==409
        data.update(versao=2,destinatario='a@example.org\nBcc: bad@example.org')
        assert c.post('/configuracoes/email/1',data=data).status_code==400
    with app.app_context():
        assert db.session.get(PrefeituraEmailConfig,1).destinatario=='new@example.org'
        assert db.session.get(PrefeituraEmailConfig,2).destinatario=='b@example.org'


def test_shared_destination_and_dev_all_cities(app):
    setup_config(app)
    with app.app_context():
        other=Usuario(login='a2',nome_uvis='A2',senha_hash='unused',tipo_usuario='covisa',prefeitura_id=1)
        db.session.add(other);db.session.commit();uid=other.id
    assert client(app,uid).get('/relatorios/consultas/email-destino?prefeitura_id=1').json['destinatario']=='a@example.org'
    with app.app_context():
        db.session.get(Usuario,uid).tipo_usuario='dev';db.session.commit()
    with patch.object(email_settings,'render_template',return_value='settings'):
        assert client(app,uid).get('/configuracoes/email/2').status_code==200
    assert client(app,uid).get('/relatorios/consultas/email-destino?prefeitura_id=2').json['destinatario']=='b@example.org'


def test_delivery_confirmation_audit_and_duplicate(app):
    setup_config(app);app.config.update(REPORT_SMTP_HOST='smtp.invalid',REPORT_SMTP_FROM='reports@example.org')
    c=client(app);payload=send_payload()
    with patch.object(mail,'send_report') as send:
        assert c.post('/relatorios/consultas/email',json=send_payload(destinatario='other@example.org')).status_code==409
        assert c.post('/relatorios/consultas/email',json=send_payload(versao=0)).status_code==409
        assert c.post('/relatorios/consultas/email',json=send_payload(prefeitura_id=2)).status_code==404
        assert c.post('/relatorios/consultas/email',json=send_payload(definicao=spec())).status_code==400
        send.assert_not_called()
        assert c.post('/relatorios/consultas/email',json=payload).status_code==200
        send.assert_called_once();assert send.call_args.args[0]=='a@example.org'
        assert send.call_args.args[1].startswith(b'%PDF')
        assert c.post('/relatorios/consultas/email',json=payload).status_code==409
        assert send.call_count==1
    with app.app_context():
        row=db.session.get(ConsultaEmailEnvio,payload['envio_id'])
        assert row.prefeitura_id==1 and row.usuario_id==1 and row.estado=='aceito'
    with patch.object(email_settings,'render_template',side_effect=lambda *args,**kw:jsonify(destinos=[r.destinatario for r,login in kw['history']])):
        assert c.get('/configuracoes/email/1').json['destinos']==['a@example.org']
        assert client(app,2).get('/configuracoes/email/2').json['destinos']==[]


def test_consult_only_permission_cannot_send_or_read_destination(app):
    setup_config(app)
    with app.app_context():
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='covisa',versao=2,atualizado_por_id=1));db.session.flush()
        for code in ['area:prefeitura','prefeitura.relatorios.consultar']:
            db.session.add(CentralTiSelecao(perfil_codigo='covisa',codigo=code))
        db.session.commit()
    app.config.update(CENTRAL_TI_ENABLED=True,CENTRAL_TI_ENFORCE_PERMISSIONS=True)
    c=client(app)
    assert c.post('/relatorios/consultas/executar',json=spec()).status_code==200
    assert c.get('/relatorios/consultas/email-destino?prefeitura_id=1').status_code==403
    assert c.post('/relatorios/consultas/email',json=send_payload()).status_code==403
    assert c.get('/configuracoes/email/1').status_code==403


def test_municipal_email_migration_roundtrip():
    import importlib.util
    import sqlalchemy as sa
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path=Path(__file__).parents[1]/'migrations/versions/b72c931ae804_municipal_report_email.py'
    module_spec=importlib.util.spec_from_file_location('email_migration',path)
    mod=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(mod)
    engine=sa.create_engine('sqlite://')
    with engine.begin() as conn:
        mod.op=Operations(MigrationContext.configure(conn));mod.upgrade()
        assert sa.inspect(conn).has_table('prefeitura_email_config')
        assert sa.inspect(conn).has_table('consulta_email_envios')
        mod.downgrade()
        assert not sa.inspect(conn).has_table('prefeitura_email_config')
