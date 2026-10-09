import unittest

from flask import Flask, jsonify, render_template_string, request
from flask_login import LoginManager, UserMixin, current_user, login_user

from app.shared.csrf_security import register_csrf_security, rotate_csrf_token


class DummyUser(UserMixin):
    id = 7


class CsrfSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="isolated-csrf-test-key-1234567890123456", TESTING=True,
                               CSRF_PROTECTION_ENABLED=True)
        manager = LoginManager(self.app)
        manager.user_loader(lambda user_id: DummyUser() if user_id == "7" else None)
        register_csrf_security(self.app)
        self.mutations = 0

        @self.app.route("/login", methods=["GET", "POST"], endpoint="auth.login")
        def login():
            if request.method == "GET":
                return render_template_string('<meta name="csrf-token" content="{{ csrf_token() }}">')
            login_user(DummyUser())
            rotate_csrf_token()
            return jsonify(ok=True)

        @self.app.post("/change")
        def change():
            if not current_user.is_authenticated:
                return jsonify(error="login required"), 401
            self.mutations += 1
            return jsonify(ok=True)

        @self.app.post("/public")
        def public():
            return jsonify(ok=True)

        self.client = self.app.test_client()

    def token(self):
        with self.client.session_transaction() as stored:
            return stored.get("_ija_csrf")

    def sign_in(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        initial_token = self.token()
        self.assertIn(initial_token.encode(), response.data)
        response = self.client.post("/login", data={"_csrf_token": initial_token})
        self.assertEqual(response.status_code, 200)
        return initial_token

    def test_missing_token_blocks_login(self):
        page = self.client.get("/login")
        self.assertIn("no-store", page.headers["Cache-Control"])
        self.assertEqual(self.client.post("/login").status_code, 403)

    def test_token_rotates_at_login_and_old_one_is_rejected(self):
        old_token = self.sign_in()
        new_token = self.token()
        self.assertNotEqual(old_token, new_token)
        self.assertEqual(self.client.post("/change", data={"_csrf_token": old_token}).status_code, 403)
        self.assertEqual(self.mutations, 0)
        self.assertEqual(self.client.post("/change", data={"_csrf_token": new_token}).status_code, 200)
        self.assertEqual(self.mutations, 1)

    def test_json_header_works_and_missing_header_returns_403_json(self):
        self.sign_in()
        self.assertEqual(self.client.post("/change", json={"a": 1}).status_code, 403)
        response = self.client.post("/change", json={"a": 1}, headers={"X-CSRFToken": self.token()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mutations, 1)

    def test_form_submission_works_with_standard_header(self):
        self.sign_in()
        response = self.client.post("/change", headers={"X-CSRF-Token": self.token()})
        self.assertEqual(response.status_code, 200)

    def test_invalid_token_cannot_execute_operation(self):
        self.sign_in()
        for supplied in ("", "wrong", "inválido"):
            self.assertEqual(self.client.post("/change", data={"_csrf_token": supplied}).status_code, 403)
        self.assertEqual(self.mutations, 0)

    def test_public_unauthenticated_post_remains_available(self):
        self.assertEqual(self.client.post("/public").status_code, 200)

    def test_disabled_flag_preserves_existing_behavior(self):
        self.app.config["CSRF_PROTECTION_ENABLED"] = False
        self.assertEqual(self.client.post("/login").status_code, 200)
        self.assertEqual(self.client.post("/change").status_code, 200)
        self.assertEqual(self.mutations, 1)

    def test_enabling_csrf_requires_a_stable_secret(self):
        other = Flask(__name__)
        other.config.update(SECRET_KEY="dev-short", CSRF_PROTECTION_ENABLED=True)
        with self.assertRaisesRegex(ValueError, "SECRET_KEY fixa"):
            register_csrf_security(other)


if __name__ == "__main__":
    unittest.main()
