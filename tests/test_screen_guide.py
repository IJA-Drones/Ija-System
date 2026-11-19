"""Real-screen guide availability does not grant business access. Disposable SQLite only."""
import pytest
import json
from pathlib import Path

from app.extensions import db
from app.models import Usuario, CentralTiPerfilConfiguracao
from app.modules.gestao_ti.catalog import CATALOG
from tests import test_central_ti as base


@pytest.fixture
def guide_app():
    setup = base.CentralTiTests()
    setup.setUp()
    setup.app.config['CENTRAL_TI_ENFORCE_PERMISSIONS'] = True
    from app.modules.chatbot import settings
    settings.policy()
    try:
        yield setup
    finally:
        setup.tearDown()


@pytest.mark.parametrize('role', [p['id'] for p in CATALOG['profiles']] + ['ortomosaico'])
def test_each_profile_can_open_help_on_its_authorized_training_screen(guide_app, role):
    if role not in guide_app.users:
        user = Usuario(login='guide_' + role, nome_uvis='Perfil de teste',
                       senha_hash='unused', tipo_usuario=role)
        db.session.add(user)
        db.session.commit()
        guide_app.users[role] = user
    guide_app.login(role)
    path = '/central-ti' if role == 'gestor_ti' else '/treinamentos'
    response = guide_app.client.get(path, follow_redirects=True)
    assert response.status_code == 200
    assert 'js/screen-guide.js' in response.text
    assert 'css/components/screen-guide.css' in response.text
    assert 'data-screen-guide-open' in response.text
    if role != 'gestor_ti':
        assert 'Guia prático nas telas' in response.text


def test_help_remains_available_when_business_permissions_are_removed(guide_app):
    db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='uvis', versao=2))
    db.session.commit()
    guide_app.login('uvis')
    page = guide_app.client.get('/treinamentos')
    assert page.status_code == 200
    assert 'data-screen-guide-open' in page.text
    assert 'video-quadra' not in page.text
    assert guide_app.client.get('/novo_cadastro').status_code == 403
    assert guide_app.client.get('/financeiro').status_code == 403
    assert guide_app.client.get('/agro/admin').status_code == 403


def test_template_inventory_has_no_uncovered_standalone_operational_page():
    from scripts.inventory_screen_guides import inventory
    current = inventory()
    saved = json.loads((Path(__file__).resolve().parents[1] /
                        'docs/treinamentos/inventario-guia-pratico.json').read_text())
    assert current == saved
    assert {'base.html', 'app_movel.html', 'cadastro.html', 'financeiro_central.html'} <= {
        page['template'] for page in current['pages']}
