import unittest
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from flask import Blueprint, Flask
from flask_login import LoginManager
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest

from app.modules.portal_cidadao import health_data, health_news
from app.modules.portal_cidadao.routes import register_routes
from app.modules.portal_cidadao.municipalities import public_health_municipality


def weekly_record(**overrides):
    year = date.today().year
    return {
        "SE": year * 100 + 35,
        "data_iniSE": f"{year}-08-30",
        "casos": 260,
        "casos_est": 260.0,
        "p_inc100k": 2.13,
        "p_rt1": 0.0,
        "nivel": 1,
        **overrides,
    }


class PortalHealthDataTests(unittest.TestCase):
    def setUp(self):
        health_data.clear_dengue_summary_cache()
        self.addCleanup(health_data.clear_dengue_summary_cache)
        self.response = Mock()
        self.response.json.return_value = [weekly_record()]
        patcher = patch.object(health_data.requests, "get", return_value=self.response)
        self.get = patcher.start()
        self.addCleanup(patcher.stop)

    def test_latest_week_is_selected_and_numbers_are_localized(self):
        self.response.json.return_value = [
            weekly_record(SE=date.today().year * 100 + 34, casos=999),
            weekly_record(),
            weekly_record(SE=(date.today().year - 1) * 100 + 52, casos=500),
        ]
        summary = health_data.get_portal_dengue_summary()
        self.assertTrue(summary["available"])
        self.assertFalse(summary["stale"])
        self.assertEqual(summary["week_label"], f"SE 35/{date.today().year}")
        self.assertEqual(summary["reported_cases"], "260")
        self.assertEqual(summary["estimated_cases"], "260,0")
        self.assertEqual(summary["incidence"], "2,13")
        self.assertEqual(summary["probability"], "0,0%")
        self.assertEqual(summary["level_label"], "Baixo")
        self.assertEqual(self.get.call_args.kwargs["params"]["geocode"], 3550308)

    def test_missing_values_are_not_reported_as_zero(self):
        self.response.json.return_value = [weekly_record(
            casos=None, casos_est=float("nan"), p_inc100k=-1, p_rt1=2, nivel=None,
        )]
        summary = health_data.get_portal_dengue_summary()
        for key in ("reported_cases", "estimated_cases", "incidence", "probability"):
            self.assertEqual(summary[key], "—")
        self.assertEqual(summary["level_label"], "Não informado")

    def test_json_timestamp_and_percentage_are_formatted(self):
        start = datetime(date.today().year, 8, 30, tzinfo=timezone.utc)
        self.response.json.return_value = [weekly_record(
            data_iniSE=int(start.timestamp() * 1000), casos=12345,
            p_rt1=0.987, nivel=4,
        )]
        summary = health_data.get_portal_dengue_summary()
        self.assertEqual(summary["week_start_label"], start.strftime("%d/%m/%Y"))
        self.assertEqual(summary["reported_cases"], "12.345")
        self.assertEqual(summary["probability"], "98,7%")
        self.assertEqual(summary["level_class"], "high")

    def test_cache_avoids_repeated_requests(self):
        first = health_data.get_portal_dengue_summary()
        self.assertEqual(health_data.get_portal_dengue_summary(), first)
        self.get.assert_called_once()

    def test_source_failure_preserves_previous_values_and_recovers(self):
        with patch.object(health_data.time, "monotonic", return_value=100):
            first = health_data.get_portal_dengue_summary()
        self.get.side_effect = requests.Timeout("offline")
        expiry = 100 + health_data.CACHE_TTL_SECONDS
        with patch.object(health_data.time, "monotonic", return_value=expiry):
            stale = health_data.get_portal_dengue_summary()
            self.assertTrue(stale["available"])
            self.assertTrue(stale["stale"])
            self.assertEqual(stale["reported_cases"], first["reported_cases"])
            health_data.get_portal_dengue_summary()
            self.assertEqual(self.get.call_count, 2)
        self.get.side_effect = None
        with patch.object(health_data.time, "monotonic", return_value=expiry + health_data.RETRY_TTL_SECONDS):
            self.assertFalse(health_data.get_portal_dengue_summary()["stale"])

    def test_initial_failure_does_not_invent_health_data(self):
        self.get.side_effect = requests.ConnectionError("offline")
        summary = health_data.get_portal_dengue_summary()
        self.assertFalse(summary["available"])
        self.assertNotIn("reported_cases", summary)
        self.assertIn("report_url", summary)
        health_data.get_portal_dengue_summary()
        self.get.assert_called_once()

    def test_empty_or_invalid_source_response_is_unavailable(self):
        for payload in ([], {"error": "unavailable"}, [None], [weekly_record(SE="invalid")], [weekly_record(data_iniSE=None)]):
            with self.subTest(payload=payload):
                health_data.clear_dengue_summary_cache()
                self.response.json.return_value = payload
                self.assertFalse(health_data.get_portal_dengue_summary()["available"])


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.anchors = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.anchors.add(attrs["href"][1:])


