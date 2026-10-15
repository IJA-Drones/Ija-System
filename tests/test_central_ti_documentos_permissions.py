"""Document settings grants/revocations, using disposable SQLite and fake storage."""

import unittest

from flask import render_template
from flask_login import login_user
from werkzeug.exceptions import Forbidden

from app.extensions import db
from app.models import CentralTiPerfilConfiguracao, PrefeituraDocumentoConfig, Usuario
from app.modules.configuracoes import service
from app.modules.gestao_ti.current_rules import current_rules
from app.modules.gestao_ti.navigation import area_home_endpoint
from app.modules.gestao_ti.permissions import validate_route_policy
from app.modules.gestao_ti.service import save_configurations
from tests import test_configuracoes_documentos as documents_base


CONSULTAR = "prefeitura.documentos.consultar"
CONFIGURAR = "prefeitura.documentos.configurar"


class CentralTiDocumentosPermissionsTests(unittest.TestCase):
    login = documents_base.DocumentSettingsTests.login
    save = documents_base.DocumentSettingsTests.save

    def setUp(self):
        documents_base.DocumentSettingsTests.setUp(self)
        self.app.config.update(CENTRAL_TI_ENABLED=True, CENTRAL_TI_ENFORCE_PERMISSIONS=True)
        self.addCleanup(self.dispose_database)

    def dispose_database(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def configure(self, role, permissions=()):
        with self.app.app_context():
            row = db.session.get(CentralTiPerfilConfiguracao, role)
            save_configurations(db.session.get(Usuario, 3), {"profiles": [{
                "id": role, "version": row.versao if row else 0,
                "areas": ["prefeitura"] if permissions else [],
                "permissions": list(permissions),
            }]})

    def test_routes_and_legacy_defaults_are_mapped(self):
        validate_route_policy(self.app)
        for role in ("dev", "covisa"):
            self.assertTrue({CONSULTAR, CONFIGURAR} <= set(current_rules(role)["permissions"]))
        for role in ("admin", "prefeitura_admin", "visualizar", "gestor_ti"):
            self.assertNotIn(CONSULTAR, current_rules(role)["permissions"])
        for key in (1, 4):
            self.login(key)
            self.assertEqual(self.client.get("/configuracoes").location, "/configuracoes/documentos/1")
            self.assertEqual(self.client.get("/configuracoes/documentos/1").status_code, 200)
        self.login(3)
        self.assertEqual(self.client.get("/configuracoes").status_code, 200)

    def test_consult_only_shows_settings_without_write_controls(self):
        self.configure("admin", [CONSULTAR])
        self.login(6)
        page = self.client.get("/configuracoes/documentos/1")
        self.assertEqual(page.status_code, 200)
        self.assertIn('href="/configuracoes"', page.text)
        self.assertIn("<fieldset disabled>", page.text)
        self.assertNotIn("Salvar configurações</button>", page.text)
        self.assertEqual(self.save(ativo="1", identificar_usuario="1").status_code, 403)
        with self.app.app_context():
            self.assertIsNone(db.session.get(PrefeituraDocumentoConfig, 1))
            with self.assertRaises(Forbidden):
                service.save_config(db.session.get(Usuario, 6), 1, {}, None)
            self.assertEqual(area_home_endpoint(db.session.get(Usuario, 6), "prefeitura"), "main.configuracoes")

    def test_configure_permission_grants_save_but_keeps_persisted_municipality(self):
        self.configure("admin", [CONSULTAR, CONFIGURAR])
        self.login(6)
        page = self.client.get("/configuracoes/documentos/1")
        self.assertIn("Salvar configurações</button>", page.text)
        self.assertEqual(self.save(ativo="1", identificar_usuario="1").status_code, 303)
        self.assertEqual(self.client.get("/configuracoes/documentos/2").status_code, 404)
        self.assertEqual(self.save(city=2, ativo="1", identificar_usuario="1").status_code, 404)
        self.assertEqual(self.save(versao="1", _csrf_token="wrong").status_code, 403)
        with self.app.app_context():
            self.assertTrue(db.session.get(PrefeituraDocumentoConfig, 1).ativo)
            self.assertIsNone(db.session.get(PrefeituraDocumentoConfig, 2))

    def test_revocation_and_grant_take_effect_in_same_session_including_image(self):
        self.configure("covisa", [CONSULTAR, CONFIGURAR])
        self.login(1)
        self.assertEqual(self.save(ativo="1", imagem=(documents_base.picture(), "brasao.png")).status_code, 303)
        self.configure("admin", [CONSULTAR])
        self.login(6)
        self.assertEqual(self.client.get("/configuracoes/documentos/1/imagem").status_code, 200)
        self.assertEqual(self.client.get("/configuracoes/documentos/2/imagem").status_code, 404)
        self.configure("admin")
        for suffix in ("", "/imagem"):
            self.assertEqual(self.client.get("/configuracoes/documentos/1" + suffix).status_code, 403)
        self.configure("admin", [CONSULTAR, CONFIGURAR])
        self.assertEqual(self.client.get("/configuracoes/documentos/1").status_code, 200)
        self.assertEqual(self.save(versao="1", ativo="1", identificar_usuario="1").status_code, 303)

    def test_saved_dev_profile_does_not_gain_new_permission_automatically(self):
        self.configure("dev")
        self.login(3)
        self.assertEqual(self.client.get("/configuracoes").status_code, 403)
        self.configure("dev", [CONSULTAR, CONFIGURAR])
        self.assertIn("Prefeitura Beta", self.client.get("/configuracoes").text)
        self.assertEqual(self.client.get("/configuracoes/documentos/2").status_code, 200)

    def test_unlinked_dynamic_profile_cannot_choose_another_municipality(self):
        self.configure("admin", [CONSULTAR, CONFIGURAR])
        with self.app.app_context():
            db.session.get(Usuario, 6).prefeitura_id = None
            db.session.commit()
        self.login(6)
        self.assertIn("ainda não está vinculado", self.client.get("/configuracoes").text)
        self.assertEqual(self.client.get("/configuracoes/documentos/1").status_code, 404)
        self.assertEqual(self.save().status_code, 404)

    def test_documents_navigation_stays_out_of_agro_and_finance(self):
        self.configure("admin", [CONSULTAR])
        for agro, finance in ((False, False), (True, False), (False, True)):
            with self.subTest(agro=agro, finance=finance), self.app.test_request_context("/configuracoes"):
                login_user(db.session.get(Usuario, 6))
                html = render_template("_configuracoes_nav.html", is_agro_context=agro,
                                       is_financeiro_context=finance, is_covisa_user=service.is_covisa_user,
                                       is_dev_user=service.is_dev_user)
                self.assertEqual('href="/configuracoes"' in html, not agro and not finance)


if __name__ == "__main__":
    unittest.main()
