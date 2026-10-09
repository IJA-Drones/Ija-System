import unittest
from datetime import date, time
from types import SimpleNamespace
from unittest.mock import patch

from flask import Blueprint, Flask, g
from flask_login import LoginManager

from app.extensions import db
from app.models import Equipe, OrdemServico, OrdemServicoEquipeUvis, Prefeitura, Solicitacao, Usuario
from app.modules.mapas.routes import register_routes
from app.modules.mapas.service import build_heatmap_points, build_heatmap_query, build_uvis_disponiveis


MISSING = object()


class HeatmapFilterTests(unittest.TestCase):
    def setUp(self):
        # Do not call create_app(): it loads the real project's .env/database.
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="isolated-heatmap-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)
        self.admin = SimpleNamespace(id=99, tipo_usuario="admin", is_authenticated=True)
        self.endpoint_user = self.admin

        @login_manager.request_loader
        def load_test_user(_request):
            return self.endpoint_user

        bp = Blueprint("mapas_test", __name__)
        register_routes(bp)
        self.app.register_blueprint(bp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        db.session.add_all([
            Prefeitura(id=1, nome="Prefeitura A", slug="prefeitura-a"),
            Prefeitura(id=2, nome="Prefeitura B", slug="prefeitura-b"),
        ])
        self.uvis = self._new_uvis("UVIS A Oeste", "OESTE", 1)
        self.uvis_same_region = self._new_uvis("UVIS A Oeste 2", "OESTE", 1)
        self.uvis_other_region = self._new_uvis("UVIS A Leste", "LESTE", 1)
        self.uvis_other_city = self._new_uvis("UVIS B Oeste", "OESTE", 2)
        self.equipe = Equipe(nome_equipe="Equipe sintética", prefeitura_id=1)
        db.session.add(self.equipe)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _new_uvis(self, name, region, prefeitura_id):
        user = Usuario(
            nome_uvis=name,
            login=name,
            senha_hash="unused-test-hash",
            tipo_usuario="uvis",
            regiao=region,
            prefeitura_id=prefeitura_id,
        )
        db.session.add(user)
        return user

    def _new_request(self, *, user=None, drone=MISSING, equipe_uvis=MISSING, **kwargs):
        user = user or self.uvis
        values = dict(
            data_agendamento=date(2026, 10, 9),
            hora_agendamento=time(9),
            foco="Piscina",
            cep="00000-000",
            logradouro="Rua Sintética",
            bairro="Bairro Teste",
            cidade="Cidade Teste",
            uf="SP",
            status="CONCLUÍDO",
            usuario_id=user.id,
            prefeitura_id=user.prefeitura_id,
            latitude="-23.55",
            longitude="-46.63",
        )
        values.update(kwargs)
        solicitacao = Solicitacao(**values)
        db.session.add(solicitacao)
        db.session.flush()
        if drone is not MISSING:
            db.session.add(OrdemServico(
                solicitacao_id=solicitacao.id,
                equipe_id=self.equipe.id,
                larva_visualizada=drone,
            ))
        if equipe_uvis is not MISSING:
            db.session.add(OrdemServicoEquipeUvis(
                solicitacao_id=solicitacao.id,
                equipe_uvis_nome="Equipe UVIS sintética",
                larva_visualizada=equipe_uvis,
            ))
        db.session.flush()
        return solicitacao

    def _ids(self, user=None, **filters):
        return {item.id for item in build_heatmap_query(user or self.admin, **filters).all()}

    def _get(self, **query):
        # The test keeps an app context open for SQLite; refresh Flask-Login per request.
        g.pop("_login_user", None)
        return self.app.test_client().get("/api/heatmap-data", query_string=query)

    def test_month_and_year_filter_independently_and_together(self):
        october = self._new_request(data_agendamento=date(2026, 10, 9))
        september = self._new_request(data_agendamento=date(2026, 9, 9))
        last_year = self._new_request(data_agendamento=date(2025, 10, 9))
        cases = [
            ({}, {october.id, september.id, last_year.id}),
            ({"mes": 10}, {october.id, last_year.id}),
            ({"ano": 2026}, {october.id, september.id}),
            ({"mes": 10, "ano": 2026}, {october.id}),
            ({"mes": 1, "ano": 2026}, set()),
        ]
        for filters, expected in cases:
            with self.subTest(filters=filters):
                self.assertEqual(self._ids(**filters), expected)

    def test_approved_and_completed_statuses_are_visible(self):
        expected = set()
        for status in [
            "APROVADO", "APROVADO COM RECOMENDACOES", "APROVADO COM RECOMENDAÇÕES",
            "CONCLUIDO", "CONCLUÍDO",
        ]:
            expected.add(self._new_request(status=status, drone="SIM").id)
        for status in ["EM ANÁLISE", "PENDENTE", "NEGADO", "CANCELADO"]:
            self._new_request(status=status, drone="SIM")
        self.assertEqual(self._ids(), expected)
        self.assertEqual(self._ids(larva_visualizada="SIM"), expected)

    def test_larva_answers_from_both_order_types_are_exclusive_and_complete(self):
        expected = {"SIM": set(), "NAO": set(), "NAO_INFORMADO": set()}
        cases = [
            ("SIM", MISSING, "SIM"),
            (MISSING, " sim ", "SIM"),
            ("sim", "SIM", "SIM"),
            ("SIM", "NÃO", "SIM"),
            ("NAO", "SIM", "SIM"),
            ("NÃO", MISSING, "NAO"),
            (MISSING, "não", "NAO"),
            (" nao ", "Não", "NAO"),
            (None, "NAO", "NAO"),
            ("NÃO", "desconhecido", "NAO"),
            (MISSING, MISSING, "NAO_INFORMADO"),
            (None, None, "NAO_INFORMADO"),
            ("", "   ", "NAO_INFORMADO"),
            ("desconhecido", "N/A", "NAO_INFORMADO"),
        ]
        for drone, equipe_uvis, classification in cases:
            item = self._new_request(drone=drone, equipe_uvis=equipe_uvis)
            expected[classification].add(item.id)

        for classification, ids in expected.items():
            with self.subTest(classification=classification):
                query = build_heatmap_query(self.admin, larva_visualizada=classification)
                self.assertEqual({item.id for item in query.all()}, ids)
                self.assertEqual(query.count(), len(ids))
                self.assertEqual(len(build_heatmap_points(self.admin, larva_visualizada=classification)), len(ids))

        self.assertEqual(self._ids(larva_visualizada=" não "), expected["NAO"])
        self.assertEqual(self._ids(larva_visualizada="não_informado"), expected["NAO_INFORMADO"])
        all_ids = set.union(*expected.values())
        for unfiltered in [None, "", " todos "]:
            with self.subTest(unfiltered=unfiltered):
                self.assertEqual(self._ids(larva_visualizada=unfiltered), all_ids)

    def test_filters_combine_uvis_month_year_and_larva(self):
        match = self._new_request(drone="SIM")
        self._new_request(drone="NAO")
        self._new_request(drone="SIM", data_agendamento=date(2025, 10, 9))
        self._new_request(drone="SIM", data_agendamento=date(2026, 9, 9))
        self._new_request(drone="SIM", user=self.uvis_same_region)
        self._new_request(drone="SIM", status="NEGADO")
        self.assertEqual(self._ids(
            uvis_id=self.uvis.id, mes=10, ano=2026, larva_visualizada="SIM"
        ), {match.id})

    def test_global_admin_roles_can_filter_any_uvis_across_cities(self):
        here = self._new_request(drone="SIM")
        elsewhere = self._new_request(drone="SIM", user=self.uvis_other_city)
        for role in ["admin", "dev", "diretor"]:
            user = SimpleNamespace(tipo_usuario=role, prefeitura_id=1)
            with self.subTest(role=role):
                self.assertEqual(self._ids(user, larva_visualizada="SIM"), {here.id, elsewhere.id})
                self.assertEqual(self._ids(user, uvis_id=self.uvis_other_city.id, larva_visualizada="SIM"), {elsewhere.id})

    def test_regional_scope_still_restricts_city_and_region_with_larva_filter(self):
        here = self._new_request(drone="SIM")
        same_region = self._new_request(equipe_uvis="SIM", user=self.uvis_same_region)
        self._new_request(drone="SIM", user=self.uvis_other_region)
        self._new_request(drone="SIM", user=self.uvis_other_city)
        user = SimpleNamespace(tipo_usuario="regional", prefeitura_id=1, regiao=" oeste ")
        self.assertEqual(self._ids(user, larva_visualizada="SIM"), {here.id, same_region.id})
        self.assertEqual(self._ids(user, uvis_id=self.uvis_same_region.id, larva_visualizada="SIM"), {same_region.id})
        for outside in [self.uvis_other_region, self.uvis_other_city]:
            with self.subTest(outside=outside.nome_uvis):
                self.assertEqual(self._ids(user, uvis_id=outside.id, larva_visualizada="SIM"), set())
        user.regiao = ""
        self.assertEqual(self._ids(user, larva_visualizada="SIM"), set())

    def test_prefeitura_admin_cannot_expand_scope_with_uvis_filter(self):
        here = self._new_request(equipe_uvis="SIM")
        same_city = self._new_request(drone="SIM", user=self.uvis_other_region)
        self._new_request(drone="SIM", user=self.uvis_other_city)
        user = SimpleNamespace(tipo_usuario="prefeitura_admin", prefeitura_id=1)
        self.assertEqual(self._ids(user, larva_visualizada="SIM"), {here.id, same_city.id})
        self.assertEqual(self._ids(user, uvis_id=self.uvis_other_region.id, larva_visualizada="SIM"), {same_city.id})
        self.assertEqual(self._ids(user, uvis_id=self.uvis_other_city.id, larva_visualizada="SIM"), set())
        user.prefeitura_id = None
        self.assertEqual(self._ids(user, larva_visualizada="SIM"), set())

    def test_uvis_cannot_change_ownership_with_query_parameter(self):
        own = self._new_request(equipe_uvis="SIM")
        self._new_request(drone="SIM", user=self.uvis_same_region)
        self._new_request(drone="SIM", user=self.uvis_other_city)
        self.assertEqual(self._ids(self.uvis, larva_visualizada="SIM"), {own.id})
        self.assertEqual(self._ids(self.uvis, uvis_id=self.uvis_other_city.id, larva_visualizada="SIM"), {own.id})

    def test_uvis_options_follow_access_scope(self):
        all_uvis = {self.uvis.id, self.uvis_same_region.id, self.uvis_other_region.id, self.uvis_other_city.id}
        cases = [
            (self.admin, all_uvis),
            (SimpleNamespace(tipo_usuario="dev"), all_uvis),
            (SimpleNamespace(tipo_usuario="diretor", prefeitura_id=1), all_uvis),
            (SimpleNamespace(tipo_usuario="prefeitura_admin", prefeitura_id=1), all_uvis - {self.uvis_other_city.id}),
            (SimpleNamespace(tipo_usuario="regional", prefeitura_id=1, regiao="OESTE"), {self.uvis.id, self.uvis_same_region.id}),
            (self.uvis, set()),
        ]
        for user, expected in cases:
            with self.subTest(role=user.tipo_usuario):
                self.assertEqual({item.id for item in build_uvis_disponiveis(user)}, expected)

    def test_points_discard_missing_nonfinite_and_out_of_range_coordinates(self):
        self._new_request(latitude="-90", longitude="180", foco=" Piscina ")
        self._new_request(latitude="90", longitude="-180", foco="   ")
        for latitude, longitude in [
            (None, "0"), ("0", None), ("", "0"), ("abc", "0"),
            ("nan", "0"), ("0", "NaN"), ("inf", "0"), ("0", "-inf"),
            ("90.01", "0"), ("-90.01", "0"), ("0", "180.01"), ("0", "-180.01"),
        ]:
            self._new_request(latitude=latitude, longitude=longitude)
        self.assertCountEqual(build_heatmap_points(self.admin), [
            {"lat": -90.0, "lng": 180.0, "foco": "Piscina"},
            {"lat": 90.0, "lng": -180.0, "foco": "Outros"},
        ])

    def test_endpoint_applies_combined_filters_and_accepts_normalized_answers(self):
        self._new_request(drone="SIM", latitude="-23.1")
        self._new_request(equipe_uvis="não", latitude="-23.2")
        self._new_request(drone="SIM", user=self.uvis_other_city, latitude="-23.3")
        self._new_request(drone="SIM", data_agendamento=date(2025, 10, 9), latitude="-23.4")
        for answer, expected in [(" sim ", -23.1), (" NÃO ", -23.2)]:
            with self.subTest(answer=answer):
                response = self._get(uvis_id=self.uvis.id, mes=10, ano=2026, larva_visualizada=answer)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([item["lat"] for item in response.get_json()], [expected])

    def test_endpoint_accepts_empty_and_boundary_filters(self):
        self._new_request()
        for filters in [
            {}, {"mes": "", "ano": "", "uvis_id": "", "larva_visualizada": ""},
            {"larva_visualizada": "todos"}, {"mes": 1}, {"mes": 12},
            {"ano": 1}, {"ano": 9999}, {"uvis_id": self.uvis.id},
        ]:
            with self.subTest(filters=filters):
                response = self._get(**filters)
                self.assertEqual(response.status_code, 200)
                self.assertIsInstance(response.get_json(), list)

    def test_endpoint_rejects_invalid_filters_instead_of_silently_ignoring(self):
        invalid_values = {
            "mes": ["abc", "0", "13", "-1", "1.5"],
            "ano": ["abc", "0", "10000", "-1", "2026.5"],
            "uvis_id": ["abc", "0", "-1", "1.5"],
            "larva_visualizada": ["talvez", "1", "false"],
        }
        for parameter, values in invalid_values.items():
            for value in values:
                with self.subTest(parameter=parameter, value=value):
                    response = self._get(**{parameter: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertFalse(response.get_json()["ok"])
                    self.assertTrue(response.get_json()["message"])

    def test_endpoint_requires_authentication(self):
        self.endpoint_user = None
        self.assertEqual(self._get().status_code, 401)

    def test_geocode_endpoint_returns_coordinates_and_place_id(self):
        with patch(
            "app.modules.mapas.routes.geocode_endereco_google",
            return_value=(-23.55, -46.63, "synthetic-place-id"),
        ):
            response = self.app.test_client().post("/api/geocode", json={
                "logradouro": "Rua Sintética",
                "numero": "1",
                "cidade": "Cidade Teste",
                "uf": "SP",
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "ok": True,
            "lat": -23.55,
            "lng": -46.63,
            "place_id": "synthetic-place-id",
        })

    def test_geocode_endpoint_handles_no_result_with_three_value_return(self):
        with patch(
            "app.modules.mapas.routes.geocode_endereco_google",
            return_value=(None, None, None),
        ):
            response = self.app.test_client().post("/api/geocode", json={
                "logradouro": "Rua Sintética",
                "numero": "1",
                "cidade": "Cidade Teste",
                "uf": "SP",
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "ok": False,
            "message": "Não foi possível geocodificar",
        })


if __name__ == "__main__":
    unittest.main()
