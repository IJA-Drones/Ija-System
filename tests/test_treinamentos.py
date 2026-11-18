"""Autenticação, isolamento e distribuição dos materiais em SQLite descartável."""

import pytest

from app.extensions import db
from app.models import Usuario, Prefeitura, CentralTiPerfilConfiguracao, CentralTiSelecao
from app.modules.gestao_ti.permissions import validate_route_policy
from app.modules.treinamentos.catalog import MATERIALS, REQUEST_VIDEOS, RESOURCE_DIR
from app.modules.treinamentos.access import POLICIES
from app.modules.vigilancia.sinan_import import parse_cases
from tests import test_central_ti as base


@pytest.fixture
def training():
    setup = base.CentralTiTests()
    setup.setUp()
    setup.app.config.update(CENTRAL_TI_ENFORCE_PERMISSIONS=True,
                            VIGILANCIA_IMPORT_ENABLED=True, SINAN_ENABLED=True,
                            ACOES_PUBLICAS_ENABLED=True)
    prefeitura = Prefeitura(id=14, nome="Pesqueira", slug="pesqueira-treinamento")
    db.session.add(prefeitura)
    for user in setup.users.values():
        user.prefeitura_id = 14
    setup.users["dev"].trabalha_agro = True
    for key, role, regiao in (("covisa", "visualizar", "COVISA"), ("agent", "agente_endemias", "")):
        user = Usuario(login=f"training_{key}", nome_uvis=f"Conta fictícia {key}", senha_hash="unused",
                       tipo_usuario=role, regiao=regiao, prefeitura_id=14)
        db.session.add(user)
        setup.users[key] = user
    db.session.commit()
    # O widget global inicializa sua configuração antes da verificação de leitura.
    from app.modules.chatbot import settings as chatbot_settings
    chatbot_settings.policy()
    try:
        yield setup
    finally:
        setup.tearDown()


