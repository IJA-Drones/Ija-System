import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from flask import Blueprint
from flask_login import login_user, logout_user

from app.extensions import db
from app.models import AuditoriaUsuario, FeedbackTopico, Usuario
from app.modules.chatbot import dev_briefing
from tests.test_azul_exports import app, client


def seed(app):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        for status, age, kind, endpoint in [(500, 1, 'ACESSO', None), (403, 2, 'ACESSO', None),
                (401, 1, 'SESSAO_EXPIRADA', None), (409, 1, 'ACESSO', 'edit_control.lease'),
                (500, 25, 'ACESSO', None)]:
            db.session.add(AuditoriaUsuario(usuario_nome='PRIVATE_NAME', metodo='GET', path='/PRIVATE_PATH',
                endpoint=endpoint, tipo_evento=kind, status_code=status, criado_em=now-timedelta(hours=age)))
        for status, age, sector in [('aberto', 1, 'tecnico'), ('concluido', 1, 'tecnico'),
                                   ('aberto', 25, 'tecnico'), ('aberto', 1, 'operacional')]:
            db.session.add(FeedbackTopico(uvis_usuario_id=1, uvis_nome='Test', criado_por_id=1,
                criado_por_nome='PRIVATE_NAME', titulo='PRIVATE_TITLE', descricao='PRIVATE_DESCRIPTION',
                categoria='bug', setor_suporte=sector, status=status, criado_em=now-timedelta(hours=age)))
        db.session.commit()


def test_briefing_uses_only_last_24h_and_open_technical_bugs(app):
    seed(app)
    with app.test_request_context(), patch.object(dev_briefing.voice, 'offer', return_value={'url':'/api/azul/voz','token':'signed'}) as offer:
        data = dev_briefing.build(db.session.get(Usuario, 1))
        assert offer.call_args.args[0] == data['answer']
    assert data['metrics'] == {'errors_24h':2,'server_errors_24h':1,'new_open_bugs_24h':1}
    assert len(data['answer']) < 3000
    assert 'PRIVATE_' not in json.dumps(data)
    assert len(data['links']) == 3


def test_briefing_omits_inaccessible_bug_counts_and_denies_non_dev(app):
    seed(app)
    with app.test_request_context(), patch.object(dev_briefing, 'can_access_endpoint', side_effect=lambda user, endpoint, *args, **kwargs: endpoint != 'main.feedback_listar'):
        data = dev_briefing.build(db.session.get(Usuario, 1))
        assert data['metrics']['new_open_bugs_24h'] is None
        assert all(link['url'] != '/feedback' for link in data['links'])
    with app.test_request_context(), pytest.raises(PermissionError):
        dev_briefing.build(db.session.get(Usuario, 2))


def test_login_invites_dev_once_and_logout_clears_it(app):
    with app.test_request_context():
        from flask import session
        login_user(db.session.get(Usuario, 1))
        assert session['dev_briefing_pending'] is True
        logout_user()
        assert 'dev_briefing_pending' not in session
        login_user(db.session.get(Usuario, 2))
        assert 'dev_briefing_pending' not in session


def test_briefing_route_is_private_and_dashboard_consumes_invitation(app, monkeypatch):
    from app.modules.dev_dashboard import routes
    bp = Blueprint('dev_test', __name__)
    routes.register_routes(bp)
    app.register_blueprint(bp)
    seed(app)
    c = client(app)
    with c.session_transaction() as session:
        session['dev_briefing_pending'] = True
    monkeypatch.setattr(routes, 'render_template', lambda template, **context: json.dumps({'invite':context['dev_briefing_invite']}))
    assert json.loads(c.get('/dev').data)['invite'] is True
    assert json.loads(c.get('/dev').data)['invite'] is False
    response = c.get('/dev/briefing')
    assert response.status_code == 200
    assert 'no-store' in response.headers['Cache-Control']
    assert client(app, 2).get('/dev/briefing').status_code == 403
    assert app.test_client().get('/dev/briefing').status_code == 401
