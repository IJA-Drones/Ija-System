"""Finance hub permissions and navigation, without a DB connection."""

import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, render_template_string
from flask_login import LoginManager, UserMixin, login_user

from app.modules.auth.routes import bp as auth_bp
from app.modules.auth.service import get_authenticated_redirect_endpoint
from app.modules.financeiro.service import build_financeiro_empresas
from app.routes import bp as main_bp


APP_DIR = Path(__file__).resolve().parents[1] / "app"


class FinanceUser(UserMixin):
    id = 7
    nome_uvis = "Equipe Financeiro"
    regiao = None
    prefeitura_id = None
    trabalha_oceano_azul = True

    def __init__(self, role="financeiro", trabalha_agro=True):
        self.tipo_usuario = role
        self.trabalha_agro = trabalha_agro


class FinanceiroCentralTests(unittest.TestCase):
    def setUp(self):
        self.user = FinanceUser()
        self.app = Flask(__name__, template_folder=str(APP_DIR / "templates"), static_folder=str(APP_DIR / "static"))
        self.app.config.update(TESTING=True, SECRET_KEY="isolated-finance-hub-test-secret-1234567890", SESSION_PROTECTION=None)
        manager = LoginManager(self.app)
        manager.login_view = "auth.login"
        manager.user_loader(lambda user_id: self.user if user_id == "7" else None)
        self.app.register_blueprint(auth_bp)
        self.app.register_blueprint(main_bp)
        self.client = self.app.test_client()

    def login(self, role="financeiro", trabalha_agro=True):
        self.user = FinanceUser(role, trabalha_agro)
        with self.client.session_transaction() as stored:
            stored["_user_id"] = "7"
            stored["_fresh"] = True

    def test_anonymous_users_must_log_in(self):
        for path in ("/financeiro", "/financeiro/empresas/ija"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.location)
                self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_global_admin_and_finance_roles_can_open_hub(self):
        for role in ("dev", "diretor", "admin", "financeiro_admin", "financeiro"):
            with self.subTest(role=role):
                self.login(role)
                response = self.client.get("/financeiro")
                self.assertEqual(response.status_code, 200)
                self.assertIn("Suas empresas", response.get_data(as_text=True))
                self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_other_roles_are_denied_before_building_companies(self):
        with patch("app.modules.financeiro.routes.build_financeiro_empresas") as companies:
            for role in ("piloto", "piloto_agro", "operario", "prefeitura_admin", "regional", "uvis"):
                self.login(role)
                for path in ("/financeiro", "/financeiro/empresas/ija"):
                    with self.subTest(role=role, path=path):
                        self.assertEqual(self.client.get(path).status_code, 403)
            companies.assert_not_called()

    def test_hub_initially_uses_one_company_with_marked_demo_cnpj(self):
        self.login()
        html = self.client.get("/financeiro").get_data(as_text=True)
        self.assertIn("11.111.111/0001-11", html)
        self.assertNotIn("22.222.222/0001-22", html)
        self.assertNotIn("Empresa Demonstrativa Ltda.", html)
        self.assertEqual(html.count("CNPJ fictício para demonstração"), 1)
        self.assertIn('href="/financeiro/empresas/ija"', html)
        self.assertNotIn('href="/financeiro/empresas/oa"', html)
        self.assertNotIn("Disponível em breve", html)

    def test_hub_and_company_do_not_change_selected_company_in_session(self):
        self.login()
        with self.client.session_transaction() as stored:
            original = dict(stored)
        self.assertEqual(self.client.get("/financeiro/empresas/ija").status_code, 200)
        self.assertEqual(self.client.get("/financeiro").status_code, 200)
        with self.client.session_transaction() as stored:
            self.assertEqual(dict(stored), original)

    def test_company_registration_is_visible_but_not_implemented(self):
        self.login("financeiro_admin")
        html = self.client.get("/financeiro").get_data(as_text=True)
        self.assertIn('disabled aria-describedby="finance-register-status"', html)
        self.assertIn("Cadastrar empresa", html)
        self.assertIn('id="finance-register-status">Em breve', html)
        self.assertNotIn("<form", html)

    def test_company_registration_is_reserved_for_finance_admin(self):
        for role in ("financeiro", "admin", "diretor", "dev"):
            with self.subTest(role=role):
                self.login(role)
                html = self.client.get("/financeiro").get_data(as_text=True)
                self.assertNotIn("Cadastrar empresa", html)

    def test_hub_and_workspace_support_multiple_company_entries(self):
        self.login()
        with self.app.app_context():
            companies = build_financeiro_empresas(self.user)
        companies.append({
            **companies[0], "slug": "empresa-teste", "nome": "Empresa de teste",
            "sigla": "ET", "razao_social": "Empresa de teste",
            "cnpj": "22222222000122", "cnpj_formatado": "22.222.222/0001-22",
        })
        with patch("app.modules.financeiro.routes.build_financeiro_empresas", return_value=companies):
            html = self.client.get("/financeiro").get_data(as_text=True)
            self.assertIn("2 empresas disponíveis", html)
            self.assertIn('href="/financeiro/empresas/empresa-teste"', html)
            response = self.client.get("/financeiro/empresas/empresa-teste")
            self.assertEqual(response.status_code, 200)
            self.assertIn("Empresa de teste", response.get_data(as_text=True))

    def test_ija_permission_preserves_existing_agro_work_flag(self):
        for role in ("admin", "financeiro_admin", "financeiro"):
            with self.subTest(role=role):
                self.login(role, trabalha_agro=False)
                html = self.client.get("/financeiro").get_data(as_text=True)
                self.assertNotIn('href="/financeiro/empresas/ija"', html)
                self.assertNotIn('data-admin-context="agro"', html)
                self.assertEqual(self.client.get("/financeiro/empresas/ija").status_code, 403)

    def test_company_workspace_is_empty_and_separate_from_operational_menus(self):
        self.login("dev")
        response = self.client.get("/financeiro/empresas/ija")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("O financeiro da IJA começa aqui.", html)
        self.assertIn("Trocar empresa", html)
        sidebar = html.split('id="appSidebar"', 1)[1].split('id="appContent"', 1)[0]
        self.assertIn("Empresas", sidebar)
        self.assertIn("Visão geral", sidebar)
        for old_menu in ("Notificações", "Ordens de Servico", "Mapas", "Caixa Diário", "Backups"):
            self.assertNotIn(old_menu, sidebar)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.assertNotIn("https://maps.googleapis.com/maps/api/js?", html)

    def test_existing_hubs_keep_operational_menus_and_maps_script(self):
        self.user = FinanceUser("diretor")
        with patch("app.core.templating.db.session") as stored:
            stored.query.side_effect = RuntimeError("No database in template regression test")
            for path, expected_menu in (("/admin", "Mapas"), ("/agro/admin", "Financeiro")):
                with self.subTest(path=path), self.app.test_request_context(path):
                    login_user(self.user)
                    html = render_template_string('{% extends "base.html" %}{% block content %}Teste{% endblock %}')
                    sidebar = html.split('id="appSidebar"', 1)[1].split('id="appContent"', 1)[0]
                    self.assertIn(expected_menu, sidebar)
                    self.assertIn("Central Financeiro", sidebar)
                    self.assertIn("https://maps.googleapis.com/maps/api/js?", html)

    def test_future_and_unknown_companies_cannot_be_opened_directly(self):
        self.login("dev")
        for slug in ("oa", "outra", "IJA"):
            with self.subTest(slug=slug):
                self.assertEqual(self.client.get(f"/financeiro/empresas/{slug}").status_code, 404)

    def test_company_identity_is_escaped(self):
        self.login()
        with self.app.app_context():
            companies = build_financeiro_empresas(self.user)
        companies[0]["razao_social"] = '<script>alert("teste")</script>'
        with patch("app.modules.financeiro.routes.build_financeiro_empresas", return_value=companies):
            for path in ("/financeiro", "/financeiro/empresas/ija"):
                with self.subTest(path=path):
                    html = self.client.get(path).get_data(as_text=True)
                    self.assertNotIn('<script>alert("teste")</script>', html)
                    self.assertIn("&lt;script&gt;", html)

    def test_finance_login_and_root_land_on_hub(self):
        for role in ("financeiro_admin", "financeiro"):
            for work_flag in (True, False):
                with self.subTest(role=role, trabalha_agro=work_flag):
                    self.login(role, work_flag)
                    self.assertEqual(get_authenticated_redirect_endpoint(self.user), "main.financeiro_central")
                    self.assertEqual(self.client.get("/").location, "/financeiro")
                    self.assertEqual(self.client.get("/login").location, "/financeiro")

    def test_finance_users_keep_access_to_existing_agro_entry(self):
        self.login()
        html = self.client.get("/financeiro").get_data(as_text=True)
        self.assertIn('data-admin-context="agro"', html)
        self.assertNotIn('data-admin-context="uvis_prefeitura"', html)
        self.assertEqual(self.client.get("/agro").location, "/agro/admin")

    def test_global_admins_can_switch_between_three_hubs(self):
        self.login("diretor")
        html = self.client.get("/financeiro").get_data(as_text=True)
        for context in ("uvis_prefeitura", "agro", "financeiro"):
            self.assertIn(f'data-admin-context="{context}"', html)
        self.assertIn('class="admin-context-btn is-active"\n                  data-admin-context="financeiro"', html)

    def test_views_do_not_accept_mutations(self):
        self.login()
        for path in ("/financeiro", "/financeiro/empresas/ija"):
            self.assertEqual(self.client.post(path).status_code, 405)


if __name__ == "__main__":
    unittest.main()
