"""Cadastro administrativo e login real do novo perfil, em banco descartável."""

from app.extensions import db
from app.models import Prefeitura, Usuario
from app.modules.auth.service import get_authenticated_redirect_endpoint
from app.modules.usuarios.service import validate_new_admin_user
from tests import test_central_ti as base


def test_create_agent_account_require_municipality_and_login_to_own_page():
    setup = base.CentralTiTests()
    setup.setUp()
    try:
        setup.app.config['VIGILANCIA_IMPORT_ENABLED'] = True
        prefeitura = Prefeitura(nome='Prefeitura fictícia', slug='agente-teste', ativa=True)
        db.session.add(prefeitura)
        db.session.commit()
        setup.login('dev')
        page = setup.client.get('/admin/usuarios/novo')
        assert 'value="agente_endemias"' in page.text
        assert 'prefeitura_id' in validate_new_admin_user('Agente teste', 'agente-teste', 'agente_endemias', '', None, 'AgenteTeste#2026', 'AgenteTeste#2026')
        response = setup.client.post('/admin/usuarios/novo', data=dict(nome='Agente teste', login='agente-teste',
            tipo_usuario='agente_endemias', prefeitura_id=prefeitura.id, senha='AgenteTeste#2026', senha2='AgenteTeste#2026'))
        assert response.status_code == 302
        user = Usuario.query.filter_by(login='agente-teste').one()
        assert user.tipo_usuario == 'agente_endemias' and user.prefeitura_id == prefeitura.id
        assert user.check_senha('AgenteTeste#2026')
        assert get_authenticated_redirect_endpoint(user) == 'main.vigilancia_agente'
        with setup.client.session_transaction() as session:
            session.clear()
        response = setup.client.post('/login', data={'login':'agente-teste', 'senha':'AgenteTeste#2026'})
        assert response.status_code == 302 and response.location.endswith('/vigilancia/agente')
        page = setup.client.get('/vigilancia/agente')
        assert page.status_code == 200 and 'Meus levantamentos' in page.text
        assert setup.client.get('/vigilancia/planejamento').status_code == 403
        assert setup.client.get('/admin/usuarios/novo').status_code == 403
    finally:
        setup.tearDown()


def test_covisa_default_navigation_and_planning_use_own_municipality():
    setup = base.CentralTiTests()
    setup.setUp()
    try:
        setup.app.config['VIGILANCIA_IMPORT_ENABLED'] = True
        prefeitura = Prefeitura(nome='Município de teste', slug='covisa-navegacao', ativa=True)
        db.session.add(prefeitura)
        db.session.flush()
        user = Usuario(nome_uvis='Coordenação municipal', login='coord-teste', senha_hash='unused',
                       tipo_usuario='visualizar', regiao='COVISA', prefeitura_id=prefeitura.id)
        db.session.add(user)
        db.session.commit()
        setup.users['covisa'] = user
        setup.login('covisa')
        page = setup.client.get('/vigilancia')
        assert page.status_code == 200 and '<span>Vigilância</span>' in page.text
        assert 'Acessar Focal e LIRAa' in page.text
        page = setup.client.get('/vigilancia/planejamento')
        assert page.status_code == 200 and 'Criar rascunho' in page.text
        assert 'Código da prefeitura cadastrada' in page.text and 'readonly' in page.text
        from app.shared.csrf_security import CSRF_SESSION_KEY
        with setup.client.session_transaction() as session:
            csrf = session[CSRF_SESSION_KEY]
        response = setup.client.post('/vigilancia/planejamento', data=dict(acao='territorio', demo='true',
            _csrf_token=csrf, quarteirao='Q-COVISA', bairro='Bairro fictício', area='A-01', imoveis='100', referencia='RG de teste'))
        assert response.status_code == 303
        assert setup.client.get('/vigilancia/planejamento?prefeitura_id=9999').status_code == 403
    finally:
        setup.tearDown()
