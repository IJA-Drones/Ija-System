"""Navigation and execution workflows with fictitious data in an isolated database."""
import html
import json
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import pytest
from flask import Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader

from app.extensions import db
from app.models import Equipe, EquipePiloto, OrdemServico, Pilotos, Prefeitura, Solicitacao, Usuario


ROOT = Path(__file__).resolve().parents[1]
PLAN = {'cenario': 'planejamento preservado', 'medicao': {'resumo': 'Medicao de teste'}, 'resultado': {}}


@pytest.fixture
def app():
    app = Flask(__name__, template_folder=str(ROOT / 'app/templates'), static_folder=str(ROOT / 'app/static'))
    app.config.update(TESTING=True, SECRET_KEY='sprint1-test', SQLALCHEMY_DATABASE_URI='sqlite://',
                      CENTRAL_TI_ENABLED=False, SECURITY_CONTROLS_ENABLED=False, SKYBOX_ENABLED=False,
                      AUDIT_SKYBOX_ENABLED=False)
    db.init_app(app)
    login = LoginManager(app)
    login.user_loader(lambda uid: db.session.get(Usuario, int(uid)))
    from app.routes import bp
    with patch('app.modules.backup.routes.start_daily_backup_scheduler'):
        app.register_blueprint(bp)
    app.jinja_loader = ChoiceLoader([
        DictLoader({'base.html': '{% block content %}{% endblock %}{% block scripts %}{% endblock %}'}),
        app.jinja_loader,
    ])
    app.jinja_env.globals['brazil_datetime'] = lambda value: value
    with app.app_context():
        db.create_all()
        db.session.add(Prefeitura(id=1, nome='Municipio de teste', slug='teste'))
        db.session.add(Pilotos(id=1, nome_piloto='Piloto de teste', prefeitura_id=1, regiao='OESTE'))
        db.session.add(Equipe(id=1, nome_equipe='Equipe de teste', prefeitura_id=1, regiao='OESTE', ativa=True))
        db.session.flush()
        for uid, role in [(1, 'admin'), (2, 'uvis'), (3, 'piloto')]:
            db.session.add(Usuario(id=uid, nome_uvis=f'Usuario de teste {uid}', login=f'teste-{uid}',
                                   senha_hash='test', tipo_usuario=role, prefeitura_id=1, regiao='OESTE',
                                   piloto_id=1 if role == 'piloto' else None))
        db.session.add(EquipePiloto(equipe_id=1, piloto_id=1, papel='piloto'))
        for sid in range(1, 252):
            db.session.add(Solicitacao(
                id=sid, prefeitura_id=1, usuario_id=2, equipe_id=1, status='PENDENTE',
                data_agendamento=date.today() + timedelta(days=sid), hora_agendamento=time(9),
                data_criacao=datetime(2026, 1, 1) + timedelta(minutes=sid),
                tipo_visita='Culex', foco='Corrego', distrito_administrativo='Distrito de teste',
                cep='00000000', logradouro='Rua de teste', numero=str(sid), bairro='Centro',
                cidade='Municipio de teste', uf='SP', place_id=f'local-teste-{sid}',
            ))
        db.session.commit()
    with patch('app.modules.solicitacoes.service.resolve_google_place_id_for_address', return_value='local-teste'):
        yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def client(app, uid):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(uid)
        session['_fresh'] = True
    return client


def edit_form(**extra):
    return dict(data_agendamento=date.today().isoformat(), hora_agendamento='09:00',
                tipo_visita='Culex', foco='Corrego', distrito_administrativo='Distrito de teste', **extra)


def hidden_value(response, name):
    match = re.search(r'<input\b[^>]*name="' + re.escape(name) + r'"[^>]*value="([^"]*)"',
                      response.get_data(as_text=True))
    assert match, response.get_data(as_text=True)
    return html.unescape(match.group(1))


@pytest.mark.parametrize('uid,base,per_page', [(1, '/admin', '&per_page=25'), (2, '/', '')])
def test_edit_links_save_and_cancel_keep_page_ten_and_repeated_filters(app, uid, base, per_page):
    c = client(app, uid)
    origin = base + '?page=10&status=PENDENTE&foco=Corrego&foco=Valeta' + per_page
    listing = c.get(origin)
    assert listing.status_code == 200
    links = re.findall(r'href="([^"]*solicitacao/editar/[^\"]*)"', listing.get_data(as_text=True))
    assert links
    for link in links:
        assert parse_qs(urlsplit(html.unescape(link)).query)['next'] == [origin]
    edit_url = html.unescape(links[0])
    form = c.get(edit_url)
    assert form.status_code == 200
    assert hidden_value(form, 'next') == origin
    assert f'href="{html.escape(origin, quote=True)}"' in form.get_data(as_text=True)
    result = c.post(urlsplit(edit_url).path, data=edit_form(next=hidden_value(form, 'next')))
    assert result.status_code == 302
    assert result.location == origin
    assert c.get(result.location).status_code == 200


