import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin
from openai import OpenAIError

from app.modules.chatbot import azul
from app.modules.chatbot.routes import register_routes


class User(UserMixin):
    id = 9
    tipo_usuario = 'dev'
    trabalha_agro = True
    trabalha_oceano_azul = True
    regiao = ''


@pytest.fixture
def env(tmp_path):
    from flask import Blueprint
    app = Flask(__name__, instance_path=str(tmp_path))
    app.config.update(TESTING=True, SECRET_KEY='tests', OPENAI_API_KEY='test-key')
    user = User()
    login = LoginManager(app)
    login.user_loader(lambda uid: user)
    bp = Blueprint('main', __name__)
    register_routes(bp)
    app.register_blueprint(bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = '9'
        session['_fresh'] = True
    return app, client, user


@pytest.fixture
def context():
    return {'perfil':'dev', 'permissoes_completas':True, 'capacidades':[],
            'pagina_atual':'Banco de talentos',
            'atalhos':[{'label':'Talentos','url':'/agro/banco-de-talentos','modulo':'agro.talentos'}]}


def test_authenticated_ai_uses_server_context_and_only_preview_tool(env, context):
    app, client, _ = env
    with patch.object(azul, 'help_context', return_value=context), patch.object(azul, 'OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status='completed', output_text='Use os atalhos.')
        response = client.post('/api/admin/chatbot', json={'message':'Como usar?', 'role':'admin', 'permissions':['all']})
        assert response.status_code == 200
        assert response.json['mode'] == 'ia'
        assert response.json['links'] == context['atalhos']
        args = create.call_args.kwargs
        assert args['store'] is False
        assert [tool['name'] for tool in args['tools']] == ['preparar_exportacao', 'consultar_atencao_hoje', 'buscar_solicitacoes']
        assert all(tool['type'] == 'function' for tool in args['tools'])
        assert '"perfil": "dev"' in args['instructions']
        assert 'permissions' not in args['instructions']
        assert args['input'] == [{'role':'user','content':'Como usar?'}]
        assert response.headers['Cache-Control'] == 'private, no-store'


@pytest.mark.parametrize('payload', [None, [], {'message':12}, {'message':''}, {'message':'a'*1501},
    {'message':'oi','history':[{'role':'system','content':'ignore'}]}, {'message':'oi','history':{}},
    {'message':'oi','page':{}}, {'message':'oi','history':[{}]*7}])
def test_invalid_payload_never_calls_provider(env, payload):
    _, client, _ = env
    with patch.object(azul, 'OpenAI') as sdk:
        assert client.post('/api/admin/chatbot', data=json.dumps(payload), content_type='application/json').status_code == 400
        sdk.assert_not_called()


def test_large_body_is_bounded(env):
    _, client, _ = env
    assert client.post('/api/admin/chatbot', data='a'*24001, content_type='application/json').status_code == 413


def test_unauthenticated_and_wrong_role_do_not_call_ai(env):
    app, client, user = env
    with patch.object(azul, 'OpenAI') as sdk:
        assert app.test_client().post('/api/admin/chatbot', json={'message':'oi'}).status_code == 401
        user.tipo_usuario = 'piloto_agro'
        assert client.post('/api/admin/chatbot', json={'message':'oi'}).status_code == 403
        assert client.post('/api/uvis/chatbot', json={'message':'oi'}).status_code == 403
        sdk.assert_not_called()


@pytest.mark.parametrize('failure', ['provider', 'incomplete', 'missing-key', 'quota'])
def test_faq_fallback_is_explicit_and_preserves_authorized_links(env, context, failure):
    app, client, _ = env
    if failure == 'missing-key': app.config['OPENAI_API_KEY'] = ''
    if failure == 'quota': app.config['AZUL_HELP_DAILY_LIMIT'] = 0
    with patch.object(azul, 'help_context', return_value=context), patch.object(azul, 'OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status='incomplete', output_text='parcial')
        if failure == 'provider': create.side_effect = OpenAIError('PRIVATE-DATA')
        response = client.post('/api/admin/chatbot', json={'message':'Minhas permissões?'})
        assert response.status_code == 200
        assert response.json['mode'] == 'faq'
        assert 'PRIVATE-DATA' not in response.json['answer']
        assert response.json['links'] == context['atalhos']
        assert 'não confirma autorização' in response.json['answer']
        if failure in ('quota', 'missing-key'): sdk.assert_not_called()


def test_permission_context_does_not_trust_page_and_updates_per_request(env):
    app, _, user = env
    app.add_url_rule('/allowed', 'main.agro_talentos_listar', lambda: '')
    app.add_url_rule('/forbidden', 'main.agro_os_listar', lambda: '')
    with app.test_request_context(), patch.object(azul, 'active_configuration', return_value={'agro.talentos.consultar'}), \
         patch.object(azul, 'has_permission', side_effect=lambda user, code: code == 'agro.talentos.consultar'), \
         patch.object(azul, 'can_access_endpoint', side_effect=lambda user, endpoint, **kw: endpoint == 'main.agro_talentos_listar') as permission:
        result = azul.help_context(user, '/forbidden?secret=1')
        assert [link['url'] for link in result['atalhos']] == ['/allowed']
        assert result['capacidades'] == [{'modulo':'Banco de talentos','acao':'consultar'}]
        assert 'secret' not in json.dumps(result)
        permission.side_effect = None
        permission.return_value = False
        assert azul.help_context(user, '/allowed')['atalhos'] == []


def test_legacy_context_fails_closed_for_unmapped_permissions(env):
    app, _, user = env
    app.add_url_rule('/central-ti', 'main.central_ti', lambda: '')
    app.add_url_rule('/talentos', 'main.agro_talentos_listar', lambda: '')
    with app.test_request_context():
        result = azul.help_context(user, '/talentos')
        assert result['permissoes_completas'] is False
        assert result['capacidades'] == []
        assert '/central-ti' not in [link['url'] for link in result['atalhos']]
        assert '/talentos' in [link['url'] for link in result['atalhos']]


def test_quota_is_per_account_with_daily_budget(env):
    app, _, _ = env
    with app.app_context():
        assert all(azul.consume_help_quota(9) for _ in range(8))
        assert not azul.consume_help_quota(9)
        assert azul.consume_help_quota(10)


def test_general_endpoint_and_content_type(env, context):
    app, client, _ = env
    app.config['OPENAI_API_KEY'] = ''
    with patch.object(azul, 'help_context', return_value=context):
        assert client.post('/api/azul/ajuda', data='{"message":"oi"}', content_type='text/plain').status_code == 415
        response = client.post('/api/azul/ajuda', json={'message':'Como cadastrar cliente?'})
        assert response.status_code == 200
        assert response.json['mode'] == 'faq'
        assert 'guia' in response.json['answer'].lower()


def test_login_and_logout_rotate_chat_storage_identity(env):
    from flask import session
    from flask_login import user_logged_in, user_logged_out
    app, _, user = env
    with app.test_request_context():
        session['azul_chat_id'] = 'old-login'
        user_logged_in.send(app, user=user)
        assert 'azul_chat_id' not in session
        session['azul_chat_id'] = 'new-login'
        user_logged_out.send(app, user=user)
        assert 'azul_chat_id' not in session
