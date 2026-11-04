"""The access overview is local, permission-aware, and never reads report data."""
from html.parser import HTMLParser
from pathlib import Path
import re
from unittest.mock import Mock, patch

import pytest
from flask import render_template
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from sqlalchemy import event

from app.extensions import db
from app.models import (
    AuditoriaUsuario, CentralTiPerfilConfiguracao, CentralTiSelecao,
    FeedbackTopico, OrdemServico, Solicitacao, Usuario,
)
from app.modules.chatbot import azul, exports, operations, search
from app.modules.gestao_ti.catalog import PERMISSION_CODES
from app.modules.gestao_ti.navigation import SCREENS
from tests.test_azul_exports import app, client
from tests.test_azul_isolation import isolated


@pytest.fixture
def local_only(monkeypatch):
    guards = []
    for owner, name in [(azul, 'OpenAI'), (azul, 'consume_help_quota'),
                        (search, 'execute'), (operations, 'summarize'), (exports, 'prepare')]:
        guard = Mock(side_effect=AssertionError(f'Overview must not call {name}'))
        monkeypatch.setattr(owner, name, guard)
        guards.append(guard)
    yield
    for guard in guards:
        guard.assert_not_called()


@pytest.mark.parametrize('payload', [
    {'message': 'Mostrar recursos', 'intent': 'access_overview'},
    {'message': 'O que posso acessar no sistema?'},
])
@pytest.mark.parametrize('provider_key', ['', 'test-key'])
def test_overview_needs_no_provider_quota_or_record_query(app, local_only, payload, provider_key):
    app.config['OPENAI_API_KEY'] = provider_key
    statements = []
    with app.app_context():
        engine = db.engine

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(engine, 'before_cursor_execute', capture)
    try:
        response = client(app).post('/api/azul/ajuda', json=payload)
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert response.status_code == 200
    assert response.json['mode'] == 'guided'
    assert response.json['export_preview'] is None
    assert response.json['chat_key']
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert not (Path(app.instance_path) / 'azul_help_quota.sqlite').exists()
    for model in (Solicitacao, OrdemServico, AuditoriaUsuario, FeedbackTopico):
        table_reference = rf'\b(?:from|join)\s+"?{re.escape(model.__tablename__)}"?\b'
        assert not any(re.search(table_reference, sql) for sql in statements)


def test_legacy_uvis_overview_offers_only_confirmed_shortcuts(isolated, local_only):
    isolated.config['CENTRAL_TI_ENFORCE_PERMISSIONS'] = False
    isolated.add_url_rule('/minhas-solicitacoes', endpoint='main.dashboard', view_func=lambda: '')
    isolated.add_url_rule('/agro/clientes', endpoint='main.agro_clientes_listar', view_func=lambda: '')
    response = client(isolated, 10).post('/api/azul/ajuda', json={
        'message': 'Meu acesso', 'role': 'dev', 'permissions': ['all'],
        'links': [{'label': 'Administração', 'url': '/admin'}]})
    assert response.status_code == 200
    assert response.json['profile'] == 'uvis'
    assert {link['url'] for link in response.json['links']} == {'/minhas-solicitacoes'}
    answer = response.json['answer']
    assert 'orientações e atalhos' in answer
    assert 'Buscar solicitações' not in answer
    assert 'Preparar relatórios' not in answer
    assert azul.UVIS_SCOPES['uvis'] in answer


@pytest.mark.parametrize('uid,role', [(10, 'uvis'), (22, 'equipe_uvis')])
def test_custom_unit_overview_reflects_granted_search_without_export_or_spoofing(isolated, local_only, uid, role):
    response = client(isolated, uid).post('/api/azul/ajuda', json={
        'message': 'Mostrar recursos', 'intent': 'access_overview',
        'role': 'dev', 'usuario_id': 1, 'permissions': ['all']})
    assert response.status_code == 200
    assert response.json['profile'] == role
    assert 'Buscar solicitações municipais' in response.json['answer']
    assert 'Preparar relatórios' not in response.json['answer']
    assert azul.UVIS_SCOPES[role] in response.json['answer']
    assert 'SEGREDO-' not in response.json['answer']
    assert 'Privado-' not in response.json['answer']


def test_changed_permissions_invalidate_overview_before_building_it(isolated, local_only):
    c = client(isolated, 10)
    first = c.post('/api/azul/ajuda', json={'message': 'Meu acesso'}).json
    with isolated.app_context():
        CentralTiSelecao.query.filter_by(
            perfil_codigo='uvis', codigo='prefeitura.solicitacoes.consultar').delete()
        db.session.commit()
    with patch.object(azul, 'access_overview', wraps=azul.access_overview) as overview:
        response = c.post('/api/azul/ajuda', json={
            'message': 'Meu acesso', 'intent': 'access_overview', 'chat_key': first['chat_key']})
        assert response.status_code == 409
        assert response.json['code'] == 'access_changed'
        overview.assert_not_called()
    fresh = c.post('/api/azul/ajuda', json={'message': 'Meu acesso'}).json
    assert fresh['chat_key'] != first['chat_key']
    assert 'Buscar solicitações municipais' not in fresh['answer']


