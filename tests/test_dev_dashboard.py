"""Expected auth events must not contaminate operational failure metrics."""
from datetime import datetime, timedelta

import pytest
from flask import Flask

from app.extensions import db
from app.models import AuditoriaUsuario
from app.modules.dev_dashboard.service import (
    _base_dev_dashboard_context, _failure_timeline, _serialize_datetime, get_dev_error_detail,
)


@pytest.fixture
def dashboard():
    app = Flask(__name__)
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', SECRET_KEY='test-key')
    db.init_app(app)
    with app.app_context():
        db.create_all()
        now = datetime.utcnow()
        cases = [
            ('SESSAO_EXPIRADA', 401, 'private.route'),
            ('ACESSO', 401, 'session_security.status'),
            ('ACESSO', 401, 'session_security.activity'),
            ('SESSAO_EXPIRADA', 303, 'private.route'),
            ('ACESSO', 401, 'private.route'),
            ('ACESSO', 403, 'session_security.activity'),
            ('SESSAO_EXPIRADA', 500, 'private.route'),
            ('ACESSO', 200, 'private.route'),
            ('ACESSO', 401, None),
        ]
        for kind, status, endpoint in cases:
            db.session.add(AuditoriaUsuario(usuario_nome='Teste', metodo='GET', path='/test',
                                            tipo_evento=kind, status_code=status, endpoint=endpoint,
                                            criado_em=now))
        db.session.commit()
        yield now
        db.session.remove()
        db.drop_all()


def test_expected_sessions_excluded_from_all_failure_views(dashboard):
    context = _base_dev_dashboard_context()
    assert context['metrics']['errors_24h'] == 4
    assert context['metrics']['expired_sessions_24h'] == 4
    assert context['metrics']['server_errors_7d'] == 1
    assert context['metrics']['error_rate'] == 44.4
    assert len(context['recent_errors']) == 4
    assert sum(row.total for row in context['top_error_routes']) == 4
    assert sum(point['total'] for point in context['failure_timeline']) == 4
    assert get_dev_error_detail(1)["title"] == "Sessão expirada"
    assert get_dev_error_detail(2)["title"] == "Sessão expirada"
    assert get_dev_error_detail(5)['status_code'] == 401
    assert get_dev_error_detail(7)['status_code'] == 500


def test_timeline_keeps_dates_separate_and_uses_brazil_time(dashboard):
    start = datetime(2026, 10, 19, 17, 30)
    AuditoriaUsuario.query.delete()
    for created in (start + timedelta(minutes=5), start + timedelta(hours=24)):
        db.session.add(AuditoriaUsuario(usuario_nome='Teste', metodo='GET', path='/test',
                                        tipo_evento='ACESSO', status_code=500, criado_em=created))
    db.session.commit()
    points = _failure_timeline(start)
    assert len(points) == 25
    assert points[0] == {'hour': '14:00', 'total': 1}
    assert points[-1] == {'hour': '14:00', 'total': 1}


def test_datetime_serialization_declares_utc():
    assert _serialize_datetime(datetime(2026, 10, 20, 17, 18)).endswith('+00:00')


def test_clear_errors_preserves_audit_and_new_failures(dashboard):
    from app.modules.dev_dashboard.service import clear_dev_errors

    original = AuditoriaUsuario.query.count()
    assert clear_dev_errors() == 4
    assert AuditoriaUsuario.query.count() == original + 1
    context = _base_dev_dashboard_context()
    assert context['metrics']['errors_24h'] == 0
    assert context['metrics']['server_errors_7d'] == 0
    assert context['recent_errors'] == []
    assert get_dev_error_detail(5)['status_code'] == 401
    assert get_dev_error_detail(7)['status_code'] == 500
    assert get_dev_error_detail(1)['title'] == 'Sessão expirada'
    assert get_dev_error_detail(99999) is None
    assert get_dev_error_detail(8) is None
    assert context['top_error_routes'] == []
    assert sum(point['total'] for point in context['failure_timeline']) == 0
    db.session.add(AuditoriaUsuario(usuario_nome='Teste', metodo='GET', path='/new',
                                    tipo_evento='ACESSO', status_code=500,
                                    criado_em=dashboard))
    db.session.commit()
    context = _base_dev_dashboard_context()
    assert context['metrics']['errors_24h'] == 1
    assert context['metrics']['server_errors_7d'] == 1
    assert len(context['recent_errors']) == 1
    assert clear_dev_errors() == 1
    assert _base_dev_dashboard_context()['metrics']['errors_24h'] == 0


def test_detail_route_keeps_old_rows_available_after_clear(dashboard, monkeypatch):
    from flask import Blueprint, current_app
    from flask_login import LoginManager
    from app.modules.dev_dashboard import routes
    from app.modules.dev_dashboard.service import clear_dev_errors

    app = current_app._get_current_object()
    LoginManager(app)
    app.config['LOGIN_DISABLED'] = True
    monkeypatch.setattr(routes, 'is_admin_global_user', lambda user: True)
    monkeypatch.setattr(routes, 'is_dev_user', lambda user: True)
    monkeypatch.setattr(routes, 'route_access', lambda *args: True)
    bp = Blueprint('main', __name__)
    routes.register_routes(bp)
    app.register_blueprint(bp)
    clear_dev_errors()
    client = app.test_client()
    response = client.get('/dev/errors/5')
    assert response.status_code == 200
    assert response.json['id'] == 5
    assert client.get('/dev/errors/1').json['title'] == 'Sessão expirada'
    assert client.get('/dev/errors/99999').status_code == 404
