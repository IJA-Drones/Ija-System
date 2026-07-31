import unittest
from datetime import date, time
from types import SimpleNamespace

from flask import Flask
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Equipe, OrdemServico, Prefeitura, Solicitacao, Usuario
from app.modules.relatorios.service import build_retornos_automaticos_context


class RelatoriosRetornosAutomaticosTests(unittest.TestCase):
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

        self.prefeitura = Prefeitura(id=1, nome="Prefeitura Teste", slug="prefeitura-teste")
        self.equipe = Equipe(nome_equipe="PLOA 24", regiao="SUL", ativa=True, prefeitura_id=1)
        self.uvis = Usuario(
            nome_uvis="UVIS Teste",
            login="uvis-teste",
            senha_hash="x",
            tipo_usuario="uvis",
            prefeitura_id=1,
            regiao="SUL",
        )
        db.session.add_all([self.prefeitura, self.equipe, self.uvis])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _solicitacao(self, **overrides):
        data = {
            "prefeitura_id": 1,
            "data_agendamento": date(2026, 8, 15),
            "hora_agendamento": time(9, 0),
            "foco": "Aedes",
            "tipo_operacao": "Monitoramento",
            "cep": "00000-000",
            "logradouro": "Rua Retorno",
            "numero": "100",
            "bairro": "Centro",
            "cidade": "Sao Paulo",
            "uf": "SP",
            "usuario_id": self.uvis.id,
            "status": "PENDENTE",
        }
        data.update(overrides)
        solicitacao = Solicitacao(**data)
        db.session.add(solicitacao)
        db.session.flush()
        return solicitacao

    def test_build_context_groups_automatic_returns_by_team_and_general_list(self):
        retorno = self._solicitacao(equipe_id=self.equipe.id, gerada_automaticamente=True)
        db.session.add(
            OrdemServico(
                solicitacao_id=retorno.id,
                equipe_id=self.equipe.id,
                identificador_os="OS-RET-24",
                piloto="",
                data_aplicacao=date(2026, 8, 15),
            )
        )
        self._solicitacao(gerada_automaticamente=True, logradouro="Rua Sem Equipe")
        self._solicitacao(gerada_automaticamente=False, logradouro="Rua Normal")
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)
        args = MultiDict({"data_ini": "2026-08-01", "data_fim": "2026-08-31"})

        context = build_retornos_automaticos_context(user, args)

        self.assertEqual(context["total_retornos"], 2)
        self.assertEqual(context["total_sem_equipe"], 1)
        self.assertEqual([item["id"] for item in context["retornos"]], [retorno.id, retorno.id + 1])
        self.assertIn("Rua Retorno", context["retornos"][0]["endereco"])
        cards = {card["nome"]: card for card in context["equipes_cards"]}
        self.assertEqual(cards["PLOA 24"]["total"], 1)
        self.assertEqual(cards["Sem equipe"]["total"], 1)

    def test_build_context_without_date_filters_does_not_limit_period(self):
        self._solicitacao(
            data_agendamento=date(2025, 1, 10),
            gerada_automaticamente=True,
            logradouro="Rua Antiga",
        )
        self._solicitacao(
            data_agendamento=date(2027, 3, 20),
            gerada_automaticamente=True,
            logradouro="Rua Futura",
        )
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)

        context = build_retornos_automaticos_context(user, MultiDict())

        self.assertIsNone(context["filters"]["data_ini"])
        self.assertIsNone(context["filters"]["data_fim"])
        self.assertEqual(context["total_retornos"], 2)

    def test_build_context_orders_expired_dates_last_and_newest_first(self):
        self._solicitacao(
            data_agendamento=date(2000, 1, 10),
            gerada_automaticamente=True,
            logradouro="Rua Vencida",
        )
        self._solicitacao(
            data_agendamento=date(2098, 3, 20),
            gerada_automaticamente=True,
            logradouro="Rua Futura Menor",
        )
        self._solicitacao(
            data_agendamento=date(2099, 4, 25),
            gerada_automaticamente=True,
            logradouro="Rua Futura Maior",
        )
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)

        context = build_retornos_automaticos_context(user, MultiDict())

        enderecos = [item["endereco"] for item in context["retornos"]]
        self.assertIn("Rua Futura Maior", enderecos[0])
        self.assertIn("Rua Futura Menor", enderecos[1])
        self.assertIn("Rua Vencida", enderecos[-1])

    def test_build_context_includes_active_team_cards_even_without_returns(self):
        equipe_sem_retorno = Equipe(nome_equipe="PLOA 20", regiao="SUL", ativa=True, prefeitura_id=1)
        db.session.add(equipe_sem_retorno)
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)

        context = build_retornos_automaticos_context(user, MultiDict())

        cards = {card["nome"]: card for card in context["equipes_cards"]}
        self.assertIn("PLOA 20", cards)
        self.assertEqual(cards["PLOA 20"]["total"], 0)

    def test_build_context_filters_by_complete_search_fields(self):
        self._solicitacao(
            equipe_id=self.equipe.id,
            gerada_automaticamente=True,
            logradouro="Rua Filtrada",
            bairro="Bairro Certo",
            foco="Escorpiao",
            tipo_visita="Retorno",
            tipo_imovel="Residencial",
            apoio_cet=True,
        )
        self._solicitacao(
            equipe_id=self.equipe.id,
            gerada_automaticamente=True,
            logradouro="Rua Ignorada",
            bairro="Outro Bairro",
            foco="Aedes",
            tipo_visita="Inicial",
            tipo_imovel="Comercial",
            apoio_cet=False,
        )
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)
        args = MultiDict(
            {
                "unidade": "UVIS Teste",
                "regiao": "SUL",
                "apoio_cet": "SIM",
                "tipo_visita": "Retorno",
                "tipo_imovel": "Residencial",
                "tipo_operacao": "Monitoramento",
                "foco": "Escorpiao",
                "endereco": "Filtrada",
            }
        )

        context = build_retornos_automaticos_context(user, args)

        self.assertEqual(context["total_retornos"], 1)
        self.assertIn("Rua Filtrada", context["retornos"][0]["endereco"])

    def test_build_context_uses_origin_team_when_return_has_no_team(self):
        origem = self._solicitacao(
            equipe_id=self.equipe.id,
            gerada_automaticamente=False,
            data_agendamento=date(2026, 7, 1),
        )
        db.session.add(
            OrdemServico(
                solicitacao_id=origem.id,
                equipe_id=self.equipe.id,
                identificador_os="OS-ORIGEM-20",
                data_aplicacao=date(2026, 7, 1),
            )
        )
        retorno = self._solicitacao(
            equipe_id=None,
            gerada_automaticamente=True,
            origem_retorno_id=origem.id,
            data_agendamento=date(2026, 8, 1),
            logradouro="Rua Retorno Origem",
        )
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)
        args = MultiDict({"equipe_id": str(self.equipe.id)})

        context = build_retornos_automaticos_context(user, args)

        self.assertEqual(context["total_retornos"], 1)
        self.assertEqual(context["retornos"][0]["id"], retorno.id)
        self.assertEqual(context["retornos"][0]["equipe_nome"], "PLOA 24")
        self.assertEqual(context["equipes_cards"][0]["nome"], "PLOA 24")
        self.assertEqual(context["total_sem_equipe"], 0)

    def test_build_context_applies_prefeitura_scope(self):
        self._solicitacao(gerada_automaticamente=True, equipe_id=self.equipe.id)
        prefeitura_outra = Prefeitura(id=2, nome="Outra Prefeitura", slug="outra-prefeitura")
        uvis_outra = Usuario(
            nome_uvis="UVIS Outra",
            login="uvis-outra",
            senha_hash="x",
            tipo_usuario="uvis",
            prefeitura_id=2,
        )
        db.session.add_all([prefeitura_outra, uvis_outra])
        db.session.flush()
        self._solicitacao(
            prefeitura_id=2,
            usuario_id=uvis_outra.id,
            gerada_automaticamente=True,
            logradouro="Rua Fora do Escopo",
        )
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="prefeitura_admin", prefeitura_id=1)
        args = MultiDict({"data_ini": "2026-08-01", "data_fim": "2026-08-31"})

        context = build_retornos_automaticos_context(user, args)

        self.assertEqual(context["total_retornos"], 1)
        self.assertNotIn("Rua Fora do Escopo", context["retornos"][0]["endereco"])


if __name__ == "__main__":
    unittest.main()