def test_validation_error_preserves_return_context(app):
    c = client(app, 1)
    origin = '/admin?page=10&status=PENDENTE&per_page=25'
    data = edit_form(next=origin)
    data['foco'] = 'Foco inexistente'
    response = c.post('/solicitacao/editar/1', data=data)
    assert response.status_code == 200
    assert hidden_value(response, 'next') == origin


@pytest.mark.parametrize('target', [
    'https://external.test/admin?page=10', '//external.test/admin?page=10',
    '/solicitacao/editar/1', '/admin/deletar/1', '/\\external.test/admin',
])
def test_return_context_rejects_external_urls_and_non_list_actions(app, target):
    response = client(app, 1).post('/solicitacao/editar/1', data=edit_form(next=target),
                                  headers={'Referer': 'http://localhost/solicitacao/editar/1'})
    assert response.status_code == 302
    assert response.location == '/admin'


def test_direct_edit_uses_list_referrer_without_creating_edit_loop(app):
    c = client(app, 2)
    origin = 'http://localhost/?page=10&status=PENDENTE'
    form = c.get('/solicitacao/editar/1', headers={'Referer': origin})
    assert hidden_value(form, 'next') == origin
    response = c.post('/solicitacao/editar/1', data=edit_form(),
                      headers={'Referer': 'http://localhost/solicitacao/editar/1'})
    assert response.location == '/'


def test_edit_removing_last_filtered_page_returns_to_nearest_available_page(app):
    c = client(app, 1)
    origin = '/admin?page=11&per_page=25&status=PENDENTE&foco=Corrego&foco=Valeta'
    response = c.post('/solicitacao/editar/1', data=edit_form(next=origin, status='APROVADO'))
    assert response.location == origin
    fallback = c.get(response.location)
    assert fallback.status_code == 302
    params = parse_qs(urlsplit(fallback.location).query)
    assert params['page'] == ['10']
    assert params['per_page'] == ['25']
    assert params['status'] == ['PENDENTE']
    assert params['foco'] == ['Corrego', 'Valeta']
    assert c.get(fallback.location).status_code == 200


@pytest.mark.parametrize('origin,expected_page', [
    ('/?page=99&status=PENDENTE', '42'),
    ('/?page=10&protocolo=INEXISTENTE', '1'),
    ('/admin?page=10&protocolo=INEXISTENTE&per_page=25', '1'),
])
def test_empty_or_removed_pages_are_canonicalized_without_losing_filters(app, origin, expected_page):
    c = client(app, 1 if origin.startswith('/admin') else 2)
    response = c.get(origin)
    assert response.status_code == 302
    params = parse_qs(urlsplit(response.location).query)
    assert params['page'] == [expected_page]
    for key, value in parse_qs(urlsplit(origin).query).items():
        if key != 'page':
            assert params[key] == value
    assert c.get(response.location).status_code == 200


def prepare_os(app):
    with app.app_context():
        db.session.get(Solicitacao, 1).status = 'APROVADO'
        db.session.add(OrdemServico(solicitacao_id=1, equipe_id=1,
            descricao_produto='Bti', formulacao_produto='Granulo dispersivel', dosagem_g_10l='500',
            tipo_aplicacao='Pulverizacao de area (liq)', quantidade_produto_administrada_ml=100,
            pulverizacao_area_l_ha=10, ponta_pulverizacao='TXA8001',
            calculo_dosagem_planejado=json.dumps(PLAN)))
        db.session.commit()


def execution_form(situation, **extra):
    return dict(situacao_aplicacao=situation, da='Distrito de teste',
                nome_rf_ace_responsavel_os='Responsavel de teste', data_aplicacao=date.today().isoformat(),
                hora_inicio_aplicacao='09:00', hora_termino_aplicacao='09:15', **extra)


@pytest.mark.parametrize('situation', ['NENHUM VOO REALIZADO', 'APENAS MONITORADO'])
def test_save_and_complete_without_application_drops_stale_defaults_and_keeps_plan(app, situation):
    prepare_os(app)
    c = client(app, 3)
    fields = execution_form(situation, motivo_nao_realizacao='Chuva no local')
    if situation == 'APENAS MONITORADO':
        fields.update(larva_visualizada='NAO', criadouro_os_tipo_volume='Piscina', tratamento_adicional_realizado='NAO')
    # Even an older browser sending application defaults must not register an application.
    fields.update(descricao_produto='Bti', dosagem_g_10l='500', quantidade_produto_administrada_ml='100')
    saved = c.post('/piloto/os/1/formulario', data=fields)
    assert saved.status_code == 302
    result = c.post('/piloto/os/1/concluir')
    assert result.status_code == 302
    with app.app_context():
        request = db.session.get(Solicitacao, 1)
        assert request.status == 'CONCLUÍDO'
        order = request.ordem_servico
        for field in ('descricao_produto', 'formulacao_produto', 'dosagem_g_10l', 'tipo_aplicacao',
                      'quantidade_produto_administrada_ml', 'pulverizacao_area_l_ha', 'ponta_pulverizacao'):
            assert getattr(order, field) is None
        assert json.loads(order.calculo_dosagem_planejado) == PLAN
        if situation == 'NENHUM VOO REALIZADO':
            assert not order.larva_visualizada
            assert not order.tratamento_adicional_realizado