class PublicHealthMunicipalityTests(unittest.TestCase):
    def test_all_condomar_municipalities_are_available_without_database_mapping(self):
        selected, options, config = public_health_municipality({}, MultiDict({"municipio": "2610905"}))
        self.assertEqual(len([item for item in options if item["region"] == "condomar"]), 15)
        self.assertEqual(selected["name"], "Pesqueira")
        self.assertEqual(config["INFODENGUE_GEOCODE"], "2610905")
        self.assertEqual(config["INFODENGUE_CITY"], "Pesqueira")
        self.assertNotIn("DATABASE_URL", config)

    def test_default_municipality_can_be_changed_by_public_filter(self):
        config = {"INFODENGUE_GEOCODE": "2610905", "INFODENGUE_CITY": "Pesqueira"}
        self.assertEqual(public_health_municipality(config, MultiDict())[0]["ibge"], "2610905")
        selected = public_health_municipality(config, MultiDict({"municipio": "2601201"}))[0]
        self.assertEqual(selected["name"], "Arcoverde")
        self.assertEqual(config["INFODENGUE_GEOCODE"], "2610905")

    def test_unknown_and_ambiguous_municipalities_are_rejected(self):
        for args in (MultiDict({"municipio": "9999999"}), MultiDict([("municipio", "2610905"), ("municipio", "2601201")])):
            with self.subTest(args=args), self.assertRaises(BadRequest):
                public_health_municipality({}, args)

    def test_existing_configured_municipality_outside_catalog_is_preserved(self):
        selected, options, _ = public_health_municipality(
            {"INFODENGUE_GEOCODE": "2611606", "INFODENGUE_CITY": "Recife"}, MultiDict(),
        )
        self.assertEqual(selected["name"], "Recife")
        self.assertEqual(selected["uf"], "PE")
        self.assertEqual(len(options), 17)

    def test_region_filter_lists_only_condomar_and_accepts_switching_from_sao_paulo(self):
        for previous in ("3550308", "2610905"):
            selected, options, config = public_health_municipality({}, MultiDict({"regiao": "condomar", "municipio": previous}))
            self.assertEqual(len(options), 15)
            self.assertTrue(all(item["region"] == "condomar" for item in options))
            self.assertEqual(selected["region"], "condomar")
            self.assertEqual(config["INFODENGUE_GEOCODE"], selected["ibge"])
        for args in (MultiDict({"regiao": "invalida"}), MultiDict([("regiao", "todos"), ("regiao", "condomar")])):
            with self.assertRaises(BadRequest):
                public_health_municipality({}, args)


