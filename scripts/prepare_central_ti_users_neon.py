"""Prepare only individual-access tables in Neon. Default execution is read-only.

Reads the Neon DATABASE_URL from .env.neon.local or a commented line in .env.
Never uses the active Render connection and never advances alembic_version.
The later normal migration validates and reuses this prepared structure.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / 'migrations/versions/d92e7a4b6c81_add_central_ti_user_permissions.py'


def target_url(root=ROOT):
    local = root / '.env.neon.local'
    candidates = []
    if local.exists():
        candidates = [dotenv_values(local).get('DATABASE_URL')]
    else:
        for line in (root / '.env').read_text().splitlines():
            if re.match(r'^\s*#\s*DATABASE_URL\s*=', line):
                value = dotenv_values(stream=io.StringIO(re.sub(r'^\s*#\s*', '', line))).get('DATABASE_URL')
                if value and '.neon.tech' in value:
                    candidates.append(value)
    urls = {value for value in candidates if value}
    if len(urls) != 1:
        raise ValueError('É necessário um único DATABASE_URL Neon em .env.neon.local ou comentado no .env.')
    url = make_url(urls.pop().replace('postgres://', 'postgresql://', 1))
    if (url.get_backend_name() != 'postgresql' or not (url.host or '').lower().endswith('.neon.tech')
            or url.query.get('sslmode') not in {'require', 'verify-full'}
            or any(key in url.query for key in ('host', 'hostaddr', 'service'))):
        raise ValueError('Somente Neon com SSL e destino direto é aceito.')
    identity = '|'.join((url.host or '', url.database or '', url.username or ''))
    return url, hashlib.sha256(identity.encode()).hexdigest()[:16]


def load_migration():
    spec = importlib.util.spec_from_file_location('central_ti_users_migration', MIGRATION)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    return migration


def preserved_state(connection):
    tables = set(sa.inspect(connection).get_table_names())
    required = {'usuarios', 'central_ti_perfis_configuracoes', 'central_ti_selecoes', 'central_ti_auditoria'}
    if not required <= tables:
        raise ValueError('O Neon precisa ter os usuários e a Central de TI atual preparados.')
    if connection.execute(sa.text('SELECT current_schema()')).scalar_one() != 'public':
        raise ValueError('Schema inesperado; esperado public.')
    snapshot = {}
    for table in sorted(required):
        # A deterministic digest verifies preservation without exposing records.
        count, digest = connection.execute(sa.text(
            f"SELECT count(*), md5(coalesce(string_agg(md5(row_to_json(t)::text), '' ORDER BY md5(row_to_json(t)::text)), '')) FROM \"{table}\" t"
        )).one()
        snapshot[table] = {'count': count, 'digest': digest}
    snapshot['alembic_version'] = connection.execute(sa.text('SELECT version_num FROM alembic_version ORDER BY version_num')).scalars().all() if 'alembic_version' in tables else []
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-target')
    args = parser.parse_args()
    engine = None
    try:
        url, fingerprint = target_url()
        if args.apply and args.expected_target != fingerprint:
            raise ValueError('Use --expected-target com a identificação obtida na inspeção.')
        engine = sa.create_engine(url, poolclass=NullPool, hide_parameters=True, connect_args={'connect_timeout': 10})
        migration = load_migration()
        with engine.begin() as connection:
            if not args.apply: connection.execute(sa.text('SET TRANSACTION READ ONLY'))
            connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(sa.text("SET LOCAL statement_timeout = '60s'"))
            if args.apply: connection.execute(sa.text('SELECT pg_advisory_xact_lock(481725910064)'))
            before = preserved_state(connection)
            present = sorted(set(sa.inspect(connection).get_table_names()) & set(migration.EXPECTED_COLUMNS))
            if present and set(present) != set(migration.EXPECTED_COLUMNS):
                raise ValueError('Estrutura individual parcial; nenhuma alteração será aplicada.')
            if present: migration.validate_existing_schema(connection)
            if args.apply:
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
                migration.validate_existing_schema(connection)
                if preserved_state(connection) != before:
                    raise ValueError('Dados existentes mudaram durante a preparação; transação revertida.')
                for table in migration.EXPECTED_COLUMNS:
                    if not present and connection.execute(sa.text(f'SELECT count(*) FROM "{table}"')).scalar_one() != 0:
                        raise ValueError('A preparação não deve criar seleções ou alterar usuários.')
            summary = {'target': fingerprint, 'mode': 'apply' if args.apply else 'read_only',
                       'tables': sorted(migration.EXPECTED_COLUMNS) if args.apply else present,
                       'existing_users': before['usuarios']['count'], 'existing_data_preserved': True,
                       'alembic_version_unchanged': before['alembic_version']}
        print(json.dumps(summary, ensure_ascii=False))
    except (ValueError, sa.exc.SQLAlchemyError, RuntimeError) as exc:
        # Driver exceptions can include credentials or SQL parameters. Keep them private.
        print(json.dumps({'error': str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__}, ensure_ascii=False))
        raise SystemExit(1)
    finally:
        if engine is not None: engine.dispose()


if __name__ == '__main__':
    main()
