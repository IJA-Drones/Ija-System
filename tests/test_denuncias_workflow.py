"""HTTP workflow on an isolated database; no real reports or external APIs."""
import unittest
from datetime import date
from unittest.mock import patch

from flask import Blueprint, Flask, g
from flask_login import LoginManager
from app.extensions import db
from app.models import Denuncia, Solicitacao, Usuario
from app.modules.denuncias.routes import register_routes
from app.modules.denuncias.service import count_denuncias_alerta


class DenunciasWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY="test", SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
        db.init_app(self.app)
        login = LoginManager(self.app)
        login.user_loader(lambda uid: db.session.get(Usuario, int(uid)))
        bp = Blueprint("main", __name__)
        register_routes(bp)
        bp.add_url_rule("/dashboard", endpoint="dashboard", view_func=lambda: "ok")
        bp.add_url_rule("/admin", endpoint="admin_dashboard", view_func=lambda: "ok")
        self.app.register_blueprint(bp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for uid, role, region in [(1,"covisa","COVISA"),(2,"regional","NORTE"),(3,"uvis","NORTE"),
                                   (4,"regional","SUL"),(5,"uvis","SUL"),(6,"operario","NORTE"),
                                   (7,"visualizar","COVISA"),(8,"regional",None)]:
            db.session.add(Usuario(id=uid, login=str(uid), senha_hash="test", nome_uvis=str(uid),
                                   tipo_usuario=role, regiao=region))
        self.report = Denuncia(protocolo="DEN-TEST", status="RECEBIDA", tipo_visita="Aedes",
            tipo_imovel="Imovel Geral", foco="Piscina", descricao="Observação de teste",
            logradouro="Rua Teste", numero="10", bairro="Centro", cidade="São Paulo", uf="SP",
            cidadao_nome="Pessoa de teste", cidadao_cpf="529.982.247-25", cidadao_rg="",
            cidadao_telefone="(11) 98765-4321", consentimento=True)
        db.session.add(self.report)
        db.session.commit()
        self.client = self.app.test_client()
        self.render = patch("app.modules.denuncias.routes.render_template", return_value="rendered")
        self.render.start()
        self.geo = patch("app.modules.solicitacoes.service.resolve_google_place_id_for_address", return_value=None)
        self.geo.start()

    def tearDown(self):
        self.geo.stop()
        self.render.stop()
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def as_user(self, uid):
        g.pop("_login_user", None)
        with self.client.session_transaction() as session:
            session["_user_id"] = str(uid)
            session["_fresh"] = True

    def forward(self):
        self.as_user(1)
        self.assertEqual(self.client.post("/denuncias/1/encaminhar-coordenadoria",
            data={"coordenadoria":"NORTE"}).status_code, 302)

    def assign(self):
        self.forward()
        self.as_user(2)
        self.assertEqual(self.client.post("/coordenadoria/denuncias/1/designar-uvis",
            data={"uvis_usuario_id":3}).status_code, 302)

    def conversion_form(self):
        return dict(data=date.today().isoformat(), hora="09:00", cep="", logradouro="Rua Teste", numero="10", bairro="Centro", cidade="São Paulo", uf="SP",
                    distrito_administrativo="Santana", tipo_visita="Aedes", tipo_imovel="Imovel Geral",
                    foco="Piscina", observacao="Solicitação originada da denúncia DEN-TEST. Observação de teste")

    def test_complete_workflow_and_duplicate_submit(self):
        self.assertEqual(count_denuncias_alerta(db.session.get(Usuario, 1)), 1)
        self.assign()
        self.assertEqual(count_denuncias_alerta(db.session.get(Usuario, 1)), 0)
        self.assertEqual(count_denuncias_alerta(db.session.get(Usuario, 3)), 1)
        self.as_user(3)
        self.assertEqual(self.client.post("/uvis/denuncias/1", data=self.conversion_form()).status_code, 302)
        db.session.refresh(self.report)
        self.assertEqual(self.report.status, "CONVERTIDA_SOLICITACAO")
        self.assertEqual(self.report.solicitacao.usuario_id, 3)
        self.assertIn("Observação de teste", self.report.solicitacao.observacao)
        self.assertEqual(self.report.cidadao_rg, "")
        self.assertEqual(count_denuncias_alerta(db.session.get(Usuario, 3)), 0)
        self.client.post("/uvis/denuncias/1", data=self.conversion_form())
        self.assertEqual(Solicitacao.query.count(), 1)
        self.as_user(1)
        self.client.post("/denuncias/1/arquivar", data={"motivo":"Não deve arquivar"})
        self.assertEqual(self.report.status, "CONVERTIDA_SOLICITACAO")

    def test_roles_cannot_perform_central_actions(self):
        for uid in (2,3,4,5,6,8):
            self.as_user(uid)
            for action, data in [("encaminhar-coordenadoria",{"coordenadoria":"NORTE"}),
                                 ("arquivar",{"motivo":"Relato duplicado"})]:
                self.assertEqual(self.client.post("/denuncias/1/"+action, data=data).status_code, 403)
        self.assertEqual(self.report.status, "RECEBIDA")

    def test_region_scope_and_wrong_uvis(self):
        self.forward()
        for uid in (4,5,8):
            self.as_user(uid)
            self.assertEqual(self.client.get("/denuncias/1").status_code, 403)
        self.as_user(2)
        self.client.post("/coordenadoria/denuncias/1/designar-uvis", data={"uvis_usuario_id":5})
        self.assertIsNone(self.report.uvis_usuario_id)

    def test_reassignment_revokes_previous_uvis(self):
        self.assign()
        self.as_user(1)
        self.client.post("/denuncias/1/encaminhar-coordenadoria", data={"coordenadoria":"SUL"})
        db.session.refresh(self.report)
        self.assertIsNone(self.report.uvis_usuario_id)
        self.as_user(3)
        self.assertEqual(self.client.get("/uvis/denuncias/1").status_code, 403)

    def test_archive_blocks_conversion(self):
        self.assign()
        self.as_user(1)
        self.client.post("/denuncias/1/arquivar", data={"motivo":"Relato duplicado confirmado"})
        self.as_user(3)
        self.assertEqual(self.client.post("/uvis/denuncias/1", data=self.conversion_form()).status_code, 409)
        self.assertEqual(Solicitacao.query.count(), 0)

    def test_conversion_failure_rolls_back_solicitacao(self):
        self.assign()
        self.as_user(3)
        with patch.object(db.session, "commit", side_effect=RuntimeError("simulated failure")):
            response = self.client.post("/uvis/denuncias/1", data=self.conversion_form())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Solicitacao.query.count(), 0)
        db.session.refresh(self.report)
        self.assertEqual(self.report.status, "ENCAMINHADA_UVIS")
        self.assertIsNone(self.report.solicitacao_id)

    def test_legacy_covisa_and_role_redirects(self):
        self.as_user(7)
        self.assertEqual(self.client.get("/denuncias").status_code, 200)
        self.forward()
        self.as_user(2)
        self.assertTrue(self.client.get("/denuncias/1").location.endswith("/coordenadoria/denuncias/1"))
        self.assertEqual(self.client.get("/coordenadoria/denuncias").status_code, 200)
        self.as_user(6)
        self.assertEqual(self.client.get("/denuncias").status_code, 403)


if __name__ == "__main__":
    unittest.main()
