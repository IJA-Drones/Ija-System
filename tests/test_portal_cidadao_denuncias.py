import unittest
from io import BytesIO
from types import SimpleNamespace

from flask import Flask
from werkzeug.datastructures import FileStorage, MultiDict

from app.clients import cep_client
from app.modules.portal_cidadao import health_news
from app.modules.portal_cidadao import service as portal_service


class PortalCidadaoDenunciaServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True)
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.original_skybox_enabled = portal_service.skybox_enabled
        self.original_upload_file_to_skybox = portal_service.upload_file_to_skybox

    def tearDown(self):
        portal_service.skybox_enabled = self.original_skybox_enabled
        portal_service.upload_file_to_skybox = self.original_upload_file_to_skybox
        self.ctx.pop()

    def test_parse_denuncia_requires_valid_cpf_and_phone(self):
        data = portal_service._parse_denuncia_form(MultiDict({
            "tipo_visita": "Aedes",
            "tipo_imovel": "Imovel Geral",
            "foco": "Piscina",
            "cep": "01001-000",
            "logradouro": "Praca da Se",
            "numero": "1",
            "bairro": "Se",
            "cidade": "Sao Paulo",
            "nome": "Cidadao Teste",
            "cpf": "111.111.111-11",
            "rg": "12.345.678-9",
            "telefone": "1234",
            "consentimento": "1",
        }))
        errors = portal_service._validate_denuncia_data(data)

        self.assertEqual(data["cep"], "01001-000")
        self.assertEqual(errors["cpf"], "Informe um CPF valido.")
        self.assertEqual(errors["telefone"], "Informe um telefone com DDD.")

    def test_parse_denuncia_formats_valid_identity_fields(self):
        data = portal_service._parse_denuncia_form(MultiDict({
            "tipo_visita": "Culex",
            "foco": "Corrego",
            "cep": "01001000",
            "logradouro": "Praca da Se",
            "numero": "1",
            "bairro": "Se",
            "cidade": "Sao Paulo",
            "nome": "Cidadao Teste",
            "cpf": "52998224725",
            "rg": "123456789",
            "telefone": "11987654321",
            "consentimento": "true",
        }))
        errors = portal_service._validate_denuncia_data(data)

        self.assertEqual(errors, {})
        self.assertEqual(data["cpf"], "529.982.247-25")
        self.assertEqual(data["telefone"], "(11) 98765-4321")

    def test_denuncia_accepts_address_without_cep(self):
        data = portal_service._parse_denuncia_form(MultiDict({
            "tipo_visita": "Outro",
            "foco": "Outro",
            "logradouro": "Rua Teste",
            "numero": "10",
            "bairro": "Centro",
            "cidade": "Sao Paulo",
            "nome": "Cidadao Teste",
            "cpf": "52998224725",
            "rg": "123456789",
            "telefone": "11987654321",
            "consentimento": "1",
        }))
        errors = portal_service._validate_denuncia_data(data)

        self.assertEqual(data["cep"], "")
        self.assertNotIn("cep", errors)

    def test_address_geocode_overwrites_browser_location_coordinates(self):
        original_geocode = portal_service.geocode_endereco_google
        try:
            portal_service.geocode_endereco_google = lambda **kwargs: (-23.55052, -46.633308, "place-address")
            data = {
                "cep": "",
                "logradouro": "Praca da Se",
                "numero": "1",
                "bairro": "Se",
                "cidade": "Sao Paulo",
                "uf": "SP",
                "latitude": "-22.0",
                "longitude": "-43.0",
                "place_id": "place-browser",
            }

            portal_service._try_geocode_address(data)

            self.assertEqual(data["latitude"], "-23.55052")
            self.assertEqual(data["longitude"], "-46.633308")
            self.assertEqual(data["place_id"], "place-address")
        finally:
            portal_service.geocode_endereco_google = original_geocode

    def test_save_denuncia_media_uses_skybox_denuncias_folder(self):
        captured = {}

        def fake_upload(file_storage, remote_path):
            captured["remote_path"] = remote_path
            captured["body"] = file_storage.stream.read()
            return f"skybox://{remote_path}"

        portal_service.skybox_enabled = lambda: True
        portal_service.upload_file_to_skybox = fake_upload

        denuncia = SimpleNamespace(id=77)
        storage = FileStorage(
            stream=BytesIO(b"video"),
            filename="foco.mp4",
            content_type="video/mp4",
        )

        anexo = portal_service._save_denuncia_media(denuncia, storage)

        self.assertTrue(captured["remote_path"].startswith("denuncias/77/video/denuncia_77_"))
        self.assertTrue(captured["remote_path"].endswith(".mp4"))
        self.assertEqual(captured["body"], b"video")
        self.assertEqual(anexo.arquivo_path, f"skybox://{captured['remote_path']}")
        self.assertEqual(anexo.tipo_midia, "video")

    def test_correios_address_payload_is_normalized(self):
        payload = cep_client._normalize_correios_address({
            "cep": "01001001",
            "uf": "SP",
            "localidade": "Sao Paulo",
            "logradouro": "Praca da Se",
            "complemento": "- lado par",
            "bairro": "Se",
        })

        self.assertEqual(payload["cep"], "01001-001")
        self.assertEqual(payload["logradouro"], "Praca da Se")
        self.assertEqual(payload["cidade"], "Sao Paulo")

    def test_health_news_fetches_only_official_health_items(self):
        class Response:
            content = b"""
                <rss><channel>
                  <item>
                    <title>Dengue tem nova orientacao de prevencao</title>
                    <link>https://www.saude.sp.gov.br/noticia/dengue-prevencao</link>
                    <description><![CDATA[Medidas contra o Aedes aegypti.]]></description>
                    <pubDate>Tue, 15 Sep 2026 12:00:00 GMT</pubDate>
                  </item>
                  <item>
                    <title>Agenda cultural da semana</title>
                    <link>https://www.saude.sp.gov.br/noticia/cultura</link>
                    <description>Programacao artistica da semana.</description>
                  </item>
                  <item>
                    <title>Dengue em portal nao oficial</title>
                    <link>https://example.com/dengue</link>
                    <description>Deve ser ignorado.</description>
                  </item>
                </channel></rss>
            """

            def raise_for_status(self):
                return None

        original_get = health_news.requests.get
        try:
            health_news.clear_health_news_cache()
            health_news.requests.get = lambda *args, **kwargs: Response()

            items = health_news.get_portal_health_news()

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["title"], "Dengue tem nova orientacao de prevencao")
            self.assertEqual(items[0]["source"], "Secretaria de Estado da Saúde de SP")
        finally:
            health_news.requests.get = original_get
            health_news.clear_health_news_cache()

    def test_health_news_uses_official_fallback_when_feed_fails(self):
        original_get = health_news.requests.get
        try:
            health_news.clear_health_news_cache()
            health_news.requests.get = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline"))

            items = health_news.get_portal_health_news()

            self.assertGreaterEqual(len(items), 1)
            self.assertEqual(items[0]["source"], "COVISA/SMS-SP")
            self.assertIn("prefeitura.sp.gov.br", items[0]["url"])
        finally:
            health_news.requests.get = original_get
            health_news.clear_health_news_cache()

    def test_infodengue_alert_normalizes_latest_epidemiological_week(self):
        rows = [
            {
                "SE": 202636,
                "casos": 8,
                "casos_est": 10.5,
                "p_inc100k": 2.25,
                "p_rt1": 0.61,
                "nivel": 1,
                "data_iniSE": 1788748800000,
            },
            {
                "SE": 202637,
                "casos": 12,
                "casos_est": 14.2,
                "p_inc100k": 3.1,
                "p_rt1": 0.73,
                "nivel": 2,
                "data_iniSE": 1789353600000,
            },
        ]

        alert = health_news._build_infodengue_alert(
            rows,
            city="São Paulo",
            disease="dengue",
            source_url="https://info.dengue.mat.br/api/alertcity?geocode=3550308",
        ).to_dict()

        self.assertEqual(alert["city"], "São Paulo")
        self.assertEqual(alert["disease"], "Dengue")
        self.assertEqual(alert["week_label"], "SE 37/2026")
        self.assertEqual(alert["alert_label"], "Atenção")
        self.assertEqual(alert["cases"], "12")
        self.assertEqual(alert["estimated_cases"], "14,2")
        self.assertEqual(alert["incidence"], "3,10")
        self.assertEqual(alert["probability_rt_above_1"], "73,0%")

    def test_infodengue_alert_returns_none_when_api_fails(self):
        original_get = health_news.requests.get
        try:
            health_news.clear_health_news_cache()
            health_news.requests.get = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline"))

            alert = health_news.get_infodengue_alert(config={})

            self.assertIsNone(alert)
        finally:
            health_news.requests.get = original_get
            health_news.clear_health_news_cache()

    def test_infodengue_report_builds_series_summary_and_peak(self):
        rows = [
            {
                "SE": 202601,
                "casos": 10,
                "casos_est": 12.5,
                "p_inc100k": 1.25,
                "p_rt1": 0.40,
                "nivel": 1,
                "data_iniSE": 1767225600000,
            },
            {
                "SE": 202602,
                "casos": 18,
                "casos_est": 25.2,
                "p_inc100k": 2.10,
                "p_rt1": 0.82,
                "nivel": 2,
                "data_iniSE": 1767830400000,
            },
        ]

        report = health_news._build_infodengue_report(
            rows,
            city="São Paulo",
            disease="dengue",
            year=2026,
            source_url="https://info.dengue.mat.br/api/alertcity?geocode=3550308",
        )

        self.assertEqual(report["city"], "São Paulo")
        self.assertEqual(report["disease_label"], "Dengue")
        self.assertEqual(report["summary"]["latest_week_label"], "SE 02/2026")
        self.assertEqual(report["summary"]["latest_alert_label"], "Atenção")
        self.assertEqual(report["summary"]["total_cases"], "28")
        self.assertEqual(report["summary"]["total_estimated_cases"], "37,7")
        self.assertEqual(report["summary"]["peak_week_label"], "SE 02/2026")
        self.assertEqual(len(report["series"]), 2)
        self.assertEqual(report["series"][1]["bar_percent"], 100)

    def test_infodengue_report_returns_none_when_api_fails(self):
        original_get = health_news.requests.get
        try:
            health_news.clear_health_news_cache()
            health_news.requests.get = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline"))

            report = health_news.get_infodengue_report(config={}, disease="dengue", year=2026)

            self.assertIsNone(report)
        finally:
            health_news.requests.get = original_get
            health_news.clear_health_news_cache()


if __name__ == "__main__":
    unittest.main()
