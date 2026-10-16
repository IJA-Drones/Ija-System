"""SINAN: filtros, paginação, dados ausentes e falhas da fonte, sem rede/banco."""

import json
from unittest.mock import patch

import pytest
import requests
from flask import Blueprint, Flask
from flask_login import LoginManager, UserMixin
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

from app.modules.vigilancia import sinan, sinan_routes


def record(**values):
    return {"nu_ano": "2026", "id_municip": "261090", "id_mn_resi": "261090", "classi_fin": "10", "sem_not": "202601", **values}


class FakeResponse:
    status_code = 200

    def __init__(self, records=None, body=None):
        self.body = body if body is not None else json.dumps({"dengue": records or []}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, chunk_size):
        yield self.body


def test_pagination_uses_row_offset_and_keeps_identical_notifications():
    rows = [record()] * sinan.PAGE_SIZE
    with patch.object(sinan.requests, "get", return_value=FakeResponse(rows)) as get:
        result = sinan.fetch_page(ibge="2610905", year=2026)
    assert result["summary"]["total"] == 10
    assert result["next_offset"] == 10
    assert result["finished"] is False
    assert result["persisted"] is False
    params = get.call_args.kwargs["params"]
    assert params == {"id_municip": "261090", "nu_ano": 2026, "offset": 0, "limit": 10, "campos": sinan.FIELDS}
    assert get.call_args.kwargs["allow_redirects"] is False
    with patch.object(sinan.requests, "get", return_value=FakeResponse([record()])) as get:
        last = sinan.fetch_page(ibge="2610905", year=2026, offset=result["next_offset"])
    assert get.call_args.kwargs["params"]["offset"] == 10
    assert last["finished"] is True
    assert last["next_offset"] is None


def test_empty_source_is_successful_read_not_an_error():
    with patch.object(sinan.requests, "get", return_value=FakeResponse()):
        result = sinan.fetch_page(ibge="2610905", year=2026)
    assert result["summary"]["total"] == 0
    assert result["finished"] is True


def test_unknowns_residence_and_epidemiological_year_boundary_are_preserved():
    result = sinan.summarize([
        record(classi_fin="nan", sem_not=None, id_mn_resi=None),
        record(classi_fin=8.0, sem_not="202553", id_mn_resi="355030"),
        record(classi_fin=99, sem_not="202654", id_mn_resi="261090"),
        record(classi_fin="1", nu_ano=2026, id_municip=261090),
        record(classi_fin="2"),
    ], year=2026, municipality_code="261090")
    assert result["classifications"] == {"unknown": 1, "8": 1, "99": 1, "1": 1, "2": 1}
    assert result["weeks"] == {"202553": 1, "202601": 2}
    assert result["unknown_week"] == 2
    assert result["residence"] == {"unknown": 1, "other": 1, "local": 3}


@pytest.mark.parametrize("bad", [record(id_municip="355030"), record(nu_ano="2025"), {}, None])
def test_mismatched_source_scope_rejects_entire_page(bad):
    with patch.object(sinan.requests, "get", return_value=FakeResponse([record(), bad])):
        with pytest.raises(sinan.SinanError, match="fora do município ou ano"):
            sinan.fetch_page(ibge="2610905", year=2026)


@pytest.mark.parametrize("body", [b'{}', b'{"dengue":null}', b'[]', b'<html>Unavailable</html>', b'{"dengue":{}}'])
def test_bad_response_does_not_become_zero(body):
    with patch.object(sinan.requests, "get", return_value=FakeResponse(body=body)):
        with pytest.raises(sinan.SinanError):
            sinan.fetch_page(ibge="2610905", year=2026)


def test_response_size_and_timeout_are_bounded():
    with patch.object(sinan.requests, "get", return_value=FakeResponse(body=b' ' * (sinan.MAX_RESPONSE_BYTES + 1))):
        with pytest.raises(sinan.SinanError, match="limite"):
            sinan.fetch_page(ibge="2610905", year=2026)
    with patch.object(sinan.requests, "get", side_effect=requests.Timeout("internal URL")):
        with pytest.raises(sinan.SinanError, match="tempo de espera") as error:
            sinan.fetch_page(ibge="2610905", year=2026)
    assert "internal URL" not in str(error.value)


