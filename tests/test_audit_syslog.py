"""Only disposable SQLite and loopback collectors; no production configuration."""
import importlib.util
import json
import socket
import ssl
import subprocess
import threading
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select

from app.extensions import db
from app.models import AuditoriaUsuario, AuditoriaSyslogEntrega
from app.modules.auditoria import syslog
from app.modules.auditoria.recorder import event_values, utcnow
from app.modules.auditoria.service import trim_auditoria_usuarios
from tests.test_audit_trail import app


def seed():
    with db.engine.begin() as conn:
        data = event_values('LOGIN', 'SUCESSO')
        data.update(usuario_nome='João\nTeste', query_string='secret-query', referrer='secret-url',
                    user_agent='secret-agent', detalhes={'identificadores': {'id': 42}})
        return conn.execute(AuditoriaUsuario.__table__.insert().values(**data)).inserted_primary_key[0]


def configure(app):
    app.config.update(AUDIT_SYSLOG_ENABLED=True, AUDIT_SYSLOG_HOST='localhost',
                      AUDIT_SYSLOG_TRANSPORT='tcp', AUDIT_SYSLOG_PORT=5514)


def test_wire_format_and_allowlist(app):
    with app.app_context():
        uid = seed()
        row = db.session.execute(select(AuditoriaUsuario.__table__).where(AuditoriaUsuario.id == uid)).mappings().one()
        wire = syslog.frame(row, 'installation-id')
        length, message = wire.split(b' ', 1)
        assert int(length) == len(message)
        assert message.startswith(b'<134>1 ')
        assert b' IJA-System - AUDIT - ' in message
        assert all(word not in wire for word in (b'secret-query', b'secret-url', b'secret-agent', b'\n'))
        payload = json.loads(message.split(b' AUDIT - ', 1)[1])
        assert payload['usuario_nome'] == 'João\nTeste'
        assert payload['instalacao_id'] == 'installation-id'
        assert payload['evento_id'] == row['evento_id']


def test_disabled_does_not_connect_or_require_new_table(app):
    with app.app_context():
        seed()
        AuditoriaSyslogEntrega.__table__.drop(db.engine)
        with patch.object(syslog, 'send_frame') as send:
            assert syslog.process_syslog()['habilitado'] is False
            assert syslog.syslog_status() == {'habilitado': False}
            send.assert_not_called()


def test_actual_tcp_collector_receives_event_and_no_repeat(app):
    configure(app)
    received = []
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen(); listener.settimeout(5)
        app.config.update(AUDIT_SYSLOG_HOST='127.0.0.1', AUDIT_SYSLOG_PORT=listener.getsockname()[1])
        def collect():
            with listener.accept()[0] as connection:
                connection.settimeout(5)
                chunks = []
                while chunk := connection.recv(65536):
                    chunks.append(chunk)
                received.append(b''.join(chunks))
        worker = threading.Thread(target=collect)
        worker.start()
        with app.app_context():
            uid = seed()
            assert syslog.process_syslog()['transmitidos'] == 1
            assert syslog.process_syslog()['transmitidos'] == 0
            assert db.session.get(AuditoriaSyslogEntrega, uid).enviado_em is not None
        worker.join(timeout=6)
        assert not worker.is_alive()
    assert len(received) == 1 and b'"tipo_evento":"LOGIN"' in received[0]


