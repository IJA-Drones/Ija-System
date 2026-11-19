"""Dedicated mapping accounts cannot cross module or municipality boundaries."""
import io

import pytest

from test_ortomosaicos import app, client, tiff, upload
from app.extensions import db
from app.models import Prefeitura, Usuario, Ortomosaico, CentralTiPerfilConfiguracao, CentralTiSelecao
from app.modules.auth.service import get_authenticated_redirect_endpoint
from app.modules.ortomosaicos import uploads, service
from app.modules.usuarios.service import validate_new_admin_user, validate_edit_admin_user

HEADERS = {'X-CSRFToken': 'token'}


@pytest.fixture
def mapping(app):
    with app.app_context():
        db.session.add(Prefeitura(id=2, nome='Outra prefeitura', slug='outra', ativa=True))
        db.session.add(Usuario(id=10, nome_uvis='Mapeamento', login='mapa', senha_hash='test',
                               tipo_usuario='ortomosaico', prefeitura_id=1))
        db.session.commit()
    return client(app, 10)


def test_upload_view_and_private_download(mapping, app):
    response = upload(mapping)
    assert response.status_code == 202
    oid = response.json['item']['id']
    with app.app_context():
        assert service.process_one(oid)
        assert db.session.get(Ortomosaico, oid).usuario_id == 10
        assert get_authenticated_redirect_endpoint(db.session.get(Usuario, 10)) == 'main.ortomosaicos'
    assert mapping.get(f'/ortomosaicos/{oid}/arquivo.tif', headers={'Range': 'bytes=0-15'}).status_code == 206
    html = mapping.get('/ortomosaicos').get_data(as_text=True)
    assert 'Outra prefeitura' not in html
    assert 'data-request-url=""' in html
    assert 'id="ortho-request-toggle" hidden disabled' in html
    assert 'value="1"' in html
    assert mapping.get('/novo_cadastro').status_code == 403


@pytest.mark.parametrize('tipo', ['rgb', 'dem'])
def test_resumable_upload_and_owner_scope(mapping, app, tipo):
    from tests.test_dem_contours import dem
    app.config['SKYBOX_BASE_DIR'] = 'dados ordens de serviço'
    body = dem() if tipo == "dem" else tiff()
    payload = dict(nome='Levantamento', prefeitura_id=1, filename='base.tif', size=len(body),
                   tipo=tipo, elevacoes_metros="1", intervalo_m=5, resolucao_m=1)
    response = mapping.post('/api/ortomosaicos/uploads', json=payload, headers=HEADERS)
    assert response.status_code == 201, response.data
    state = response.json
    assert mapping.put(state['url'], data=body, headers={**HEADERS, 'Upload-Offset': '0'},
                       content_type='application/octet-stream').status_code == 200
    assert mapping.post(state['url'], headers=HEADERS).status_code == 202
    with app.app_context():
        uploads.finalize(state['id'])
        row = Ortomosaico.query.one()
        assert row.prefeitura_id == 1 and row.usuario_id == 10 and row.tipo == tipo
        oid = row.id
        assert service.process_one(oid)
        row = db.session.get(Ortomosaico, oid)
        assert row.original_path.startswith('skybox://ortomosaico/')
        parent = row.original_path.rsplit('/', 1)[0]
        outputs = [row.curvas_path, row.jpeg_path] if tipo == 'dem' else [row.cog_path]
        assert all(path.startswith(parent + '/') for path in outputs)
        assert '/teste-1/' in parent
        oid = row.id
    suffix = 'curvas.geojson' if tipo == 'dem' else 'arquivo.tif'
    assert mapping.get(f'/ortomosaicos/{oid}/{suffix}').status_code == 200
    # Changing the user's municipality invalidates even their own existing transfer.
    with app.app_context():
        db.session.get(Usuario, 10).prefeitura_id = 2
        db.session.commit()
    for method in ('get', 'put', 'post'):
        assert getattr(mapping, method)(state['url'], headers=HEADERS).status_code == 404


