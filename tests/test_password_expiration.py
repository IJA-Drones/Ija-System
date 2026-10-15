"""Expiration rollout, renewal proof, session enforcement and DEV administration."""
from datetime import timedelta
from importlib.util import module_from_spec, spec_from_file_location
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from flask import jsonify
from flask_login import login_required
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import LoginEvento, PoliticaSenha, Usuario, PilotoAgro
from app.shared import password_expiration as expiry
from app.shared.csrf_security import CSRF_SESSION_KEY
from app.shared.login_protection import utcnow
import test_login_protection as login_tests
from test_login_protection import authorized_client, PASSWORD, ROOT

app = login_tests.app

NEW_PASSWORD = 'Uma senha renovada segura 8!'


@pytest.fixture
def expiry_app(app):
    expiry.register_password_expiration(app)
    app.config['PASSWORD_MIN_LENGTH'] = 15
    app.config['SECRET_KEY'] = 'password-expiration-test-key-not-for-production'
    app.mutations = 0

    @app.route('/protected-expiry', methods=['GET', 'POST'])
    @login_required
    def protected_expiry():
        app.mutations += 1
        return jsonify(ok=True)

    with app.app_context():
        db.session.add(PoliticaSenha(id=1, validade_dias=90))
        db.session.commit()
    return app


def age_user(app, login='unidade', days=91):
    with app.app_context():
        user = Usuario.query.filter_by(login=login).one()
        user.senha_alterada_em = utcnow() - timedelta(days=days)
        db.session.commit()


def challenge(app, path='/login', login='unidade'):
    age_user(app, login)
    client = app.test_client()
    response = client.post(path, data={'login': login, 'senha': PASSWORD})
    assert response.status_code == 303 and response.location.endswith('/renovar-senha')
    with client.session_transaction() as state:
        assert '_user_id' not in state
        token = state[CSRF_SESSION_KEY]
    return client, token


def renew(client, token, password=NEW_PASSWORD, **extra):
    return client.post('/renovar-senha', data={'senha': password, 'senha2': password, '_csrf_token': token, **extra})


@pytest.mark.parametrize('path,login', [('/login', 'unidade'), ('/uvis-operacional/login', 'unidade'), ('/agro/login', 'piloto')])
def test_expired_credentials_only_allow_renewal_in_all_three_portals(expiry_app, path, login):
    client, token = challenge(expiry_app, path, login)
    assert client.get('/protected-expiry').status_code == 302
    assert expiry_app.mutations == 0
    page = client.get('/renovar-senha')
    assert page.status_code == 200
    assert 'Sua senha venceu' in page.get_data(as_text=True)
    assert page.headers['Cache-Control'] == 'private, no-store'
    assert PASSWORD not in page.get_data(as_text=True)
    with client.session_transaction() as state:
        assert PASSWORD not in str(dict(state))
        old_cookie = dict(state)
    response = renew(client, token)
    assert response.status_code == 303 and response.location.endswith(path)
    with client.session_transaction() as state:
        assert '_user_id' not in state and expiry.RENEWAL_KEY not in state
    with expiry_app.app_context():
        user = Usuario.query.filter_by(login=login).one()
        assert user.check_senha(NEW_PASSWORD) and not user.check_senha(PASSWORD)
        assert not expiry.password_expired(user)
        assert [e.resultado for e in LoginEvento.query.order_by(LoginEvento.id)] == ['senha_expirada', 'senha_renovada']
        assert all(NEW_PASSWORD not in str(e.__dict__) and PASSWORD not in str(e.__dict__) for e in LoginEvento.query)
    # A copied pre-renewal signed session cannot renew the same credential twice.
    replay = expiry_app.test_client()
    with replay.session_transaction() as state: state.update(old_cookie)
    assert renew(replay, token).status_code == 303
    assert client.post(path, data={'login': login, 'senha': NEW_PASSWORD}).status_code == 302
    assert client.get('/protected-expiry').status_code == 200


