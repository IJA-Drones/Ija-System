"""Shared, transactional login limits. No passwords or session tokens are logged."""
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import ipaddress
import math

from flask import current_app, has_request_context, request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import LoginBloqueio, LoginEvento


class LoginBlocked(Exception):
    def __init__(self, seconds):
        self.seconds = max(1, math.ceil(seconds))


class LoginProtectionUnavailable(Exception):
    pass


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def policy():
    values = {
        'account_limit': int(current_app.config.get('LOGIN_MAX_FAILURES', 5)),
        'ip_limit': int(current_app.config.get('LOGIN_IP_MAX_FAILURES', 50)),
        'window_minutes': int(current_app.config.get('LOGIN_FAILURE_WINDOW_MINUTES', 15)),
        'lock_minutes': int(current_app.config.get('LOGIN_LOCKOUT_MINUTES', 15)),
    }
    if any(value < 1 for value in values.values()):
        raise ValueError('Os limites de proteção de login devem ser positivos.')
    return values


def client_ip():
    # Never trust arbitrary client-supplied forwarding headers. Walk right to
    # left only while the current peer belongs to an explicitly trusted proxy.
    trusted = [ipaddress.ip_network(item.strip()) for item in
               current_app.config.get('LOGIN_TRUSTED_PROXY_CIDRS', '').split(',') if item.strip()]
    try:
        peer = ipaddress.ip_address(request.remote_addr or '0.0.0.0')
        forwarded = request.headers.get('X-Forwarded-For', '').split(',')
        while forwarded and any(peer in network for network in trusted):
            peer = ipaddress.ip_address(forwarded.pop().strip())
        return str(peer)
    except ValueError:
        return str(ipaddress.ip_address(request.remote_addr or '0.0.0.0'))


def bucket_key(scope, value):
    # Case variants share a counter, including when the database is case sensitive.
    normalized = value.strip().casefold() if scope == 'conta' else value
    return hashlib.sha256(f'{scope}:{normalized}'.encode('utf-8')).hexdigest()


def _bucket(store, scope, value, now, rules):
    key = bucket_key(scope, value)
    dialect = store.get_bind().dialect.name
    if dialect not in {'postgresql', 'sqlite'}:
        raise LoginProtectionUnavailable()
    insert = pg_insert if dialect == 'postgresql' else sqlite_insert
    store.execute(insert(LoginBloqueio).values(
        chave=key, escopo=scope, identificacao=value[:128], falhas=0, janela_inicio=now,
    ).on_conflict_do_nothing(index_elements=['chave']))
    bucket = store.execute(select(LoginBloqueio).where(LoginBloqueio.chave == key)
                           .with_for_update().execution_options(populate_existing=True)).scalar_one()
    now = utcnow()  # A competing worker may have held the row lock.
    if bucket.bloqueado_ate and bucket.bloqueado_ate <= now:
        bucket.falhas, bucket.janela_inicio, bucket.bloqueado_ate = 0, now, None
    elif not bucket.bloqueado_ate and now >= bucket.janela_inicio + timedelta(minutes=rules['window_minutes']):
        bucket.falhas, bucket.janela_inicio = 0, now
    return bucket


def _remaining(bucket, now):
    return max(0, (bucket.bloqueado_ate - now).total_seconds()) if bucket.bloqueado_ate else 0


def _event(store, login, ip, channel, result, now, user=None):
    store.add(LoginEvento(criado_em=now, login=login[:50], ip=ip, canal=channel,
                          resultado=result, usuario_id=user.id if user else None))


def protect_login(channel):
    def decorate(authenticate):
        @wraps(authenticate)
        def protected(login_value, password):
            if not has_request_context() or not current_app.config.get('LOGIN_PROTECTION_ENABLED', False):
                return authenticate(login_value, password)
            login_value = login_value or ''
            wait = 0
            result = (None, 'invalid') if channel == 'agro' else None
            try:
                rules, ip = policy(), client_ip()
                # Authentication runs before login_user/presence. Use its request
                # transaction for verification, counters and events, so one request
                # never needs a second connection while holding a row lock.
                store = db.session
                now = utcnow()
                origin = _bucket(store, 'origem', ip, now, rules)
                wait = _remaining(origin, utcnow())
                account = None
                if not wait:
                    account = _bucket(store, 'conta', login_value, now, rules)
                    wait = _remaining(account, utcnow())
                if wait:
                    _event(store, login_value, ip, channel, 'bloqueado', now)
                else:
                    # Bound expensive password hashing and malformed identifiers.
                    if 0 < len(login_value) <= 50 and password and len(password) <= 128:
                        # Verify on this same connection: concurrent workers
                        # must not each reserve two connections from the pool.
                        result = authenticate(login_value, password, auth_session=store)
                    user = result[0] if isinstance(result, tuple) else result
                    now = utcnow()  # The block starts after verification finishes.
                    if user:
                        account.falhas, account.bloqueado_ate, account.janela_inicio = 0, None, now
                        # A valid account must not clear failures from other
                        # accounts using the same origin (password spraying).
                        _event(store, login_value, ip, channel, 'sucesso', now, user)
                    else:
                        for bucket, limit in ((origin, rules['ip_limit']), (account, rules['account_limit'])):
                            bucket.falhas += 1
                            if bucket.falhas >= limit:
                                bucket.bloqueado_ate = now + timedelta(minutes=rules['lock_minutes'])
                                wait = max(wait, _remaining(bucket, now))
                        _event(store, login_value, ip, channel,
                               'limite_atingido' if wait else 'falha', now)
                store.commit()
                # Raise only after committing the counter and its corresponding event.
                if wait:
                    raise LoginBlocked(wait)
                return result
            except (SQLAlchemyError, ValueError) as exc:
                db.session.rollback()
                current_app.logger.error('Proteção de login indisponível: %s', type(exc).__name__)
                raise LoginProtectionUnavailable() from None
        return protected
    return decorate


def unlock_bucket(key, actor, reason):
    """Caller enforces DEV identity, capability and CSRF. Unlock is audited atomically."""
    if not reason or not 5 <= len(reason.strip()) <= 300:
        raise ValueError('Informe um motivo entre 5 e 300 caracteres.')
    store = db.session
    try:
        row = store.execute(select(LoginBloqueio).where(LoginBloqueio.chave == key)
                            .with_for_update()).scalar_one_or_none()
        if row is None:
            return False
        now = utcnow()
        row.falhas, row.bloqueado_ate, row.janela_inicio = 0, None, now
        store.add(LoginEvento(criado_em=now, login=row.identificacao[:50] if row.escopo == 'conta' else '',
                              ip=client_ip(), canal='desenvolvedor', resultado='desbloqueio',
                              responsavel_id=actor.id,
                              motivo=f'{row.escopo}: {row.identificacao}; {reason.strip()}'))
        store.commit()
    except SQLAlchemyError:
        store.rollback()
        raise
    return True
