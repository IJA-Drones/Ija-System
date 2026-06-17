import unittest
from types import SimpleNamespace

from flask import Flask

from app.extensions import db
from app.models import Equipe, Prefeitura, Veiculos
from app.modules.veiculos.service import build_piloto_veiculos_context, update_veiculo


class VeiculosOperationalScopeTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        prefeitura = Prefeitura(id=1, nome="Prefeitura Teste", slug="prefeitura-teste")
        self.equipe = Equipe(nome_equipe="PLOA 23", regiao="SUL", ativa=True, prefeitura_id=1)
        db.session.add_all([prefeitura, self.equipe])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _novo_veiculo(self, **overrides):
        data = {
            "tipo_equipamento": "veiculos",
            "status": "Ativo",
            "modelo": "FIORINO",
            "ano_fabricacao": 2024,
            "renomacao": "ABC1D23",
            "frota": "PROPRIA",
            "operacao": "PMSP",
            "placa": "ABC1D23",
            "km_atual": 1000,
            "equipe_id": self.equipe.id,
            "prefeitura_id": None,
        }
        data.update(overrides)
        veiculo = Veiculos(**data)
        db.session.add(veiculo)
        db.session.commit()
        return veiculo

    def test_equipe_oceano_sees_legacy_vehicle_linked_by_team_id_without_prefeitura(self):
        veiculo = self._novo_veiculo()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )

        context = build_piloto_veiculos_context(user)

        self.assertTrue(context["piloto_vinculado"])
        self.assertEqual([item.id for item in context["veiculos"]], [veiculo.id])

    def test_update_vehicle_inherits_prefeitura_from_selected_team(self):
        veiculo = self._novo_veiculo(equipe_id=None)

        update_veiculo(
            veiculo,
            {
                "modelo": "FIORINO",
                "ano_fabricacao": 2024,
                "frota": "PROPRIA",
                "operacao": "PMSP",
                "placa": "ABC1D23",
                "responsavel": None,
                "equipe_id": self.equipe.id,
                "km_atual": 1000,
                "km_prox_revisao": None,
                "status": "Ativo",
                "revisao_marcada_em": None,
                "revisao_obs": None,
            },
        )

        self.assertEqual(veiculo.prefeitura_id, 1)


if __name__ == "__main__":
    unittest.main()
