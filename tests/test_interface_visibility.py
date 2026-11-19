"""A retirada visual é global e não remove a estrutura dos módulos arquivados."""

import re
from unittest.mock import patch

import pytest
from flask import render_template

from app.extensions import db
from app.models import Prefeitura, Usuario
from app.modules.auth.service import get_authenticated_redirect_endpoint
from app.modules.chatbot.azul import help_context
from app.modules.gestao_ti.catalog import CATALOG
from app.modules.gestao_ti.navigation import _screens_for
from app.modules.treinamentos.access import can_read_material
from app.shared.interface_visibility import VIGILANCIA_MODULES, VIGILANCIA_SCREENS
from tests import test_central_ti as base


@pytest.fixture
def interface():
    setup = base.CentralTiTests()
    setup.setUp()
    setup.app.config.update(
        VIGILANCIA_UI_ENABLED=False, VIGILANCIA_IMPORT_ENABLED=True,
        VIGILANCIA_PREVIEW_ENABLED=True, SINAN_ENABLED=True, ACOES_PUBLICAS_ENABLED=True,
    )
    db.session.add(Prefeitura(id=1, nome="Município de exemplo", slug="exemplo"))
    for profile in CATALOG["profiles"]:
        role = profile["id"]
        if role not in setup.users:
            user = Usuario(login=f"interface_{role}", nome_uvis=role,
                           senha_hash="unused", tipo_usuario=role, prefeitura_id=1)
            setup.users[role] = user
            db.session.add(user)
    agent = Usuario(login="interface_agent", nome_uvis="Agente de exemplo",
                    senha_hash="unused", tipo_usuario="agente_endemias", prefeitura_id=1)
    setup.users["agent"] = agent
    db.session.add(agent)
    db.session.commit()
    try:
        yield setup
    finally:
        setup.tearDown()


def assert_no_module_links(html):
    for path in ("/vigilancia", "/acoes-realizadas", "/relatos-saude", "/alertas",
                 "/integracoes/esus", "/portal-cidadao/acoes", "/portal-cidadao/relato-saude"):
        assert not re.search(r'href=["\']' + re.escape(path) + r'(?:[/?#"\'])', html), path


@pytest.mark.parametrize("role", [profile["id"] for profile in CATALOG["profiles"]] + ["agent"])
def test_every_profile_sidebar_and_navigation_hide_modules(interface, role):
    interface.login(role)
    with interface.app.test_request_context("/treinamentos"):
        from flask_login import login_user
        login_user(interface.users[role])
        html = render_template("erro.html", codigo=404, titulo="Exemplo", mensagem="Exemplo")
        assert_no_module_links(html)
        assert "js/agente-rastro.js" not in html
        for module in VIGILANCIA_MODULES:
            assert not _screens_for(interface.users[role], module)
        context = help_context(interface.users[role], "/treinamentos")
        assert not any(link["modulo"] in VIGILANCIA_MODULES for link in context["atalhos"])


@pytest.mark.parametrize("role", [None, "dev", "prefeitura_admin", "uvis", "agent"])
def test_old_screen_urls_cannot_reopen_hidden_modules(interface, role):
    if role:
        interface.login(role)
    for endpoint in VIGILANCIA_SCREENS:
        rule = next(iter(interface.app.url_map.iter_rules(endpoint)))
        values = {key: "1" for key in rule.arguments}
        path = rule.build(values)[1]
        assert interface.client.get(path).status_code == 404, (role, path)
    # Form submissions to the old screens cannot create records invisibly.
    for path in ("/vigilancia/campo", "/acoes-realizadas/nova", "/portal-cidadao/relato-saude"):
        assert interface.client.post(path).status_code == 404


def test_citizen_portal_keeps_public_apis_azul_alerts_and_app_without_internal_risk(interface):
    with patch("app.modules.portal_cidadao.routes.get_public_risk_report") as risk, \
         patch("app.modules.portal_cidadao.routes.get_infodengue_alert", return_value=None) as alert, \
         patch("app.modules.portal_cidadao.routes.get_portal_health_news", return_value=[]) as news:
        response = interface.client.get("/portal-cidadao")
    assert response.status_code == 200
    assert_no_module_links(response.text)
    assert 'id="portalCidadaoForm"' in response.text
    assert 'href="/portal-cidadao/contatos"' in response.text
    for removed in ("mapa-risco", "portal-mapa-vigilancia.js", "Suspeita de adoecimento"):
        assert removed not in response.text
    for restored in ('id="boletim-saude"', 'id="portal-push-button"', "portal-push.js",
                     "portal-chatbot.js", "portal-offline.js", "portal-chat-report.js",
                     'href="/app"', "https://t.me/", 'href="/portal-cidadao/boletim-dengue'):
        assert restored in response.text
    risk.assert_not_called()
    alert.assert_called_once()
    news.assert_called_once()
    app = interface.client.get("/m/?preview=1")
    assert app.status_code == 200 and 'data-vigilancia-enabled="false"' in app.text
    assert "app-movel.js" in app.text and "portal-chatbot.js" in app.text
    download = interface.client.get("/app")
    assert download.status_code == 200 and "Baixar APK" in download.text
    assert "Sou agente de endemias" not in download.text
    # O nome novo também passa pelo Flask quando WhiteNoise serve /sw.js na raiz.
    from whitenoise import WhiteNoise
    interface.app.wsgi_app = WhiteNoise(interface.app.wsgi_app, root=interface.app.static_folder)
    worker = interface.client.get("/service-worker.js")
    assert worker.status_code == 200 and "caches.delete" in worker.text
    assert "cache.addAll" in worker.text and 'addEventListener("push"' in worker.text