def test_cross_city_access_rejected_for_every_resource(mapping, app):
    oid = upload(client(app)).json['item']['id']
    with app.app_context():
        db.session.get(Ortomosaico, oid).prefeitura_id = 2
        db.session.commit()
    for suffix in ('arquivo.tif', 'original.tif', 'curvas.geojson', 'curvas.jpg',
                   'exportar/curvas.geojson', 'exportar/medicoes.zip'):
        assert mapping.get(f'/ortomosaicos/{oid}/{suffix}').status_code == 404, suffix
    for method, suffix in [('get', ''), ('post', '/reprocessar'), ('get', '/agua'),
                           ('post', '/agua'), ('post', '/agua/calcular'),
                           ('put', '/agua/1'), ('delete', '/agua/1')]:
        assert getattr(mapping, method)(f'/api/ortomosaicos/{oid}{suffix}', headers=HEADERS).status_code == 404
    assert mapping.get('/api/ortomosaicos').json == {'items': []}
    assert mapping.get('/api/ortomosaicos?prefeitura_id=2').status_code == 403
    assert mapping.post('/api/ortomosaicos', data={'prefeitura_id': 2,
                        'arquivo': (io.BytesIO(tiff()), 'base.tif')}, headers=HEADERS).status_code == 400
    assert mapping.post('/api/ortomosaicos/uploads', json=dict(nome='Outro', prefeitura_id=2,
                        filename='base.tif', size=100), headers=HEADERS).status_code == 400


@pytest.mark.parametrize('state', ['missing', 'inactive'])
def test_missing_or_inactive_municipality_denied(mapping, app, state):
    with app.app_context():
        if state == 'missing':
            db.session.get(Usuario, 10).prefeitura_id = None
        else:
            db.session.get(Prefeitura, 1).ativa = False
        db.session.commit()
    assert mapping.get('/ortomosaicos').status_code == 403
    assert mapping.get('/api/ortomosaicos').status_code == 403
    assert upload(mapping).status_code == 403


def test_municipality_required_on_create_and_edit(mapping, app):
    with app.app_context():
        for pid in (None, 999, 1):
            new = validate_new_admin_user('Mapa', 'novo_mapa', 'ortomosaico', '', pid, 'SenhaForte123!', 'SenhaForte123!')
            edit = validate_edit_admin_user('Mapa', 'mapa', 'ortomosaico', '', pid, '', '', 10)
            assert ('prefeitura_id' in new) == (pid != 1)
            assert ('prefeitura_id' in edit) == (pid != 1)
            assert 'tipo_usuario' not in new and 'tipo_usuario' not in edit


