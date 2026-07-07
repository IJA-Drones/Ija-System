import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.dji_flight_logs import service


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, limit):
        self.rows = self.rows[:limit]
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, routes=None, linked_route_rows=None):
        self.routes = routes or []
        self.linked_route_rows = linked_route_rows or []
        self.commits = 0

    def query(self, *args, **kwargs):
        if args and args[0] is service.DjiFlightKmlRoute:
            return FakeQuery(self.routes)
        return FakeQuery(self.linked_route_rows)

    def commit(self):
        self.commits += 1


class DjiKmlAutoLinkTests(unittest.TestCase):
    def test_dry_run_reports_match_without_mutating_os(self):
        route = SimpleNamespace(id=7, route_code="ROTA-7", points_json="[]")
        ordem = SimpleNamespace(id=42, identificador_os="OS-42", dji_kml_route_id=None)
        fake_session = FakeSession([route])

        with (
            patch.object(service.db, "session", fake_session),
            patch.object(
                service,
                "_find_best_os_match_for_kml_route",
                return_value=(ordem, 90, {"time": 40, "aircraft": 35, "pilot": 15, "geo": 0}),
            ),
        ):
            result = service.auto_link_existing_kml_routes_to_os(commit=False)

        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["linked"], 1)
        self.assertIsNone(ordem.dji_kml_route_id)
        self.assertEqual(fake_session.commits, 0)

    def test_commit_links_os_and_commits_once(self):
        route = SimpleNamespace(id=8, route_code="ROTA-8", points_json="[]")
        ordem = SimpleNamespace(id=43, identificador_os="OS-43", dji_kml_route_id=None)
        fake_session = FakeSession([route])

        with (
            patch.object(service.db, "session", fake_session),
            patch.object(
                service,
                "_find_best_os_match_for_kml_route",
                return_value=(ordem, 95, {"time": 40, "aircraft": 35, "pilot": 15, "geo": 5}),
            ),
        ):
            result = service.auto_link_existing_kml_routes_to_os(commit=True)

        self.assertEqual(result["linked"], 1)
        self.assertEqual(ordem.dji_kml_route_id, route.id)
        self.assertEqual(fake_session.commits, 1)

    def test_linked_route_rows_are_converted_to_plain_ids(self):
        linked_route_ids = {
            service._extract_scalar_query_value(row)
            for row in [((456,),), (76,), 251]
        }

        self.assertEqual(linked_route_ids, {456, 76, 251})


if __name__ == "__main__":
    unittest.main()
