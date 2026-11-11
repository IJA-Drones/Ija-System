"""Shared AZUL settings and metering; never stores messages, transcripts or audio."""
from contextlib import contextmanager
import json
from pathlib import Path
from threading import RLock
import time

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app
from app.extensions import db

metadata = db.metadata
configuration = sa.Table('azul_configuracao', metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('revision', sa.Integer, nullable=False),
    sa.Column('data', sa.Text, nullable=False),
    sa.Column('updated_at', sa.BigInteger, nullable=False),
    sa.Column('updated_by', sa.String(80), nullable=False))
audit = sa.Table('azul_configuracao_historico', metadata,
    sa.Column('id', sa.String(32), primary_key=True),
    sa.Column('created_at', sa.BigInteger, nullable=False),
    sa.Column('actor', sa.String(80), nullable=False),
    sa.Column('revision', sa.Integer, nullable=False),
    sa.Column('fields', sa.Text, nullable=False))
events = sa.Table('azul_consumo', metadata,
    sa.Column('id', sa.String(64), primary_key=True),
    sa.Column('created_at', sa.BigInteger, nullable=False, index=True),
    sa.Column('conversation', sa.String(64), nullable=False, index=True),
    sa.Column('actor', sa.String(80), nullable=False),
    sa.Column('channel', sa.String(16), nullable=False),
    sa.Column('operation', sa.String(20), nullable=False),
    sa.Column('source', sa.String(20), nullable=False),
    sa.Column('status', sa.String(20), nullable=False),
    sa.Column('model', sa.String(120), nullable=False, default=''),
    sa.Column('provider_id', sa.String(180)),
    sa.Column('pricing', sa.Text, nullable=False),
    sa.Column('fx', sa.String(30), nullable=False),
    sa.Column('reserved_brl', sa.BigInteger, nullable=False, default=0),
    sa.Column('cost_usd', sa.BigInteger),
    sa.Column('cost_brl', sa.BigInteger),
    sa.Column('measured', sa.Boolean, nullable=False, default=False),
    *[sa.Column(name, sa.BigInteger, nullable=False, default=0) for name in (
        'input_text', 'cached_text', 'output_text', 'input_audio', 'cached_audio',
        'output_audio', 'total_tokens', 'web_calls')],
    sa.Column('audio_seconds', sa.Float, nullable=False, default=0))


class StoreError(ValueError):
    pass


class Conflict(StoreError):
    pass


class BudgetExceeded(StoreError):
    pass


class Store:
    def __init__(self, engine):
        self.engine = engine
        self.ready = False
        self.lock = RLock()

    @contextmanager
    def connection(self, write=False):
        try:
            with self.engine.begin() as conn:
                if write:
                    if self.engine.dialect.name == 'postgresql':
                        conn.execute(sa.text("SET LOCAL lock_timeout = '3s'"))
                        conn.execute(sa.select(sa.func.pg_advisory_xact_lock(1229603099, 0)))
                    elif self.engine.dialect.name == 'sqlite':
                        conn.exec_driver_sql('BEGIN IMMEDIATE')
                    else:
                        raise StoreError('O banco configurado não suporta o controle da AZUL.')
                yield conn
        except SQLAlchemyError as exc:
            current_app.logger.warning('AZUL: controle indisponível (%s)', type(exc).__name__)
            raise StoreError('Não foi possível acessar as configurações e o consumo da AZUL.') from exc

    def ensure(self):
        with self.lock:
            if not self.ready:
                # Only these three additive tables; no operational schema or data changes.
                with self.connection(write=True) as conn:
                    metadata.create_all(conn,tables=[configuration,audit,events],checkfirst=True)
                    if conn.execute(sa.select(configuration.c.id).where(configuration.c.id == 1)).first() is None:
                        conn.execute(configuration.insert().values(id=1, revision=0, data='{}',
                            updated_at=int(time.time()), updated_by='system'))
                self.ready = True
        return self

    def load(self):
        with self.connection() as conn:
            row = conn.execute(sa.select(configuration).where(configuration.c.id == 1)).mappings().one()
            return {**dict(row), 'data':json.loads(row['data'])}


def current():
    if 'azul_control_store' not in current_app.extensions:
        if current_app.config.get('AZUL_CONTROL_DATABASE_URI'):
            engine = sa.create_engine(current_app.config['AZUL_CONTROL_DATABASE_URI'], pool_pre_ping=True)
        elif 'sqlalchemy' in current_app.extensions:
            from app.extensions import db
            engine = db.engine
        else:
            # Isolated tests/minimal Flask installations have no application database.
            path = Path(current_app.instance_path)
            path.mkdir(parents=True, exist_ok=True)
            engine = sa.create_engine('sqlite:///' + str(path/'azul_controle.sqlite'),
                                      connect_args={'timeout':3, 'check_same_thread':False})
        current_app.extensions['azul_control_store'] = Store(engine)
    return current_app.extensions['azul_control_store'].ensure()