def test_http_error_and_oversized_page_are_rejected():
    response = FakeResponse()
    response.status_code = 429
    with patch.object(sinan.requests, "get", return_value=response):
        with pytest.raises(sinan.SinanError, match="HTTP 429"):
            sinan.fetch_page(ibge="2610905", year=2026)
    with patch.object(sinan.requests, "get", return_value=FakeResponse([record()] * 1001)):
        with pytest.raises(sinan.SinanError, match="formato inesperado"):
            sinan.fetch_page(ibge="2610905", year=2026)


def test_read_limit_is_partial_never_complete():
    with patch.object(sinan.requests, "get", return_value=FakeResponse([record()] * sinan.PAGE_SIZE)):
        result = sinan.fetch_page(ibge="2610905", year=2026, offset=sinan.MAX_RECORDS - sinan.PAGE_SIZE)
    assert result["limit_reached"] is True
    assert result["finished"] is False
    assert result["next_offset"] is None


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="isolated-sinan-test", TESTING=True)

    class User(UserMixin):
        def __init__(self, role):
            self.id = role
            self.tipo_usuario = role

    manager = LoginManager(app)
    manager.user_loader(lambda role: User(role))
    app.jinja_loader = ChoiceLoader([
        DictLoader({"base.html": "{% block extra_styles %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}"}),
        FileSystemLoader("app/templates"),
    ])
    bp = Blueprint("main", __name__)
    bp.add_url_rule("/relatorios", endpoint="relatorios", view_func=lambda: "Relatórios")
    sinan_routes.register_routes(bp)
    app.register_blueprint(bp)
    return app


def login(client, role="admin"):
    with client.session_transaction() as session:
        session["_user_id"] = role
        session["_fresh"] = True


def test_routes_auth_and_permission_gate_before_network(app):
    client = app.test_client()
    with patch.object(sinan, "fetch_page") as fetch:
        assert client.get("/api/vigilancia/sinan").status_code == 401
        assert client.get("/vigilancia/sinan").status_code == 401
        login(client, "uvis")
        assert client.get("/api/vigilancia/sinan").status_code == 403
        assert client.get("/vigilancia/sinan").status_code == 403
        login(client)
        app.config["SINAN_ENABLED"] = False
        assert client.get("/api/vigilancia/sinan").status_code == 404
        fetch.assert_not_called()


@pytest.mark.parametrize("query", ["", "ibge=355030&year=2026", "ibge=2610905&year=2000", "ibge=2610905&year=9999", "ibge=2610905&year=abc", "ibge=2610905&year=2026&offset=1", "ibge=2610905&year=2026&offset=-1000", "ibge=2610905&year=2026&offset=1000000", "ibge=2610905&year=2026&year=2025", "ibge=2610905&year=2026&prefeitura_id=7", "ibge=2610905&year=2026&url=https://example.com"])
def test_invalid_parameters_never_query_source(app, query):
    client = app.test_client()
    login(client)
    with patch.object(sinan, "fetch_page") as fetch:
        assert client.get("/api/vigilancia/sinan?" + query).status_code == 400
        fetch.assert_not_called()


def test_real_page_contains_region_sp_and_source_explanation(app):
    client = app.test_client()
    login(client, "prefeitura_admin")
    response = client.get("/vigilancia/sinan")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    body = response.get_data(as_text=True)
    for expected in ["form-no-loading", "Limpar busca", "sinan-next", "sinan-prev", "Sobre os dados", "sinan-disease", "Zika", "Chikungunya", "CONDOMAR · 15", "São Paulo — capital", "2610905", "onde a notificação foi feita", sinan.DISEASES["dengue"]["source_url"]]:
        assert expected in body


