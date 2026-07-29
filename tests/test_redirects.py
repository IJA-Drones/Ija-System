import unittest

from flask import Flask

from app.shared.redirects import get_safe_return_url


class SafeRedirectTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.add_url_rule("/admin", "admin_dashboard", lambda: "")

    def test_uses_internal_next_url_with_filters(self):
        with self.app.test_request_context(
            "/admin/atualizar/1",
            method="POST",
            data={"next": "/admin?status=PENDENTE&unidade=Centro&foco=Aedes"},
        ):
            self.assertEqual(
                get_safe_return_url("admin_dashboard"),
                "/admin?status=PENDENTE&unidade=Centro&foco=Aedes",
            )

    def test_uses_same_origin_referrer_when_next_is_missing(self):
        with self.app.test_request_context(
            "/admin/atualizar/1",
            method="POST",
            headers={"Referer": "http://localhost/admin?status=APROVADO"},
        ):
            self.assertEqual(
                get_safe_return_url("admin_dashboard"),
                "http://localhost/admin?status=APROVADO",
            )

    def test_rejects_external_next_url(self):
        with self.app.test_request_context(
            "/admin/atualizar/1",
            method="POST",
            data={"next": "https://evil.example/admin?status=PENDENTE"},
        ):
            self.assertEqual(get_safe_return_url("admin_dashboard"), "/admin")

    def test_rejects_protocol_relative_next_url(self):
        with self.app.test_request_context(
            "/admin/atualizar/1",
            method="POST",
            data={"next": "//evil.example/admin?status=PENDENTE"},
        ):
            self.assertEqual(get_safe_return_url("admin_dashboard"), "/admin")


if __name__ == "__main__":
    unittest.main()
