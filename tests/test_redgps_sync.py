import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from flask import Flask

from app.clients.redgps_client import RedGPSClient, RedGPSError
from app.extensions import db
from app.models import RastreamentoHistorico, RastreamentoPosicao, RastreamentoSincronizacao, Veiculos
from app.modules.veiculos.redgps_sync import normalize_position, sync_redgps


def reading(**changes):
    return {
        "UnitPlate": "AAA-1A11", "Latitude": "-23.55", "Longitude": "-46.63",
        "ReportDate": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "GpsSpeed": "32", "Ignition": "1", "Odometer": "1234500",
        "Domicilio": "Rua de teste", **changes,
    }


class RedGPSSyncTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
                               REDGPS_SYNC_ENABLED=True, REDGPS_POLL_INTERVAL_SECONDS=60)
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = Mock()
        self.client.read.return_value = [reading()]
        self.app.extensions["redgps_client"] = self.client
        self.vehicle = Veiculos(placa="AAA1A11", modelo="Teste", renomacao="Teste", operacao="AGRO",
                                frota="PROPRIA", km_atual=777)
        db.session.add(self.vehicle)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def allow_next_poll(self):
        db.session.expire_all()
        state = db.session.get(RastreamentoSincronizacao, 1)
        state.tentado_em -= timedelta(seconds=61)
        db.session.commit()

    def test_persists_position_and_history_without_changing_registered_km(self):
        result = sync_redgps()
        self.assertEqual(result["matched"], 1)
        position = RastreamentoPosicao.query.one()
        self.assertEqual(position.hodometro_km, 1234.5)
        self.assertTrue(position.ignicao)
        self.assertFalse(position.is_demo)
        self.assertEqual(RastreamentoHistorico.query.count(), 1)
        self.assertEqual(db.session.get(Veiculos, self.vehicle.id).km_atual, 777)

    def test_throttles_even_when_device_report_has_not_changed(self):
        sync_redgps()
        sync_redgps()
        self.client.read.assert_called_once_with("getdata")
        self.allow_next_poll()
        sync_redgps()
        self.assertEqual(self.client.read.call_count, 2)
        self.assertEqual(RastreamentoPosicao.query.count(), 1)
        self.assertEqual(RastreamentoHistorico.query.count(), 1)

    def test_failure_keeps_previous_data_and_throttles_retries(self):
        sync_redgps()
        self.allow_next_poll()
        self.client.read.side_effect = RedGPSError("falha_conexao_ou_resposta")
        self.assertTrue(sync_redgps()["error"])
        self.assertTrue(sync_redgps()["error"])
        self.assertEqual(self.client.read.call_count, 2)
        self.assertEqual(RastreamentoPosicao.query.count(), 1)

    def test_unknown_vehicle_is_not_created_or_assigned(self):
        self.client.read.return_value = [reading(UnitPlate="ZZZ9Z99")]
        self.assertEqual(sync_redgps()["unmatched"], 1)
        self.assertEqual(Veiculos.query.count(), 1)
        self.assertEqual(RastreamentoPosicao.query.count(), 0)

    def test_ambiguous_normalized_plate_is_not_assigned(self):
        db.session.add(Veiculos(placa="AAA-1A11", modelo="Outro", renomacao="Outro", operacao="AGRO", frota="PROPRIA"))
        db.session.commit()
        self.assertEqual(sync_redgps()["unmatched"], 1)
        self.assertEqual(RastreamentoPosicao.query.count(), 0)

    def test_older_reading_does_not_replace_latest_position(self):
        sync_redgps()
        self.allow_next_poll()
        older = datetime.now(timezone.utc) - timedelta(hours=1)
        self.client.read.return_value = [reading(ReportDate=older.strftime("%Y-%m-%d %H:%M:%S"), GpsSpeed="0")]
        sync_redgps()
        self.assertEqual(RastreamentoPosicao.query.one().velocidade_kmh, 32)
        self.assertEqual(RastreamentoHistorico.query.count(), 2)

    def test_invalid_dates_coordinates_and_unknown_ignition(self):
        for changes in ({"Latitude": "nan"}, {"Longitude": 181}, {"ReportDate": "1969-12-12 00:00:00"},
                        {"ReportDate": "invalid"}, {"Latitude": 0, "Longitude": 0}):
            self.assertIsNone(normalize_position(reading(**changes)))
        parsed = normalize_position(reading(Ignition="2", Odometer="-1"))
        self.assertIsNone(parsed["ignicao"])
        self.assertIsNone(parsed["hodometro_km"])

    def test_disabled_does_not_call_api(self):
        self.app.config["REDGPS_SYNC_ENABLED"] = False
        self.assertFalse(sync_redgps()["enabled"])
        self.client.read.assert_not_called()


class RedGPSClientTests(unittest.TestCase):
    def setUp(self):
        self.client = RedGPSClient({"REDGPS_BASE_URL": "https://example.test/api", "REDGPS_API_KEY": "secret-key",
                                   "REDGPS_USERNAME": "test-user", "REDGPS_PASSWORD": "secret-password"})

    @patch("app.clients.redgps_client.requests.post")
    def test_reuses_token_and_renews_rejected_token(self, post):
        payloads = [{"status": 200, "data": "token-one"}, {"status": 200, "data": []},
                    {"status": 30400}, {"status": 200, "data": "token-two"}, {"status": 200, "data": []}]
        post.side_effect = [Mock(status_code=200, json=Mock(return_value=data)) for data in payloads]
        self.assertEqual(self.client.read("getdata"), [])
        self.assertEqual(self.client.read("getdata"), [])
        self.assertEqual(post.call_count, 5)
        self.assertEqual(post.call_args_list[1].kwargs["data"]["UseUTCDate"], "1")
        self.assertEqual(post.call_args_list[-1].kwargs["data"]["token"], "token-two")
        self.assertTrue(post.call_args.kwargs["verify"])
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    @patch("app.clients.redgps_client.requests.post")
    def test_auth_failure_never_exposes_response_body(self, post):
        post.return_value = Mock(status_code=200, json=Mock(return_value={"status": 30500, "data": "secret-password"}))
        with self.assertRaisesRegex(RedGPSError, "^autenticacao_recusada$"):
            self.client.read("getdata")

    @patch("app.clients.redgps_client.requests.post")
    def test_http_401_refreshes_token_once(self, post):
        self.client.token = "previous-token"
        self.client.expires_at = float("inf")
        post.side_effect = [Mock(status_code=401),
                            Mock(status_code=200, json=Mock(return_value={"status": 200, "data": "new-token"})),
                            Mock(status_code=200, json=Mock(return_value={"status": 200, "data": []}))]
        self.assertEqual(self.client.read("getdata"), [])
        self.assertEqual(post.call_count, 3)

    @patch("app.clients.redgps_client.requests.post")
    def test_malformed_response_is_rejected(self, post):
        post.return_value = Mock(status_code=200, json=Mock(return_value=["not-a-response"]))
        with self.assertRaisesRegex(RedGPSError, "resposta_invalida"):
            self.client.read("getdata")

    def test_refuses_write_endpoints(self):
        with self.assertRaises(ValueError):
            self.client.read("createAsset")


if __name__ == "__main__":
    unittest.main()