class InfoDengueMunicipalCacheTests(unittest.TestCase):
    def setUp(self):
        health_news.clear_health_news_cache()
        self.addCleanup(health_news.clear_health_news_cache)
        self.configs = [
            {"INFODENGUE_GEOCODE": "2610905", "INFODENGUE_CITY": "Pesqueira"},
            {"INFODENGUE_GEOCODE": "2601201", "INFODENGUE_CITY": "Arcoverde"},
        ]

    @staticmethod
    def api_response(cases):
        response = Mock()
        response.json.return_value = [weekly_record(casos=cases)]
        return response

    def test_alert_cache_never_reuses_another_city_and_preserves_cache_hits(self):
        with patch.object(health_news.requests, "get", side_effect=[self.api_response(7), self.api_response(19)]) as get:
            first = health_news.get_infodengue_alert(self.configs[0])
            second = health_news.get_infodengue_alert(self.configs[1])
            again = health_news.get_infodengue_alert(self.configs[0])
        self.assertEqual((first["city"], first["cases"]), ("Pesqueira", "7"))
        self.assertEqual((second["city"], second["cases"]), ("Arcoverde", "19"))
        self.assertEqual(again, first)
        self.assertEqual([call.kwargs["params"]["geocode"] for call in get.call_args_list], ["2610905", "2601201"])

    def test_report_cache_is_separate_for_city_disease_and_year(self):
        with patch.object(health_news.requests, "get", side_effect=[self.api_response(7), self.api_response(19), self.api_response(3)]) as get:
            first = health_news.get_infodengue_report(self.configs[0], disease="dengue", year=date.today().year)
            second = health_news.get_infodengue_report(self.configs[1], disease="dengue", year=date.today().year)
            third = health_news.get_infodengue_report(self.configs[1], disease="zika", year=date.today().year)
            self.assertEqual(health_news.get_infodengue_report(self.configs[0], disease="dengue", year=date.today().year), first)
        self.assertEqual(first["city"], "Pesqueira")
        self.assertEqual(second["city"], "Arcoverde")
        self.assertEqual(third["disease_label"], "Zika")
        self.assertEqual(first["summary"]["total_cases"], "7")
        self.assertEqual(second["summary"]["total_cases"], "19")
        self.assertEqual(get.call_count, 3)

    def test_unavailable_city_does_not_receive_previous_city_data_or_repeat_failure(self):
        with patch.object(health_news.requests, "get", side_effect=[self.api_response(7), requests.Timeout("offline")]) as get:
            self.assertIsNotNone(health_news.get_infodengue_alert(self.configs[0]))
            self.assertIsNone(health_news.get_infodengue_alert(self.configs[1]))
            self.assertIsNone(health_news.get_infodengue_alert(self.configs[1]))
        self.assertEqual(get.call_count, 2)

    def test_pernambuco_publications_use_state_sources_instead_of_sao_paulo_feed(self):
        with patch.object(health_news.requests, "get") as get:
            items = health_news.get_portal_health_news(uf="PE")
        get.assert_not_called()
        self.assertTrue(any("saude.pe.gov.br" in item["url"] for item in items))
        self.assertFalse(any("sp.gov.br" in item["url"] for item in items))


class PortalHealthPageTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "app"
        self.app = Flask(__name__, template_folder=str(root / "templates"), static_folder=str(root / "static"))
        self.app.config.update(TESTING=True, SECRET_KEY="portal-test")
        manager = LoginManager(self.app)
        manager.user_loader(lambda _: None)
        bp = Blueprint("main", __name__)
        register_routes(bp)
        bp.add_url_rule("/", endpoint="dashboard", view_func=lambda: "")
        bp.add_url_rule("/portal-cidadao/relato-saude", endpoint="portal_relato_saude", view_func=lambda: "")
        bp.add_url_rule("/portal-cidadao/contatos", endpoint="portal_contatos", view_func=lambda: "")
        self.app.register_blueprint(bp)
        self.app.add_url_rule("/login", endpoint="auth.login", view_func=lambda: "")

    @staticmethod
    def demo_risk_report():
        from app.modules.portal_cidadao.public_risk import get_public_risk_report

        return get_public_risk_report({"VIGILANCIA_IMPORT_ENABLED": False, "SINAN_ENABLED": False},
            {"ibge": "2610905", "name": "Pesqueira", "uf": "PE"}, MultiDict({"demo": "true"}))

    def render_page(self, available):
        alert = health_news._build_infodengue_alert(
            [weekly_record()], city="São Paulo", disease="dengue",
            source_url=health_data.INFO_DENGUE_SOURCE_URL,
        ).to_dict() if available else None
        with patch("app.modules.portal_cidadao.routes.list_public_prefeituras", return_value=[]), patch(
            "app.modules.portal_cidadao.routes.get_infodengue_alert", return_value=alert,
        ), patch(
            "app.modules.portal_cidadao.routes.get_portal_health_news",
            return_value=list(health_news.OFFICIAL_FALLBACK_LINKS),
        ), patch(
            "app.modules.portal_cidadao.routes.get_public_risk_report",
            return_value=self.demo_risk_report(),
        ):
            page = self.app.test_client().get("/portal-cidadao?demo=true")
        self.assertEqual(page.status_code, 200)
        return page.get_data(as_text=True)

    def test_public_page_renders_metrics_and_navigation_destinations(self):
        html = self.render_page(True)
        links = PageLinks()
        links.feed(html)
        for target in ("portal-inicio", "boletim-saude", "mapa-risco", "como-funciona", "portal-relato"):
            self.assertIn(target, links.ids)
            self.assertIn(target, links.anchors)
        for text in ("Dengue em São Paulo", "260,0", "2,13", "0,0%", "Ver relatório completo", "Consultar dados no InfoDengue", "portalCidadaoForm"):
            self.assertIn(text, html)
        self.assertEqual(html.count('id="portal-dengue-title"'), 1)
        self.assertEqual(html.count("Casos notificados"), 1)
        self.assertIn('href="/portal-cidadao/boletim-dengue?municipio=3550308&amp;demo=true"', html)
        self.assertIn('href="#mapa-risco"', html)
        self.assertIn("Mapa de risco e vigilância", html)
        self.assertIn("Os limites municipais são reais. Os registros de vigilância exibidos neste mapa são fictícios.", html)
        self.assertIn("CONDOMAR · 15 municípios de Pernambuco", html)
        self.assertIn("Relatar suspeita de adoecimento", html)
        self.assertIn('id="portal-risco-data"', html)

    def test_public_page_keeps_form_news_and_source_links_when_api_fails(self):
        html = self.render_page(False)
        self.assertIn("indicadores estão temporariamente indisponíveis", html)
        self.assertIn("portalCidadaoForm", html)
        self.assertIn("Boletim epidemiológico de arboviroses", html)
        self.assertIn(health_data.HEALTH_REPORT_URL, html)
        self.assertIn(health_data.INFO_DENGUE_SOURCE_URL, html)
        self.assertNotIn("portal-cidadao-health-metrics", html)

    def test_public_municipality_filter_queries_selected_city_and_preserves_report_link(self):
        def alert_for_city(config, logger):
            return health_news._build_infodengue_alert(
                [weekly_record(casos=7)], city=config["INFODENGUE_CITY"], disease="dengue",
                source_url=f'https://info.dengue.mat.br/api/alertcity?geocode={config["INFODENGUE_GEOCODE"]}',
            ).to_dict()

        with patch("app.modules.portal_cidadao.routes.list_public_prefeituras", return_value=[]), patch(
            "app.modules.portal_cidadao.routes.get_infodengue_alert", side_effect=alert_for_city,
        ) as get, patch("app.modules.portal_cidadao.routes.get_public_risk_report", return_value=None):
            response = self.app.test_client().get("/portal-cidadao?municipio=2610905")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get.call_args.kwargs["config"]["INFODENGUE_GEOCODE"], "2610905")
        self.assertIn("Dengue em Pesqueira", html)
        self.assertIn('<option value="2610905" selected>', html)
        self.assertIn('href="/portal-cidadao/boletim-dengue?municipio=2610905"', html)
        self.assertIn("SES-PE", html)
        self.assertNotIn("COVISA/SMS-SP", html)

    def test_full_report_filters_municipality_disease_and_year_without_database_access(self):
        with patch("app.modules.portal_cidadao.routes.get_infodengue_report", return_value=None) as get:
            response = self.app.test_client().get("/portal-cidadao/boletim-dengue?municipio=2601201&doenca=zika&ano=2025")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get.call_args.kwargs["config"]["INFODENGUE_GEOCODE"], "2601201")
        self.assertEqual(get.call_args.kwargs["disease"], "zika")
        self.assertEqual(get.call_args.kwargs["year"], 2025)
        html = response.get_data(as_text=True)
        self.assertIn("Arcoverde/PE", html)
        self.assertIn('<option value="2601201" selected>', html)
        self.assertIn('<option value="zika" selected>', html)
        self.assertIn('href="/portal-cidadao?municipio=2601201"', html)
        self.assertIn("Ausência de dados não significa ausência de casos", html)

    def test_invalid_public_municipalities_do_not_query_external_api(self):
        with patch("app.modules.portal_cidadao.routes.get_infodengue_alert") as alert, patch(
            "app.modules.portal_cidadao.routes.get_infodengue_report",
        ) as report:
            for path in ("/portal-cidadao", "/portal-cidadao/boletim-dengue"):
                for query in ("?municipio=9999999", "?municipio=2610905&municipio=2601201"):
                    with self.subTest(path=path, query=query):
                        self.assertEqual(self.app.test_client().get(path + query).status_code, 400)
        alert.assert_not_called()
        report.assert_not_called()


if __name__ == "__main__":
    unittest.main()