@pytest.mark.parametrize('uid,can_export,technical_summary', [(1, True, True), (2, True, False), (3, False, False)])
def test_global_overview_offers_only_its_real_tools(isolated, local_only, uid, can_export, technical_summary):
    with isolated.app_context():
        db.session.get(Usuario, uid).trabalha_oceano_azul = True
        db.session.commit()
    response = client(isolated, uid).post('/api/azul/ajuda', json={'message': 'Meu acesso'})
    assert response.status_code == 200
    answer = response.json['answer']
    assert 'Buscar solicitações municipais' in answer
    assert ('Preparar relatórios' in answer) == can_export
    assert ('falhas e bugs do Painel Dev' in answer) == technical_summary
    assert ('precisam de atenção hoje' in answer) == (not technical_summary)


def test_director_overview_does_not_offer_an_ungranted_report_source(isolated, local_only):
    with isolated.app_context():
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='diretor', versao=2, atualizado_por_id=1))
        db.session.flush()
        for code in ('area:prefeitura', 'prefeitura.relatorios.consultar', 'prefeitura.relatorios.exportar'):
            db.session.add(CentralTiSelecao(perfil_codigo='diretor', codigo=code))
        db.session.commit()
    response = client(isolated, 2).post('/api/azul/ajuda', json={'message': 'Meu acesso'})
    assert response.status_code == 200
    assert 'Preparar relatórios de OS municipais' in response.json['answer']
    assert 'relatórios de solicitações' not in response.json['answer']
    assert 'Buscar solicitações municipais' not in response.json['answer']


def test_overview_shortcuts_cover_authorized_areas_without_duplicate_modules(isolated, local_only):
    for screens in SCREENS.values():
        for endpoint, _ in screens:
            endpoint = 'main.' + endpoint
            if endpoint not in isolated.view_functions:
                isolated.add_url_rule('/verified/' + endpoint[5:], endpoint=endpoint, view_func=lambda: '')
    # Grant many municipal modules and one module in each additional area.
    modules = [module for module in SCREENS if module.startswith('prefeitura.')][:14]
    modules += ['agro.clientes', 'financeiro.contas', 'sistema.suporte']
    codes = {f'area:{module.split(".")[0]}' for module in modules}
    codes.update(f'{module}.consultar' for module in modules if f'{module}.consultar' in PERMISSION_CODES)
    with isolated.app_context():
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='dev', versao=2, atualizado_por_id=1))
        db.session.flush()
        db.session.add_all(CentralTiSelecao(perfil_codigo='dev', codigo=code) for code in codes)
        db.session.commit()
    with isolated.test_request_context():
        authorized = azul.help_context(db.session.get(Usuario, 1), '')['atalhos']
    response = client(isolated).post('/api/azul/ajuda', json={'message': 'Meu acesso'})
    assert response.status_code == 200
    links = response.json['links']
    assert len(links) == 12
    assert len({link['modulo'] for link in links}) == len(links)
    assert {link['modulo'].split('.')[0] for link in links} == {'prefeitura', 'agro', 'financeiro', 'sistema'}
    assert all(link in authorized for link in links)
    assert '/verified/admin_usuarios_listar' not in {link['url'] for link in links}


@pytest.mark.parametrize('authenticated', [False, True])
def test_overview_does_not_bypass_login_or_area_access(isolated, local_only, authenticated):
    if authenticated:
        with isolated.app_context():
            CentralTiSelecao.query.filter_by(perfil_codigo='uvis', codigo='area:prefeitura').delete()
            db.session.commit()
        c = client(isolated, 10)
    else:
        c = isolated.test_client()
    with patch.object(azul, 'access_overview', wraps=azul.access_overview) as overview:
        response = c.post('/api/azul/ajuda', json={'message': 'Meu acesso', 'intent': 'access_overview'})
        assert response.status_code == (403 if authenticated else 401)
        overview.assert_not_called()


@pytest.mark.parametrize('template', ['azul_chat.html', '_chatbot_widget.html'])
def test_access_button_dispatches_the_local_overview(app, local_only, template):
    app.jinja_loader = ChoiceLoader([
        DictLoader({'base.html': '{% block content %}{% endblock %}'}),
        FileSystemLoader(str(Path(__file__).resolve().parents[1] / 'app/templates')),
    ])
    if template == '_chatbot_widget.html':
        app.add_url_rule('/widget-preview', endpoint='widget_preview', view_func=lambda: render_template(
            template, chatbot_api_url='/api/azul/ajuda', chatbot_id_prefix='test'))

    class Buttons(HTMLParser):
        def __init__(self):
            super().__init__()
            self.overview = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'button' and attrs.get('data-intent') == 'access_overview':
                self.overview.append(attrs)

    c = client(app)
    page = c.get('/azul' if template == 'azul_chat.html' else '/widget-preview')
    assert page.status_code == 200
    buttons = Buttons()
    buttons.feed(page.get_data(as_text=True))
    assert len(buttons.overview) == 1
    button = buttons.overview[0]
    response = c.post('/api/azul/ajuda', json={
        'message': button['data-question'], 'intent': button['data-intent']})
    assert response.status_code == 200
    assert response.json['mode'] == 'guided'
