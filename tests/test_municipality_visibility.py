"""A POC fica fora da interface mesmo com cadastro ativo e configuração antiga."""

from html.parser import HTMLParser
from unittest.mock import patch

import pytest
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Prefeitura, Usuario
from app.modules.portal_cidadao.municipalities import public_health_municipality
from tests import test_central_ti as base


@pytest.fixture
def setup():
    state = base.CentralTiTests()
    state.setUp()
    state.app.config.update(VIGILANCIA_UI_ENABLED=False, INFODENGUE_GEOCODE="2610905", INFODENGUE_CITY="Pesqueira")
    state.hidden_city = Prefeitura(id=14, nome="Prefeitura de Pesqueira", slug="pesqueira", ativa=True)
    state.visible_city = Prefeitura(id=40, nome="Prefeitura de Arcoverde", slug="arcoverde", ativa=True)
    db.session.add_all([state.hidden_city, state.visible_city])
    state.hidden_unit = Usuario(nome_uvis="Unidade da POC", login="preservar_login", senha_hash="preservar_hash",
                                tipo_usuario="uvis", prefeitura_id=14, regiao="OESTE")
    state.visible_unit = Usuario(nome_uvis="Unidade disponível", login="unidade_disponivel", senha_hash="test",
                                 tipo_usuario="uvis", prefeitura_id=40, regiao="OESTE")
    db.session.add_all([state.hidden_unit, state.visible_unit])
    db.session.commit()
    try:
        yield state
    finally:
        state.tearDown()


@pytest.mark.parametrize("config", [{}, {"PORTAL_EXCLUDED_MUNICIPALITIES": ()},
    {"INFODENGUE_GEOCODE": "2610905", "INFODENGUE_CITY": "Pesqueira"}])
@pytest.mark.parametrize("query", [{}, {"municipio": "2610905"}, {"regiao": "condomar", "municipio": "2610905"}])
def test_public_catalog_never_reintroduces_closed_poc(config, query):
    selected, options, sources = public_health_municipality(config, MultiDict(query))
    assert selected["ibge"] == sources["INFODENGUE_GEOCODE"] != "2610905"
    assert all(row["ibge"] != "2610905" for row in options)
    from app.modules.vigilancia.sinan import MUNICIPALITIES_BY_IBGE
    assert MUNICIPALITIES_BY_IBGE["2610905"]["name"] == "Pesqueira"


@pytest.mark.parametrize("role", [None, "dev"])
def test_citizen_bulletin_and_directory_hide_city_even_when_active(setup, role):
    if role:
        setup.login(role)
    with patch("app.modules.portal_cidadao.routes.get_infodengue_alert", return_value=None) as alert, \
         patch("app.modules.portal_cidadao.routes.get_infodengue_report", return_value=None) as report, \
         patch("app.modules.portal_cidadao.routes.get_portal_health_news", return_value=[]):
        for path in ("/portal-cidadao?municipio=2610905", "/portal-cidadao/boletim-dengue?municipio=2610905",
                     "/portal-cidadao/contatos"):
            response = setup.client.get(path)
            assert response.status_code == 200
            assert "Pesqueira" not in response.text and 'value="2610905"' not in response.text
            assert "Arcoverde" in response.text
    assert alert.call_args.kwargs["config"]["INFODENGUE_GEOCODE"] != "2610905"
    assert report.call_args.kwargs["config"]["INFODENGUE_GEOCODE"] != "2610905"
    config = setup.client.get("/api/mobile/config").json
    assert 14 not in {p["id"] for p in config["prefeituras"]}
    assert 40 in {p["id"] for p in config["prefeituras"]}
    assert db.session.get(Prefeitura, 14).ativa is True


def test_map_and_report_choices_hide_associated_units_without_deleting_users(setup):
    from app.modules.mapas.service import build_uvis_disponiveis as map_units
    from app.modules.relatorios.service import build_uvis_disponiveis as report_units
    from app.modules.admin_dashboard.service import build_uvis_select
    for choices in (map_units(setup.users["dev"]), report_units(setup.users["dev"]),
                    build_uvis_select(setup.users["dev"])):
        ids = {row.id for row in choices}
        assert setup.hidden_unit.id not in ids
        assert setup.visible_unit.id in ids
        assert setup.users["uvis"].id in ids  # Contas antigas sem prefeitura continuam disponíveis.
    setup.login("dev")
    response = setup.client.get("/mapa-relatorio")
    assert response.status_code == 200 and "Unidade da POC" not in response.text
    assert "Unidade disponível" in response.text
    kept = db.session.get(Usuario, setup.hidden_unit.id)
    assert (kept.login, kept.senha_hash, kept.prefeitura_id) == ("preservar_login", "preservar_hash", 14)


class MunicipalitySelect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.selected = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.active = attrs.get("name") == "prefeitura_id"
        if tag == "option" and self.active and "selected" in attrs:
            self.selected.append(attrs.get("value"))

    def handle_endtag(self, tag):
        if tag == "select":
            self.active = False


def test_hidden_registration_and_old_links_stay_hidden_but_account_binding_survives(setup):
    setup.login("dev")
    for path in ("/admin/prefeituras", "/admin/prefeituras?ativa=1", "/admin/prefeituras?q=Pesqueira"):
        response = setup.client.get(path)
        assert response.status_code == 200 and "Prefeitura de Pesqueira" not in response.text
    for path in ("/admin/prefeituras/14/editar", "/configuracoes/documentos/14", "/configuracoes/contatos/14"):
        assert setup.client.get(path).status_code == 404
    bound_admin = Usuario(nome_uvis="Gestão da POC", login="gestao_poc", senha_hash="preservar",
                          tipo_usuario="prefeitura_admin", prefeitura_id=14)
    db.session.add(bound_admin)
    db.session.commit()
    # A edição da conta deve enviar o mesmo vínculo; ocultá-lo não pode zerá-lo.
    for active in (True, False):
        setup.hidden_city.ativa = active
        db.session.commit()
        for path in (f"/admin/usuarios/{bound_admin.id}/editar", f"/admin/uvis/{setup.hidden_unit.id}/editar"):
            response = setup.client.get(path)
            assert response.status_code == 200, (path, response.location)
            assert "Prefeitura de Pesqueira" not in response.text
            selector = MunicipalitySelect()
            selector.feed(response.text)
            assert selector.selected == ["14"]
    assert db.session.get(Usuario, setup.hidden_unit.id).prefeitura_id == 14