@pytest.mark.parametrize('enforce', [False, True])
def test_full_application_is_exclusive_even_with_ti_grants(enforce):
    from test_central_ti import CentralTiTests
    case = CentralTiTests()
    case.setUp()
    try:
        case.app.config['CENTRAL_TI_ENFORCE_PERMISSIONS'] = enforce
        user = Usuario(nome_uvis='Mapa', login='mapa', tipo_usuario='ortomosaico', senha_hash='test', prefeitura_id=1)
        db.session.add(Prefeitura(id=1, nome='Minha cidade', slug='minha', ativa=True))
        db.session.add(user)
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='ortomosaico', versao=2))
        db.session.add(CentralTiSelecao(perfil_codigo='ortomosaico', codigo='prefeitura.solicitacoes.consultar'))
        db.session.commit()
        case.users['ortomosaico'] = user
        case.login('ortomosaico')
        from app.modules.ortomosaicos.access import dedicated_endpoint_allowed
        from app.modules.gestao_ti.permissions import can_access_endpoint, validate_route_policy
        validate_route_policy(case.app)
        # Both root URLs must serve the shared worker for the dedicated account.
        for path in ('/service-worker.js', '/sw.js'):
            worker = case.client.get(path)
            assert worker.status_code == 200, (path, worker.status_code)
            assert worker.mimetype == 'application/javascript'
            assert worker.headers['Service-Worker-Allowed'] == '/'
            assert worker.cache_control.no_cache or worker.cache_control.no_store
            assert 'addEventListener' in worker.text
        # Check all registered business routes, with concrete values for converters.
        for rule in case.app.url_map.iter_rules():
            if dedicated_endpoint_allowed(rule.endpoint) or not rule.endpoint.startswith('main.'):
                continue
            values = {name: 1 if converter.__class__.__name__ == 'IntegerConverter' else 'test'
                      for name, converter in rule._converters.items()}
            for name, converter in rule._converters.items():
                if hasattr(converter, 'items'):
                    values[name] = next(iter(converter.items))
            from flask import url_for
            with case.app.test_request_context():
                path = url_for(rule.endpoint, **values)
                assert not can_access_endpoint(user, rule.endpoint)
            for method in rule.methods - {'HEAD', 'OPTIONS'}:
                assert case.client.open(path, method=method).status_code == 403, (rule.endpoint, method)
        assert case.client.get('/login').location.endswith('/ortomosaicos')
        response = case.client.get('/ortomosaicos')
        assert response.status_code == 200, response.data[:500]
        html = response.get_data(as_text=True)
        sidebar = html.split('id="appSidebar"', 1)[1].split('id="appContent"', 1)[0]
        assert 'Ortomosaicos e curvas' in sidebar
        assert 'Treinamentos' in sidebar
        for label in ('Dashboard', 'Configurações', 'Agenda', 'Azul'):
            assert label not in sidebar
        training_page = case.client.get('/treinamentos')
        assert training_page.status_code == 200
        assert '/treinamentos/arquivos/guia-ortomosaicos' in training_page.text
        assert case.client.get('/treinamentos/arquivos/guia-frota-turnos').status_code == 403
    finally:
        case.tearDown()


def test_admin_can_create_list_and_edit_mapping_account():
    from test_central_ti import CentralTiTests
    case = CentralTiTests()
    case.setUp()
    try:
        db.session.add(Prefeitura(id=1, nome='Minha cidade', slug='minha', ativa=True))
        db.session.commit()
        case.login()
        payload = dict(nome='Mapeamento municipal', login='mapa_novo', tipo_usuario='ortomosaico',
                       prefeitura_id=1, senha='Mapeamento!2026-Teste', senha2='Mapeamento!2026-Teste')
        assert 'value="ortomosaico"' in case.client.get('/admin/usuarios/novo').text
        assert case.client.post('/admin/usuarios/novo', data=payload).status_code == 302
        user = Usuario.query.filter_by(login='mapa_novo').one()
        assert user.tipo_usuario == 'ortomosaico' and user.prefeitura_id == 1
        assert 'mapa_novo' in case.client.get('/admin/usuarios?tipo=ortomosaico').text
        response = case.client.post(f'/admin/usuarios/{user.id}/editar', data=dict(
            nome_uvis='Mapeamento atualizado', login=user.login, tipo_usuario='ortomosaico', prefeitura_id=1))
        assert response.status_code == 302
        db.session.refresh(user)
        assert user.nome_uvis == 'Mapeamento atualizado' and user.prefeitura_id == 1
    finally:
        case.tearDown()


def test_library_filters_municipality_before_result_limit(mapping, app):
    from datetime import datetime, timedelta
    with app.app_context():
        now = datetime.now()
        for i in range(102):
            db.session.add(Ortomosaico(
                prefeitura_id=1 if i == 0 else 2, usuario_id=1, nome=f'Levantamento {i}',
                arquivo_nome='base.tif', original_path='private/base.tif', sha256='a'*64,
                tamanho_bytes=10, criado_em=now + timedelta(seconds=i)))
        db.session.commit()
    items = mapping.get('/api/ortomosaicos').json['items']
    assert [item['nome'] for item in items] == ['Levantamento 0']
