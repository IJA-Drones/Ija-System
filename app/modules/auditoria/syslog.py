"""RFC 5424 over TCP/TLS with octet counting and durable retry state.

sendall means transport submission, not acknowledged storage by the collector.
Event IDs permit collector-side deduplication after an ambiguous retry.
"""
import json
import socket
import ssl
import threading
from datetime import timedelta, timezone
from uuid import uuid4

import click
from flask import current_app
from sqlalchemy import func, or_, select, update

from app.extensions import db
from app.models import AuditoriaUsuario, AuditoriaSyslogEntrega, AuditoriaInstalacao
from app.modules.auditoria.archive import _encode
from app.modules.auditoria.recorder import utcnow

TIMEOUT_SECONDS = 5


def settings():
    config = current_app.config
    host = config.get('AUDIT_SYSLOG_HOST', '').strip()
    transport = config.get('AUDIT_SYSLOG_TRANSPORT', 'tls').lower()
    port = int(config.get('AUDIT_SYSLOG_PORT', 6514))
    if not host or any(c.isspace() for c in host) or '://' in host or '@' in host or '/' in host:
        raise ValueError('Informe um host syslog válido, sem URL ou credenciais.')
    if transport not in {'tcp', 'tls'} or not 1 <= port <= 65535:
        raise ValueError('Configure transporte tcp/tls e uma porta syslog válida.')
    cert = config.get('AUDIT_SYSLOG_CERT_FILE') or None
    key = config.get('AUDIT_SYSLOG_KEY_FILE') or None
    if bool(cert) != bool(key):
        raise ValueError('Certificado e chave de cliente devem ser configurados juntos.')
    return host, port, transport, cert, key