def test_legacy_password_remains_exempt_until_changed(expiry_app):
    client = expiry_app.test_client()
    assert client.post('/login', data={'login': 'unidade', 'senha': PASSWORD}).status_code == 302
    with expiry_app.app_context():
        user = Usuario.query.filter_by(login='unidade').one()
        assert user.senha_alterada_em is None and not expiry.password_expired(user)
        db.session.get(PoliticaSenha, 1).validade_dias = 1
        db.session.commit()
    assert client.get('/protected-expiry').status_code == 200
    with expiry_app.app_context():
        user = Usuario.query.filter_by(login='unidade').one()
        user.set_senha(NEW_PASSWORD)
        db.session.commit()
        assert user.senha_alterada_em is not None
    # Resetting an old password enrolls it and invalidates its old active session.
    assert client.post('/protected-expiry').status_code == 303
    assert expiry_app.mutations == 1


def test_password_creation_and_failed_validation_dates(expiry_app):
    with expiry_app.app_context():
        user = Usuario(login='novo', nome_uvis='Novo', tipo_usuario='uvis')
        user.set_senha(NEW_PASSWORD)
        db.session.add(user); db.session.commit()
        original = user.senha_alterada_em
        assert original and not expiry.password_expired(user)
        expiry_app.config['SECURITY_CONTROLS_ENABLED'] = True
        with pytest.raises(ValueError): user.set_senha('fraca')
        assert user.senha_alterada_em == original


def test_expiration_boundary_and_existing_session_cannot_bypass(expiry_app):
    age_user(expiry_app, days=89)
    client = expiry_app.test_client()
    assert client.post('/login', data={'login': 'unidade', 'senha': PASSWORD}).status_code == 302
    with expiry_app.app_context():
        changed = Usuario.query.filter_by(login='unidade').one().senha_alterada_em
        with patch.object(expiry, 'utcnow', return_value=changed + timedelta(days=90, microseconds=-1)):
            assert not expiry.password_expired(Usuario.query.filter_by(login='unidade').one())
    with patch.object(expiry, 'utcnow', return_value=changed + timedelta(days=90)):
        response = client.post('/protected-expiry', json={})
    assert response.status_code == 401 and response.json['code'] == 'password_expired'
    assert expiry_app.mutations == 0
    with client.session_transaction() as state: assert '_user_id' not in state


@pytest.mark.parametrize('value', ['', 'fraca', PASSWORD, 'x'*129])
def test_rejects_bad_or_reused_password_without_altering_it(expiry_app, value):
    client, token = challenge(expiry_app)
    assert renew(client, token, password=value).status_code == 400
    assert renew(client, token, senha2='diferente').status_code == 400
    with expiry_app.app_context():
        assert Usuario.query.filter_by(login='unidade').one().check_senha(PASSWORD)
        assert LoginEvento.query.filter_by(resultado='senha_renovada').count() == 0


def test_csrf_and_ten_minute_challenge_required(expiry_app):
    assert expiry_app.test_client().post('/renovar-senha', data={'senha': NEW_PASSWORD}).status_code == 303
    client, token = challenge(expiry_app)
    assert renew(client, '').status_code == 403
    assert renew(client, 'invalid').status_code == 403
    with client.session_transaction() as state:
        state[expiry.RENEWAL_KEY] = {**state[expiry.RENEWAL_KEY], 'created_at': expiry.time.time() - 601}
    assert renew(client, token).status_code == 303
    with expiry_app.app_context(): assert Usuario.query.filter_by(login='unidade').one().check_senha(PASSWORD)


def test_admin_reset_invalidates_outstanding_renewal_proof(expiry_app):
    client, token = challenge(expiry_app)
    with expiry_app.app_context():
        user = Usuario.query.filter_by(login='unidade').one()
        user.set_senha('Senha definida pelo suporte 2!')
        db.session.commit()
    assert renew(client, token).status_code == 303
    with expiry_app.app_context():
        assert Usuario.query.filter_by(login='unidade').one().check_senha('Senha definida pelo suporte 2!')


