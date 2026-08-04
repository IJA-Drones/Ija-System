import unittest
from datetime import date, time
from unittest.mock import patch

from flask import Flask
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Prefeitura, Solicitacao, Usuario
from app.modules.solicitacoes import service as solicitacoes_service
from app.modules.solicitacoes.service import NovoCadastroValidationError


class SolicitacaoPlaceIdBlockTests(unittest.TestCase):
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

        self.prefeitura = Prefeitura(id=1, nome="Prefeitura A", slug="prefeitura-a")
        self.outra_prefeitura = Prefeitura(id=2, nome="Prefeitura B", slug="prefeitura-b")
        self.uvis = Usuario(
            nome_uvis="UVIS A",
            regiao="OESTE",
            login="uvis_a",
            senha_hash="hash",
            tipo_usuario="uvis",
            prefeitura_id=1,
        )
        self.outra_uvis = Usuario(
            nome_uvis="UVIS B",
            regiao="LESTE",
            login="uvis_b",
            senha_hash="hash",
            tipo_usuario="uvis",
            prefeitura_id=2,
        )
        db.session.add_all([self.prefeitura, self.outra_prefeitura, self.uvis, self.outra_uvis])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _solicitacao_form(self, place_id):
        return MultiDict({
            "data": "2026-08-10",
            "hora": "09:30",
            "cep": "02131-040",
            "logradouro": "Rua Hiroshima",
            "numero": "100",
            "bairro": "Vila Maria Alta",
            "cidade": "Sao Paulo",
            "uf": "SP",
            "latitude": "-23.5001",
            "longitude": "-46.6001",
            "place_id": place_id,
            "tipo_visita": "Visita",
            "tipo_imovel": "Casa",
            "foco": "Foco Teste",
            "tipo_operacao": "Tratamento",
            "altura_voo": "30",
            "distrito_administrativo": "DA Teste",
            "apoio_cet": "nao",
        })

    def _bloqueio_existente(self, *, prefeitura_id=1, place_id="place-123"):
        bloqueada = Solicitacao(
            data_agendamento=date(2026, 8, 1),
            hora_agendamento=time(8, 0),
            foco="Foco Teste",
            cep="02131-040",
            logradouro="Rua Hiroshima",
            numero="100",
            bairro="Vila Maria Alta",
            cidade="Sao Paulo",
            uf="SP",
            status="CONCLU\u00cdDO",
            usuario_id=self.uvis.id if prefeitura_id == 1 else self.outra_uvis.id,
            prefeitura_id=prefeitura_id,
            place_id=place_id,
            endereco_bloqueado=True,
        )
        db.session.add(bloqueada)
        db.session.commit()
        return bloqueada

    def test_create_blocks_same_place_id_when_concluded_in_same_prefeitura(self):
        bloqueada = self._bloqueio_existente()

        with self.assertRaises(NovoCadastroValidationError) as exc:
            solicitacoes_service.create_nova_solicitacao(
                self.uvis,
                self._solicitacao_form("place-123"),
            )

        self.assertIn(f"OS #{bloqueada.id}", exc.exception.message)
        self.assertEqual(Solicitacao.query.count(), 1)

    def test_create_allows_same_place_id_in_other_prefeitura(self):
        self._bloqueio_existente(prefeitura_id=1, place_id="place-123")

        with (
            patch.object(solicitacoes_service, "detectar_area_restrita", return_value=False),
            patch.object(
                solicitacoes_service,
                "validate_foco_selection",
                return_value=("Visita", "Casa", "Foco Teste"),
            ),
        ):
            nova = solicitacoes_service.create_nova_solicitacao(
                self.outra_uvis,
                self._solicitacao_form("place-123"),
            )

        self.assertEqual(nova.prefeitura_id, 2)
        self.assertEqual(nova.place_id, "place-123")
        self.assertEqual(Solicitacao.query.count(), 2)


if __name__ == "__main__":
    unittest.main()