def test_concluding_an_older_monitoring_form_also_removes_application_defaults(app):
    prepare_os(app)
    with app.app_context():
        order = db.session.get(Solicitacao, 1).ordem_servico
        order.situacao_aplicacao = 'APENAS MONITORADO'
        order.distrito_administrativo = 'Distrito de teste'
        order.nome_rf_ace_responsavel_os = 'Responsavel de teste'
        order.data_aplicacao = date.today()
        order.hora_inicio_aplicacao = time(9)
        order.hora_termino_aplicacao = time(9, 15)
        order.larva_visualizada = 'NAO'
        order.criadouro_os_tipo_volume = 'Piscina'
        order.tratamento_adicional_realizado = 'NAO'
        db.session.commit()
    client(app, 3).post('/piloto/os/1/concluir')
    with app.app_context():
        request = db.session.get(Solicitacao, 1)
        assert request.status == 'CONCLUÍDO'
        assert request.ordem_servico.descricao_produto is None
        assert request.ordem_servico.quantidade_produto_administrada_ml is None
        assert json.loads(request.ordem_servico.calculo_dosagem_planejado) == PLAN


@pytest.mark.parametrize('situation,missing_label', [
    ('NENHUM VOO REALIZADO', 'Motivo da nao realizacao'),
    ('APENAS MONITORADO', 'Larva visualizada'),
    ('MONITORADO E LARVICIDA APLICADO', 'Dosagem (g/10L)'),
    ('APENAS LARVICIDA APLICADO (FALTA DE SEGURANÇA)', 'Dosagem (g/10L)'),
])
def test_conclusion_still_rejects_missing_fields_for_each_situation(app, situation, missing_label):
    prepare_os(app)
    c = client(app, 3)
    saved = c.post('/piloto/os/1/formulario', data=execution_form(situation))
    assert saved.status_code == 302
    result = c.post('/piloto/os/1/concluir')
    assert result.location.endswith('/piloto/os/1/formulario')
    with c.session_transaction() as session:
        assert any(missing_label in message for category, message in session['_flashes'])
    with app.app_context():
        assert db.session.get(Solicitacao, 1).status == 'APROVADO'


def test_normal_application_can_still_be_saved_and_completed(app):
    prepare_os(app)
    c = client(app, 3)
    fields = execution_form('MONITORADO E LARVICIDA APLICADO', larva_visualizada='SIM',
        criadouro_os_tipo_volume='Piscina', tratamento_adicional_realizado='NAO', descricao_produto='Bti',
        formulacao_produto='Granulo dispersivel', dosagem_g_10l='500', tipo_aplicacao='Pulverizacao de area (liq)',
        quantidade_produto_administrada_ml='100', pulverizacao_area_l_ha='10', ponta_pulverizacao='TXA8001')
    assert c.post('/piloto/os/1/formulario', data=fields).status_code == 302
    c.post('/piloto/os/1/concluir')
    with app.app_context():
        request = db.session.get(Solicitacao, 1)
        assert request.status == 'CONCLUÍDO'
        assert request.ordem_servico.quantidade_produto_administrada_ml == 100


@pytest.mark.parametrize('uid', [1, 2, 3])
def test_no_flight_form_renders_consistently_for_admin_uvis_and_pilot(app, uid):
    prepare_os(app)
    c = client(app, 3)
    c.post('/piloto/os/1/formulario', data=execution_form('NENHUM VOO REALIZADO', motivo_nao_realizacao='Chuva'))
    url = {1: '/admin/os/1/formulario', 2: '/uvis/os/1/formulario', 3: '/piloto/os/1/formulario'}[uid]
    response = client(app, uid).get(url)
    assert response.status_code == 200
    source = response.get_data(as_text=True)
    assert re.search(r'<fieldset id="os-campos-aplicacao"\s+disabled hidden', source)
    assert re.search(r'name="motivo_nao_realizacao"[^>]*required', source)
    assert not re.search(r'<select name="larva_visualizada"[^>]*required', source)
    assert 'piloto-os-situacao.js' in source
