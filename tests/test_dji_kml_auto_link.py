import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.dji_flight_logs import service


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def options(self, *args, **kwargs):
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

    def test_auto_link_can_resolve_missing_route_place_id(self):
        route = SimpleNamespace(
            id=9,
            route_code="ROTA-9",
            points_json='[{"lat": -22.425, "lng": -45.452}]',
            place_id=None,
        )
        ordem = SimpleNamespace(id=44, identificador_os="OS-44", dji_kml_route_id=None)
        fake_session = FakeSession([route])

        with (
            patch.object(service.db, "session", fake_session),
            patch.object(
                service,
                "_reverse_geocode_kml_route",
                return_value={"place_id": "ChIJ-francisco-111", "formatted_address": "Rua Francisco"},
            ) as reverse_geocode,
            patch.object(
                service,
                "_find_best_os_match_for_kml_route",
                return_value=(ordem, 90, {"time": 40, "aircraft": 0, "pilot": 0, "place": 65, "address": 0, "geo": 0}),
            ),
        ):
            result = service.auto_link_existing_kml_routes_to_os(
                commit=False,
                resolve_missing_place_id=True,
            )

        reverse_geocode.assert_called_once()
        self.assertEqual(route.place_id, "ChIJ-francisco-111")
        self.assertEqual(result["place_resolved"], 1)
        self.assertEqual(result["linked"], 1)

    def test_place_id_match_uses_route_and_linked_flight_record(self):
        ordem = SimpleNamespace(
            solicitacao=SimpleNamespace(place_id="ChIJ-francisco-111"),
        )

        route_place_score = service._score_kml_os_place_match(
            ordem,
            SimpleNamespace(place_id=" ChIJ-francisco-111 ", flight_record=None),
        )
        record_place_score = service._score_kml_os_place_match(
            ordem,
            SimpleNamespace(
                place_id=None,
                flight_record=SimpleNamespace(place_id="ChIJ-francisco-111"),
            ),
        )

        self.assertEqual(route_place_score, 65)
        self.assertEqual(record_place_score, 65)

    def test_address_match_handles_different_formatting(self):
        ordem = SimpleNamespace(
            solicitacao=SimpleNamespace(
                logradouro="Rua Francisco Guimaraes da Silva",
                numero="111",
                bairro="Varginha",
                cidade="Itajuba",
                uf="MG",
                cep="",
                place_id=None,
            ),
        )
        route = SimpleNamespace(
            place_id=None,
            flight_record=SimpleNamespace(
                location="Francisco Guimaraes Silva, 111 - Varginha, Itajuba/MG",
                field_name="",
            ),
        )

        self.assertGreaterEqual(service._score_kml_os_address_match(ordem, route), 28)

    def test_confidence_accepts_place_id_with_supporting_signal(self):
        details = {
            "time": 12,
            "aircraft": 0,
            "pilot": 0,
            "place": 65,
            "address": 0,
            "geo": 5,
            "distance_meters": 1200,
        }

        self.assertTrue(service._is_confident_os_kml_match(82, details))

    def test_reverse_geocode_kml_route_uses_representative_point(self):
        points = [
            {"lat": -22.425, "lng": -45.452},
            {"lat": -22.427, "lng": -45.454},
        ]

        with patch.object(
            service,
            "reverse_geocode_lat_lng_google",
            return_value=("Rua Francisco Guimaraes da Silva, 111", "ChIJ-francisco-111"),
        ) as reverse_geocode:
            result = service._reverse_geocode_kml_route(points)

        reverse_geocode.assert_called_once()
        _, kwargs = reverse_geocode.call_args
        self.assertAlmostEqual(kwargs["lat"], -22.426)
        self.assertAlmostEqual(kwargs["lng"], -45.453)
        self.assertEqual(result["place_id"], "ChIJ-francisco-111")
        self.assertIn("Francisco", result["formatted_address"])

    def test_score_includes_place_and_address_details(self):
        ordem = SimpleNamespace(
            data_aplicacao=None,
            hora_inicio_aplicacao=None,
            hora_termino_aplicacao=None,
            respondido_em=None,
            piloto="",
            auxiliar="",
            solicitacao=SimpleNamespace(
                place_id="ChIJ-francisco-111",
                logradouro="Rua Francisco Guimaraes da Silva",
                numero="111",
                bairro="Varginha",
                cidade="Itajuba",
                uf="MG",
                cep="",
                latitude=None,
                longitude=None,
                data_agendamento=None,
                hora_agendamento=None,
            ),
        )
        route = SimpleNamespace(
            route_timestamp=None,
            aircraft_name="",
            pilot_name="",
            place_id="ChIJ-francisco-111",
            flight_record=SimpleNamespace(
                place_id=None,
                raw_payload=None,
                location="Francisco Guimaraes da Silva, 111 - Itajuba/MG",
                field_name="",
            ),
        )

        score, details = service._score_os_kml_match(ordem, route, [])

        self.assertEqual(score, details["place"] + details["address"])
        self.assertEqual(details["place"], 65)
        self.assertGreaterEqual(details["address"], 28)


if __name__ == "__main__":
    unittest.main()
