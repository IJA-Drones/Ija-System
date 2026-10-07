"""HTTP checks in an isolated Flask app; no application DB or real create_app."""

import csv
import json
import re
import unittest
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

from flask import Blueprint, Flask
from flask_login import LoginManager, UserMixin
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

from app.modules.vigilancia import register_routes
from app.modules.vigilancia import routes
from app.modules.vigilancia.sample import build_sample_csv
from app.shared.csrf_security import CSRF_SESSION_KEY, register_csrf_security


class DummyUser(UserMixin):
    def __init__(self, user_id, role, prefeitura_id=None):
        self.id = user_id
        self.tipo_usuario = role
        self.prefeitura_id = prefeitura_id


class VigilanciaRoutesTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="isolated-vigilancia-test-key-1234567890123456",
            VIGILANCIA_PREVIEW_ENABLED=True,
            CSRF_PROTECTION_ENABLED=False,
        )
        self.users = {
            "global": DummyUser("global", "admin", 99),
            "municipal": DummyUser("municipal", "prefeitura_admin", 7),
            "unbound": DummyUser("unbound", "prefeitura_admin"),
            "regional": DummyUser("regional", "regional", 7),
            "uvis": DummyUser("uvis", "uvis", 7),
            "covisa": DummyUser("covisa", "covisa", 7),
        }
        manager = LoginManager(self.app)
        manager.user_loader(self.users.get)
        register_csrf_security(self.app)
        self.app.jinja_loader = DictLoader({
            "vigilancia_validacao.html": (
                '{{ prefeitura_id }}|{{ municipio_editavel }}|{{ layout_version }}|'
                '{{ preview_csrf_token }}|{{ erro or "" }}|{{ result|tojson }}|'
                '{{ csv_columns|join(",") }}'
            ),
        })
        bp = Blueprint("main", __name__)
        register_routes(bp)
        self.app.register_blueprint(bp)
        self.client = self.app.test_client()
        self.preview_result = {"status": "VALIDO", "linhas_validas": 1}
        self.real_preview = routes.preview_csv
        self.preview_patch = patch.object(routes, "preview_csv", return_value=self.preview_result)
        self.preview = self.preview_patch.start()
        self.addCleanup(self.preview_patch.stop)

    def login(self, user_id="municipal"):
        with self.client.session_transaction() as stored:
            stored["_user_id"] = user_id
            stored["_fresh"] = True

    def token(self):
        with self.client.session_transaction() as stored:
            return stored.get(CSRF_SESSION_KEY)

    def prepare(self, user_id="municipal", query=""):
        self.login(user_id)
        page = self.client.get("/vigilancia/validacao" + query)
        self.assertEqual(page.status_code, 200)
        return self.token()

    def upload(self, *, path="/api/vigilancia/validacao", content=b"csv body", filename="sample.csv", **form):
        form.setdefault("_csrf_token", self.token())
        form["arquivo"] = (BytesIO(content), filename)
        response = self.client.post(path, data=form)
        self.addCleanup(response.request.environ["wsgi.input"].close)
        return response

    def assert_no_store(self, response):
        self.assertEqual(response.headers.get("Cache-Control"), "private, no-store")

    def test_every_endpoint_requires_login(self):
        for path, method in (
            ("/vigilancia/validacao", "get"),
            ("/vigilancia/validacao", "post"),
            ("/api/vigilancia/validacao", "post"),
            ("/vigilancia/modelo.csv", "get"),
        ):
            with self.subTest(path=path, method=method):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 401)
                self.assert_no_store(response)
        self.preview.assert_not_called()

    def test_disabled_feature_returns_404_even_without_login(self):
        self.app.config["VIGILANCIA_PREVIEW_ENABLED"] = False
        for user_id in (None, "municipal"):
            if user_id:
                self.login(user_id)
            for path, method in (
                ("/vigilancia/validacao", "get"),
                ("/vigilancia/validacao", "post"),
                ("/api/vigilancia/validacao", "post"),
                ("/vigilancia/modelo.csv", "get"),
            ):
                with self.subTest(user=user_id, path=path, method=method):
                    response = getattr(self.client, method)(path)
                    self.assertEqual(response.status_code, 404)
                    self.assert_no_store(response)
        self.preview.assert_not_called()

    def test_other_roles_are_denied_before_service(self):
        for user_id in ("regional", "uvis", "covisa"):
            self.login(user_id)
            for path, method in (
                ("/vigilancia/validacao", "get"),
                ("/api/vigilancia/validacao", "post"),
                ("/vigilancia/modelo.csv", "get"),
            ):
                with self.subTest(user=user_id, path=path):
                    response = getattr(self.client, method)(path)
                    self.assertEqual(response.status_code, 403)
                    self.assert_no_store(response)
        self.preview.assert_not_called()

    def test_municipal_user_without_link_is_denied(self):
        self.login("unbound")
        self.assertEqual(self.client.get("/vigilancia/validacao").status_code, 403)
        response = self.client.post("/api/vigilancia/validacao", data={"prefeitura_id": "7"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.get_json())
        self.assertEqual(self.client.get("/vigilancia/modelo.csv?prefeitura_id=7").status_code, 403)
        self.preview.assert_not_called()

    def test_municipal_scope_comes_from_login(self):
        token = self.prepare()
        page = self.client.get("/vigilancia/validacao")
        self.assertIn(b"7|False|", page.data)
        self.assertIn(token.encode(), page.data)
        self.assert_no_store(page)
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), self.preview_result)
        self.preview.assert_called_once_with(b"csv body", prefeitura_id=7)
        self.assert_no_store(response)

    def test_municipal_user_cannot_override_scope_in_form_or_query(self):
        self.prepare()
        for query, form in (
            ("", {"prefeitura_id": "8"}),
            ("?prefeitura_id=8", {}),
            ("?prefeitura_id=8", {"prefeitura_id": "7"}),
            ("", {"prefeitura_id": "0"}),
        ):
            with self.subTest(query=query, form=form):
                response = self.upload(path="/api/vigilancia/validacao" + query, **form)
                self.assertEqual(response.status_code, 403)
                self.assertIn("error", response.get_json())
                self.assert_no_store(response)
        self.assertEqual(self.client.get("/vigilancia/modelo.csv?prefeitura_id=8").status_code, 403)
        self.preview.assert_not_called()

    def test_global_page_does_not_invent_a_municipality(self):
        self.prepare("global")
        response = self.client.get("/vigilancia/validacao")
        self.assertIn(b"None|True|", response.data)
        self.assert_no_store(response)

    def test_global_upload_requires_explicit_positive_municipality(self):
        self.prepare("global")
        for form in ({}, {"prefeitura_id": "0"}, {"prefeitura_id": "-7"}, {"prefeitura_id": "abc"}):
            with self.subTest(form=form):
                response = self.upload(**form)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())
        self.assertEqual(self.client.get("/vigilancia/modelo.csv").status_code, 400)
        self.preview.assert_not_called()
        response = self.upload(prefeitura_id="12")
        self.assertEqual(response.status_code, 200)
        self.preview.assert_called_once_with(b"csv body", prefeitura_id=12)

    def test_global_query_scope_works_and_conflicting_parameters_fail(self):
        self.prepare("global")
        response = self.upload(path="/api/vigilancia/validacao?prefeitura_id=12")
        self.assertEqual(response.status_code, 200)
        self.preview.assert_called_once_with(b"csv body", prefeitura_id=12)
        self.preview.reset_mock()
        response = self.upload(path="/api/vigilancia/validacao?prefeitura_id=12", prefeitura_id="13")
        self.assertEqual(response.status_code, 400)
        self.preview.assert_not_called()

    def test_ids_beyond_integer_range_are_rejected_on_get_post_and_download(self):
        self.prepare("global")
        for value in (str(routes.MAX_PREFEITURA_ID + 1), "9" * 5000):
            with self.subTest(value_length=len(value)):
                response = self.client.get("/vigilancia/validacao", query_string={"prefeitura_id": value})
                self.assertEqual(response.status_code, 400)
                self.assert_no_store(response)
                response = self.client.get("/vigilancia/modelo.csv", query_string={"prefeitura_id": value})
                self.assertEqual(response.status_code, 400)
                self.assert_no_store(response)
                response = self.upload(prefeitura_id=value)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())
        self.preview.assert_not_called()
        response = self.client.get("/vigilancia/modelo.csv", query_string={"prefeitura_id": routes.MAX_PREFEITURA_ID})
        self.assertEqual(response.status_code, 200)

    def test_municipal_account_with_invalid_integer_scope_fails_closed(self):
        self.users["municipal"].prefeitura_id = routes.MAX_PREFEITURA_ID + 1
        self.login()
        for path in ("/vigilancia/validacao", "/vigilancia/modelo.csv"):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post("/api/vigilancia/validacao").status_code, 403)
        self.preview.assert_not_called()

    def test_html_post_renders_result_and_missing_upload_error(self):
        self.prepare()
        response = self.upload(path="/vigilancia/validacao")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"status": "VALIDO"', response.data)
        self.assert_no_store(response)
        response = self.client.post("/vigilancia/validacao", data={"_csrf_token": self.token()})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Selecione um arquivo CSV".encode(), response.data)
        self.assert_no_store(response)

    def test_missing_upload_and_wrong_extension_are_400(self):
        self.prepare()
        response = self.client.post("/api/vigilancia/validacao", data={"_csrf_token": self.token()})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())
        response = self.upload(filename="sample.xlsx")
        self.assertEqual(response.status_code, 400)
        self.preview.assert_not_called()

    def test_oversized_upload_is_413_before_service(self):
        self.prepare()
        response = self.upload(content=b"x" * (routes.MAX_FILE_BYTES + 1))
        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.get_json())
        self.assert_no_store(response)
        self.preview.assert_not_called()

    def test_structural_service_error_is_400_in_html_and_json(self):
        self.prepare()
        self.preview.side_effect = routes.PreviewValidationError("Cabeçalho inválido.", codigo="CABECALHO_INVALIDO", linha=1)
        response = self.upload()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "Cabeçalho inválido."})
        self.assert_no_store(response)
        response = self.upload(path="/vigilancia/validacao")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Cabeçalho inválido.".encode(), response.data)
        self.assert_no_store(response)

    def test_real_synthetic_sample_can_be_previewed_without_db(self):
        self.prepare()
        with patch.object(routes, "preview_csv", self.real_preview):
            response = self.upload(content=build_sample_csv(7))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("error", response.get_json())
        self.assert_no_store(response)

    def test_real_template_renders_sample_counts_percentage_json_and_escapes_csv(self):
        template_directory = Path(__file__).resolve().parents[1] / "app" / "templates"
        self.app.jinja_loader = ChoiceLoader([
            DictLoader({"base.html": "{% block extra_styles %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}"}),
            FileSystemLoader(str(template_directory)),
        ])
        self.prepare()
        with patch.object(routes, "preview_csv", self.real_preview):
            response = self.upload(path="/vigilancia/validacao", content=build_sample_csv(7))
            self.assertEqual(response.status_code, 200)
            page = response.get_data(as_text=True)
            self.assertIn("33,33%", page)
            for label, count in (("Linhas", 5), ("Aceitas", 5), ("Duplicadas", 0), ("Rejeitadas", 0)):
                self.assertIn(f"<dt>{label}</dt><dd>{count}</dd>", page)
            self.assertIn('id="download-report"', page)
            embedded = re.search(r'<script type="application/json" id="preview-report">(.*?)</script>', page, re.DOTALL)
            self.assertIsNotNone(embedded)
            exported = json.loads(embedded.group(1))
            self.assertEqual(exported["indicadores"][0]["iip"], 33.33)
            self.assertEqual(exported["resumo"]["aceitas"], 5)

            payload = '<script>alert("preview")</script>'
            content = build_sample_csv(7).replace("Bairro Sintético — Exemplo".encode(), payload.encode())
            response = self.upload(path="/vigilancia/validacao", content=content)
            self.assertEqual(response.status_code, 200)
            page = response.get_data(as_text=True)
            self.assertNotIn(payload, page)
            self.assertIn("&lt;script&gt;alert(&#34;preview&#34;)&lt;/script&gt;", page)
            embedded = re.search(r'<script type="application/json" id="preview-report">(.*?)</script>', page, re.DOTALL)
            self.assertIsNotNone(embedded)
            self.assertIn(r"\u003cscript\u003e", embedded.group(1))
            self.assertEqual(json.loads(embedded.group(1))["registros"][0]["bairro"], payload)
            self.assert_no_store(response)

    def test_csrf_is_required_even_when_global_protection_is_disabled(self):
        self.prepare()
        for value in ("", "wrong", "inválido"):
            with self.subTest(value=value):
                response = self.upload(_csrf_token=value)
                self.assertEqual(response.status_code, 403)
                self.assertIn("error", response.get_json())
                self.assert_no_store(response)
        self.preview.assert_not_called()

    def test_post_without_a_get_token_is_denied(self):
        self.login()
        response = self.upload(_csrf_token="forged")
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.token())
        self.preview.assert_not_called()

    def test_csrf_header_and_existing_shared_token_work_without_rotation(self):
        self.login()
        with self.client.session_transaction() as stored:
            stored[CSRF_SESSION_KEY] = "existing-shared-token"
        self.client.get("/vigilancia/validacao")
        self.assertEqual(self.token(), "existing-shared-token")
        response = self.client.post(
            "/api/vigilancia/validacao",
            data={"arquivo": (BytesIO(b"csv body"), "sample.csv")},
            headers={"X-CSRFToken": self.token()},
        )
        self.assertEqual(response.status_code, 200)
        self.preview.assert_called_once_with(b"csv body", prefeitura_id=7)

    def test_shared_token_is_compatible_with_enabled_global_csrf(self):
        self.app.config["CSRF_PROTECTION_ENABLED"] = True
        self.prepare()
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assert_no_store(response)
        self.preview.reset_mock()
        response = self.upload(_csrf_token="wrong")
        self.assertEqual(response.status_code, 403)
        self.assert_no_store(response)
        self.preview.assert_not_called()

    def test_download_is_synthetic_scoped_and_not_cached(self):
        self.login()
        response = self.client.get("/vigilancia/modelo.csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertLessEqual(len(response.data), routes.MAX_FILE_BYTES)
        parsed = list(csv.DictReader(StringIO(response.data.decode("utf-8-sig"))))
        self.assertTrue(parsed)
        self.assertEqual({row["municipio_id"] for row in parsed}, {"7"})
        self.assertEqual(response.data, build_sample_csv(7))
        self.assert_no_store(response)
        self.preview.assert_not_called()

    def test_global_download_uses_the_explicit_scope(self):
        self.login("global")
        response = self.client.get("/vigilancia/modelo.csv?prefeitura_id=12")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, build_sample_csv(12))
        self.assert_no_store(response)


if __name__ == "__main__":
    unittest.main()
