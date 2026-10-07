"""Finance hub permissions and navigation, without a DB connection."""

import unittest
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask, Response, render_template_string
from flask_login import LoginManager, UserMixin, login_user

from app.extensions import db
from app.models import FinanceiroEmpresaPerfil, ClienteAgro, OrcamentoAgro, ContratoAgro
from app.modules.auth.routes import bp as auth_bp
from app.modules.auth.service import get_authenticated_redirect_endpoint
from app.modules.financeiro.service import build_financeiro_empresas
from app.modules.agro.service import can_access_agro_panel, can_edit_agro_finance_panel, can_manage_agro_finance_settings
from app.shared.financeiro_navigation import is_financeiro_legacy_endpoint, is_financeiro_settings_endpoint
from app.shared.csrf_security import register_csrf_security
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
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        db.init_app(self.app)
        with self.app.app_context():
            FinanceiroEmpresaPerfil.__table__.create(db.engine)
        manager = LoginManager(self.app)
        manager.login_view = "auth.login"
        manager.user_loader(lambda user_id: self.user if user_id == "7" else None)
        self.app.register_blueprint(auth_bp)
        self.app.register_blueprint(main_bp)
        self.client = self.app.test_client()
        self.logo_files = {}
        def upload(storage, path):
            marker = "skybox://" + path
            self.logo_files[marker] = storage.stream.read()
            return marker
        def stream(path, *args, **kwargs):
            return Response(self.logo_files[path], mimetype="image/png")
        def delete(path):
            self.logo_files.pop(path, None)
        for target, handler in (("app.modules.financeiro.logos.upload_file_to_skybox", upload),
                                ("app.modules.financeiro.routes.stream_skybox_file", stream),
                                ("app.modules.financeiro.logos.delete_skybox_file", delete)):
            patcher = patch(target, side_effect=handler)
            patcher.start()
            self.addCleanup(patcher.stop)

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

    def test_finance_and_dev_roles_can_open_hub(self):
        for role in ("financeiro_admin", "financeiro", "admin", "dev"):
            with self.subTest(role=role):
                self.login(role)
                response = self.client.get("/financeiro")
                self.assertEqual(response.status_code, 200)
                self.assertIn("Suas empresas", response.get_data(as_text=True))
                self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_other_roles_are_denied_before_building_companies(self):
        with patch("app.modules.financeiro.routes.build_financeiro_empresas") as companies:
            for role in ("diretor", "piloto", "piloto_agro", "operario", "prefeitura_admin", "regional", "uvis"):
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
        for role in ("financeiro_admin", "admin", "dev"):
            with self.subTest(role=role):
                self.login(role)
                html = self.client.get("/financeiro").get_data(as_text=True)
                self.assertIn('disabled aria-describedby="finance-register-status"', html)
                self.assertIn("Cadastrar empresa", html)
                self.assertIn('id="finance-register-status">Em breve', html)
                self.assertNotIn("<form", html)

    def test_company_registration_preview_is_reserved_for_finance_admin_and_dev(self):
        for role in ("financeiro", "diretor"):
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
            self.assertNotIn('href="/agro/financeiro/contas"', response.get_data(as_text=True))

    def test_finance_company_does_not_require_operational_agro_work_flag(self):
        for role in ("financeiro_admin", "financeiro"):
            with self.subTest(role=role):
                self.login(role, trabalha_agro=False)
                html = self.client.get("/financeiro").get_data(as_text=True)
                self.assertIn('href="/financeiro/empresas/ija"', html)
                self.assertNotIn('data-admin-context="agro"', html)
                self.assertIn('data-admin-context="financeiro"', html)
                self.assertEqual(self.client.get("/financeiro/empresas/ija").status_code, 200)
                self.assertFalse(can_access_agro_panel(self.user))

    def test_dev_can_validate_company_without_operational_agro_work_flag(self):
        self.login("dev", trabalha_agro=False)
        self.assertFalse(can_access_agro_panel(self.user))
        self.assertEqual(get_authenticated_redirect_endpoint(self.user), "main.dev_dashboard")
        self.assertEqual(self.client.get("/login").location, "/dev")
        html = self.client.get("/financeiro").get_data(as_text=True)
        self.assertIn('href="/financeiro/empresas/ija"', html)
        response = self.client.get("/financeiro/empresas/ija")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('href="/agro/financeiro/configuracoes"', html)
        self.assertIn('href="/agro/financeiro/categorias"', html)
        # The finance exception does not grant operational Agro access.
        self.assertEqual(self.client.get("/agro/admin").status_code, 403)

    def test_company_workspace_contains_financial_tabs_and_no_operational_menus(self):
        self.login("financeiro_admin")
        response = self.client.get("/financeiro/empresas/ija")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Funcionalidades financeiras", html)
        self.assertIn("Trocar empresa", html)
        self.assertIn("Central Financeiro</span>", html)
        self.assertNotIn('class="navbar-logo', html)
        sidebar = html.split('id="appSidebar"', 1)[1].split('id="appContent"', 1)[0]
        self.assertIn("Empresas", sidebar)
        self.assertIn("Visão geral", sidebar)
        for finance_menu in ("Clientes", "Comercial", "Contas", "Recebíveis", "Contas a Pagar", "Caixa Diário", "Bancos", "Configurações", "Categorias"):
            self.assertIn(finance_menu, sidebar)
        for old_menu in ("Notificações", "Ordens de Servico", "Mapas", "Backups"):
            self.assertNotIn(old_menu, sidebar)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.assertNotIn("https://maps.googleapis.com/maps/api/js?", html)

    def test_existing_hubs_keep_operational_menus_and_maps_script(self):
        self.user = FinanceUser("diretor")
        with patch("app.core.templating.db.session") as stored:
            stored.query.side_effect = RuntimeError("No database in template regression test")
            for path, expected_menu in (("/admin", "Mapas"), ("/agro/admin", "Comercial")):
                with self.subTest(path=path), self.app.test_request_context(path):
                    login_user(self.user)
                    html = render_template_string('{% extends "base.html" %}{% block content %}Teste{% endblock %}')
                    sidebar = html.split('id="appSidebar"', 1)[1].split('id="appContent"', 1)[0]
                    self.assertIn(expected_menu, sidebar)
                    self.assertNotIn("Central Financeiro", sidebar)
                    self.assertNotIn("menuFinanceiroAgro", sidebar)
                    self.assertNotIn('href="/agro/financeiro', sidebar)
                    self.assertIn("https://maps.googleapis.com/maps/api/js?", html)
                    self.assertIn('class="navbar-logo', html)

    def test_future_and_unknown_companies_cannot_be_opened_directly(self):
        self.login()
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

    def test_finance_users_enter_their_own_central(self):
        self.login()
        html = self.client.get("/financeiro").get_data(as_text=True)
        self.assertIn('data-admin-context="financeiro"', html)
        self.assertNotIn('data-admin-context="agro"', html)
        self.assertNotIn('data-admin-context="uvis_prefeitura"', html)
        self.assertEqual(self.client.get("/agro").status_code, 403)
        self.assertEqual(self.client.get("/agro/admin").status_code, 403)

    def test_finance_central_is_in_context_selector_for_authorized_profiles(self):
        with patch("app.core.templating.db.session") as stored:
            stored.query.side_effect = RuntimeError("No database in navigation test")
            for role in ("admin", "diretor", "dev", "financeiro_admin", "financeiro"):
                self.user = FinanceUser(role)
                for path in ("/admin", "/agro/clientes"):
                    with self.subTest(role=role, path=path), self.app.test_request_context(path):
                        login_user(self.user)
                        html = render_template_string('{% extends "base.html" %}{% block content %}Teste{% endblock %}')
                        sidebar = html.split('id="appSidebar"', 1)[1].split('id="appContent"', 1)[0]
                        self.assertNotIn("Central Financeiro", sidebar)
                        if role in {"financeiro_admin", "financeiro"}:
                            self.assertIn('href="/financeiro"', sidebar)
                            self.assertNotIn('href="/agro', sidebar)
                            self.assertNotIn('href="/mapa-relatorio', sidebar)
                        else:
                            self.assertNotIn('href="/financeiro', sidebar)
                        self.assertEqual('data-admin-context="financeiro"' in html,
                                         role in {"admin", "dev", "financeiro_admin", "financeiro"})

    def test_global_admins_keep_original_hubs_without_finance_access(self):
        self.user = FinanceUser("diretor")
        with patch("app.core.templating.db.session") as stored, self.app.test_request_context("/admin"):
            stored.query.side_effect = RuntimeError("No database in navigation test")
            login_user(self.user)
            html = render_template_string('{% extends "base.html" %}{% block content %}Teste{% endblock %}')
            for context in ("uvis_prefeitura", "agro"):
                self.assertIn(f'data-admin-context="{context}"', html)
            self.assertNotIn('data-admin-context="financeiro"', html)

    def test_admin_can_access_three_centrals_without_work_flag(self):
        self.login("admin", trabalha_agro=False)
        self.assertTrue(can_access_agro_panel(self.user))
        self.assertEqual(get_authenticated_redirect_endpoint(self.user), "main.admin_dashboard")
        self.assertEqual(self.client.get("/financeiro").status_code, 200)
        self.assertEqual(self.client.get("/financeiro/empresas/ija").status_code, 200)
        with patch("app.modules.agro.routes.get_agro_dashboard_context", return_value={"ultimos_orcamentos": []}), \
             patch("app.core.templating.db.session") as stored:
            stored.query.side_effect = RuntimeError("No database in dashboard test")
            response = self.client.get("/agro/admin")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for central in ("uvis_prefeitura", "agro", "financeiro"):
            self.assertIn(f'data-admin-context="{central}"', html)

    def test_finance_users_cannot_open_operational_centrals_even_with_work_flag(self):
        with patch("app.modules.agro.routes.db.session") as stored:
            for role in ("financeiro_admin", "financeiro"):
                for flag in (True, False):
                    self.login(role, trabalha_agro=flag)
                    for path in ("/agro/admin", "/agro/clientes", "/agro/orcamentos", "/agro/contratos", "/agro/os", "/mapa-relatorio", "/api/heatmap-data"):
                        with self.subTest(role=role, trabalha_agro=flag, path=path):
                            self.assertEqual(self.client.get(path).status_code, 403)
                    response = self.client.get("/admin", follow_redirects=True)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.request.path, "/financeiro")
                    self.assertEqual(self.client.post("/agro/clientes/cadastrar").status_code, 403)
            stored.query.assert_not_called()
            stored.add.assert_not_called()
            stored.commit.assert_not_called()

    def test_finance_keeps_access_to_shared_receipt_files(self):
        with patch("app.modules.agro.routes._get_contrato_agro_or_404", return_value=SimpleNamespace(id=1)), \
             patch("app.modules.agro.routes.resolve_contrato_payment_receipt", return_value=("/tmp", "receipt.pdf", "receipt.pdf")), \
             patch("app.modules.agro.routes.send_from_directory", return_value="receipt"):
            for role in ("financeiro", "financeiro_admin", "admin", "dev"):
                self.login(role, trabalha_agro=False)
                self.assertEqual(self.client.get("/agro/contratos/1/comprovante-pagamento").status_code, 200)

    def test_agro_supplier_registration_keeps_existing_operational_permissions(self):
        with patch("app.core.templating.db.session") as stored:
            stored.query.side_effect = RuntimeError("No database in supplier permission test")
            for role, flag in (("diretor", True), ("operario", True), ("admin", False),
                               ("financeiro", False), ("financeiro_admin", False), ("dev", False)):
                with self.subTest(role=role):
                    self.login(role, trabalha_agro=flag)
                    response = self.client.get("/agro/fornecedores/cadastrar")
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('name="nome"', response.get_data(as_text=True))
            self.login("diretor", trabalha_agro=False)
            self.assertEqual(self.client.get("/agro/fornecedores/cadastrar").status_code, 403)
            stored.add.assert_not_called()
            stored.commit.assert_not_called()

    def test_agro_dashboard_no_longer_contains_financial_shortcuts(self):
        self.login("diretor")
        with patch("app.modules.agro.routes.get_agro_dashboard_context", return_value={"ultimos_orcamentos": []}), \
             patch("app.core.templating.db.session") as stored:
            stored.query.side_effect = RuntimeError("No database in dashboard test")
            response = self.client.get("/agro/admin")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Comercial", html)
        self.assertIn("Operacional", html)
        for old_item in ("Pendencias Financeiras", 'id="menuFinanceiroAgro"', 'href="/agro/financeiro', 'href="/agro/bancos', 'href="/agro/caixa'):
            self.assertNotIn(old_item, html)

    def test_finance_user_has_tabs_but_no_settings(self):
        self.login()
        html = self.client.get("/financeiro/empresas/ija").get_data(as_text=True)
        self.assertIn("Conciliação Bancária", html)
        self.assertNotIn('href="/agro/financeiro/configuracoes"', html)
        self.assertNotIn('href="/agro/financeiro/categorias"', html)

    def test_all_existing_financial_routes_reject_other_roles_before_queries(self):
        rules = [rule for rule in self.app.url_map.iter_rules() if is_financeiro_legacy_endpoint(rule.endpoint)]
        self.assertGreaterEqual(len(rules), 35)
        with patch("app.modules.agro.routes.db.session") as stored:
            for role in ("diretor", "operario", "regional", "piloto_agro"):
                self.login(role)
                for rule in rules:
                    path = re.sub(r"<[^>]+>", "1", rule.rule)
                    for method in rule.methods & {"GET", "POST"}:
                        with self.subTest(role=role, endpoint=rule.endpoint, method=method):
                            self.assertEqual(self.client.open(path, method=method).status_code, 403)
            stored.query.assert_not_called()
            stored.add.assert_not_called()
            stored.commit.assert_not_called()

    def test_existing_financial_routes_redirect_anonymous_users_to_login(self):
        for path in ("/agro/financeiro/contas", "/agro/bancos", "/agro/caixa"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login", response.location)

    def test_settings_routes_are_reserved_for_finance_admin_and_dev(self):
        self.login()
        for rule in self.app.url_map.iter_rules():
            if is_financeiro_settings_endpoint(rule.endpoint):
                path = re.sub(r"<[^>]+>", "1", rule.rule)
                for method in rule.methods & {"GET", "POST"}:
                    with self.subTest(endpoint=rule.endpoint, method=method):
                        self.assertEqual(self.client.open(path, method=method).status_code, 403)
        for role, work_flag in (("financeiro_admin", True), ("financeiro_admin", False), ("admin", False), ("dev", True), ("dev", False)):
            with self.subTest(role=role, trabalha_agro=work_flag):
                self.login(role, trabalha_agro=work_flag)
                with patch("app.modules.agro.routes.build_agro_finance_competencia_settings", return_value=[]):
                    response = self.client.get("/agro/financeiro/configuracoes")
                self.assertEqual(response.status_code, 200)

    def test_existing_accounts_and_banks_open_inside_finance_context(self):
        query = MagicMock()
        query.all.return_value = []
        with patch("app.modules.agro.routes.build_financeiro_agro_query", return_value=query), \
             patch("app.modules.agro.routes.build_financeiro_agro_entrada_query", return_value=query), \
             patch("app.modules.agro.routes.build_financeiro_agro_saida_query", return_value=query), \
             patch("app.modules.agro.routes.build_bancos_agro_query", return_value=query):
            for role, work_flag in (("financeiro_admin", True), ("financeiro_admin", False), ("financeiro", True), ("financeiro", False), ("admin", False), ("dev", True), ("dev", False)):
                self.login(role, trabalha_agro=work_flag)
                for path in ("/agro/financeiro/contas", "/agro/bancos"):
                    with self.subTest(role=role, path=path):
                        response = self.client.get(path)
                        html = response.get_data(as_text=True)
                        self.assertEqual(response.status_code, 200)
                        self.assertIn('class="financeiro-mode"', html)
                        self.assertIn("CNPJ 11.111.111/0001-11", html)
                        self.assertIn('href="/financeiro/empresas/ija"', html)
                        self.assertNotIn('id="menuFinanceiroAgro"', html)
                        self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_dev_financial_mutations_still_require_csrf_when_enabled(self):
        self.app.config["CSRF_PROTECTION_ENABLED"] = True
        register_csrf_security(self.app)
        self.login("dev", trabalha_agro=False)
        self.assertEqual(self.client.get("/financeiro").status_code, 200)
        with self.client.session_transaction() as stored:
            token = stored["_ija_csrf"]
        form = {"tipo_movimento": "ENTRADA", "categoria": "Teste", "subcategoria": "Validação", "ativo": "SIM"}
        # Exercise the real controller, replacing persistence so no DB is used.
        with patch("app.modules.agro.routes._ensure_financeiro_agro_categoria_subcategoria",
                   return_value=(MagicMock(), MagicMock())) as categories, \
             patch("app.modules.agro.routes.db.session") as stored:
            for supplied in (None, "invalid"):
                headers = {} if supplied is None else {"X-CSRFToken": supplied}
                self.assertEqual(self.client.post("/agro/financeiro/categorias/cadastrar", data=form,
                                                 headers=headers).status_code, 403)
            categories.assert_not_called()
            stored.commit.assert_not_called()
            response = self.client.post("/agro/financeiro/categorias/cadastrar", data=form,
                                        headers={"X-CSRFToken": token})
            self.assertEqual(response.status_code, 302)
            categories.assert_called_once_with("ENTRADA", "Teste", "Validação")
            stored.commit.assert_called_once()

    def test_financial_permission_helpers_follow_exclusive_roles(self):
        for role in ("financeiro_admin", "financeiro", "admin", "diretor", "dev", "operario"):
            with self.subTest(role=role):
                user = FinanceUser(role)
                self.assertEqual(can_edit_agro_finance_panel(user), role in {"financeiro_admin", "financeiro", "admin", "dev"})
                self.assertEqual(can_manage_agro_finance_settings(user), role in {"financeiro_admin", "admin", "dev"})
        user = FinanceUser("dev", trabalha_agro=False)
        self.assertTrue(can_edit_agro_finance_panel(user))
        self.assertTrue(can_manage_agro_finance_settings(user))

    def test_company_consultations_require_authorized_company_before_queries(self):
        paths = tuple("/financeiro/empresas/ija/" + area for area in ("relacionamentos", "clientes", "fornecedores", "comercial"))
        with patch.dict(self.app.view_functions, {endpoint: MagicMock() for endpoint in ("main.agro_clientes_menu", "main.agro_clientes_listar", "main.agro_fornecedores_listar", "main.agro_orcamentos_listar", "main.agro_orcamentos_template_mapeamento", "main.agro_contratos_listar")}):
            consultas = [self.app.view_functions[endpoint] for endpoint in ("main.agro_clientes_menu", "main.agro_clientes_listar", "main.agro_fornecedores_listar", "main.agro_orcamentos_listar", "main.agro_orcamentos_template_mapeamento", "main.agro_contratos_listar")]
            for path in paths:
                self.assertEqual(self.client.get(path).status_code, 302)
            for role, work_flag in (("diretor", True), ("piloto", True)):
                self.login(role, trabalha_agro=work_flag)
                for path in paths:
                    with self.subTest(role=role, path=path):
                        self.assertEqual(self.client.get(path).status_code, 403)
            self.login()
            for suffix in ("relacionamentos", "clientes", "fornecedores", "comercial"):
                self.assertEqual(self.client.get(f"/financeiro/empresas/outra/{suffix}").status_code, 404)
            with self.app.app_context():
                companies = build_financeiro_empresas(self.user)
            companies.append({**companies[0], "slug": "outra", "nome": "Outra empresa", "cnpj": "22222222000122"})
            with patch("app.modules.financeiro.routes.build_financeiro_empresas", return_value=companies):
                for suffix in ("relacionamentos", "clientes", "fornecedores", "comercial"):
                    self.assertEqual(self.client.get(f"/financeiro/empresas/outra/{suffix}").status_code, 403)
            self.assertEqual(self.client.get("/financeiro/empresas/ija/comercial?aba=invalida").status_code, 404)
            for consulta in consultas:
                consulta.assert_not_called()

    def test_company_consultations_reuse_original_screens_and_preserve_agro(self):
        client = ClienteAgro(id=1, nome='Cliente IJA <script>alert(1)</script>', documento="11111111000111")
        budget = OrcamentoAgro(id=2, protocolo="IJA-2", cliente_nome="Cliente IJA", nome_fazenda="Fazenda IJA",
                               servico="Mapeamento", preco_pulverizacao=150, data_criacao=datetime(2026, 10, 7))
        contract = ContratoAgro(id=3, contratante_nome="Cliente IJA", contratante_documento="11111111000111",
                                propriedade_nome="Fazenda IJA", status="APROVADO", valor_total=150,
                                orcamento=budget, criado_em=datetime(2026, 10, 7), atualizado_em=datetime(2026, 10, 7))
        cases = (("clientes", "clientes", "build_clientes_agro_query", client),
                 ("comercial", "orcamentos", "build_orcamentos_agro_query", budget),
                 ("comercial", "mapeamentos", "build_orcamentos_agro_query", budget),
                 ("comercial", "contratos", "build_contratos_agro_query", contract))
        for role, flag in (("financeiro", True), ("financeiro", False), ("financeiro_admin", True),
                           ("financeiro_admin", False), ("admin", False), ("dev", False), ("diretor", True)):
            self.login(role, trabalha_agro=flag)
            for suffix, tab, builder, record in cases:
                with self.subTest(role=role, tipo=tab):
                    query = MagicMock()
                    query.count.return_value = 14
                    query.offset.return_value = query
                    query.limit.return_value = query
                    query.filter.return_value = query
                    query.all.return_value = [record]
                    # Keep the original budget client's filter query isolated too.
                    with patch("app.modules.agro.routes.build_clientes_agro_query", return_value=MagicMock(all=lambda: [])), \
                         patch("app.modules.agro.routes." + builder, return_value=query) as read_query, \
                         patch("app.modules.agro.routes._build_agro_equipes_ativas", return_value=[]), \
                         patch("app.modules.agro.routes._build_latest_os_by_contrato", return_value={}), \
                         patch("app.core.templating.db.session") as stored:
                        stored.query.side_effect = RuntimeError("No database in template regression test")
                        if role == "diretor":
                            path = {"clientes": "/agro/clientes", "orcamentos": "/agro/orcamentos",
                                    "mapeamentos": "/agro/orcamentos/template-mapeamento", "contratos": "/agro/contratos"}[tab]
                        else:
                            path = f"/financeiro/empresas/ija/{suffix}"
                        response = self.client.get(path + f"?aba={tab}&q=IJA&page=999")
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    self.assertIn("Cliente IJA", html)
                    self.assertNotIn('<script>alert(1)</script>', html)
                    self.assertEqual(read_query.call_args.kwargs["q"], "IJA")
                    if role != "diretor":
                        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
                        self.assertIn('href="/financeiro/empresas/ija"', html)
                        self.assertIn('action="/financeiro/empresas/ija/' + suffix, html)
                        if role not in {"admin"}:
                            self.assertNotIn('data-admin-context="agro"', html)
                        if tab != "clientes":
                            self.assertIn(f'name="aba" value="{tab}"', html)
                    else:
                        self.assertIn('href="/agro/admin"', html)
                        self.assertIn('data-admin-context="agro"', html)
                    if role in {"financeiro", "financeiro_admin"}:
                        self.assertNotIn("Editar orçamento", html)
                        self.assertNotIn("Editar contrato", html)
                        self.assertNotIn("Salvar template de mapeamento", html)
                        self.assertNotIn('action="/agro/clientes/cadastrar"', html)
                    if tab != "mapeamentos":
                        query.offset.assert_called_once_with(12)
                        query.limit.assert_called_once_with(12)
                    else:
                        query.filter.assert_called_once()

    def test_company_consultations_do_not_allow_mutations(self):
        with patch.dict(self.app.view_functions, {endpoint: MagicMock() for endpoint in ("main.agro_clientes_menu", "main.agro_clientes_listar", "main.agro_fornecedores_listar", "main.agro_orcamentos_listar", "main.agro_orcamentos_template_mapeamento", "main.agro_contratos_listar")}):
            consultas = [self.app.view_functions[endpoint] for endpoint in ("main.agro_clientes_menu", "main.agro_clientes_listar", "main.agro_fornecedores_listar", "main.agro_orcamentos_listar", "main.agro_orcamentos_template_mapeamento", "main.agro_contratos_listar")]
            for role in ("financeiro", "financeiro_admin", "admin", "dev"):
                self.login(role)
                for suffix in ("relacionamentos", "clientes", "fornecedores", "comercial"):
                    with self.subTest(role=role, area=suffix):
                        self.assertEqual(self.client.post(f"/financeiro/empresas/ija/{suffix}").status_code, 405)
            for consulta in consultas:
                consulta.assert_not_called()

    def test_company_identity_persists_and_replaces_demo_document(self):
        self.login("financeiro_admin")
        response = self.client.post("/financeiro/empresas/ija/configuracoes", data={
            "secao": "dados", "nome": "Minha empresa", "razao_social": "Minha Empresa Ltda.", "cnpj": "11.222.333/0001-81"})
        self.assertEqual(response.status_code, 302)
        html = self.client.get("/financeiro").get_data(as_text=True)
        self.assertIn("Minha empresa", html)
        self.assertIn("11.222.333/0001-81", html)
        self.assertNotIn("CNPJ fictício", html)
        self.client.post("/financeiro/empresas/ija/configuracoes", data={
            "secao": "dados", "nome": "Inválida", "razao_social": "Inválida", "cnpj": "123"})
        with self.app.app_context():
            self.assertEqual(db.session.get(FinanceiroEmpresaPerfil, "ija").nome, "Minha empresa")

    def test_logo_upload_display_invalid_replacement_and_removal(self):
        from io import BytesIO
        from PIL import Image
        self.login("admin")
        upload = BytesIO()
        Image.new("RGBA", (800, 400), (20, 80, 120, 100)).save(upload, format="PNG")
        upload.seek(0)
        response = self.client.post("/financeiro/empresas/ija/configuracoes", data={"secao": "layout", "logo": (upload, "logo.png")})
        self.assertEqual(response.status_code, 302)
        logo = self.client.get("/financeiro/empresas/ija/logo")
        self.assertEqual(logo.mimetype, "image/png")
        self.assertEqual(Image.open(BytesIO(logo.data)).size, (512, 256))
        self.assertEqual(logo.headers["Cache-Control"], "private, no-store")
        for path in ("/financeiro", "/financeiro/empresas/ija", "/financeiro/empresas/ija/configuracoes?secao=layout"):
            self.assertIn('src="/financeiro/empresas/ija/logo"', self.client.get(path).get_data(as_text=True))
        for data in (b"<svg onload=alert(1)></svg>", b"x" * (2 * 1024 * 1024 + 1)):
            self.client.post("/financeiro/empresas/ija/configuracoes", data={"secao": "layout", "logo": (BytesIO(data), "fake.png")})
            self.assertEqual(self.client.get("/financeiro/empresas/ija/logo").data, logo.data)
        self.client.post("/financeiro/empresas/ija/configuracoes", data={"secao": "layout", "remover_logo": "1"})
        self.assertEqual(self.client.get("/financeiro/empresas/ija/logo").status_code, 404)
        self.assertNotIn('src="/financeiro/empresas/ija/logo"', self.client.get("/financeiro").get_data(as_text=True))

    def test_logo_skybox_failure_preserves_previous_path(self):
        from io import BytesIO
        from PIL import Image
        from app.shared.skybox import SkyboxError
        self.login("admin")
        with self.app.app_context():
            db.session.add(FinanceiroEmpresaPerfil(empresa_slug="ija", logo_path="skybox://old.png", tem_logo=True))
            db.session.commit()
        upload = BytesIO()
        Image.new("RGB", (10, 10)).save(upload, format="PNG")
        upload.seek(0)
        with patch("app.modules.financeiro.logos.upload_file_to_skybox", side_effect=SkyboxError("Unavailable")):
            self.client.post("/financeiro/empresas/ija/configuracoes", data={"secao": "layout", "logo": (upload, "logo.png")})
        with self.app.app_context():
            self.assertEqual(db.session.get(FinanceiroEmpresaPerfil, "ija").logo_path, "skybox://old.png")
        self.assertEqual(self.logo_files, {})

    def test_logo_replacement_deletes_old_file_only_after_commit(self):
        from io import BytesIO
        from PIL import Image
        self.login("admin")
        with self.app.app_context():
            db.session.add(FinanceiroEmpresaPerfil(empresa_slug="ija", logo_path="skybox://old.png", tem_logo=True))
            db.session.commit()
        self.logo_files["skybox://old.png"] = b"old"
        upload = BytesIO()
        Image.new("RGB", (10, 10)).save(upload, format="PNG")
        upload.seek(0)
        self.client.post("/financeiro/empresas/ija/configuracoes", data={"secao": "layout", "logo": (upload, "logo.png")})
        self.assertNotIn("skybox://old.png", self.logo_files)
        with self.app.app_context():
            path = db.session.get(FinanceiroEmpresaPerfil, "ija").logo_path
            self.assertTrue(path.startswith("skybox://financeiro/empresas/ija/logos/"))
            self.assertIn(path, self.logo_files)
            self.assertNotIn("logo", FinanceiroEmpresaPerfil.__table__.columns)

    def test_settings_are_scoped_and_protected(self):
        self.login("financeiro")
        path = "/financeiro/empresas/ija/configuracoes"
        self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post(path, data={"secao": "layout", "remover_logo": "1"}).status_code, 403)
        self.login("dev")
        self.assertEqual(self.client.post("/financeiro/empresas/inexistente/configuracoes").status_code, 404)
        with self.app.app_context():
            db.session.add(FinanceiroEmpresaPerfil(empresa_slug="outra", nome="Outra empresa", logo_path="skybox://other.png", tem_logo=True))
            db.session.commit()
        self.client.post(path, data={"secao": "layout", "remover_logo": "1"})
        with self.app.app_context():
            self.assertEqual(db.session.get(FinanceiroEmpresaPerfil, "outra").logo_path, "skybox://other.png")
        self.assertEqual(self.client.get("/financeiro/empresas/outra/logo").status_code, 404)

    def test_company_settings_require_csrf(self):
        self.app.config["CSRF_PROTECTION_ENABLED"] = True
        register_csrf_security(self.app)
        self.login("admin")
        path = "/financeiro/empresas/ija/configuracoes"
        self.assertEqual(self.client.post(path, data={"secao": "layout", "remover_logo": "1"}).status_code, 403)
        self.client.get(path)
        with self.client.session_transaction() as stored:
            token = stored["_ija_csrf"]
        self.assertEqual(self.client.post(path, data={"secao": "layout", "remover_logo": "1", "_csrf_token": token}).status_code, 302)

    def test_settings_sections_keep_competencies_separate(self):
        self.login("admin")
        for section, expected in (("dados", 'id="empresa-cnpj"'), ("layout", 'id="empresa-logo"'), ("competencias", 'id="competencia_select"')):
            with patch("app.modules.agro.routes.build_agro_finance_competencia_settings", return_value=[]):
                html = self.client.get("/financeiro/empresas/ija/configuracoes?secao=" + section).get_data(as_text=True)
            self.assertIn(expected, html)
            if section != "competencias":
                self.assertNotIn('id="competencia_select"', html)

    def test_views_do_not_accept_mutations(self):
        self.login()
        for path in ("/financeiro", "/financeiro/empresas/ija"):
            self.assertEqual(self.client.post(path).status_code, 405)


if __name__ == "__main__":
    unittest.main()