def test_reset_between_password_check_and_session_creation_denies_access(expiry_app):
    from app.modules.auth.service import authenticate_user
    age_user(expiry_app)
    def authenticate_then_reset(login, password):
        user = authenticate_user(login, password)
        user.set_senha(NEW_PASSWORD)
        db.session.commit()
        return user
    client = expiry_app.test_client()
    with patch('app.modules.auth.routes.authenticate_user', side_effect=authenticate_then_reset):
        assert client.post('/login', data={'login':'unidade', 'senha':PASSWORD}).status_code == 503
    with client.session_transaction() as state:
        assert '_user_id' not in state and expiry.RENEWAL_KEY not in state


def test_inactive_agro_pilot_cannot_complete_renewal(expiry_app):
    client, token = challenge(expiry_app, '/agro/login', 'piloto')
    with expiry_app.app_context():
        db.session.get(PilotoAgro, 1).ativo = False
        db.session.commit()
    assert renew(client, token).status_code == 303
    with expiry_app.app_context(): assert Usuario.query.filter_by(login='piloto').one().check_senha(PASSWORD)


def test_renewal_commit_failure_rolls_back_password_and_event(expiry_app):
    client, token = challenge(expiry_app)
    with patch.object(db.session, 'commit', side_effect=SQLAlchemyError('simulated')):
        assert renew(client, token).status_code == 503
    with expiry_app.app_context():
        assert Usuario.query.filter_by(login='unidade').one().check_senha(PASSWORD)
        assert LoginEvento.query.filter_by(resultado='senha_renovada').count() == 0
    assert renew(client, token).status_code == 303


def test_dev_changes_policy_and_records_history(expiry_app):
    client = authorized_client(expiry_app, 3)
    assert client.get('/dev/seguranca-login').status_code == 200
    path = '/dev/seguranca-login/validade-senha'
    assert client.post(path, data={'validade_dias':'30'}).status_code == 403
    for value in ['0','366','-1','3.5','abc','']:
        assert client.post(path, data={'validade_dias':value,'_csrf_token':'known-csrf'}).status_code == 400
    assert client.post(path, data={'validade_dias':'30','_csrf_token':'known-csrf'}).status_code == 303
    with expiry_app.app_context():
        assert expiry.validity_days() == 30
        event = LoginEvento.query.filter_by(resultado='politica_senha').one()
        assert event.responsavel_id == 3 and '90 para 30 dias' in event.motivo
        assert all(user.senha_alterada_em is None for user in Usuario.query)


@pytest.mark.parametrize('user_id', [1,2,4,5,6])
def test_policy_is_exclusive_to_dev(expiry_app, user_id):
    client = authorized_client(expiry_app, user_id)
    assert client.post('/dev/seguranca-login/validade-senha',
                       data={'validade_dias':'30','_csrf_token':'known-csrf'}).status_code == 403
    with expiry_app.app_context(): assert expiry.validity_days() == 90


def test_policy_commit_failure_rolls_back_with_event(expiry_app):
    client = authorized_client(expiry_app, 3)
    with patch.object(db.session, 'commit', side_effect=SQLAlchemyError('simulated')):
        assert client.post('/dev/seguranca-login/validade-senha',
                           data={'validade_dias':'30','_csrf_token':'known-csrf'}).status_code == 503
    with expiry_app.app_context():
        assert expiry.validity_days() == 90
        assert LoginEvento.query.count() == 0


def test_policy_changes_apply_to_enrolled_credentials_only(expiry_app):
    age_user(expiry_app, days=40)
    with expiry_app.app_context():
        user = Usuario.query.filter_by(login='unidade').one()
        legacy = Usuario.query.filter_by(login='dev').one()
        assert not expiry.password_expired(user)
        settings = db.session.get(PoliticaSenha, 1)
        settings.validade_dias = 30
        db.session.commit()
        assert expiry.password_expired(user) and not expiry.password_expired(legacy)
        settings.validade_dias = 60
        db.session.commit()
        assert not expiry.password_expired(user)


