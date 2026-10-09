"""Central persistence/security tests, using only disposable in-memory SQLite."""

import importlib.util
import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.config import Config
from alembic.script import ScriptDirectory
from flask import Flask, g
from flask_login import LoginManager
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import CentralTiAuditoria, CentralTiPerfilConfiguracao, CentralTiSelecao, Usuario
from app.modules.auth.routes import bp as auth_bp
from app.modules.auth.service import get_authenticated_redirect_endpoint
from app.modules.gestao_ti.catalog import AREA_CODES, CATALOG, PERMISSION_CODES
from app.modules.gestao_ti.current_rules import current_rules
from app.modules.gestao_ti.routes import CSRF_SESSION_KEY, MAX_PAYLOAD_BYTES
from app.modules.gestao_ti.service import can_manage_central_ti, validate_configurations
from app.modules.admin_dashboard.service import can_access_admin_panel
from app.modules.agro.service import can_access_agro_panel
from app.routes import bp as main_bp
from app.shared.access import can_access_financeiro_panel, is_admin_global_user
from app.shared.csrf_security import register_csrf_security
from scripts.prepare_central_ti_neon import seed_profiles


ROOT = Path(__file__).resolve().parents[1]


class CentralTiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder=str(ROOT / "app/templates"), static_folder=str(ROOT / "app/static"))
        self.app.config.update(
            TESTING=True, SECRET_KEY="isolated-central-ti-tests-secret-1234567890",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:", SQLALCHEMY_TRACK_MODIFICATIONS=False,
            CENTRAL_TI_ENABLED=True, CSRF_PROTECTION_ENABLED=False, SESSION_PROTECTION=None,
        )
        db.init_app(self.app)
        manager = LoginManager(self.app)
        manager.login_view = "auth.login"
        manager.user_loader(lambda user_id: db.session.get(Usuario, int(user_id)))
        register_csrf_security(self.app)

        @self.app.before_request
        def clear_cached_test_user():
            # setUp keeps an app context open; each request must load its own user.
            g.pop("_login_user", None)

        self.app.register_blueprint(auth_bp)
        self.app.register_blueprint(main_bp)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.users = {}
        for role in ("dev", "gestor_ti", "admin", "diretor", "financeiro", "financeiro_admin", "uvis", "piloto", "operario", "prefeitura_admin"):
            user = Usuario(nome_uvis=role, login=f"central_{role}", senha_hash="test-only", tipo_usuario=role)
            db.session.add(user)
            self.users[role] = user
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def login(self, role="dev"):
        with self.client.session_transaction() as stored:
            stored["_user_id"] = str(self.users[role].id)
            stored["_fresh"] = True

    def editor_data(self):
        response = self.client.get("/central-ti")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:250])
        match = re.search(r'<script type="application/json" id="ti-central-data">(.*?)</script>', response.get_data(as_text=True), re.S)
        self.assertIsNotNone(match)
        return json.loads(match.group(1))

    def token(self):
        with self.client.session_transaction() as stored:
            return stored[CSRF_SESSION_KEY]["token"]

    def save(self, profiles, **kwargs):
        return self.client.post("/central-ti/configuracoes", json={"profiles": profiles}, headers={"X-Central-TI-CSRF": self.token()}, **kwargs)

    def selection(self, code="dev", version=0):
        return {"id": code, "version": version, "areas": ["sistema"], "permissions": ["sistema.estoque.consultar"]}

    def test_disabled_central_has_no_db_dependency(self):
        self.login()
        self.app.config["CENTRAL_TI_ENABLED"] = False
        with patch("app.modules.gestao_ti.routes.build_editor_data") as load:
            self.assertEqual(self.client.get("/central-ti").status_code, 404)
            self.assertEqual(self.client.post("/central-ti/configuracoes", json={}).status_code, 404)
            load.assert_not_called()
        self.assertFalse(can_manage_central_ti(self.users["dev"]))

    def test_anonymous_users_require_login(self):
        for path in ("/central-ti", "/central-ti/configuracoes"):
            response = self.client.get(path) if path == "/central-ti" else self.client.post(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login", response.location)
            self.assertIn("no-store", response.headers["Cache-Control"])

    def test_only_dev_and_ti_manager_can_load_and_save(self):
        for role in self.users:
            self.login(role)
            if role in {"dev", "gestor_ti"}:
                data = self.editor_data()
                self.assertEqual(len(data["states"]), 20)
                response = self.save([self.selection(role)])
                self.assertEqual(response.status_code, 200)
            else:
                with patch("app.modules.gestao_ti.routes.build_editor_data") as load:
                    self.assertEqual(self.client.get("/central-ti").status_code, 403)
                    self.assertEqual(self.client.post("/central-ti/configuracoes", json={}).status_code, 403)
                    load.assert_not_called()

    def test_unconfigured_profiles_display_existing_rules_without_writing(self):
        self.login()
        statements = []
        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().split()[0].upper())
        sa.event.listen(db.engine, "before_cursor_execute", capture)
        self.addCleanup(sa.event.remove, db.engine, "before_cursor_execute", capture)
        data = self.editor_data()
        for state in data["states"]:
            self.assertEqual(state["version"], 0)
            self.assertFalse(state["configured"])
            self.assertEqual(state["source"], "current_rules")
            validate_configurations({"profiles": [{key: state[key] for key in ("id", "version", "areas", "permissions")}]})
        states = {state["id"]: state for state in data["states"]}
        self.assertEqual(states["gestor_ti"]["permissions"], ["sistema.perfis.configurar", "sistema.perfis.consultar"])
        self.assertNotIn("sistema.usuarios.consultar", states["gestor_ti"]["permissions"])
        self.assertNotIn("financeiro", states["admin"]["areas"])
        self.assertNotIn("agro", states["financeiro"]["areas"])
        self.assertIn("financeiro.contas.operar", states["financeiro"]["permissions"])
        self.assertNotIn("financeiro.configuracoes.configurar", states["financeiro"]["permissions"])
        self.assertIn("financeiro.configuracoes.configurar", states["financeiro_admin"]["permissions"])
        self.assertTrue(set(statements) <= {"SELECT"}, statements)
        self.assertEqual(CentralTiPerfilConfiguracao.query.count(), 0)
        self.assertEqual(CentralTiSelecao.query.count(), 0)
        self.assertEqual(CentralTiAuditoria.query.count(), 0)

    def test_neutral_seed_displays_defaults_but_preserves_its_version(self):
        seed_profiles(db.session.connection(), CATALOG["profiles"])
        db.session.commit()
        self.login()
        data = self.editor_data()
        for state in data["states"]:
            self.assertEqual(state["version"], 1)
            self.assertEqual(state["source"], "current_rules")
            self.assertFalse(state["configured"])
            self.assertEqual(state["permissions"], state["current_rules"]["permissions"])
        self.assertEqual(CentralTiSelecao.query.count(), 0)
        self.assertEqual(CentralTiAuditoria.query.count(), 20)

    def test_deliberately_clearing_seeded_profile_does_not_restore_defaults(self):
        seed_profiles(db.session.connection(), CATALOG["profiles"])
        db.session.commit()
        self.login()
        self.editor_data()
        response = self.save([{"id": "dev", "version": 1, "areas": [], "permissions": []}])
        self.assertEqual(response.status_code, 200)
        state = next(item for item in self.editor_data()["states"] if item["id"] == "dev")
        self.assertEqual(state["source"], "saved_configuration")
        self.assertEqual(state["version"], 2)
        self.assertEqual(state["permissions"], [])
        self.assertIn("sistema.perfis.configurar", state["current_rules"]["permissions"])
        self.assertEqual(CentralTiAuditoria.query.count(), 21)

    def test_empty_authored_configuration_is_never_treated_as_a_seed(self):
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo="dev", versao=1, atualizado_por_id=None))
        db.session.commit()
        self.login()
        state = next(item for item in self.editor_data()["states"] if item["id"] == "dev")
        self.assertEqual(state["source"], "saved_configuration")
        self.assertEqual(state["permissions"], [])

    def test_current_rules_preserve_conditional_and_legacy_differences(self):
        self.assertIn("Trabalha no Agro", current_rules("dev")["notes"]["agro"])
        self.assertNotIn("agro", current_rules("admin")["notes"])
        self.assertIn("prefeitura.solicitacoes.criar", current_rules("covisa")["permissions"])
        self.assertIn("sistema.suporte.criar", current_rules("covisa")["permissions"])
        self.assertNotIn("sistema.suporte.criar", current_rules("visualizar")["permissions"])
        self.assertNotIn("prefeitura.veiculos.consultar", current_rules("sup_veiculo")["permissions"])
        self.assertIn("prefeitura.os.concluir", current_rules("sup_veiculo")["permissions"])
        with self.assertRaises(ValueError):
            current_rules("unknown")

    def test_save_persists_several_profiles_with_shared_audit_batch(self):
        self.login()
        self.editor_data()
        response = self.save([self.selection("diretor"), self.selection("dev")])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["active_rules_changed"])
        self.assertEqual(CentralTiPerfilConfiguracao.query.count(), 2)
        self.assertEqual(CentralTiSelecao.query.count(), 4)
        events = CentralTiAuditoria.query.all()
        self.assertEqual(len(events), 2)
        self.assertEqual(len({event.lote for event in events}), 1)
        self.assertTrue(all(event.usuario_id == self.users["dev"].id for event in events))
        self.assertEqual(events[0].antes, {"areas": [], "permissions": []})
        reloaded = {state["id"]: state for state in self.editor_data()["states"]}
        self.assertEqual(reloaded["diretor"]["permissions"], ["sistema.estoque.consultar"])
        self.assertTrue(reloaded["diretor"]["configured"])
        self.assertEqual(reloaded["diretor"]["version"], 1)
        self.assertEqual(reloaded["diretor"]["source"], "saved_configuration")
        self.assertIn("sistema.estoque.editar", reloaded["diretor"]["current_rules"]["permissions"])

    def test_removing_all_choices_is_a_saved_configuration(self):
        self.login()
        self.editor_data()
        self.assertEqual(self.save([self.selection()]).status_code, 200)
        response = self.save([{"id": "dev", "version": 1, "areas": [], "permissions": []}])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CentralTiSelecao.query.count(), 0)
        self.assertEqual(db.session.get(CentralTiPerfilConfiguracao, "dev").versao, 2)
        self.assertTrue(can_manage_central_ti(self.users["dev"]))

    def test_unchanged_save_does_not_create_duplicate_audit_events(self):
        self.login()
        self.editor_data()
        self.save([self.selection()])
        response = self.save([self.selection(version=1)])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["profiles"][0]["version"], 1)
        self.assertEqual(CentralTiAuditoria.query.count(), 1)

    def test_stale_editor_is_rejected_and_entire_batch_is_rolled_back(self):
        self.login()
        self.editor_data()
        self.save([self.selection()])
        response = self.save([self.selection("admin"), self.selection("dev", version=0)])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["code"], "configuration_conflict")
        self.assertIsNone(db.session.get(CentralTiPerfilConfiguracao, "admin"))
        self.assertEqual(CentralTiAuditoria.query.count(), 1)
        self.assertEqual(db.session.get(CentralTiPerfilConfiguracao, "dev").versao, 1)

    def test_validation_rejects_unknown_keys_and_invalid_dependencies(self):
        self.login()
        self.editor_data()
        invalid = [
            {**self.selection(), "id": "unknown"},
            {**self.selection(), "version": True},
            {**self.selection(), "version": -1},
            {**self.selection(), "areas": ["unknown"]},
            {**self.selection(), "permissions": ["sistema.root.gerenciar"]},
            {**self.selection(), "permissions": ["sistema.estoque.excluir"]},
            {**self.selection(), "areas": []},
            {**self.selection(), "areas": ["sistema", "sistema"]},
            {**self.selection(), "permissoes_ativas": True},
        ]
        for profile in invalid:
            with self.subTest(profile=profile):
                self.assertEqual(self.save([profile]).status_code, 400)
        self.assertEqual(self.save([self.selection(), self.selection()]).status_code, 400)
        self.assertEqual(CentralTiPerfilConfiguracao.query.count(), 0)
        self.assertEqual(CentralTiAuditoria.query.count(), 0)

    def test_csrf_is_required_even_with_global_protection_disabled(self):
        self.login()
        self.editor_data()
        for headers in ({}, {"X-Central-TI-CSRF": "wrong"}):
            response = self.client.post("/central-ti/configuracoes", json={"profiles": [self.selection()]}, headers=headers)
            self.assertEqual(response.status_code, 403)
        self.assertEqual(CentralTiPerfilConfiguracao.query.count(), 0)

    def test_token_is_bound_to_the_authenticated_editor(self):
        self.login("dev")
        self.editor_data()
        old = self.token()
        self.login("gestor_ti")
        response = self.client.post("/central-ti/configuracoes", json={"profiles": [self.selection()]}, headers={"X-Central-TI-CSRF": old})
        self.assertEqual(response.status_code, 403)
        self.editor_data()
        self.assertNotEqual(old, self.token())
        self.assertEqual(self.save([self.selection()]).status_code, 200)

    def test_central_also_respects_global_csrf_when_enabled(self):
        self.app.config["CSRF_PROTECTION_ENABLED"] = True
        self.login()
        self.editor_data()
        with self.assertLogs(self.app.logger, level="WARNING"):
            self.assertEqual(self.save([self.selection()]).status_code, 403)
        with self.client.session_transaction() as stored:
            global_token = stored["_ija_csrf"]
        response = self.client.post("/central-ti/configuracoes", json={"profiles": [self.selection()]}, headers={"X-Central-TI-CSRF": self.token(), "X-CSRFToken": global_token})
        self.assertEqual(response.status_code, 200)

    def test_all_catalog_options_fit_and_save_together(self):
        self.login()
        self.editor_data()
        profiles = [{"id": p["id"], "version": 0, "areas": sorted(AREA_CODES), "permissions": sorted(PERMISSION_CODES)} for p in CATALOG["profiles"]]
        self.assertLess(len(json.dumps({"profiles": profiles}).encode()), MAX_PAYLOAD_BYTES)
        response = self.save(profiles)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CentralTiAuditoria.query.count(), len(CATALOG["profiles"]))

    def test_payload_size_and_content_type_limits(self):
        self.login()
        self.editor_data()
        headers = {"X-Central-TI-CSRF": self.token()}
        self.assertEqual(self.client.post("/central-ti/configuracoes", data="x" * (MAX_PAYLOAD_BYTES + 1), content_type="application/json", headers=headers).status_code, 413)
        self.assertEqual(self.client.post("/central-ti/configuracoes", data="{", content_type="application/json", headers=headers).status_code, 400)
        self.assertEqual(self.client.post("/central-ti/configuracoes", data="{}", headers=headers).status_code, 415)
        self.assertEqual(CentralTiAuditoria.query.count(), 0)

    def test_database_failure_rolls_back_configurations_and_audit(self):
        self.login()
        self.editor_data()
        with self.assertLogs(self.app.logger, level="ERROR"), patch.object(db.session, "commit", side_effect=SQLAlchemyError("test failure")):
            self.assertEqual(self.save([self.selection()]).status_code, 503)
        self.assertEqual(CentralTiPerfilConfiguracao.query.count(), 0)
        self.assertEqual(CentralTiAuditoria.query.count(), 0)

    def test_saving_never_changes_existing_users_or_access_rules(self):
        self.login()
        self.editor_data()
        def access_snapshot():
            return {role: (user.tipo_usuario, user.prefeitura_id, user.regiao, user.trabalha_agro,
                           can_access_financeiro_panel(user), can_access_admin_panel(user),
                           can_access_agro_panel(user), is_admin_global_user(user))
                    for role, user in self.users.items()}
        before = access_snapshot()
        selection = self.selection("financeiro")
        selection["permissions"] = ["sistema.usuarios.consultar", "sistema.usuarios.gerenciar"]
        self.assertEqual(self.save([selection]).status_code, 200)
        after = access_snapshot()
        self.assertEqual(before, after)
        self.assertEqual(Usuario.query.count(), len(self.users))
        self.assertFalse(can_manage_central_ti(self.users["financeiro"]))

    def test_saved_choices_cannot_grant_route_access_or_revoke_dev_access(self):
        self.login("dev")
        self.editor_data()
        profiles = [{"id": "gestor_ti", "version": 0, "areas": sorted(AREA_CODES), "permissions": sorted(PERMISSION_CODES)},
                    {"id": "dev", "version": 0, "areas": [], "permissions": []}]
        self.assertEqual(self.save(profiles).status_code, 200)
        self.assertEqual(self.client.get("/central-ti").status_code, 200)
        self.assertEqual(self.client.get("/admin/usuarios").status_code, 200)
        self.login("gestor_ti")
        for path in ("/admin/usuarios", "/financeiro", "/agro/admin", "/estoque"):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.get("/central-ti").status_code, 200)

    def test_ti_manager_redirect_and_navigation_are_flagged(self):
        user = self.users["gestor_ti"]
        self.assertEqual(get_authenticated_redirect_endpoint(user), "main.central_ti")
        self.login("gestor_ti")
        html = self.client.get("/central-ti").get_data(as_text=True)
        self.assertIn('href="/central-ti"', html)
        self.assertNotIn('href="/admin/usuarios"', html)
        self.assertNotIn('href="/agenda"', html)
        self.assertNotIn('href="/financeiro"', html)
        self.assertNotIn('href="/agro/admin"', html)
        self.app.config["CENTRAL_TI_ENABLED"] = False
        self.assertEqual(get_authenticated_redirect_endpoint(user), "main.dashboard")

    def test_ti_manager_login_opens_central_and_keeps_other_panels_blocked(self):
        user = self.users["gestor_ti"]
        user.set_senha("LoginTI!2026-Local")
        db.session.commit()
        response = self.client.post("/login", data={"login": user.login, "senha": "LoginTI!2026-Local"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/central-ti")
        central = self.client.get(response.location)
        self.assertEqual(central.status_code, 200)
        self.assertIn('id="ti-central-data"', central.get_data(as_text=True))
        self.assertEqual(self.client.get("/dev").status_code, 403)
        self.assertEqual(self.client.get("/financeiro").status_code, 403)
        self.assertEqual(self.client.get("/agro/admin").status_code, 403)
        self.assertEqual(self.client.get("/admin").status_code, 403)
        self.assertEqual(self.client.get("/login").location, "/central-ti")

    def test_dev_login_preserves_dashboard_and_central_is_accessible(self):
        user = self.users["dev"]
        user.set_senha("LoginDev!2026-Local")
        db.session.commit()
        response = self.client.post("/login", data={"login": user.login, "senha": "LoginDev!2026-Local"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/dev")
        dashboard = self.client.get(response.location)
        self.assertEqual(dashboard.status_code, 200)
        html = dashboard.get_data(as_text=True)
        hero = re.search(r'<div class="dev-hero-actions">(.*?)</div>', html, re.S)
        self.assertIsNotNone(hero)
        self.assertIn('href="/central-ti"', hero.group(1))
        self.assertIn("Central de TI", hero.group(1))
        self.assertEqual(self.client.get("/central-ti").status_code, 200)

    def test_new_ti_profile_is_restricted_to_central_business_routes(self):
        self.login("gestor_ti")
        for path in ("/admin", "/agenda", "/estoque", "/financeiro", "/agro/admin"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post("/estoque/novo", data={}).status_code, 403)
        self.assertEqual(self.client.get("/central-ti").status_code, 200)

    def test_ti_manager_does_not_gain_business_access_when_central_is_disabled(self):
        self.login("gestor_ti")
        self.app.config["CENTRAL_TI_ENABLED"] = False
        self.assertEqual(self.client.get("/central-ti").status_code, 404)
        self.assertEqual(self.client.get("/agenda").status_code, 403)
        self.assertEqual(self.client.get("/estoque").status_code, 403)

    def test_dev_can_create_a_ti_manager_through_existing_user_form(self):
        self.login()
        self.assertIn('value="gestor_ti"', self.client.get("/admin/usuarios/novo").get_data(as_text=True))
        response = self.client.post("/admin/usuarios/novo", data={
            "nome": "Gestor TI de teste", "login": "isolated_ti_manager",
            "tipo_usuario": "gestor_ti", "senha": "TesteTI!2026-Local", "senha2": "TesteTI!2026-Local",
        })
        self.assertEqual(response.status_code, 302)
        user = Usuario.query.filter_by(login="isolated_ti_manager").one()
        self.assertEqual(user.tipo_usuario, "gestor_ti")
        self.assertTrue(user.check_senha("TesteTI!2026-Local"))
        self.assertFalse(is_admin_global_user(user))

    def test_ti_assignment_is_blocked_server_side_for_other_admins_and_flag_off(self):
        payload = {"nome": "Teste", "login": "must_not_exist", "tipo_usuario": "gestor_ti",
                   "senha": "TesteTI!2026-Local", "senha2": "TesteTI!2026-Local"}
        for role in ("admin", "diretor"):
            self.login(role)
            self.assertNotIn('value="gestor_ti"', self.client.get("/admin/usuarios/novo").get_data(as_text=True))
            self.assertEqual(self.client.post("/admin/usuarios/novo", data=payload).status_code, 403)
            target = self.users["operario"]
            self.assertEqual(self.client.post(f"/admin/usuarios/{target.id}/editar", data={
                "nome_uvis": "Teste", "login": target.login, "tipo_usuario": "gestor_ti",
            }).status_code, 403)
        self.login()
        self.app.config["CENTRAL_TI_ENABLED"] = False
        self.assertNotIn('value="gestor_ti"', self.client.get("/admin/usuarios/novo").get_data(as_text=True))
        self.assertEqual(self.client.post("/admin/usuarios/novo", data=payload).status_code, 403)
        self.assertIsNone(Usuario.query.filter_by(login="must_not_exist").first())
        self.assertEqual(self.users["operario"].tipo_usuario, "operario")

    def test_existing_ti_accounts_are_listed_and_only_dev_can_manage_them(self):
        target = self.users["gestor_ti"]
        for role in ("admin", "diretor"):
            self.login(role)
            self.assertEqual(self.client.get(f"/admin/usuarios/{target.id}/editar").status_code, 403)
            for action in ("reset_senha", "excluir"):
                self.assertEqual(self.client.post(f"/admin/usuarios/{target.id}/{action}", data={}).status_code, 403)
        self.login()
        listing = self.client.get("/admin/usuarios?tipo=gestor_ti")
        self.assertEqual(listing.status_code, 200)
        self.assertIn(target.login, listing.get_data(as_text=True))
        self.assertIn("GESTOR DE TI", listing.get_data(as_text=True))
        self.assertNotIn(self.users["financeiro"].login, listing.get_data(as_text=True))
        self.assertEqual(self.client.get(f"/admin/usuarios/{target.id}/editar").status_code, 200)
        response = self.client.post(f"/admin/usuarios/{target.id}/editar", data={
            "nome_uvis": "Gestor TI atualizado", "login": target.login, "tipo_usuario": "gestor_ti",
        })
        self.assertEqual(response.status_code, 302)
        db.session.refresh(target)
        self.assertEqual(target.nome_uvis, "Gestor TI atualizado")


class CentralTiMigrationTests(unittest.TestCase):
    def test_pending_migration_is_not_executed_by_automatic_upgrade(self):
        config = Config(str(ROOT / "migrations/alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        revisions = {revision.revision for revision in ScriptDirectory.from_config(config).walk_revisions()}
        self.assertNotIn("c1a0f8b6d2e4", revisions)
        self.assertIn("f2c531cc9f71", revisions)

    def test_migration_only_adds_and_removes_central_tables(self):
        path = ROOT / "migrations/pending/c1a0f8b6d2e4_add_central_ti_configurations.py"
        spec = importlib.util.spec_from_file_location("isolated_central_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, tipo_usuario TEXT NOT NULL)"))
            connection.execute(sa.text("INSERT INTO usuarios VALUES (1, 'dev')"))
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            tables = set(sa.inspect(connection).get_table_names())
            self.assertEqual(tables, {"usuarios", "central_ti_perfis_configuracoes", "central_ti_selecoes", "central_ti_auditoria"})
            inspector = sa.inspect(connection)
            for model in (CentralTiPerfilConfiguracao, CentralTiSelecao, CentralTiAuditoria):
                self.assertEqual({column["name"] for column in inspector.get_columns(model.__tablename__)}, set(model.__table__.columns.keys()))
                self.assertEqual(set(inspector.get_pk_constraint(model.__tablename__)["constrained_columns"]), {column.name for column in model.__table__.primary_key.columns})
            self.assertEqual(connection.execute(sa.text("SELECT tipo_usuario FROM usuarios WHERE id=1")).scalar_one(), "dev")
            with Operations.context(context):
                migration.downgrade()
            self.assertEqual(sa.inspect(connection).get_table_names(), ["usuarios"])
            self.assertEqual(connection.execute(sa.text("SELECT count(*) FROM usuarios")).scalar_one(), 1)
        engine.dispose()

    def test_later_upgrade_reuses_neon_tables_without_losing_selections(self):
        from scripts.prepare_central_ti_neon import load_migration
        migration = load_migration()
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY)"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                connection.execute(sa.text("INSERT INTO central_ti_perfis_configuracoes (perfil_codigo, versao) VALUES ('dev', 2)"))
                connection.execute(sa.text("INSERT INTO central_ti_selecoes VALUES ('dev', 'area:sistema')"))
                migration.upgrade()
            self.assertEqual(connection.execute(sa.text("SELECT versao FROM central_ti_perfis_configuracoes WHERE perfil_codigo='dev'")).scalar_one(), 2)
            self.assertEqual(connection.execute(sa.text("SELECT codigo FROM central_ti_selecoes")).scalar_one(), "area:sistema")
        engine.dispose()

    def test_partial_existing_schema_is_rejected_without_creating_other_tables(self):
        from scripts.prepare_central_ti_neon import load_migration
        migration = load_migration()
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE central_ti_selecoes (perfil_codigo TEXT, codigo TEXT)"))
            with Operations.context(MigrationContext.configure(connection)), self.assertRaises(RuntimeError):
                migration.upgrade()
            self.assertEqual(sa.inspect(connection).get_table_names(), ["central_ti_selecoes"])
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
