from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import Flask, Response, has_request_context
from sqlalchemy import inspect, text

from app.extensions import db
from scripts.migrate_company_logos_to_skybox import migrate_company_logos


def migration(name):
    path = next((Path(__file__).resolve().parents[1] / 'migrations/versions').glob(name + '*.py'))
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('matches', [True, False])
def test_legacy_transfer_verifies_bytes_before_removing_blob(matches):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    db.init_app(app)
    with app.app_context():
        with db.engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                migration('d8a210bf7c35').upgrade()
                migration('e2b431cc9f70').upgrade()
            conn.execute(text("INSERT INTO financeiro_empresa_perfis (empresa_slug, logo, tem_logo) VALUES ('ija', :logo, TRUE)"), {'logo': b'original'})
        def stream_logo(path):
            assert has_request_context()
            return Response(b'original' if matches else b'corrupt')
        with patch('scripts.migrate_company_logos_to_skybox.upload_company_logo', return_value='skybox://verified.png'), patch('scripts.migrate_company_logos_to_skybox.stream_skybox_file', side_effect=stream_logo):
            if matches:
                assert migrate_company_logos() == 1
                assert migrate_company_logos() == 0
            else:
                with pytest.raises(RuntimeError, match='verificação'):
                    migrate_company_logos()
        row = db.session.execute(text('SELECT logo, logo_path FROM financeiro_empresa_perfis')).one()
        assert row.logo == (None if matches else b'original')
        assert row.logo_path == ('skybox://verified.png' if matches else None)
        db.session.rollback()
        with db.engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                if matches:
                    migration('f2c531cc9f71').upgrade()
                    assert 'logo' not in {c['name'] for c in inspect(conn).get_columns('financeiro_empresa_perfis')}
                else:
                    with pytest.raises(RuntimeError, match='Migre as logos'):
                        migration('f2c531cc9f71').upgrade()