def test_central_ti_permissions_apply_to_policy_updates(expiry_app):
    from app.models import CentralTiPerfilConfiguracao, CentralTiSelecao
    expiry_app.config.update(CENTRAL_TI_ENABLED=True, CENTRAL_TI_ENFORCE_PERMISSIONS=True)
    with expiry_app.app_context():
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='dev', versao=2, atualizado_por_id=3))
        db.session.add_all([CentralTiSelecao(perfil_codigo='dev', codigo=code)
                            for code in ['area:sistema', 'sistema.tecnico.consultar']])
        db.session.commit()
    client = authorized_client(expiry_app, 3)
    path = '/dev/seguranca-login/validade-senha'
    assert client.get('/dev/seguranca-login').status_code == 200
    assert client.post(path, data={'validade_dias':30, '_csrf_token':'known-csrf'}).status_code == 403
    with expiry_app.app_context():
        db.session.add(CentralTiSelecao(perfil_codigo='dev', codigo='sistema.tecnico.operar'))
        db.session.commit()
    assert client.post(path, data={'validade_dias':30, '_csrf_token':'known-csrf'}).status_code == 303


def test_wrong_password_or_blocked_account_cannot_start_renewal(expiry_app):
    age_user(expiry_app)
    client = expiry_app.test_client()
    for status in [200, 200, 429]:
        assert client.post('/login', data={'login':'unidade', 'senha':'wrong'}).status_code == status
    assert client.post('/login', data={'login':'unidade', 'senha':PASSWORD}).status_code == 429
    with client.session_transaction() as state:
        assert expiry.RENEWAL_KEY not in state and '_user_id' not in state


def test_renewal_also_works_with_global_csrf_enabled(expiry_app):
    expiry_app.config['CSRF_PROTECTION_ENABLED'] = True
    age_user(expiry_app)
    client = expiry_app.test_client()
    assert client.get('/login').status_code == 200
    with client.session_transaction() as state: token = state[CSRF_SESSION_KEY]
    assert client.post('/login', data={'login':'unidade', 'senha':PASSWORD, '_csrf_token':token}).status_code == 303
    with client.session_transaction() as state: renewal_token = state[CSRF_SESSION_KEY]
    assert renewal_token != token
    assert renew(client, renewal_token).status_code == 303


def test_unavailable_policy_does_not_allow_login_or_protected_operation(expiry_app):
    age_user(expiry_app, days=1)
    client = expiry_app.test_client()
    with patch.object(expiry, 'validity_days', side_effect=SQLAlchemyError('simulated')):
        assert client.post('/login', data={'login':'unidade', 'senha':PASSWORD}).status_code == 503
    with client.session_transaction() as state: assert '_user_id' not in state
    assert client.post('/login', data={'login':'unidade', 'senha':PASSWORD}).status_code == 302
    with patch.object(expiry, 'validity_days', side_effect=SQLAlchemyError('simulated')):
        assert client.post('/protected-expiry').status_code == 503
    assert expiry_app.mutations == 0


def test_migration_preserves_existing_passwords_and_reverses_cleanly():
    spec = spec_from_file_location('expiry_migration', ROOT/'migrations/versions/d94f2a7610be_password_expiration.py')
    migration = module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('PRAGMA foreign_keys=ON'))
        conn.execute(text('CREATE TABLE usuarios (id INTEGER PRIMARY KEY, senha_hash VARCHAR(200) NOT NULL)'))
        conn.execute(text("INSERT INTO usuarios VALUES (1, 'existing-hash')"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            assert tuple(conn.execute(text('SELECT senha_hash, senha_alterada_em FROM usuarios')).one()) == ('existing-hash', None)
            assert conn.execute(text('SELECT validade_dias FROM politica_senha')).scalar() == 90
            conn.execute(text('UPDATE politica_senha SET atualizado_por_id=1'))
            conn.execute(text('DELETE FROM usuarios WHERE id=1'))
            assert conn.execute(text('SELECT atualizado_por_id FROM politica_senha')).scalar() is None
            migration.downgrade()
            assert 'politica_senha' not in inspect(conn).get_table_names()
            assert 'senha_alterada_em' not in {c['name'] for c in inspect(conn).get_columns('usuarios')}
    scripts = ScriptDirectory(str(ROOT/'migrations'))
    assert len(scripts.get_heads()) == 1
    assert migration.revision in {revision.revision for revision in scripts.walk_revisions()}
