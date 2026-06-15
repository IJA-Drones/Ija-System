import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from app.modules.agenda_notificacoes import service as agenda_service
from app.modules.piloto_os import service as piloto_os_service


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 6, 15, 10, 30)
        return value.replace(tzinfo=tz) if tz else value


class EmptyQuery:
    def all(self):
        return []


class OperationalScheduleFilterTests(unittest.TestCase):
    def test_piloto_dashboard_uses_current_brasilia_day(self):
        with patch.object(piloto_os_service, "datetime", FixedDatetime):
            self.assertEqual(
                piloto_os_service.current_piloto_dashboard_date().isoformat(),
                "2026-06-15",
            )

    def test_current_week_runs_from_monday_through_sunday(self):
        with patch.object(agenda_service, "datetime", FixedDatetime):
            inicio, fim = agenda_service.current_week_range()

        self.assertEqual(inicio.isoformat(), "2026-06-15")
        self.assertEqual(fim.isoformat(), "2026-06-21")

    def test_piloto_agenda_forces_current_week_over_month_filters(self):
        user = SimpleNamespace(tipo_usuario="piloto")
        args = MultiDict(
            {
                "data_ini": "2026-06-01",
                "data_fim": "2026-06-30",
                "mes": "6",
                "ano": "2026",
            }
        )

        with (
            patch.object(agenda_service, "datetime", FixedDatetime),
            patch.object(agenda_service, "build_agenda_query", return_value=EmptyQuery()) as build_query,
            patch.object(agenda_service, "build_agenda_uvis_disponiveis", return_value=[]),
            patch.object(agenda_service, "build_agenda_anos_disponiveis", return_value=[2026]),
            patch.object(agenda_service, "get_agenda_google_maps_key", return_value=""),
        ):
            context = agenda_service.build_agenda_context(user, args)

        query_args = build_query.call_args.kwargs
        self.assertEqual(query_args["data_ini"], "2026-06-15")
        self.assertEqual(query_args["data_fim"], "2026-06-21")
        self.assertIsNone(query_args["mes"])
        self.assertIsNone(query_args["ano"])
        self.assertTrue(context["periodo_semanal_fixo"])
        self.assertEqual(context["initial_date"], "2026-06-15")

    def test_admin_agenda_keeps_month_filter_behavior(self):
        user = SimpleNamespace(tipo_usuario="admin")
        args = MultiDict({"mes": "6", "ano": "2026"})

        with (
            patch.object(agenda_service, "datetime", FixedDatetime),
            patch.object(agenda_service, "build_agenda_query", return_value=EmptyQuery()) as build_query,
            patch.object(agenda_service, "build_agenda_uvis_disponiveis", return_value=[]),
            patch.object(agenda_service, "build_agenda_anos_disponiveis", return_value=[2026]),
            patch.object(agenda_service, "get_agenda_google_maps_key", return_value=""),
        ):
            context = agenda_service.build_agenda_context(user, args)

        query_args = build_query.call_args.kwargs
        self.assertIsNone(query_args["data_ini"])
        self.assertIsNone(query_args["data_fim"])
        self.assertEqual(query_args["mes"], 6)
        self.assertEqual(query_args["ano"], 2026)
        self.assertFalse(context["periodo_semanal_fixo"])


if __name__ == "__main__":
    unittest.main()
