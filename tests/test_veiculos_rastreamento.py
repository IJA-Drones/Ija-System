import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from flask import Blueprint, Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader

from app.extensions import db
from app.models import (
    Equipe,
    EquipePiloto,
    LogVeiculo,
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
        self.assertEqual(self.client.post('/veiculos/rastreamento/historico', json={}).status_code, 401)

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

    def test_registered_responsible_is_resolved_separately_from_shift_driver(self):
        supervisor = Usuario(nome_uvis="Responsável cadastrado", login="responsavel", senha_hash="unused",
                             tipo_usuario="sup_veiculos", prefeitura_id=1)
        db.session.add(supervisor)
        db.session.flush()
        self.vehicle("AAA1A11", prefeitura_id=1, responsavel=f"sup_veiculos:{supervisor.id}")
        self.vehicle("BBB2B22", prefeitura_id=1, responsavel="Nome do cadastro antigo")
        self.vehicle("CCC3C33", prefeitura_id=1)
        self.vehicle("DDD4D44", prefeitura_id=2, responsavel="Outra prefeitura")
        self.login(prefeitura_id=1)
        vehicles = self.data()["vehicles"]
        self.assertEqual([v["responsible"] for v in vehicles],
                         ["Responsável cadastrado", "Nome do cadastro antigo", None])
        self.assertTrue(all(v["driver"] is None for v in vehicles))

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
        self.assertIn('type="datetime-local" id="trackingPeriodStart"', html)
        self.assertIn('type="datetime-local" id="trackingPeriodEnd"', html)
        self.assertNotIn('</script><script>alert("x")', html)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_live_sync_keeps_vehicle_scope_and_credentials_private(self):
        self.vehicle("AAA1A11", prefeitura_id=1)
        self.vehicle("BBB2B22", prefeitura_id=2)
        self.login(prefeitura_id=1)
        self.app.config.update(REDGPS_SYNC_ENABLED=True, REDGPS_API_KEY="private-test-key")
        client = Mock()
        from tests.test_redgps_sync import reading
        client.read.return_value = [reading(UnitPlate="AAA1A11"), reading(UnitPlate="BBB2B22")]
        self.app.extensions["redgps_client"] = client
        data = self.data()
        self.assertEqual([v["plate"] for v in data["vehicles"]], ["AAA1A11"])
        self.assertEqual(data["integration"]["status"], "connected")
        self.assertTrue(data["vehicles"][0]["position"]["reported_at"].endswith("Z"))
        self.assertNotIn("private-test-key", str(data))
        self.assertEqual(db.session.query(RastreamentoPosicao).count(), 2)

    def test_history_is_filtered_by_selected_brazilian_day(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.login(prefeitura_id=1)
        for when in (datetime(2026, 10, 7, 2, 59), datetime(2026, 10, 7, 3, 0)):
            db.session.add(RastreamentoHistorico(veiculo_id=vehicle.id, latitude=-23, longitude=-46,
                                                reportado_em=when, is_demo=False))
        db.session.commit()
        data = self.client.get("/veiculos/rastreamento/dados?date=2026-10-07").get_json()
        self.assertEqual(len(data["vehicles"][0]["history"]), 1)
        self.assertEqual(data["vehicles"][0]["history"][0]["reported_at"], "2026-10-07T03:00:00Z")

    def shift(self, vehicle, **changes):
        log = LogVeiculo(**{
            "veiculo_id": vehicle.id, "equipe_id": vehicle.equipe_id,
            "data_registro": datetime(2026, 10, 7, 8), "encerrado_em": datetime(2026, 10, 7, 8, 10),
            "km_inicial": 100, "km_final": 110, "condutor_nome": "Condutora de teste", **changes,
        })
        db.session.add(log)
        db.session.flush()
        return log

    def samples(self, vehicle, minutes=(0, 5, 10), odometers=(100, 105, 110), **changes):
        for minute, odometer in zip(minutes, odometers):
            db.session.add(RastreamentoHistorico(**{
                "veiculo_id": vehicle.id, "latitude": -23.55, "longitude": -46.63,
                "reportado_em": datetime(2026, 10, 7, 11) + timedelta(minutes=minute),
                "velocidade_kmh": 60, "hodometro_km": odometer, "is_demo": False, **changes,
            }))

    def day_data(self):
        db.session.commit()
        response = self.client.get('/veiculos/rastreamento/dados?date=2026-10-07')
        self.assertEqual(response.status_code, 200)
        return response.get_json()["vehicles"][0]

    def test_links_route_to_shift_driver_with_explicit_brazil_timezone(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        log = self.shift(vehicle)
        self.samples(vehicle)
        self.login(prefeitura_id=1)
        data = self.day_data()
        row = data["daily"]["logs"][0]
        self.assertEqual(row["started_at"], "2026-10-07T08:00:00-03:00")
        self.assertEqual(row["gps"]["distance_km"], 10)
        self.assertEqual(row["comparison"], "within_tolerance")
        self.assertEqual(row["difference_km"], 0)
        self.assertEqual(data["daily"]["recorded_km"], 10)
        self.assertTrue(all(p["log_id"] == log.id and p["driver_name"] == "Condutora de teste" for p in data["history"]))
        self.assertIn(f"#turnoHeader{log.id}", row["url"])
        self.assertIsNone(data["driver"])  # A closed shift is not the current driver.
        self.assertEqual(db.session.get(Veiculos, vehicle.id).km_atual, 1234)
        self.assertEqual(db.session.get(LogVeiculo, log.id).km_final, 110)

    def test_detects_difference_without_changing_logged_or_vehicle_km(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.shift(vehicle)
        self.samples(vehicle, odometers=(100, 107.5, 115))
        self.login(prefeitura_id=1)
        row = self.day_data()["daily"]["logs"][0]
        self.assertEqual(row["comparison"], "difference")
        self.assertEqual(row["difference_km"], 5)
        self.assertEqual(row["tolerance_km"], 2)

    def test_legacy_log_without_end_is_inconclusive_and_not_assigned_to_samples(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.shift(vehicle, encerrado_em=None)
        self.samples(vehicle)
        self.login(prefeitura_id=1)
        data = self.day_data()
        self.assertEqual(data["daily"]["logs"][0]["reason"], "unknown_end")
        self.assertEqual(data["daily"]["unlinked_samples"], 3)
        self.assertTrue(all(p["log_id"] is None for p in data["history"]))

    def test_route_gaps_are_not_joined_or_treated_as_complete_comparison(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.shift(vehicle, encerrado_em=datetime(2026, 10, 7, 8, 30))
        self.samples(vehicle, minutes=(0, 5, 30), odometers=(100, 105, 130))
        self.login(prefeitura_id=1)
        data = self.day_data()
        self.assertEqual(data["daily"]["distance_km"], 5)
        self.assertEqual(data["daily"]["gaps"], 1)
        self.assertTrue(data["history"][2]["break_before"])
        self.assertEqual(data["daily"]["logs"][0]["reason"], "partial_gps")

    def test_uncovered_shift_boundaries_prevent_a_false_difference(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.shift(vehicle, data_registro=datetime(2026, 10, 7, 7))
        self.samples(vehicle)
        self.login(prefeitura_id=1)
        row = self.day_data()["daily"]["logs"][0]
        self.assertEqual(row["reason"], "partial_gps")
        self.assertIsNone(row["difference_km"])

    def test_missing_odometer_produces_only_estimate(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.shift(vehicle)
        self.samples(vehicle, odometers=(None, None, None))
        self.login(prefeitura_id=1)
        row = self.day_data()["daily"]["logs"][0]
        self.assertEqual(row["gps"]["distance_source"], "estimated")
        self.assertEqual(row["reason"], "estimated_gps")
        self.assertIsNone(row["difference_km"])

    def test_odometer_resets_and_implausible_jumps_are_discarded(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.shift(vehicle)
        self.samples(vehicle, odometers=(100, 90, 1000))
        self.login(prefeitura_id=1)
        data = self.day_data()
        self.assertIsNone(data["daily"]["distance_km"])
        self.assertEqual(data["daily"]["invalid_segments"], 2)
        self.assertTrue(all(not p["geometry_break_before"] for p in data["history"]))
        self.assertEqual(data["daily"]["logs"][0]["reason"], "partial_gps")

    def test_overlapping_shifts_do_not_assign_driver_to_ambiguous_samples(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.shift(vehicle)
        self.shift(vehicle, condutor_nome="Outro condutor")
        self.samples(vehicle)
        self.login(prefeitura_id=1)
        data = self.day_data()
        self.assertTrue(all(row["reason"] == "overlap" for row in data["daily"]["logs"]))
        self.assertTrue(all(p["log_id"] is None for p in data["history"]))

    def test_open_driver_is_current_even_when_consulting_a_past_day(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        now = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        log = self.shift(vehicle, data_registro=now - timedelta(minutes=10), encerrado_em=None, km_final=None)
        self.login(prefeitura_id=1)
        data = self.day_data()
        self.assertEqual(data["driver"]["log_id"], log.id)
        self.assertEqual(data["daily"]["logs"], [])

    def test_unidentified_team_driver_does_not_fall_back_to_supervisor_or_team_name(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1, equipe_id=1, responsavel="Supervisor responsável")
        self.shift(vehicle, condutor_nome=None, km_final=None, encerrado_em=None)
        self.login(prefeitura_id=1)
        self.assertIsNone(self.day_data()["driver"]["name"])

    def test_current_ploa_driver_is_available_without_a_shift_and_is_separate_from_old_logs(self):
        titular = Pilotos(nome_piloto="Piloto titular do PLOA", prefeitura_id=1)
        db.session.add(titular); db.session.flush()
        db.session.add(EquipePiloto(equipe_id=1, piloto_id=titular.id, papel="piloto"))
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1, equipe_id=1, responsavel="Supervisor cadastrado")
        self.shift(vehicle, condutor_nome="Condutor registrado no passado")
        self.login(prefeitura_id=1)
        data = self.day_data()
        self.assertEqual(data['ploa_driver']['name'], 'Piloto titular do PLOA')
        self.assertEqual(data['ploa_driver']['pilot_id'], titular.id)
        self.assertIsNone(data['driver'])
        self.assertEqual(data['daily']['logs'][0]['driver']['name'], 'Condutor registrado no passado')
        self.assertEqual(data['responsible'], 'Supervisor cadastrado')

    def test_no_log_still_exposes_route_and_unlinked_sample_count(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.samples(vehicle)
        self.login(prefeitura_id=1)
        data = self.day_data()
        self.assertEqual(data["daily"]["logs"], [])
        self.assertEqual(data["daily"]["unlinked_samples"], 3)
        self.assertIsNone(data["daily"]["recorded_km"])

    def test_cross_midnight_shift_is_linked_but_not_compared_to_only_one_day(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        log = self.shift(vehicle, data_registro=datetime(2026, 10, 6, 23))
        self.samples(vehicle)
        self.login(prefeitura_id=1)
        data = self.day_data()
        self.assertEqual(data["daily"]["logs"][0]["reason"], "crosses_day")
        self.assertEqual(data["history"][0]["log_id"], log.id)
        self.assertIsNone(data["daily"]["recorded_km"])

    def test_foreign_vehicle_logs_and_former_team_drivers_remain_private(self):
        own = self.vehicle("AAA1A11", prefeitura_id=1, equipe_id=1)
        foreign = self.vehicle("BBB2B22", prefeitura_id=2, equipe_id=2)
        self.shift(own, equipe_id=2, condutor_nome="Equipe anterior")
        self.shift(foreign, condutor_nome="Outro município")
        self.login("equipe_oceano", prefeitura_id=1, codigo_setor="1")
        data = self.day_data()
        self.assertEqual(data["plate"], own.placa)
        self.assertEqual(data["daily"]["logs"], [])
        self.assertNotIn("Outro município", str(data))

    def test_shared_account_can_record_driver_and_real_closing_time(self):
        from io import BytesIO
        from unittest.mock import patch
        from werkzeug.datastructures import FileStorage
        from app.modules.veiculos.service import iniciar_turno_piloto, encerrar_turno_piloto
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1, equipe_id=1)
        user = self.login("equipe_oceano", prefeitura_id=1, codigo_setor="1")
        photo = lambda: FileStorage(stream=BytesIO(b"fake"), filename="demo.png")
        with patch('app.modules.veiculos.service._salvar_upload_veiculo', return_value='fixture.png'):
            iniciar_turno_piloto(user, vehicle.id, {"assinatura_b64": "fixture", "condutor_nome": "  Condutor Fictício  "}, {"foto_painel": photo()}, "/tmp")
            log = LogVeiculo.query.one()
            self.assertEqual(log.condutor_nome, "Condutor Fictício")
            self.assertIsNone(log.encerrado_em)
            encerrar_turno_piloto(user, vehicle.id, {"km_final": "1240"}, {"foto_painel_final": photo()}, "/tmp")
        self.assertIsNotNone(log.encerrado_em)
        self.assertGreaterEqual(log.encerrado_em, log.data_registro)

    def test_history_api_imports_only_authorized_vehicle_and_reuses_recent_result(self):
        from tests.test_redgps_history import historical
        from tests.test_redgps_sync import reading
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        foreign = self.vehicle("BBB2B22", prefeitura_id=2)
        self.login(prefeitura_id=1)
        self.app.config['REDGPS_SYNC_ENABLED'] = True
        client = Mock()
        client.read.return_value = [reading(GpsIdentif="device-test")]
        client.read_history.return_value = [historical(gmt="-3")]
        self.app.extensions['redgps_client'] = client
        url = '/veiculos/rastreamento/historico'
        self.assertEqual(self.client.post(url, json={'vehicle_id': foreign.id, 'date': '2026-10-07'}).status_code, 404)
        client.read.assert_not_called()
        for _ in range(2):
            result = self.client.post(url, json={'vehicle_id': vehicle.id, 'date': '2026-10-07'})
            self.assertEqual(result.status_code, 200)
            self.assertIn('no-store', result.headers['Cache-Control'])
        client.read_history.assert_called_once()
        self.assertEqual(RastreamentoHistorico.query.count(), 1)

    def test_history_api_rejects_forbidden_roles_and_bad_requests(self):
        url = '/veiculos/rastreamento/historico'
        user = self.login('financeiro', prefeitura_id=1)
        self.assertEqual(self.client.post(url, json={}).status_code, 403)
        user.tipo_usuario = 'prefeitura_admin'
        db.session.commit()
        for payload in (None, [], {'vehicle_id': 'invalid', 'date': '2026-10-07'}):
            self.assertEqual(self.client.post(url, json=payload).status_code, 400)

    def test_period_filters_local_hours_across_midnight_including_the_last_minute(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.login(prefeitura_id=1)
        for when in (datetime(2026, 10, 7, 2, 58), datetime(2026, 10, 7, 2, 59),
                     datetime(2026, 10, 7, 3, 1, 59), datetime(2026, 10, 7, 3, 2)):
            db.session.add(RastreamentoHistorico(veiculo_id=vehicle.id, latitude=-23, longitude=-46,
                                                reportado_em=when, is_demo=False))
        db.session.commit()
        data = self.client.get('/veiculos/rastreamento/dados?start=2026-10-06T23:59&end=2026-10-07T00:01').get_json()
        self.assertEqual([p['reported_at'] for p in data['vehicles'][0]['history']],
                         ['2026-10-07T02:59:00Z', '2026-10-07T03:01:59Z'])
        self.assertEqual(data['history_period']['end_before'], '2026-10-07T00:02:00-03:00')

    def test_invalid_or_overlong_period_is_rejected_before_contacting_provider(self):
        self.vehicle("AAA1A11", prefeitura_id=1)
        self.login(prefeitura_id=1)
        self.app.config['REDGPS_SYNC_ENABLED'] = True
        client = self.app.extensions['redgps_client'] = Mock()
        for query in ('start=2026-10-07T10:00', 'start=invalid&end=invalid',
                      'start=2026-10-07T10:00&end=2026-10-07T09:00',
                      'start=2026-10-01T00:00&end=2026-10-16T00:00'):
            self.assertEqual(self.client.get('/veiculos/rastreamento/dados?' + query).status_code, 400)
        client.read.assert_not_called()

    def test_cached_route_query_does_not_wait_for_the_external_provider(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.samples(vehicle)
        self.login(prefeitura_id=1)
        self.app.config['REDGPS_SYNC_ENABLED'] = True
        client = self.app.extensions['redgps_client'] = Mock()
        db.session.commit()
        data = self.client.get(f'/veiculos/rastreamento/dados?date=2026-10-07&cached=1&vehicle_id={vehicle.id}').get_json()
        self.assertEqual(len(data['vehicles'][0]['history']), 3)
        client.read.assert_not_called()

    def test_page_uses_saved_data_without_waiting_for_the_provider(self):
        self.vehicle("AAA1A11", prefeitura_id=1)
        self.login(prefeitura_id=1)
        self.app.config['REDGPS_SYNC_ENABLED'] = True
        client = self.app.extensions['redgps_client'] = Mock()
        self.assertEqual(self.client.get('/veiculos/rastreamento').status_code, 200)
        client.read.assert_not_called()

    def test_default_payload_loads_one_route_and_keeps_other_fleet_rows_lightweight(self):
        first = self.vehicle("AAA1A11", prefeitura_id=1)
        second = self.vehicle("BBB2B22", prefeitura_id=1)
        self.samples(first); self.samples(second)
        self.login(prefeitura_id=1)
        db.session.commit()
        data = self.client.get('/veiculos/rastreamento/dados?date=2026-10-07&cached=1').get_json()
        self.assertEqual(len(data['vehicles'][0]['history']), 3)
        self.assertFalse(data['vehicles'][1]['history_loaded'])
        self.assertEqual(data['vehicles'][1]['history'], [])

    def test_background_refresh_checks_scope_before_scheduling_work(self):
        own = self.vehicle("AAA1A11", prefeitura_id=1)
        other = self.vehicle("BBB2B22", prefeitura_id=2)
        self.login(prefeitura_id=1)
        self.app.config['REDGPS_SYNC_ENABLED'] = True
        with patch('app.modules.veiculos.routes.request_history_refresh', return_value=({'busy': True}, 202)) as schedule:
            response = self.client.post('/veiculos/rastreamento/historico', json={
                'vehicle_id': other.id, 'date': '2026-10-07', 'background': True})
            self.assertEqual(response.status_code, 404)
            schedule.assert_not_called()
            response = self.client.post('/veiculos/rastreamento/historico', json={
                'vehicle_id': own.id, 'date': '2026-10-07', 'background': True})
            self.assertEqual(response.status_code, 202)
            self.assertIn('no-store', response.headers['Cache-Control'])
            schedule.assert_called_once()

    def test_period_loads_only_selected_vehicle_history_and_preserves_fleet_metadata(self):
        first = self.vehicle("AAA1A11", prefeitura_id=1)
        second = self.vehicle("BBB2B22", prefeitura_id=1)
        foreign = self.vehicle("CCC3C33", prefeitura_id=2)
        self.samples(first); self.samples(second)
        self.login(prefeitura_id=1)
        db.session.commit()
        data = self.client.get(f'/veiculos/rastreamento/dados?date=2026-10-07&vehicle_id={second.id}').get_json()
        self.assertEqual(len(data['vehicles']), 2)
        self.assertFalse(data['vehicles'][0]['history_loaded'])
        self.assertEqual(data['vehicles'][0]['history'], [])
        self.assertEqual(len(data['vehicles'][1]['history']), 3)
        self.assertEqual(self.client.get(f'/veiculos/rastreamento/dados?vehicle_id={foreign.id}').status_code, 403)

    def test_full_period_can_reconcile_a_shift_crossing_midnight(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.shift(vehicle, data_registro=datetime(2026, 10, 6, 23, 59),
                   encerrado_em=datetime(2026, 10, 7, 0, 1), km_final=102)
        for minute in (0, 1, 2):
            db.session.add(RastreamentoHistorico(veiculo_id=vehicle.id, latitude=-23, longitude=-46,
                reportado_em=datetime(2026, 10, 7, 2, 59) + timedelta(minutes=minute),
                hodometro_km=100+minute, is_demo=False))
        self.login(prefeitura_id=1)
        data = self.client.get('/veiculos/rastreamento/dados?start=2026-10-06T23:59&end=2026-10-07T00:01').get_json()
        row = data['vehicles'][0]['daily']['logs'][0]
        self.assertEqual(row['comparison'], 'within_tolerance')
        self.assertIsNone(row['reason'])

    def test_partial_shift_is_inconclusive_for_a_narrower_period(self):
        vehicle = self.vehicle("AAA1A11", prefeitura_id=1)
        self.shift(vehicle)
        self.samples(vehicle)
        self.login(prefeitura_id=1)
        data = self.client.get('/veiculos/rastreamento/dados?start=2026-10-07T08:05&end=2026-10-07T08:09').get_json()
        self.assertEqual(data['vehicles'][0]['daily']['logs'][0]['reason'], 'outside_period')


if __name__ == "__main__":
    unittest.main()
