"""Importação/registro -> projeção pública, sem dados individuais ou escrita em GET."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from flask import Blueprint, Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Prefeitura, Usuario
from app.modules.portal_cidadao.public_risk import get_public_risk_report
from app.modules.portal_cidadao.routes import register_routes
from app.modules.vigilancia.field_store import FieldStore
from app.modules.vigilancia.field_capture import capture_csv
from app.modules.vigilancia.planning import PlanningStore
from app.modules.vigilancia.sample import build_geolocated_sample_csv
from app.modules.vigilancia.sinan_database import DatabaseStore
from app.modules.vigilancia.sinan_models import SinanJob
from app.modules.vigilancia import sinan_import
from test_vigilancia_capture import record
from test_vigilancia_planning import create, change, prepare_planned
from test_vigilancia_results import POLYGON


CITY = {"ibge": "2610905", "name": "Pesqueira", "uf": "PE"}


@pytest.fixture
def public_app(tmp_path):
    root = Path(__file__).resolve().parents[1]
    app = Flask(__name__, static_folder=str(root / "app/static"))
    app.config.update(TESTING=True, SECRET_KEY="public-map-test", SQLALCHEMY_DATABASE_URI="sqlite:///" + str(tmp_path / "public.sqlite"),
        VIGILANCIA_IMPORT_ENABLED=True, SINAN_ENABLED=True, SINAN_IMPORT_ENABLED=True, SINAN_STORAGE_BACKEND="database",
        VIGILANCIA_MUNICIPIOS_IBGE={"7": "2610905", "8": "2600609"}, INFODENGUE_GEOCODE="2610905")
    db.init_app(app)
    LoginManager(app).user_loader(lambda _: None)
    app.jinja_loader = ChoiceLoader([DictLoader({"base.html": "{% block extra_styles %}{% endblock %}{% block auth_content %}{% endblock %}{% block scripts %}{% endblock %}"}), FileSystemLoader(str(root / "app/templates"))])
    bp = Blueprint("main", __name__)
    register_routes(bp)
    bp.add_url_rule("/relato", endpoint="portal_relato_saude", view_func=lambda: "")
    bp.add_url_rule("/contatos", endpoint="portal_contatos", view_func=lambda: "")
    app.register_blueprint(bp)
    app.add_url_rule("/login", endpoint="auth.login", view_func=lambda: "")
    with app.app_context(), patch("app.modules.portal_cidadao.routes.get_infodengue_alert", return_value=None), patch(
        "app.modules.portal_cidadao.routes.get_portal_health_news", return_value=[]):
        db.create_all()
        db.session.add_all([Prefeitura(id=7, nome="Pesqueira fictícia", slug="pesqueira"), Prefeitura(id=8, nome="Alagoinha fictícia", slug="alagoinha"),
            Usuario(id=701, nome_uvis="Agente", login="agente", senha_hash="unused", tipo_usuario="agente_endemias", prefeitura_id=7),
            Usuario(id=50, nome_uvis="Admin global", login="admin", senha_hash="unused", tipo_usuario="dev")])
        db.session.commit()
        yield app


def field(app, *, demo=True, prefeitura=7):
    store = FieldStore(db.engine)
    batch = store.prepare(build_geolocated_sample_csv(prefeitura, "2610905", date(2026, 10, 20)), prefeitura=prefeitura,
        actor="50", source="Fonte sintética privada", filename="privado.csv", demo=demo)
    return store, batch


def job(app, *, owner="7:701", ibge="2610905", disease="dengue", year=None, demo=True, status="completed", total=3):
    scope = dict(ibge=ibge, disease=disease, year=year or date.today().year)
    store = DatabaseStore(db.engine)
    identifier, _ = store.create(owner, kind="api", demo=demo, **scope)
    store.finish(identifier, status, {"total": total, "classifications": {"1": total}, "weeks": {str(scope["year"]) + "40": total},
        "groups": [{"private": "NAO-PUBLICAR-GRUPO"}]})
    return identifier


def payload(response):
    assert response.status_code == 200
    return json.loads(response.text.split('id="portal-risco-data">', 1)[1].split("</script>", 1)[0])


def test_public_map_reads_confirmed_csv_and_never_serializes_individuals(public_app):
    app = public_app
    store, batch = field(app)
    browser = app.test_client()
    path = "/portal-cidadao?regiao=condomar&municipio=2610905&demo=true"
    assert not payload(browser.get(path))["liraa"]["disponivel"]
    store.confirm(batch["id"], prefeitura=7, actor="50")
    report = payload(browser.get(path))
    assert report["demo"] is True and report["liraa"]["visitas"] == 20
    index = report["liraa"]["indicadores"][0]
    assert (index["iip"], index["imoveis_inspecionados"], index["imoveis_positivos"]) == (25, 16, 4)
    assert report["geografia"]["features"] == []  # Sem contorno desenhado, não inventar área.
    assert report["limite"]["properties"]["codigo"] == "2610905"
    serialized = json.dumps(report)
    for private in ('"latitude"', '"longitude"', '"pontos"', '"registros"', '"imovel_codigo"', '"inspecao_codigo"', '"actor"', batch["id"], '"filename"', "Fonte sintética privada"):
        assert private not in serialized
    assert not payload(browser.get(path.replace("demo=true", "demo=false")))["liraa"]["disponivel"]
    assert not payload(browser.get(path.replace("2610905", "2600609")))["liraa"]["disponivel"]


def test_manual_planned_visits_share_internal_iip_and_preserved_geometry(public_app):
    app = public_app
    planning = PlanningStore(db.engine)
    create(planning)
    before = planning.overview(7, True)["territorio"][0]
    planning.mutate(7, True, "50", "territorio", dict(quarteirao="Q-01", bairro="Bairro Sintético", area="A-01", imoveis="100", referencia="RG",
        geometria_acao="substituir", geometria_confirmada="sim", territorio_versao=str(before["atualizado_em"]), geometria=json.dumps(POLYGON)))
    change(planning, "quarteirao", estrato="E-01", quarteirao="Q-01", meta_quarteirao="20", agente_id="701")
    change(planning, "liberar", amostra_validada="sim")
    batch = prepare_planned(None, planning)
    planning.confirm(batch["id"], prefeitura=7, actor="a")
    focal = planning.prepare(capture_csv(record(origem="FOCAL", levantamento_codigo="", estrato_codigo="", imovel_codigo="FOCAL-PRIVADO", inspecao_codigo="FOCAL-VISITA"), prefeitura=7),
        prefeitura=7, actor="50", source="Focal", filename="focal.csv", demo=True)
    planning.confirm(focal["id"], prefeitura=7, actor="50")
    report = payload(app.test_client().get("/portal-cidadao?municipio=2610905&demo=true"))
    assert report["liraa"]["visitas"] == 1 and report["focal"]["visitas"] == 1
    assert report["geografia"]["features"][0]["geometry"]["coordinates"] == [POLYGON["coordinates"]]
    assert report["geografia"]["features"][0]["properties"]["iip"] == 100
    assert "quarteiroes" not in json.dumps(report) and "FOCAL-PRIVADO" not in json.dumps(report)


def test_sinan_uses_one_snapshot_without_expiring_or_writing_on_public_get(public_app):
    app = public_app
    first = job(app, total=2)
    second = job(app, total=4)
    partial = job(app, status="partial", total=100)
    for owner, ibge, disease, year, demo in [("8:801", "2610905", "dengue", None, True), ("7:701", "2600609", "dengue", None, True),
        ("7:701", "2610905", "zika", None, True), ("7:701", "2610905", "dengue", date.today().year - 1, True), ("7:701", "2610905", "dengue", None, False)]:
        job(app, owner=owner, ibge=ibge, disease=disease, year=year, demo=demo, total=99)
    running = DatabaseStore(db.engine).create("7:701", kind="api", ibge="2610905", disease="dengue", year=date.today().year, demo=True)[0]
    with db.engine.begin() as conn:
        for identifier, created in [(first, 10), (second, 20), (partial, 30)]:
            conn.execute(SinanJob.__table__.update().where(SinanJob.id == identifier).values(created=created))
        conn.execute(SinanJob.__table__.update().where(SinanJob.id == running).values(updated=1))
    statements = []
    def observe(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    sa.event.listen(db.engine, "before_cursor_execute", observe)
    try:
        response = app.test_client().get("/portal-cidadao?municipio=2610905&demo=true")
    finally:
        sa.event.remove(db.engine, "before_cursor_execute", observe)
    report = payload(response)
    assert report["sinan"]["total"] == 4 and report["sinan"]["parcial"] is False
    assert report["sinan"]["classificacoes"] == [{"rotulo": "Confirmado", "total": 4}]
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    assert not any("vigilancia_sinan_casos" in statement for statement in statements)
    assert "NAO-PUBLICAR-GRUPO" not in response.text and second not in response.text and '"owner"' not in response.text
    assert db.session.get(SinanJob, running).status == "running"


def test_global_administrator_imports_and_partial_status_are_visible_as_aggregates(public_app):
    app = public_app
    job(app, owner="None:50", status="partial", total=7)
    report = payload(app.test_client().get("/portal-cidadao?municipio=2610905&demo=true"))
    assert report["sinan"]["total"] == 7 and report["sinan"]["parcial"] is True
    assert payload(app.test_client().get("/portal-cidadao?municipio=2600609&demo=true"))["sinan"] is None


def test_missing_or_ambiguous_mapping_never_falls_back_to_fake_data(public_app):
    app = public_app
    for mapping in ({}, "invalid-json", {"7": "2610905", "8": "2610905"}):
        app.config["VIGILANCIA_MUNICIPIOS_IBGE"] = mapping
        report = payload(app.test_client().get("/portal-cidadao?municipio=2610905&demo=true"))
        assert not report["liraa"]["disponivel"] and report["sinan"] is None
        assert report["geografia"]["features"] == [] and report["avisos"]


def test_condomar_filter_applies_to_infodengue_and_keeps_regional_navigation(public_app):
    app = public_app
    browser = app.test_client()
    with patch("app.modules.portal_cidadao.routes.get_infodengue_alert", return_value=None) as alert:
        response = browser.get("/portal-cidadao?regiao=condomar&municipio=2601201")
    assert alert.call_args.kwargs["config"]["INFODENGUE_GEOCODE"] == "2601201"
    assert payload(response)["municipio"]["name"] == "Arcoverde"
    assert '<option value="3550308"' not in response.text
    assert "boletim-dengue?municipio=2601201&amp;regiao=condomar" in response.text
    with patch("app.modules.portal_cidadao.routes.get_infodengue_report", return_value=None) as source:
        response = browser.get("/portal-cidadao/boletim-dengue?regiao=condomar&municipio=2610905&doenca=zika&ano=2025")
    assert source.call_args.kwargs["config"]["INFODENGUE_GEOCODE"] == "2610905"
    assert source.call_args.kwargs["disease"] == "zika" and source.call_args.kwargs["year"] == 2025
    assert 'value="3550308"' not in response.text and "regiao=condomar" in response.text


@pytest.mark.parametrize("query", ["demo=true&demo=false", "demo=1", "doenca=outra", "ano_sinan=9999", "inicio=2026-10-21&fim=2026-10-20", "regiao=outra"])
def test_invalid_public_filters_do_not_call_external_sources(public_app, query):
    with patch("app.modules.portal_cidadao.routes.get_infodengue_alert") as source:
        assert public_app.test_client().get("/portal-cidadao?" + query).status_code == 400
        source.assert_not_called()
