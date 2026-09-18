import math
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, jsonify
from flask_login import LoginManager, UserMixin, login_required
from werkzeug.security import generate_password_hash

from app.models import Usuario
from app.modules.auth.routes import bp as auth_bp
from app.modules.admin_uvis import service as uvis_service
from app.modules.equipes import service as equipes_service
from app.modules.usuarios import service as usuarios_service
from app.modules.uvis_equipes.service import validate_team_password
from app.shared.password_policy import PasswordPolicyError, password_input, validate_password
from app.shared.session_security import SESSION_KEY, register_session_security


STRONG_PASSWORD = "Minha frase segura 7!"


class TestUser(UserMixin):
    __test__ = False
    id = 7
    tipo_usuario = "admin"
    nome_uvis = "Usuário teste"
    trabalha_agro = False


class SessionSecurityTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.now = 10000.0
        self.stack.enter_context(patch("app.shared.session_security.time.time", side_effect=lambda: self.now))
        self.user = TestUser()
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="isolated-test-key-for-security-tests-1234", TESTING=True, SECURITY_CONTROLS_ENABLED=True,
                               SESSION_IDLE_TIMEOUT_MINUTES=1)
        manager = LoginManager(self.app)
        manager.login_view = "auth.login"
        manager.user_loader(lambda user_id: self.user if user_id == "7" else None)
        register_session_security(self.app)
        self.app.register_blueprint(auth_bp)
        self.mutations = 0

        @self.app.route("/protected", methods=["GET", "POST"], endpoint="main.admin_dashboard")
        @login_required
        def protected():
            from flask import request
            if request.method == "POST":
                self.mutations += 1
            return jsonify(ok=True)

        self.app.add_url_rule("/uvis-home", "main.dashboard_equipe_uvis", lambda: "uvis")
        self.app.add_url_rule("/agro-home", "main.agro_piloto_dashboard", lambda: "agro")
        self.app.add_url_rule("/healthz", "health", lambda: "ok")
        self.stack.enter_context(patch("app.modules.auth.routes.authenticate_user", return_value=self.user))
        self.stack.enter_context(patch("app.modules.auth.routes.authenticate_uvis_operacional", return_value=self.user))
        self.stack.enter_context(patch("app.modules.auth.routes.authenticate_piloto_agro", return_value=(self.user, None)))
        self.presence = self.stack.enter_context(patch("app.modules.auth.routes.record_user_presence"))
        self.client = self.app.test_client()
        self.sign_in()

    def sign_in(self, client=None, path="/login"):
        response = (client or self.client).post(path, data={"login": "existing", "senha": "1234"})
        self.assertEqual(response.status_code, 302)

    def state(self, client=None):
        with (client or self.client).session_transaction() as stored:
            return dict(stored.get(SESSION_KEY, {}))

    def activity(self, client=None, token=None):
        client = client or self.client
        token = self.state(client)["csrf"] if token is None else token
        return client.post("/auth/session-activity", headers={"X-Session-CSRF": token})

    def test_all_three_login_flows_initialize_session(self):
        for path in ("/login", "/uvis-operacional/login", "/agro/login"):
            with self.subTest(path=path):
                client = self.app.test_client()
                self.sign_in(client, path)
                self.assertEqual(self.state(client)["last_activity"], self.now)
                self.assertTrue(self.state(client)["csrf"])

    def test_expired_post_cannot_execute_operation(self):
        self.now += 60
        response = self.client.post("/protected")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.mutations, 0)
        with self.client.session_transaction() as stored:
            self.assertNotIn("_user_id", stored)

    def test_active_post_still_works(self):
        self.now += 59
        self.assertEqual(self.client.post("/protected").status_code, 200)
        self.assertEqual(self.mutations, 1)

    def test_background_requests_and_status_do_not_renew_session(self):
        initial = self.state()
        for _ in range(3):
            self.now += 15
            response = self.client.get("/auth/session-status")
            self.assertEqual(response.status_code, 200)
            self.client.get("/protected", headers={"Sec-Fetch-Dest": "empty", "Accept": "*/*"})
            self.assertEqual(self.state(), initial)
        self.assertEqual(response.json["expires_in"], 15)
        self.now += 15
        self.assertEqual(self.client.get("/auth/session-status").status_code, 401)
        self.assertEqual(self.presence.call_count, 1)  # Only the login records presence.

    def test_html_navigation_renews_without_javascript(self):
        self.now += 45
        self.client.get("/protected", headers={"Sec-Fetch-Mode": "navigate"})
        self.now += 30
        self.assertEqual(self.client.get("/protected").status_code, 200)

    def test_activity_renews_with_csrf_and_rejects_invalid_tokens(self):
        self.now += 30
        previous = self.state()
        for token in ("", "invalid", "inválido"):
            self.assertEqual(self.activity(token=token).status_code, 403)
            self.assertEqual(self.state(), previous)
        self.assertEqual(self.activity().status_code, 200)
        self.assertEqual(self.state()["last_activity"], self.now)

    def test_expired_activity_cannot_resurrect_session(self):
        token = self.state()["csrf"]
        self.now += 61
        self.assertEqual(self.activity(token=token).status_code, 401)
        self.assertEqual(self.state(), {})

    def test_absolute_lifetime_cannot_be_renewed_by_activity(self):
        self.app.config["SESSION_IDLE_TIMEOUT_MINUTES"] = 30
        self.app.config["SESSION_MAX_LIFETIME_HOURS"] = 1
        for _ in range(4):
            self.now += 850
            response = self.activity()
            self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["absolute"])
        self.now = self.state()["created_at"] + 3600
        self.assertEqual(self.activity().status_code, 401)
        self.assertEqual(self.state(), {})

    def test_api_expiry_returns_json_instead_of_html(self):
        self.now += 61
        response = self.client.post("/protected", json={"value": 1})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["code"], "session_expired")
        self.assertEqual(self.mutations, 0)

    def test_expiry_returns_to_original_login(self):
        for path in ("/uvis-operacional/login", "/agro/login"):
            client = self.app.test_client()
            self.sign_in(client, path)
            self.now += 61
            self.assertEqual(client.get("/protected").location, path)

    def test_independent_browser_sessions_for_same_user(self):
        other = self.app.test_client()
        self.sign_in(other)
        self.now += 45
        self.activity(other)
        self.now += 16
        self.assertEqual(self.client.get("/protected").status_code, 303)
        self.assertEqual(other.get("/protected").status_code, 200)

    def test_replayed_expired_cookie_is_rejected(self):
        cookie = self.client.get_cookie("session").value
        self.now += 61
        self.client.get("/protected")
        self.client.set_cookie("session", cookie)
        self.assertEqual(self.client.get("/protected").status_code, 303)

    def test_missing_or_invalid_session_requires_new_login(self):
        for timestamp in (None, "invalid", math.nan, math.inf, self.now + 100):
            with self.subTest(timestamp=timestamp):
                client = self.app.test_client()
                self.sign_in(client)
                with client.session_transaction() as stored:
                    if timestamp is None:
                        stored.pop(SESSION_KEY)
                    else:
                        stored[SESSION_KEY] = {**stored[SESSION_KEY], "last_activity": timestamp}
                self.assertEqual(client.get("/protected").status_code, 303)

    def test_invalid_creation_time_requires_new_login(self):
        with self.client.session_transaction() as stored:
            stored[SESSION_KEY] = {**stored[SESSION_KEY], "created_at": self.now + 100}
        self.assertEqual(self.client.get("/protected").status_code, 303)

    def test_disabled_controls_preserve_existing_sessions(self):
        self.app.config["SECURITY_CONTROLS_ENABLED"] = False
        with self.client.session_transaction() as stored:
            stored.pop(SESSION_KEY)
        self.now += 10000
        self.assertEqual(self.client.post("/protected").status_code, 200)
        self.assertEqual(self.client.get("/auth/session-status").status_code, 404)

    def test_logout_and_public_health_still_work(self):
        self.assertEqual(self.client.get("/logout").status_code, 302)
        self.assertEqual(self.state(), {})
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/auth/session-status").status_code, 401)

    def test_sensitive_responses_are_not_cached(self):
        self.assertEqual(self.client.get("/protected").headers["Cache-Control"], "no-store")


class PasswordPolicyTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECURITY_CONTROLS_ENABLED=True)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)

    def test_length_and_each_composition_rule(self):
        for password in ("Abc1!", "minha frase segura 7!", "MINHA FRASE SEGURA 7!",
                         "Minha frase segura !", "Minha frase segura 7", "A" * 129 + "a1!"):
            with self.subTest(password=password):
                self.assertIsNotNone(validate_password(password))
        self.assertIsNone(validate_password(STRONG_PASSWORD))
        self.assertIsNone(validate_password("Árvore azul ٧! " + "x" * 60))

    def test_obvious_common_passwords_are_rejected(self):
        for password in ("Password123456!", "Senha123456789!", "OceanoAzul12345!"):
            with self.subTest(password=password):
                self.assertIn("previsível", validate_password(password))

    def test_composition_and_length_are_configurable(self):
        self.app.config.update(PASSWORD_MIN_LENGTH=20, PASSWORD_REQUIRE_UPPERCASE=False,
                               PASSWORD_REQUIRE_DIGIT=False, PASSWORD_REQUIRE_SYMBOL=False)
        self.assertIsNone(validate_password("uma frase longa para acesso"))
        self.assertIsNotNone(validate_password("uma frase curta"))

    def test_model_cannot_bypass_policy_and_keeps_previous_hash_on_failure(self):
        user = Usuario(senha_hash="original")
        with self.assertRaises(PasswordPolicyError):
            user.set_senha("1234")
        self.assertEqual(user.senha_hash, "original")
        user.set_senha(STRONG_PASSWORD)
        self.assertTrue(user.check_senha(STRONG_PASSWORD))

    def test_existing_weak_password_still_authenticates(self):
        user = Usuario(senha_hash=generate_password_hash("1234"))
        self.assertTrue(user.check_senha("1234"))

    def test_spaces_are_preserved_with_policy_and_legacy_behavior_when_disabled(self):
        self.assertEqual(password_input(" senha "), " senha ")
        self.app.config["SECURITY_CONTROLS_ENABLED"] = False
        self.assertEqual(password_input(" senha "), "senha")
        self.assertIsNone(validate_password("1234"))

    def test_admin_create_edit_and_reset_reject_weak_password(self):
        with patch.object(usuarios_service, "login_em_uso", return_value=None):
            created = usuarios_service.validate_new_admin_user("Nome", "login", "admin", "", None, "1234", "1234")
            edited = usuarios_service.validate_edit_admin_user("Nome", "login", "admin", "", None, "1234", "1234", 1)
            unchanged = usuarios_service.validate_edit_admin_user("Nome", "login", "admin", "", None, "", "", 1)
        self.assertIn("senha", created)
        self.assertIn("senha", edited)
        self.assertNotIn("senha", unchanged)
        self.assertIsNotNone(usuarios_service.validate_password_reset("1234", "1234"))

    def test_uvis_and_both_team_validators_reject_weak_password(self):
        with patch.object(uvis_service, "login_em_uso", return_value=None):
            self.assertIsNotNone(uvis_service.validate_new_uvis("Nome", "login", "123456", "123456")[1])
            self.assertIsNotNone(uvis_service.validate_edit_uvis("Nome", "login", "123456", "123456", 1)[1])
        self.assertIn("senha", validate_team_password("123456", "123456", required=True))
        self.assertEqual(validate_team_password("", "", required=False), {})
        with patch.object(equipes_service, "login_em_uso", return_value=None):
            self.assertIn("senha", equipes_service.validate_equipe_account_form("login", "123456", "123456"))
            self.assertEqual(equipes_service.validate_equipe_account_form("login", "", "", SimpleNamespace(id=1)), {})

    def test_agro_validator_rejects_weak_password_before_saving(self):
        from app.modules.agro.routes import _normalize_piloto_form, _validate_piloto_agro_form
        form = _normalize_piloto_form({"nome": "Piloto", "login": "piloto", "senha": "123456", "confirmar_senha": "123456"})
        with patch("app.modules.agro.routes.Usuario") as users:
            users.query.filter.return_value.first.return_value = None
            errors, *_ = _validate_piloto_agro_form(form, [])
        self.assertIn("senha", errors)

    def test_invalid_enabled_configuration_is_rejected_early(self):
        for name, value in (("SESSION_IDLE_TIMEOUT_MINUTES", "0"), ("SESSION_IDLE_TIMEOUT_MINUTES", "abc"),
                            ("SESSION_MAX_LIFETIME_HOURS", "0"),
                            ("PASSWORD_MIN_LENGTH", "7"), ("PASSWORD_MIN_LENGTH", "129")):
            with self.subTest(name=name, value=value):
                app = Flask(__name__)
                app.config.update(SECRET_KEY="isolated-test-key-for-security-tests-1234", SECURITY_CONTROLS_ENABLED=True)
                app.config[name] = value
                with self.assertRaises(ValueError):
                    register_session_security(app)

    def test_generated_development_secret_is_not_accepted(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY="dev-generated", SECURITY_CONTROLS_ENABLED=True)
        with self.assertRaisesRegex(ValueError, "SECRET_KEY"):
            register_session_security(app)

    def test_short_secret_is_not_accepted(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY="1234", SECURITY_CONTROLS_ENABLED=True)
        with self.assertRaisesRegex(ValueError, "SECRET_KEY"):
            register_session_security(app)

    def test_empty_login_credentials_do_not_reach_password_hash(self):
        from app.modules.auth.service import authenticate_user
        with patch("app.modules.auth.service.Usuario") as users:
            self.assertIsNone(authenticate_user("someone", None))
            self.assertIsNone(authenticate_user("", "password"))
            users.query.filter_by.assert_not_called()