def test_actual_tls_collector_with_trusted_certificate(app, tmp_path):
    cert, key = tmp_path / 'collector.pem', tmp_path / 'collector.key'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost',
        '-keyout', str(key), '-out', str(cert)], check=True, capture_output=True, timeout=20)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert), str(key))
    configure(app)
    app.config.update(AUDIT_SYSLOG_TRANSPORT='tls', AUDIT_SYSLOG_CA_FILE=str(cert))
    received, errors = [], []
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen(); listener.settimeout(5)
        app.config['AUDIT_SYSLOG_PORT'] = listener.getsockname()[1]
        def collect():
            try:
                with listener.accept()[0] as raw:
                    raw.settimeout(5)
                    with context.wrap_socket(raw, server_side=True) as connection:
                        chunks = []
                        while chunk := connection.recv(65536): chunks.append(chunk)
                        received.append(b''.join(chunks))
            except Exception as exc:
                errors.append(exc)
        worker = threading.Thread(target=collect); worker.start()
        with app.app_context():
            seed()
            assert syslog.process_syslog()['transmitidos'] == 1
        worker.join(timeout=6)
        assert not worker.is_alive() and not errors
    assert len(received) == 1 and b' AUDIT - ' in received[0]


def test_other_worker_cannot_claim_event_during_network_send(app):
    configure(app)
    started, finish = threading.Event(), threading.Event()
    results = []
    def slow_send(data):
        started.set()
        assert finish.wait(5)
    def run():
        with app.app_context(): results.append(syslog.deliver_one())
    with app.app_context(): seed()
    with patch.object(syslog, 'send_frame', side_effect=slow_send):
        worker = threading.Thread(target=run); worker.start()
        try:
            assert started.wait(5)
            with app.app_context(): assert syslog.deliver_one() is None
        finally:
            finish.set(); worker.join(timeout=6)
    assert results == [True]