def test_dev_permissions_and_training_hide_modules_but_keep_saved_permissions(interface):
    interface.login("dev")
    original = interface.editor_data()
    for area in original["catalog"]:
        assert all(f"{area['id']}.{module[0]}" not in VIGILANCIA_MODULES for module in area["modules"])
    state = next(row for row in original["states"] if row["id"] == "prefeitura_admin")
    saved_permissions = set(state["permissions"])
    assert any(code.startswith("prefeitura.vigilancia.") for code in saved_permissions)
    visible_module = next(code.rsplit(".", 1)[0] for code in sorted(saved_permissions)
                          if code.rsplit(".", 1)[0] not in VIGILANCIA_MODULES)
    edited_permissions = {code for code in saved_permissions if not code.startswith(visible_module + ".")}
    result = interface.save([dict(id=state["id"], version=state["version"],
                                 areas=state["areas"], permissions=sorted(edited_permissions))])
    assert result.status_code == 200
    current = next(row for row in interface.editor_data()["states"] if row["id"] == state["id"])
    assert set(current["permissions"]) == edited_permissions
    page = interface.client.get("/treinamentos")
    assert page.status_code == 200
    assert_no_module_links(page.text)
    for label in ("LIRAa", "SINAN", "Mapa de risco", "Ações realizadas", "Suspeita de adoecimento"):
        assert label not in page.text
    for material in ("manual-liraa", "manual-sinan", "manual-mapa", "manual-publicacoes", "csv-visitas"):
        assert not can_read_material(interface.users["dev"], material)
    assert get_authenticated_redirect_endpoint(interface.users["agent"]) == "main.treinamentos"
    tutorial = interface.client.get("/azul/tutorial?publico=publico")
    assert tutorial.status_code == 200
    assert '"id": "boletim"' in tutorial.text and '"id": "foco"' in tutorial.text
    assert '"id": "saude"' not in tutorial.text


@pytest.mark.parametrize("role", [None, "dev"])
def test_public_bulletin_remains_available_in_both_layouts(interface, role):
    if role:
        interface.login(role)
    with patch("app.modules.portal_cidadao.routes.get_infodengue_report", return_value=None) as report:
        response = interface.client.get("/portal-cidadao/boletim-dengue?municipio=2610905&doenca=zika&ano=2025")
    assert response.status_code == 200 and "Boletim de arboviroses" in response.text
    assert "Pesqueira" not in response.text and "InfoDengue" in response.text
    assert report.call_args.kwargs["disease"] == "zika"
    assert report.call_args.kwargs["year"] == 2025
    assert_no_module_links(response.text)


def test_public_azul_does_not_recommend_removed_forms(interface):
    from app.modules.portal_cidadao.chatbot import public_instructions
    with interface.app.test_request_context("/portal-cidadao"):
        prompt = public_instructions()
    assert "/portal-cidadao/relato-saude" not in prompt
    assert "formulário de suspeita de adoecimento está indisponível" in prompt


def test_backend_routes_and_tables_are_preserved(interface):
    from app.modules.acoes_publicas.models import AcaoPublica
    from app.modules.vigilancia.field_models import CampoInspecao
    for endpoint in ("main.vigilancia_sinan_api", "main.vigilancia_sinan_cases_import",
                     "main.vigilancia_campo_export", "main.mobile_agente_painel"):
        assert endpoint in interface.app.view_functions
    assert AcaoPublica.__table__.name in db.metadata.tables
    assert CampoInspecao.__table__.name in db.metadata.tables


def test_original_interface_remains_available_when_explicitly_restored(interface):
    interface.app.config["VIGILANCIA_UI_ENABLED"] = True
    interface.login("dev")
    response = interface.client.get("/vigilancia")
    assert response.status_code == 200 and "SINAN" in response.text


def test_retired_poc_materials_cannot_be_downloaded_even_by_dev(interface):
    from app.modules.treinamentos.catalog import ARCHIVED_MATERIALS, MATERIALS, RESOURCE_DIR
    interface.app.config["VIGILANCIA_UI_ENABLED"] = True
    interface.login("dev")
    for material_id in ARCHIVED_MATERIALS:
        assert interface.client.get(f"/treinamentos/arquivos/{material_id}").status_code == 404
    assert "guia-assistente-cidadao" in MATERIALS
    assert (RESOURCE_DIR / MATERIALS["guia-assistente-cidadao"][0]).is_file()
    assert interface.client.get("/treinamentos/arquivos/guia-assistente-cidadao").status_code == 200
    assert "guia-geral" in MATERIALS
    assert interface.client.get("/treinamentos/arquivos/guia-geral").status_code == 200