def frame(row, installation):
    # Reuse the archive's allowlist; never transmit raw URL/query/referrer/body.
    payload = json.loads(_encode(row))
    payload['instalacao_id'] = installation
    timestamp = row['criado_em'].replace(tzinfo=timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    severity = 4 if row['resultado'] in {'FALHA', 'NEGADO', 'BLOQUEADO'} else 6
    message = (f'<{16 * 8 + severity}>1 {timestamp} - IJA-System - AUDIT - '
               + json.dumps(payload, ensure_ascii=True, separators=(',', ':'))).encode('ascii')
    return str(len(message)).encode('ascii') + b' ' + message


def send_frame(data):
    host, port, transport, cert, key = settings()
    context = None
    if transport == 'tls':
        context = ssl.create_default_context(cafile=current_app.config.get('AUDIT_SYSLOG_CA_FILE') or None)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        if cert:
            context.load_cert_chain(cert, key)
    with socket.create_connection((host, port), timeout=TIMEOUT_SECONDS) as raw:
        if context is None:
            raw.sendall(data)
        else:
            # System/private CA trust and hostname verification are mandatory.
            with context.wrap_socket(raw, server_hostname=host) as secure:
                secure.sendall(data)
                # Send TLS close_notify and drain pending TLS session tickets.
                # Closing immediately can reset the stream before the collector
                # consumes the frame. Shutdown is not an application receipt.
                try:
                    secure.unwrap().close()
                except (OSError, ssl.SSLError):
                    # Some collectors omit their close_notify or keep the socket
                    # open; sendall already completed and the timeout is bounded.
                    pass


def deliver_one():
    """Claim one committed event, send outside the DB transaction, then acknowledge locally."""
    events = AuditoriaUsuario.__table__
    deliveries = AuditoriaSyslogEntrega.__table__
    now, token = utcnow(), str(uuid4())
    due = (deliveries.c.enviado_em.is_(None),
           or_(deliveries.c.proxima_tentativa.is_(None), deliveries.c.proxima_tentativa <= now),
           or_(deliveries.c.lease_ate.is_(None), deliveries.c.lease_ate < now))
    with db.engine.begin() as conn:
        row = conn.execute(select(events).outerjoin(deliveries, deliveries.c.auditoria_id == events.c.id)
            .where(*due).order_by(events.c.id).limit(1)
            .with_for_update(of=events, skip_locked=True)).mappings().first()
        if row is None:
            return None
        if conn.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert
        elif conn.dialect.name == 'sqlite':
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise RuntimeError('Syslog requer PostgreSQL ou SQLite.')
        conn.execute(insert(deliveries).values(auditoria_id=row['id'], tentativas=0, proxima_tentativa=now)
                     .on_conflict_do_nothing(index_elements=['auditoria_id']))
        claimed = conn.execute(update(deliveries).where(deliveries.c.auditoria_id == row['id'], *due)
            .values(lease_token=token, lease_ate=now + timedelta(minutes=2), tentativas=deliveries.c.tentativas + 1))
        if claimed.rowcount != 1:
            return None
        attempts = conn.execute(select(deliveries.c.tentativas).where(deliveries.c.auditoria_id == row['id'])).scalar_one()
        installation = conn.execute(select(AuditoriaInstalacao.identificador).where(AuditoriaInstalacao.id == 1)).scalar_one()
    try:
        send_frame(frame(row, installation))
    except Exception:
        # Error bodies/URLs/certificate paths can contain secrets; keep a generic message.
        with db.engine.begin() as conn:
            conn.execute(update(deliveries).where(deliveries.c.auditoria_id == row['id'], deliveries.c.lease_token == token)
                .values(lease_token=None, lease_ate=None,
                        proxima_tentativa=utcnow() + timedelta(seconds=min(3600, 5 * 2 ** min(attempts, 10))),
                        ultimo_erro='Falha na transmissão syslog. Nova tentativa automática agendada.'))
        current_app.logger.warning('Auditoria: evento %s aguarda nova tentativa syslog.', row['id'])
        return False
    with db.engine.begin() as conn:
        result = conn.execute(update(deliveries).where(deliveries.c.auditoria_id == row['id'], deliveries.c.lease_token == token)
            .values(enviado_em=utcnow(), lease_token=None, lease_ate=None, ultimo_erro=None))
        return result.rowcount == 1


def process_syslog(max_events=100):
    if not current_app.config.get('AUDIT_SYSLOG_ENABLED', False):
        return {'transmitidos': 0, 'habilitado': False}
    settings()
    sent = 0
    for _ in range(max_events):
        outcome = deliver_one()
        if outcome is None:
            break
        if outcome:
            sent += 1
        else:
            break
    return {'transmitidos': sent, 'habilitado': True}


def syslog_status():
    if not current_app.config.get('AUDIT_SYSLOG_ENABLED', False):
        return {'habilitado': False}
    try:
        settings()
        config_error = False
    except (ValueError, TypeError):
        config_error = True
    events, deliveries = AuditoriaUsuario.__table__, AuditoriaSyslogEntrega.__table__
    with db.engine.connect() as conn:
        pending = conn.execute(select(func.count()).select_from(events.outerjoin(deliveries, events.c.id == deliveries.c.auditoria_id))
                              .where(deliveries.c.enviado_em.is_(None))).scalar_one()
        failures = conn.execute(select(func.count()).select_from(deliveries).where(deliveries.c.enviado_em.is_(None), deliveries.c.ultimo_erro.isnot(None))).scalar_one()
        last = conn.execute(select(func.max(deliveries.c.enviado_em))).scalar_one()
    return {'habilitado': True, 'erro_configuracao': config_error, 'pendentes': pending,
            'falhas': failures, 'ultima_transmissao': last}


def register_syslog_worker(app):
    lock = threading.Lock()

    def loop():
        stop = app.extensions['audit_syslog_stop']
        interval = max(1, int(app.config.get('AUDIT_SYSLOG_INTERVAL_SECONDS', 5)))
        while not stop.is_set():
            with app.app_context():
                try:
                    process_syslog()
                except Exception:
                    app.logger.warning('Auditoria: syslog pendente; confira migração, configuração e conexão.')
            stop.wait(interval)

    @app.before_request
    def start():
        if app.testing or not app.config.get('AUDIT_SYSLOG_ENABLED', False):
            return
        with lock:
            if 'audit_syslog_stop' not in app.extensions:
                app.extensions['audit_syslog_stop'] = threading.Event()
                threading.Thread(target=loop, name='audit-syslog', daemon=True).start()

    @app.cli.command('auditoria-syslog-enviar')
    @click.option('--max-eventos', default=100, type=click.IntRange(1, 10000))
    def send(max_eventos):
        """Transmit pending events; does not enable an unconfigured collector."""
        result = process_syslog(max_eventos)
        click.echo(f'Syslog habilitado: {result["habilitado"]}. Eventos transmitidos: {result["transmitidos"]}.')

    @app.cli.command('auditoria-syslog-status')
    def status():
        click.echo(json.dumps(syslog_status(), default=str, ensure_ascii=False))