def test_route_returns_only_public_columns_and_source_errors_are_explicit(app):
    client = app.test_client()
    login(client)
    with patch.object(sinan.requests, "get", return_value=FakeResponse([record(nu_notific="private-id", nm_pacient="must-not-leak", cpf="must-not-leak")])):
        response = client.get("/api/vigilancia/sinan?ibge=2610905&year=2026")
    assert response.status_code == 200
    assert response.json["summary"]["total"] == 1
    assert response.json["records"] == [{"year": 2026, "week": "202601", "classification": "10", "residence": "local"}]
    assert "must-not-leak" not in response.get_data(as_text=True)
    assert "private-id" not in response.get_data(as_text=True)
    assert "id_mn_resi" not in response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "private, no-store"
    with patch.object(sinan, "fetch_page", side_effect=sinan.SinanError("Fonte indisponível")):
        response = client.get("/api/vigilancia/sinan?ibge=2610905&year=2026")
    assert response.status_code == 502
    assert "summary" not in response.json


@pytest.mark.parametrize("disease,envelope,class_code", [
    ("dengue", "dengue", "10"), ("zika", "zikavirus", "2"), ("chikungunya", "chikungunya", "13"),
])
def test_each_disease_uses_its_endpoint_envelope_and_continues_pagination(app, disease, envelope, class_code):
    client = app.test_client()
    login(client)
    rows = [record(classi_fin=class_code)] * sinan.PAGE_SIZE
    response_body = json.dumps({envelope: rows}).encode()
    with patch.object(sinan.requests, "get", return_value=FakeResponse(body=response_body)) as get:
        first = client.get(f"/api/vigilancia/sinan?ibge=2610905&year=2026&disease={disease}")
    assert first.status_code == 200
    assert get.call_args.args[0] == f"https://apidadosabertos.saude.gov.br/arboviroses/{envelope}"
    assert first.json["disease"] == disease
    assert first.json["source_url"] == sinan.DISEASES[disease]["source_url"]
    assert first.json["summary"]["classifications"] == {class_code: 10}
    assert first.json["next_offset"] == 10
    assert first.json["finished"] is False
    with patch.object(sinan.requests, "get", return_value=FakeResponse(body=json.dumps({envelope: []}).encode())) as get:
        last = client.get(f"/api/vigilancia/sinan?ibge=2610905&year=2026&disease={disease}&offset=10")
    assert last.status_code == 200
    assert get.call_args.kwargs["params"]["offset"] == 10
    assert last.json["finished"] is True


@pytest.mark.parametrize("disease", ["", "zikavirus", "malaria", "https://example.com", "dengue&disease=zika"])
def test_unknown_or_duplicate_disease_never_calls_source(app, disease):
    client = app.test_client()
    login(client)
    with patch.object(sinan, "fetch_page") as fetch:
        result = client.get(f"/api/vigilancia/sinan?ibge=2610905&year=2026&disease={disease}")
    assert result.status_code == 400
    fetch.assert_not_called()


@pytest.mark.parametrize("disease", ["zika", "chikungunya"])
def test_dengue_envelope_cannot_be_counted_as_another_disease(disease):
    with patch.object(sinan.requests, "get", return_value=FakeResponse([record()])):
        with pytest.raises(sinan.SinanError, match="formato inesperado"):
            sinan.fetch_page(ibge="2610905", year=2026, disease=disease)


def test_zika_does_not_inherit_online_codes_and_unknown_source_codes_are_preserved():
    labels = sinan.DISEASES["zika"]["classifications"]
    assert labels["2"] == "Descartado"
    assert "10" not in labels and "13" not in labels and "5" not in labels
    assert sinan.DISEASES["chikungunya"]["classifications"]["13"] == "Chikungunya"
    with patch.object(sinan.requests, "get", return_value=FakeResponse(body=json.dumps({"zikavirus": [record(classi_fin="99")]}).encode())):
        result = sinan.fetch_page(ibge="2610905", year=2026, disease="zika")
    assert result["summary"]["classifications"] == {"99": 1}
