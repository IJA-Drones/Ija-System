import unittest
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from flask import Blueprint, Flask
from flask_login import LoginManager

from app.modules.portal_cidadao import health_data, health_news
from app.modules.portal_cidadao.routes import register_routes


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
        self.app.register_blueprint(bp)
        self.app.add_url_rule("/login", endpoint="auth.login", view_func=lambda: "")

    def render_page(self, available):
        alert = health_news._build_infodengue_alert(
            [weekly_record()], city="São Paulo", disease="dengue",
            source_url=health_data.INFO_DENGUE_SOURCE_URL,
        ).to_dict() if available else None
        with patch(
            "app.modules.portal_cidadao.routes.get_infodengue_alert", return_value=alert,
        ), patch(
            "app.modules.portal_cidadao.routes.get_portal_health_news",
            return_value=list(health_news.OFFICIAL_FALLBACK_LINKS),
        ):
            page = self.app.test_client().get("/portal-cidadao")
        self.assertEqual(page.status_code, 200)
        return page.get_data(as_text=True)

    def test_public_page_renders_metrics_and_navigation_destinations(self):
        html = self.render_page(True)
        links = PageLinks()
        links.feed(html)
        for target in ("portal-inicio", "boletim-saude", "como-funciona", "portal-relato"):
            self.assertIn(target, links.ids)
            self.assertIn(target, links.anchors)
        for text in ("Dengue em São Paulo", "260,0", "2,13", "0,0%", "Ver relatório completo", "Consultar dados no InfoDengue", "portalCidadaoForm"):
            self.assertIn(text, html)
        self.assertEqual(html.count('id="portal-dengue-title"'), 1)
        self.assertEqual(html.count("Casos notificados"), 1)
        self.assertIn('href="/portal-cidadao/boletim-dengue"', html)

    def test_public_page_keeps_form_news_and_source_links_when_api_fails(self):
        html = self.render_page(False)
        self.assertIn("indicadores estão temporariamente indisponíveis", html)
        self.assertIn("portalCidadaoForm", html)
        self.assertIn("Boletim epidemiológico de arboviroses", html)
        self.assertIn(health_data.HEALTH_REPORT_URL, html)
        self.assertIn(health_data.INFO_DENGUE_SOURCE_URL, html)
        self.assertNotIn("portal-cidadao-health-metrics", html)


if __name__ == "__main__":
    unittest.main()
