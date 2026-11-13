import importlib.util
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import Flask
from sqlalchemy import create_engine, inspect

from app.clients.redgps_client import RedGPSError
from app.extensions import db
from app.models import RastreamentoHistorico, RastreamentoPosicao, Veiculos
from app.modules.veiculos.redgps_history import import_redgps_history
from tests.test_redgps_sync import reading


def historical(**changes):
    return {"equipo": "device-test", "patente": "AAA-1A11", "fecha_reporte": "20261007080000",
            "latitud": "-23.55", "longitud": "-46.63", "velocidad": "32",
            "odometro": "1234500", "ignicion": "1", **changes}


class RedGPSHistoryTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:", REDGPS_SYNC_ENABLED=True)
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.vehicle = Veiculos(placa="AAA1A11", modelo="Fictício", renomacao="Teste",
                                operacao="AGRO", frota="PROPRIA", km_atual=777)
        db.session.add(self.vehicle)
        db.session.commit()
        self.client = Mock()
        self.client.read.return_value = [reading(GpsIdentif="device-test")]
        self.client.read_history.return_value = [historical()]
        self.app.extensions["redgps_client"] = self.client

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def recover(self, zone="America/Sao_Paulo"):
        return import_redgps_history(date(2026, 10, 7), zone)

    def test_recovery_converts_explicit_timezone_and_is_idempotent(self):
        self.assertEqual(self.recover()["inserted"], 1)
        self.assertEqual(self.recover()["duplicate"], 1)
        point = RastreamentoHistorico.query.one()
        self.assertEqual(point.reportado_em, datetime(2026, 10, 7, 11))
        self.assertEqual(point.hodometro_km, 1234.5)
        self.assertEqual(point.velocidade_kmh, 32)
        self.assertFalse(point.is_demo)
        self.assertEqual(RastreamentoPosicao.query.count(), 0)
        self.assertEqual(db.session.get(Veiculos, self.vehicle.id).km_atual, 777)
        begin, end = self.client.read_history.call_args.args[1:]
        self.assertEqual(begin.hour, 0)
        self.assertEqual(end.hour, 23)

    def test_utc_history_query_uses_brazilian_day_boundaries(self):
        self.recover("UTC")
        begin, end = self.client.read_history.call_args.args[1:]
        self.assertEqual(begin, datetime(2026, 10, 7, 3, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 10, 8, 2, 59, 59, tzinfo=timezone.utc))
        self.assertEqual(RastreamentoHistorico.query.one().reportado_em.hour, 8)

    def test_foreign_device_plate_date_or_invalid_gps_cannot_contaminate_route(self):
        self.client.read_history.return_value = [historical(equipo="other"), historical(patente="ZZZ9Z99"),
            historical(fecha_reporte="20261006080000"), historical(latitud="nan"), historical(fecha_reporte="invalid")]
        result = self.recover()
        self.assertEqual(result["invalid"], 5)
        self.assertEqual(RastreamentoHistorico.query.count(), 0)

    def test_live_reading_identity_is_reused_by_history_recovery(self):
        db.session.add(RastreamentoHistorico(veiculo_id=self.vehicle.id, latitude=-23.55, longitude=-46.63,
            reportado_em=datetime(2026, 10, 7, 11), chave_fixture=f"redgps:{self.vehicle.id}:2026-10-07T11:00:00", is_demo=False))
        db.session.commit()
        self.assertEqual(self.recover()["duplicate"], 1)
        self.assertEqual(RastreamentoHistorico.query.count(), 1)

    def test_failure_rolls_back_all_vehicles_and_releases_lock(self):
        other = Veiculos(placa="BBB2B22", modelo="Fictício", renomacao="Outro", operacao="AGRO", frota="PROPRIA")
        db.session.add(other)
        db.session.commit()
        self.client.read.return_value.append(reading(UnitPlate="BBB2B22", GpsIdentif="device-other"))
        self.client.read_history.side_effect = [[historical()], RedGPSError("consulta_recusada")]
        with self.assertRaises(RedGPSError):
            self.recover()
        self.assertEqual(RastreamentoHistorico.query.count(), 0)
        self.client.read_history.side_effect = None
        self.assertEqual(self.recover()["inserted"], 1)

    def test_ambiguous_device_mapping_is_not_imported(self):
        self.client.read.return_value.append(reading(UnitPlate="BBB2B22", GpsIdentif="device-test"))
        self.assertEqual(self.recover()["unmatched"], 1)
        self.client.read_history.assert_not_called()

    def test_conflicting_provider_gmt_is_rejected_instead_of_shifting_the_route(self):
        self.client.read_history.return_value = [historical(gmt="0")]
        self.assertEqual(self.recover()["invalid"], 1)
        self.assertEqual(RastreamentoHistorico.query.count(), 0)

    def test_recovers_a_time_period_across_midnight_and_keeps_saved_points(self):
        from app.modules.veiculos.tracking_period import parse_tracking_period
        period = parse_tracking_period({'start': '2026-10-06T23:59', 'end': '2026-10-07T00:01'})
        self.client.read_history.return_value = [historical(fecha_reporte='20261006235900'),
            historical(fecha_reporte='20261007000159'), historical(fecha_reporte='20261007000200')]
        result = import_redgps_history(period.day, 'America/Sao_Paulo', period=period)
        self.assertEqual(result['inserted'], 2)
        self.assertEqual(result['invalid'], 1)
        self.assertEqual(import_redgps_history(period.day, 'America/Sao_Paulo', period=period)['duplicate'], 2)
        begin, end = self.client.read_history.call_args.args[1:]
        self.assertEqual(begin.strftime('%Y-%m-%d %H:%M:%S'), '2026-10-06 23:59:00')
        self.assertEqual(end.strftime('%Y-%m-%d %H:%M:%S'), '2026-10-07 00:01:59')


class ShiftMigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_preserve_legacy_logs_without_inventing_end_times(self):
        path = Path(__file__).resolve().parents[1] / "migrations/versions/a3e5c7d901b2_tracking_shift_driver.py"
        spec = importlib.util.spec_from_file_location("shift_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine("sqlite://")
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE logs_veiculo (id INTEGER PRIMARY KEY, km_inicial FLOAT NOT NULL)")
            conn.exec_driver_sql("INSERT INTO logs_veiculo VALUES (1, 1234)")
            conn.exec_driver_sql("CREATE TABLE rastreamento_posicoes (id INTEGER PRIMARY KEY)")
            with patch.object(migration, "op", Operations(MigrationContext.configure(conn))):
                migration.upgrade()
                self.assertEqual(conn.exec_driver_sql("SELECT encerrado_em, condutor_nome FROM logs_veiculo").one(), (None, None))
                migration.downgrade()
                self.assertEqual(conn.exec_driver_sql("SELECT * FROM logs_veiculo").one(), (1, 1234))
                self.assertEqual({c["name"] for c in inspect(conn).get_columns("logs_veiculo")}, {"id", "km_inicial"})
        engine.dispose()


class TrackingWorkerTests(unittest.TestCase):
    def run_first_cycle(self, *arguments):
        from io import StringIO
        import scripts.sync_redgps as worker
        class Settings:
            SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
            REDGPS_SYNC_ENABLED = True
            REDGPS_POLL_INTERVAL_SECONDS = 60
        with patch.object(worker.sys, 'argv', ['sync_redgps.py', '--watch', *arguments]), \
             patch.object(worker, 'sync_redgps', return_value={'matched': 1}), \
             patch.object(worker, 'import_redgps_history', return_value={'inserted': 10}) as recover, \
             patch.object(worker.time, 'sleep', side_effect=KeyboardInterrupt), patch('sys.stdout', StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                worker.main(config_class=Settings)
        return recover

    def test_worker_preloads_previous_and_current_day_without_an_open_panel(self):
        recover = self.run_first_cycle()
        recover.assert_called_once()
        period = recover.call_args.kwargs['period']
        self.assertEqual((period.end.date() - period.start.date()).days, 2)

    def test_positions_only_remains_available(self):
        self.run_first_cycle('--positions-only').assert_not_called()
