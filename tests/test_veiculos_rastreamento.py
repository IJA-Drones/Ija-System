import unittest
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader

from app.extensions import db
from app.models import (
    Equipe,
    EquipePiloto,
    Pilotos,
    Prefeitura,
    RastreamentoAlerta,
    RastreamentoHistorico,
    RastreamentoPosicao,
    Usuario,
    Veiculos,
)
from app.modules.veiculos.routes import register_routes


class VeiculosRastreamentoTests(unittest.TestCase):
    def setUp(self):
        templates = Path(__file__).resolve().parents[1] / "app" / "templates"
        self.app = Flask(__name__, template_folder=str(templates))
        self.app.config.update(TESTING=True, SECRET_KEY="test", SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
        self.app.jinja_loader = ChoiceLoader([
            DictLoader({"base.html": "{% block content %}{% endblock %}"}),
            self.app.jinja_loader,
        ])
        db.init_app(self.app)
        manager = LoginManager(self.app)
        manager.user_loader(lambda user_id: db.session.get(Usuario, int(user_id)))
        bp = Blueprint("main", __name__)
        register_routes(bp)
        self.app.register_blueprint(bp)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([
            Prefeitura(id=1, nome="Prefeitura A", slug="a"),
            Prefeitura(id=2, nome="Prefeitura B", slug="b"),
            Equipe(id=1, nome_equipe="Equipe A", prefeitura_id=1),
            Equipe(id=2, nome_equipe="Equipe B", prefeitura_id=1),
        ])
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def login(self, role="prefeitura_admin", **fields):
        user = Usuario(nome_uvis="Teste", login="teste", senha_hash="unused", tipo_usuario=role, **fields)
        db.session.add(user)
        db.session.commit()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return user

    def vehicle(self, plate, **fields):
        vehicle = Veiculos(placa=plate, modelo="Fiorino", renomacao=plate, operacao="PMSP", frota="PROPRIA", km_atual=1234, **fields)
        db.session.add(vehicle)
        db.session.commit()
        return vehicle

    def data(self):
        response = self.client.get("/veiculos/rastreamento/dados")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        return response.get_json()

    def test_requires_login_for_page_and_data(self):
        for path in ("/veiculos/rastreamento", "/veiculos/rastreamento/dados"):
            self.assertEqual(self.client.get(path).status_code, 401)

    def test_unauthorized_role_cannot_view_page_or_data(self):
        self.login("financeiro")
        for path in ("/veiculos/rastreamento", "/veiculos/rastreamento/dados"):
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_filters_prefeitura_and_inactive_vehicles(self):
        self.vehicle("AAA1A11", prefeitura_id=1)
        self.vehicle("BBB2B22", prefeitura_id=2)
        self.vehicle("CCC3C33", prefeitura_id=1, status="Inativo")
        self.login(prefeitura_id=1)
        self.assertEqual([v["plate"] for v in self.data()["vehicles"]], ["AAA1A11"])

    def test_team_sees_only_its_vehicles_including_legacy_without_prefeitura(self):
        self.vehicle("AAA1A11", equipe_id=1, prefeitura_id=None)
        self.vehicle("BBB2B22", equipe_id=2, prefeitura_id=1)
        self.login("equipe_oceano", prefeitura_id=1, codigo_setor="1")
        self.assertEqual([v["plate"] for v in self.data()["vehicles"]], ["AAA1A11"])

    def test_pilot_only_sees_vehicles_assigned_to_their_team(self):
        pilot = Pilotos(nome_piloto="Piloto Teste", prefeitura_id=1)
        db.session.add(pilot)
        db.session.flush()
        db.session.add(EquipePiloto(equipe_id=1, piloto_id=pilot.id, papel="piloto"))
        self.vehicle("AAA1A11", equipe_id=1, prefeitura_id=1)
        self.vehicle("BBB2B22", equipe_id=2, prefeitura_id=1)
        self.login("piloto", prefeitura_id=1, piloto_id=pilot.id)
        data = self.data()
        self.assertEqual([v["plate"] for v in data["vehicles"]], ["AAA1A11"])
        self.assertIsNone(data["vehicles"][0]["logs_url"])

    def test_missing_pilot_or_prefeitura_assignment_does_not_expand_access(self):
        self.vehicle("AAA1A11", prefeitura_id=1)
        user = self.login("piloto", prefeitura_id=1)
        self.assertEqual(self.data()["vehicles"], [])
        user.tipo_usuario = "prefeitura_admin"
        user.prefeitura_id = None
        db.session.commit()
        self.assertEqual(self.data()["vehicles"], [])

    def test_pending_state_keeps_gps_unknown_and_registered_km_unchanged(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.login("dev")
        data = self.data()
        self.assertEqual(data["integration"]["status"], "pending")
        self.assertIsNone(data["integration"]["synced_at"])
        self.assertIsNone(data["vehicles"][0]["position"])
        self.assertEqual(data["vehicles"][0]["history"], [])
        self.assertEqual(data["vehicles"][0]["registered_km"], 1234)
        self.assertEqual(db.session.get(Veiculos, vehicle.id).km_atual, 1234)

    def test_fixture_positions_history_and_alerts_are_returned_for_scoped_vehicle(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        now = datetime.now()
        db.session.add(RastreamentoPosicao(
            veiculo_id=vehicle.id,
            prefeitura_id=1,
            latitude=-23.55,
            longitude=-46.63,
            velocidade_kmh=28,
            ignicao=True,
            hodometro_km=1240,
            endereco="São Paulo · fixture",
            reportado_em=now,
            is_demo=True,
            chave_fixture="test:position:1",
        ))
        db.session.add(RastreamentoHistorico(
            veiculo_id=vehicle.id,
            prefeitura_id=1,
            latitude=-23.56,
            longitude=-46.64,
            velocidade_kmh=12,
            ignicao=True,
            reportado_em=now - timedelta(minutes=5),
            is_demo=True,
            chave_fixture="test:history:1",
        ))
        db.session.add(RastreamentoAlerta(
            veiculo_id=vehicle.id,
            prefeitura_id=1,
            tipo="Velocidade",
            severidade="media",
            mensagem="Alerta de teste",
            reportado_em=now,
            is_demo=True,
            chave_fixture="test:alert:1",
        ))
        db.session.commit()
        self.login(prefeitura_id=1)
        data = self.data()
        self.assertEqual(data["integration"]["status"], "test")
        self.assertEqual(data["integration"]["source"], "Neon · fixture fictícia")
        payload = data["vehicles"][0]
        self.assertEqual(payload["position"]["lat"], -23.55)
        self.assertEqual(payload["history"][0]["lng"], -46.64)
        self.assertEqual(payload["alerts"][0]["title"], "Velocidade")

    def test_page_renders_and_escapes_embedded_vehicle_data(self):
        self.vehicle("AAA1A11", prefeitura_id=1, responsavel="Teste")
        vehicle = Veiculos.query.first()
        vehicle.modelo = '</script><script>alert("x")</script>'
        db.session.commit()
        self.login("dev")
        response = self.client.get("/veiculos/rastreamento")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Explorar demonstração", html)
        self.assertIn('class="btn btn-outline-primary"', html)
        self.assertIn('tracking-module-tabs nav nav-tabs', html)
        self.assertIn('class="form-control form-control-sm" type="date"', html)
        self.assertNotIn('</script><script>alert("x")', html)
        self.assertIn("no-store", response.headers["Cache-Control"])


if __name__ == "__main__":
    unittest.main()