def test_training_and_files_require_login(training):
    for path in ("/treinamentos", "/agro/treinamentos", "/financeiro/treinamentos",
                 "/treinamentos/arquivos/guia-geral", "/treinamentos/arquivos/csv-territorio"):
        response = training.client.get(path)
        assert response.status_code == 302
        assert "/login" in response.location
        assert response.headers["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("role", ["dev", "covisa", "agent"])
def test_learning_center_available_without_granting_other_modules(training, role):
    training.login(role)
    # Sem funções de negócio, permanecem apenas os materiais de acesso comum.
    code = "agente_endemias" if role == "agent" else role
    db.session.add(CentralTiPerfilConfiguracao(perfil_codigo=code, versao=2))
    db.session.commit()
    response = training.client.get("/treinamentos")
    assert response.status_code == 200
    assert '<span>Treinamentos</span>' in response.text
    assert "Proteção de login" in response.text
    assert "Cadastro territorial" not in response.text
    assert 'href="/vigilancia/planejamento' not in response.text
    assert 'href="/acoes-realizadas' not in response.text
    assert training.client.get("/treinamentos/arquivos/csv-visitas").status_code == 403
    if role == "agent":
        assert training.client.get("/vigilancia/planejamento").status_code == 403
        assert training.client.get("/admin/usuarios/novo").status_code == 403


def test_agent_does_not_receive_coordination_and_import_guides(training):
    training.login("agent")
    response = training.client.get("/treinamentos")
    assert 'href="/vigilancia/agente?demo=true"' not in response.text
    assert 'href="/vigilancia/planejamento' not in response.text
    assert 'href="/vigilancia/sinan' not in response.text
    assert training.client.get("/treinamentos/arquivos/manual-liraa").status_code == 403


def test_resources_are_fixed_private_and_correctly_served(training):
    training.login()
    for material_id, (relative, mimetype) in MATERIALS.items():
        response = training.client.get(f"/treinamentos/arquivos/{material_id}")
        assert response.status_code == 200, material_id
        assert response.mimetype == mimetype
        assert response.data == (RESOURCE_DIR / relative).read_bytes()
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        expected = "inline" if mimetype in {"application/pdf", "video/mp4"} else "attachment"
        assert response.headers["Content-Disposition"].startswith(expected)
        response.close()
    response = training.client.get("/treinamentos/arquivos/guia-geral?baixar=1")
    assert response.headers["Content-Disposition"].startswith("attachment")
    for path in ("inexistente", "kit-testes", "kit-testes-sp", "..%2F..%2F.env", "guia-geral/../../.env"):
        assert training.client.get("/treinamentos/arquivos/" + path).status_code == 404


def configure(training, role, codes):
    profile = "covisa" if role == "covisa" else training.users[role].tipo_usuario
    db.session.add(CentralTiPerfilConfiguracao(perfil_codigo=profile, versao=2))
    for code in codes:
        db.session.add(CentralTiSelecao(perfil_codigo=profile, codigo=code))
    db.session.commit()


def test_every_material_has_an_explicit_valid_access_policy():
    from app.modules.gestao_ti.catalog import PERMISSION_CODES, AREA_CODES
    assert set(POLICIES) == set(MATERIALS) | {video["id"] for video in REQUEST_VIDEOS}
    for policy in POLICIES.values():
        assert policy.area in {"prefeitura", "agro", "financeiro", "common"}
        assert all(code in PERMISSION_CODES or code.removeprefix("area:") in AREA_CODES
                   for code in policy.permissions)


@pytest.mark.parametrize("enforce", [True, False])
def test_uvis_sees_own_guides_and_cannot_download_pilot_agro_or_finance(training, enforce):
    training.app.config["CENTRAL_TI_ENFORCE_PERMISSIONS"] = enforce
    training.login("uvis")
    page = training.client.get("/treinamentos")
    assert page.status_code == 200
    for key in ("guia-equipes-acesso-uvis", "guia-agenda-notificacoes", "guia-mapas-operacionais"):
        assert f'/treinamentos/arquivos/{key}' in page.text
        response = training.client.get(f'/treinamentos/arquivos/{key}')
        assert response.status_code == 200
        response.close()
    for key in ("guia-checklists-semanais", "guia-frota-turnos", "guia-central-financeiro", "guia-banco-talentos-agro", "guia-agro-comercial-operacao", "guia-geral"):
        assert f'/treinamentos/arquivos/{key}' not in page.text
        for method in ("get", "head"):
            response = getattr(training.client, method)(f'/treinamentos/arquivos/{key}', headers={"Range": "bytes=0-99"})
            assert response.status_code == 403, key
            assert response.headers["Cache-Control"] == "private, no-store"
    assert training.client.get('/agro/treinamentos').status_code == 403
    assert training.client.get('/financeiro/treinamentos').status_code == 403


def test_pilot_can_read_operational_guides(training):
    training.login("piloto")
    page = training.client.get('/treinamentos')
    for key in ("guia-checklists-semanais", "guia-frota-turnos"):
        assert f'/treinamentos/arquivos/{key}' in page.text
        response = training.client.get(f'/treinamentos/arquivos/{key}')
        assert response.status_code == 200
        response.close()
    assert '/treinamentos/arquivos/guia-equipes-acesso-uvis' not in page.text


def test_uvis_drive_video_follows_creation_permission_without_local_downloads(training):
    training.login('uvis')
    page=training.client.get('/treinamentos').text
    assert 'Solicitações</h2>' in page
    assert '<details class="training-drive-videos">' in page
    assert 'Ver vídeos no Drive' in page
    assert '1TZNoxL-kYwHFet3P_JHw06ioDK-lgvsb/preview' not in page
    assert 'https://drive.google.com/file/d/1TZNoxL-kYwHFet3P_JHw06ioDK-lgvsb/view?usp=drive_link' in page
    for removed in ('Demonstração · Pesqueira', 'Demonstração · UVIS Sé', 'Kit Pesqueira', 'Kit UVIS Sé'):
        assert removed not in page
    for retired in ('video-quadra', 'legendas-quadra'):
        assert training.client.get('/treinamentos/arquivos/'+retired,headers={'Range':'bytes=0-1023'}).status_code==404
    configure(training,'uvis',['area:prefeitura','prefeitura.solicitacoes.consultar'])
    assert 'video-quadra' not in training.client.get('/treinamentos').text
    assert '1TZNoxL-kYwHFet3P_JHw06ioDK-lgvsb' not in training.client.get('/treinamentos').text
    assert training.client.get('/treinamentos/arquivos/video-quadra').status_code==404
    assert training.client.get('/treinamentos/arquivos/legendas-quadra').status_code==404


def test_finance_and_agro_are_separate_tabs_and_contexts(training):
    training.login("financeiro")
    response = training.client.get('/treinamentos')
    assert response.status_code == 302 and response.location.endswith('/financeiro/treinamentos')
    page = training.client.get(response.location)
    assert page.status_code == 200
    assert '/treinamentos/arquivos/guia-central-financeiro' in page.text
    assert '/treinamentos/arquivos/guia-banco-talentos-agro' not in page.text
    assert 'href="/agro/treinamentos"' not in page.text
    assert 'href="/treinamentos"' not in page.text
    training.login("admin")
    page = training.client.get('/agro/treinamentos')
    assert page.status_code == 200
    assert '/treinamentos/arquivos/guia-agro-comercial-operacao' in page.text
    assert '/treinamentos/arquivos/guia-central-financeiro' not in page.text
    assert '/treinamentos/arquivos/guia-checklists-semanais' not in page.text
    assert training.client.get('/financeiro/treinamentos').status_code == 403


def test_central_ti_grants_and_revokes_guides_without_borrowing_operations(training):
    training.login("uvis")
    assert training.client.get('/treinamentos/arquivos/guia-agenda-notificacoes').status_code == 200
    configure(training, "uvis", ["area:prefeitura", "prefeitura.veiculos.consultar"])
    page = training.client.get('/treinamentos')
    assert '/treinamentos/arquivos/guia-rastreamento-veiculos' in page.text
    assert '/treinamentos/arquivos/guia-frota-turnos' not in page.text
    assert '/treinamentos/arquivos/guia-agenda-notificacoes' not in page.text
    assert training.client.get('/treinamentos/arquivos/guia-agenda-notificacoes').status_code == 403
    assert training.client.get('/treinamentos/arquivos/guia-frota-turnos').status_code == 403


def test_orthomosaic_fixed_access_is_preserved(training):
    user = Usuario(login='training_mapping', nome_uvis='Mapeamento fictício', senha_hash='unused',
                   tipo_usuario='ortomosaico', prefeitura_id=14)
    db.session.add(user)
    db.session.commit()
    training.users['mapping'] = user
    training.login('mapping')
    page = training.client.get('/treinamentos')
    assert page.status_code == 200
    assert '/treinamentos/arquivos/guia-ortomosaicos' in page.text
    response = training.client.get('/treinamentos/arquivos/guia-ortomosaicos')
    assert response.status_code == 200
    response.close()
    assert training.client.get('/treinamentos/arquivos/guia-checklists-semanais').status_code == 403
    assert training.client.get('/admin/usuarios/novo').status_code == 403


def test_page_and_downloads_do_not_write_database(training):
    training.login()
    from sqlalchemy import event
    def reject_write(conn, cursor, statement, *args):
        assert statement.lstrip().split()[0].upper() not in {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    event.listen(db.engine, "before_cursor_execute", reject_write)
    try:
        assert training.client.get("/treinamentos").status_code == 200
        assert training.client.get("/treinamentos/arquivos/manual-liraa").status_code == 200
    finally:
        event.remove(db.engine, "before_cursor_execute", reject_write)
    validate_route_policy(training.app)


def test_linked_sinan_example_is_valid():
    content = (RESOURCE_DIR / MATERIALS["csv-sinan"][0]).read_bytes()
    assert len(parse_cases(content, dict(disease="dengue", ibge="2610905", year=2026), True)) == 6

