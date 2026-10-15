"""Municipal settings with a real isolated database, templates and private storage."""
import importlib.util
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from flask import Flask, Response, render_template
from flask_login import LoginManager, login_user
from PIL import Image
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Prefeitura, Usuario, PrefeituraDocumentoConfig, PrefeituraDocumentoHistorico
from app.modules.auth.routes import bp as auth_bp
from app.modules.configuracoes import service
from app.routes import bp as main_bp
from app.shared.csrf_security import register_csrf_security, CSRF_SESSION_KEY

ROOT = Path(__file__).resolve().parents[1]


def picture(color="blue", size=(60, 40)):
    data = BytesIO()
    Image.new("RGBA", size, color).save(data, format="PNG")
    data.seek(0)
    return data


class DocumentSettingsTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.app = Flask(__name__, template_folder=str(ROOT / "app/templates"),
                         static_folder=str(ROOT / "app/static"), instance_path=self.folder.name)
        self.app.config.update(TESTING=True, SECRET_KEY="isolated-settings-test-secret-1234567890",
                               SQLALCHEMY_DATABASE_URI="sqlite:///:memory:", SESSION_PROTECTION=None)
        db.init_app(self.app)
        manager = LoginManager(self.app)
        manager.login_view = "auth.login"
        manager.user_loader(lambda key: db.session.get(Usuario, int(key)))
        with patch("app.modules.backup.routes.start_daily_backup_scheduler"):
            self.app.register_blueprint(auth_bp)
            self.app.register_blueprint(main_bp)
        register_csrf_security(self.app)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            db.session.add_all([Prefeitura(id=1, nome="Prefeitura Alfa", slug="alfa"),
                                Prefeitura(id=2, nome="Prefeitura Beta", slug="beta", ativa=False)])
            db.session.add_all([
                Usuario(id=key, login=f"user{key}", nome_uvis=f"Responsável {key}", senha_hash="unused",
                        tipo_usuario=role, prefeitura_id=city, regiao=region)
                for key, role, city, region in [
                    (1, "covisa", 1, "COVISA"), (2, "covisa", 2, "COVISA"),
                    (3, "dev", None, None), (4, "visualizar", 1, "COVISA"),
                    (5, "covisa", None, "COVISA"), (6, "admin", 1, None),
                    (7, "diretor", 1, None), (8, "prefeitura_admin", 1, None),
                    (9, "uvis", 1, None), (10, "visualizar", 1, "Outra"),
                ]
            ])
            db.session.commit()
        self.remote_files = {}
        def upload(storage, path):
            marker = "skybox://" + path
            self.remote_files[marker] = storage.read()
            return marker
        for patcher in (
            patch.object(service, "skybox_enabled", return_value=True),
            patch.object(service, "upload_file_to_skybox", side_effect=upload),
            patch.object(service, "delete_skybox_file", side_effect=lambda path: self.remote_files.pop(path)),
            patch("app.modules.configuracoes.routes.stream_skybox_file",
                  side_effect=lambda path: Response(self.remote_files[path], mimetype="image/png")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.login(1)

    def login(self, key):
        with self.client.session_transaction() as stored:
            stored.clear()
            stored["_user_id"] = str(key)
            stored["_fresh"] = True
            stored[CSRF_SESSION_KEY] = "test-csrf-token"

    def save(self, city=1, **changes):
        data = dict(_csrf_token="test-csrf-token", versao="0", opacidade="12", largura_percentual="55")
        data.update(changes)
        return self.client.post(f"/configuracoes/documentos/{city}", data=data)

    def test_anonymous_and_other_roles_are_denied(self):
        self.client = self.app.test_client()
        self.assertEqual(self.client.get("/configuracoes").status_code, 302)
        for key in range(6, 11):
            self.login(key)
            for path in ("/configuracoes", "/configuracoes/documentos/1", "/configuracoes/documentos/1/imagem"):
                with self.subTest(key=key, path=path):
                    self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(self.save().status_code, 403)

    def test_missing_document_tables_only_disable_the_new_settings(self):
        with self.app.app_context():
            PrefeituraDocumentoHistorico.__table__.drop(db.engine)
            PrefeituraDocumentoConfig.__table__.drop(db.engine)
        for path in ('/configuracoes', '/configuracoes/documentos/1',
                     '/configuracoes/documentos/1/imagem'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn('no such table', response.get_data(as_text=True))
        self.assertEqual(self.save().status_code, 503)
        with self.app.app_context():
            self.assertEqual(db.session.execute(text('SELECT 1')).scalar_one(), 1)
            self.assertEqual(Prefeitura.query.count(), 2)

    def test_covisa_scope_legacy_and_missing_association(self):
        for key in (1, 4):
            self.login(key)
            self.assertEqual(self.client.get("/configuracoes").location, "/configuracoes/documentos/1")
            page = self.client.get("/configuracoes/documentos/1")
            self.assertEqual(page.status_code, 200)
            self.assertIn('href="/configuracoes"', page.text)
            self.assertNotIn("Prefeitura Beta", page.text)
            for suffix in ("", "/imagem"):
                self.assertEqual(self.client.get("/configuracoes/documentos/2" + suffix).status_code, 404)
            self.assertEqual(self.save(city=2).status_code, 404)
        self.login(5)
        page = self.client.get("/configuracoes")
        self.assertIn("ainda não está vinculado", page.text)
        self.assertNotIn('id="document-settings-form"', page.text)
        self.assertEqual(self.save().status_code, 404)

    def test_dev_can_select_and_change_every_city(self):
        self.login(3)
        page = self.client.get("/configuracoes")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Prefeitura Alfa", page.text)
        self.assertIn("Prefeitura Beta (inativa)", page.text)
        for city in (1, 2):
            self.assertEqual(self.client.get(f"/configuracoes/documentos/{city}").status_code, 200)
            self.assertEqual(self.save(city=city, ativo="1", identificar_usuario="1").status_code, 303)
        with self.app.app_context():
            self.assertEqual(PrefeituraDocumentoConfig.query.count(), 2)
            self.assertEqual({h.usuario_id for h in PrefeituraDocumentoHistorico.query.all()}, {3})

    def test_navigation_only_for_covisa_and_dev(self):
        with self.app.test_request_context("/configuracoes"):
            for key in range(1, 11):
                user = db.session.get(Usuario, key)
                login_user(user)
                # Same helpers supplied to the actual base template.
                html = render_template("_configuracoes_nav.html", is_covisa_user=service.is_covisa_user,
                                       is_dev_user=service.is_dev_user)
                self.assertEqual('href="/configuracoes"' in html, key in (1, 2, 3, 4, 5))

    def test_csrf_and_scope_tampering(self):
        for global_csrf in (False, True):
            self.app.config["CSRF_PROTECTION_ENABLED"] = global_csrf
            self.assertEqual(self.save(_csrf_token="").status_code, 403)
            self.assertEqual(self.save(_csrf_token="wrong").status_code, 403)
            self.assertEqual(self.save(prefeitura_id="2").status_code, 403)
        self.assertEqual(self.save().status_code, 303)

    def test_upload_preview_replace_remove_and_history(self):
        self.assertEqual(self.save(ativo="1", imagem=(picture(), "brasao.png")).status_code, 303)
        with self.app.app_context():
            config = db.session.get(PrefeituraDocumentoConfig, 1)
            original = config.imagem_path
            self.assertIn(original, self.remote_files)
            self.assertTrue(original.startswith("skybox://prefeituras_logo/1/"))
            self.assertEqual(config.versao, 1)
        response = self.client.get("/configuracoes/documentos/1/imagem")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(Image.open(BytesIO(response.data)).size, (60, 40))
        self.login(2)
        self.assertEqual(self.client.get("/configuracoes/documentos/1/imagem").status_code, 404)
        self.assertNotIn("Responsável 1", self.client.get("/configuracoes/documentos/2").text)
        self.login(1)
        self.assertEqual(self.save(versao="1", imagem=(picture("red"), "novo.png")).status_code, 303)
        self.assertNotIn(original, self.remote_files)
        with self.app.app_context():
            replacement = db.session.get(PrefeituraDocumentoConfig, 1).imagem_path
        self.assertEqual(self.save(versao="2", remover_imagem="1").status_code, 303)
        self.assertNotIn(replacement, self.remote_files)
        self.assertEqual(self.client.get("/configuracoes/documentos/1/imagem").status_code, 404)
        with self.app.app_context():
            config = db.session.get(PrefeituraDocumentoConfig, 1)
            self.assertIsNone(config.imagem_path)
            self.assertEqual(config.versao, 3)
            history = PrefeituraDocumentoHistorico.query.order_by(PrefeituraDocumentoHistorico.id).all()
            self.assertEqual(len(history), 3)
            self.assertEqual(history[1].antes["imagem_nome"], "brasao.png")
            self.assertTrue(history[2].depois["imagem_alterada"])

    def test_stale_update_preserves_current_image(self):
        self.assertEqual(self.save(imagem=(picture(), "first.png")).status_code, 303)
        self.assertEqual(self.save(imagem=(picture("red"), "stale.png")).status_code, 409)
        with self.app.app_context():
            self.assertEqual(db.session.get(PrefeituraDocumentoConfig, 1).imagem_nome, "first.png")
            self.assertEqual(PrefeituraDocumentoHistorico.query.count(), 1)
        self.assertEqual(len(self.remote_files), 1)
        self.assertEqual(list(Path(self.folder.name).rglob("*.png")), [])

    def test_failed_commit_keeps_old_image_and_removes_new_upload(self):
        self.assertEqual(self.save(imagem=(picture(), "first.png")).status_code, 303)
        with patch.object(db.session, "commit", side_effect=SQLAlchemyError("simulated")):
            response = self.save(versao="1", imagem=(picture("red"), "second.png"))
        self.assertEqual(response.status_code, 503)
        with self.app.app_context():
            self.assertEqual(db.session.get(PrefeituraDocumentoConfig, 1).imagem_nome, "first.png")
            self.assertEqual(PrefeituraDocumentoHistorico.query.count(), 1)
        self.assertEqual(len(self.remote_files), 1)
        self.assertEqual(list(Path(self.folder.name).rglob("*.png")), [])

    def test_invalid_fields_and_images_have_no_side_effects(self):
        cases = [dict(ativo="1"), dict(opacidade="90"), dict(largura_percentual="0"),
                 dict(versao="bad"), dict(remover_imagem="1", imagem=(picture(), "image.png")),
                 dict(imagem=(BytesIO(b"<svg/>"), "fake.png")), dict(imagem=(picture(), "image.svg")),
                 dict(imagem=(BytesIO(b"x" * (5 * 1024 * 1024 + 1)), "large.png")),
                 dict(imagem=(picture(size=(4097, 1)), "wide.png"))]
        for data in cases:
            with self.subTest(fields=list(data)):
                self.assertEqual(self.save(**data).status_code, 400)
        with self.app.app_context():
            self.assertEqual(PrefeituraDocumentoConfig.query.count(), 0)
            self.assertEqual(PrefeituraDocumentoHistorico.query.count(), 0)
        self.assertEqual(list(Path(self.folder.name).rglob("*.png")), [])

    def test_distinct_prefeituras_keep_distinct_preferences(self):
        self.assertEqual(self.save(ativo="1", identificar_usuario="1", opacidade="15").status_code, 303)
        self.login(2)
        self.assertEqual(self.save(city=2, opacidade="25").status_code, 303)
        with self.app.app_context():
            self.assertEqual(db.session.get(PrefeituraDocumentoConfig, 1).opacidade, 15)
            self.assertEqual(db.session.get(PrefeituraDocumentoConfig, 2).opacidade, 25)

    def test_storage_failure_does_not_create_settings(self):
        with patch.object(service, "store_image", side_effect=service.SkyboxError("unavailable")):
            self.assertEqual(self.save(imagem=(picture(), "brasao.png")).status_code, 503)
        with self.app.app_context():
            self.assertEqual(PrefeituraDocumentoConfig.query.count(), 0)

    def test_missing_skybox_rejects_upload_without_local_fallback(self):
        self.assertEqual(self.save(imagem=(picture(), "first.png")).status_code, 303)
        original_files = dict(self.remote_files)
        with patch.object(service, "skybox_enabled", return_value=False):
            self.assertEqual(self.save(versao="1", imagem=(picture("red"), "new.png")).status_code, 503)
        self.assertEqual(self.remote_files, original_files)
        self.assertEqual(list(Path(self.folder.name).rglob("*.png")), [])
        with self.app.app_context():
            self.assertEqual(db.session.get(PrefeituraDocumentoConfig, 1).versao, 1)
            self.assertEqual(PrefeituraDocumentoHistorico.query.count(), 1)

    def test_legacy_local_image_stays_readable_until_replaced_on_skybox(self):
        with self.app.app_context():
            old_path = "prefeituras/1/documentos/legacy.png"
            local = service.local_image_path(old_path)
            local.parent.mkdir(parents=True)
            local.write_bytes(picture().getvalue())
            db.session.add(PrefeituraDocumentoConfig(prefeitura_id=1, imagem_path=old_path, imagem_nome="legacy.png"))
            db.session.commit()
        response = self.client.get("/configuracoes/documentos/1/imagem")
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual(self.save(versao="1", imagem=(picture("red"), "new.png")).status_code, 303)
        self.assertFalse(local.exists())
        self.assertEqual(len(self.remote_files), 1)
        with self.app.app_context():
            self.assertTrue(db.session.get(PrefeituraDocumentoConfig, 1).imagem_path.startswith("skybox://prefeituras_logo/1/"))


class DocumentSettingsMigrationTests(unittest.TestCase):
    def test_upgrade_defaults_constraints_and_downgrade(self):
        path = ROOT / "migrations/versions/a71d9c4e203b_prefeitura_documento_config.py"
        spec = importlib.util.spec_from_file_location("document_settings_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))
            connection.execute(text("CREATE TABLE prefeituras (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY)"))
            connection.execute(text("INSERT INTO prefeituras VALUES (1)"))
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                connection.execute(text("INSERT INTO prefeitura_documento_config (prefeitura_id) VALUES (1)"))
                row = connection.execute(text("SELECT opacidade, largura_percentual, ativo, versao FROM prefeitura_documento_config")).one()
                self.assertEqual(tuple(row), (12, 55, 0, 1))
                with self.assertRaises(SQLAlchemyError):
                    connection.execute(text("UPDATE prefeitura_documento_config SET opacidade=99"))
                self.assertEqual(len(inspect(connection).get_foreign_keys("prefeitura_documento_historico")), 2)
                connection.execute(text("INSERT INTO usuarios VALUES (1)"))
                connection.execute(text("INSERT INTO prefeitura_documento_historico (prefeitura_id, usuario_id, usuario_nome, antes, depois) VALUES (1, 1, 'Responsável original', '{}', '{}')"))
                connection.execute(text("DELETE FROM usuarios WHERE id=1"))
                event = connection.execute(text("SELECT usuario_id, usuario_nome FROM prefeitura_documento_historico")).one()
                self.assertEqual(tuple(event), (None, "Responsável original"))
                module.downgrade()
                self.assertEqual(set(inspect(connection).get_table_names()), {"prefeituras", "usuarios"})
        scripts = ScriptDirectory(str(ROOT / "migrations"))
        self.assertEqual(len(scripts.get_heads()), 1)
        self.assertIn("c1a0f8b6d2e4", {r.revision for r in scripts.walk_revisions()})
        self.assertEqual(scripts.get_revision("c1a0f8b6d2e4").down_revision, module.revision)
        self.assertIn(module.revision, {revision.revision for revision in scripts.walk_revisions()})