def test_dev_page_shows_disabled_pending_and_failure_without_secrets(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = '1'; session['_fresh'] = True
    assert 'Envio remoto por syslog' in client.get('/admin/logs-usuarios').get_data(as_text=True)
    assert 'Desativado.' in client.get('/admin/logs-usuarios').get_data(as_text=True)
    configure(app)
    with app.app_context():
        with patch.object(syslog, 'send_frame', side_effect=OSError('SECRET')):
            syslog.process_syslog()
    html = client.get('/admin/logs-usuarios').get_data(as_text=True)
    assert 'pendente(s)' in html and 'SECRET' not in html
    with client.session_transaction() as session:
        session['_user_id'] = '2'
    assert client.get('/admin/logs-usuarios').status_code == 403


def test_failure_survives_retry_and_is_sanitized(app):
    configure(app)
    with app.app_context():
        uid = seed()
        with patch.object(syslog, 'send_frame', side_effect=OSError('password=SECRET')):
            assert syslog.process_syslog()['transmitidos'] == 0
        state = db.session.get(AuditoriaSyslogEntrega, uid)
        assert state.enviado_em is None and state.tentativas == 1
        assert 'SECRET' not in state.ultimo_erro
        assert syslog.syslog_status()['pendentes'] == 1
        with patch.object(syslog, 'send_frame') as send:
            assert syslog.process_syslog()['transmitidos'] == 0
            send.assert_not_called()
            state.proxima_tentativa = utcnow() - timedelta(seconds=1)
            db.session.commit()
            assert syslog.process_syslog()['transmitidos'] == 1
        db.session.expire_all()
        assert db.session.get(AuditoriaSyslogEntrega, uid).tentativas == 2
        assert syslog.syslog_status()['pendentes'] == 0


def test_active_lease_skips_event_and_expired_worker_can_recover(app):
    configure(app)
    with app.app_context():
        uid = seed()
        state = AuditoriaSyslogEntrega(auditoria_id=uid, tentativas=1, proxima_tentativa=utcnow(),
            lease_token='crashed-worker', lease_ate=utcnow() + timedelta(minutes=2))
        db.session.add(state); db.session.commit()
        with patch.object(syslog, 'send_frame') as send:
            assert syslog.process_syslog()['transmitidos'] == 0
            send.assert_not_called()
            state.lease_ate = utcnow() - timedelta(seconds=1); db.session.commit()
            assert syslog.process_syslog()['transmitidos'] == 1


def test_skybox_retention_waits_for_syslog(app):
    configure(app)
    with app.app_context():
        uid = seed(); seed()
        with db.engine.begin() as conn:
            conn.execute(AuditoriaUsuario.__table__.update().values(arquivado_em=utcnow()))
            assert trim_auditoria_usuarios(conn, 1) == 0
        with patch.object(syslog, 'send_frame'):
            assert syslog.process_syslog()['transmitidos'] == 2
        with db.engine.begin() as conn:
            assert trim_auditoria_usuarios(conn, 1) == 1
            assert conn.execute(select(AuditoriaUsuario.id).where(AuditoriaUsuario.id == uid)).first() is None


def test_rollback_event_never_reaches_transport(app):
    configure(app)
    with app.app_context():
        db.session.add(AuditoriaUsuario(**event_values('EDICAO', 'CONFIRMADO')))
        db.session.flush(); db.session.rollback()
        with patch.object(syslog, 'send_frame') as send:
            assert syslog.process_syslog()['transmitidos'] == 0
            send.assert_not_called()


@pytest.mark.parametrize('values', [
    {'AUDIT_SYSLOG_HOST': ''}, {'AUDIT_SYSLOG_HOST': 'https://host'},
    {'AUDIT_SYSLOG_TRANSPORT': 'udp'}, {'AUDIT_SYSLOG_PORT': 0},
    {'AUDIT_SYSLOG_CERT_FILE': '/client.pem'},
])
def test_invalid_configuration_fails_without_network(app, values):
    configure(app); app.config.update(values)
    with app.app_context(), patch.object(syslog.socket, 'create_connection') as connect:
        with pytest.raises(ValueError): syslog.process_syslog()
        connect.assert_not_called()
        assert syslog.syslog_status()['erro_configuracao']


def test_tls_verifies_hostname_and_uses_private_ca_and_client_cert(app):
    configure(app)
    app.config.update(AUDIT_SYSLOG_TRANSPORT='tls', AUDIT_SYSLOG_CA_FILE='/ca.pem',
                      AUDIT_SYSLOG_CERT_FILE='/client.pem', AUDIT_SYSLOG_KEY_FILE='/client.key')
    with app.app_context(), patch.object(syslog.ssl, 'create_default_context') as context, \
         patch.object(syslog.socket, 'create_connection') as connect:
        syslog.send_frame(b'5 hello')
        context.assert_called_once_with(cafile='/ca.pem')
        context.return_value.load_cert_chain.assert_called_once_with('/client.pem', '/client.key')
        context.return_value.wrap_socket.assert_called_once_with(connect.return_value.__enter__.return_value, server_hostname='localhost')
        assert context.return_value.minimum_version == ssl.TLSVersion.TLSv1_2


def test_tls_verification_failure_stays_pending_without_tcp_fallback(app):
    configure(app); app.config['AUDIT_SYSLOG_TRANSPORT'] = 'tls'
    with app.app_context(), patch.object(syslog.ssl, 'create_default_context') as context, \
         patch.object(syslog.socket, 'create_connection') as connect:
        uid = seed()
        context.return_value.wrap_socket.side_effect = ssl.SSLCertVerificationError('invalid cert')
        assert syslog.process_syslog()['transmitidos'] == 0
        connect.return_value.__enter__.return_value.sendall.assert_not_called()
        assert db.session.get(AuditoriaSyslogEntrega, uid).enviado_em is None


def test_migration_up_down_preserves_audit_events(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'migrations/versions/e4b8c0d129fa_audit_syslog_delivery.py'
    spec = importlib.util.spec_from_file_location('syslog_migration', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = create_engine('sqlite:///' + str(tmp_path / 'migration.sqlite'))
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE auditoria_usuarios (id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('INSERT INTO auditoria_usuarios VALUES (42)')
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            assert 'auditoria_syslog_entregas' in inspect(conn).get_table_names()
            module.downgrade()
        assert conn.exec_driver_sql('SELECT id FROM auditoria_usuarios').scalar_one() == 42
    engine.dispose()
