import unittest
from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Equipe, Solicitacao, Usuario
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

    def test_equipe_uvis_agenda_uses_owner_uvis_scope(self):
        user = SimpleNamespace(
            id=99,
            tipo_usuario="equipe_uvis",
            equipe_uvis_uvis_usuario_id=42,
        )

        self.assertEqual(agenda_service._agenda_owner_usuario_id(user), 42)
        self.assertTrue(agenda_service.can_export_agenda(user))


class AgendaVisibleStatusTests(unittest.TestCase):
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

        self.uvis = Usuario(
            nome_uvis="UVIS Teste",
            regiao="OESTE",
            login="uvis_agenda",
            senha_hash="hash",
            tipo_usuario="uvis",
        )
        db.session.add(self.uvis)
        db.session.commit()
        self.equipe = Equipe(nome_equipe="PLOA Agenda", regiao="OESTE", ativa=True)
        db.session.add(self.equipe)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _nova_solicitacao(self, status, **overrides):
        values = {
            "data_agendamento": date(2026, 7, 20),
            "hora_agendamento": time(17, 0),
            "foco": "Edificacao Abandonada com Inserviveis",
            "cep": "02131-040",
            "logradouro": "Rua Hiroshima",
            "bairro": "Vila Maria Alta",
            "cidade": "Sao Paulo",
            "uf": "SP",
            "status": status,
            "usuario_id": self.uvis.id,
        }
        values.update(overrides)
        solicitacao = Solicitacao(
            **values,
        )
        db.session.add(solicitacao)
        return solicitacao

    def test_agenda_only_lists_approved_recommended_and_completed_statuses(self):
        aprovado = self._nova_solicitacao("APROVADO")
        recomendado = self._nova_solicitacao("APROVADO COM RECOMENDAÇÕES")
        concluido = self._nova_solicitacao("CONCLUÍDO")
        self._nova_solicitacao("NEGADO")
        self._nova_solicitacao("PENDENTE")
        self._nova_solicitacao("EM ANÁLISE")
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin")
        resultados = agenda_service.build_agenda_query(
            user,
            mes=7,
            ano=2026,
        ).order_by(Solicitacao.id.asc()).all()

        self.assertEqual([item.id for item in resultados], [aprovado.id, recomendado.id, concluido.id])

    def test_admin_agenda_lists_pending_automatic_returns_as_reserved_slots(self):
        retorno = self._nova_solicitacao(
            "PENDENTE",
            gerada_automaticamente=True,
            logradouro="Rua Retorno Automatico",
        )
        self._nova_solicitacao("PENDENTE", logradouro="Rua Pendente Normal")
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin")
        resultados = agenda_service.build_agenda_query(
            user,
            mes=7,
            ano=2026,
        ).order_by(Solicitacao.id.asc()).all()

        self.assertEqual([item.id for item in resultados], [retorno.id])

    def test_admin_agenda_lists_future_pending_automatic_returns_outside_current_month(self):
        aprovado_mes_atual = self._nova_solicitacao(
            "APROVADO",
            data_agendamento=date(2026, 7, 20),
        )
        retorno_futuro = self._nova_solicitacao(
            "PENDENTE",
            gerada_automaticamente=True,
            data_agendamento=date(2026, 8, 20),
        )
        self._nova_solicitacao(
            "PENDENTE",
            data_agendamento=date(2026, 8, 20),
        )
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin")
        with patch.object(agenda_service, "datetime", FixedDatetime):
            resultados = agenda_service.build_agenda_query(
                user,
                mes=7,
                ano=2026,
            ).order_by(Solicitacao.id.asc()).all()

        self.assertEqual([item.id for item in resultados], [aprovado_mes_atual.id, retorno_futuro.id])

    def test_normal_agenda_filter_keeps_future_automatic_returns_out(self):
        aprovado_mes_atual = self._nova_solicitacao(
            "APROVADO",
            data_agendamento=date(2026, 7, 20),
        )
        self._nova_solicitacao(
            "PENDENTE",
            gerada_automaticamente=True,
            data_agendamento=date(2026, 8, 20),
        )
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin")
        with patch.object(agenda_service, "datetime", FixedDatetime):
            resultados = agenda_service.build_agenda_query(
                user,
                filtro_tipo_agenda=agenda_service.AGENDA_TIPO_NORMAL,
                mes=7,
                ano=2026,
            ).order_by(Solicitacao.id.asc()).all()

        self.assertEqual([item.id for item in resultados], [aprovado_mes_atual.id])

    def test_agenda_can_filter_only_automatic_returns(self):
        retorno = self._nova_solicitacao("PENDENTE", gerada_automaticamente=True)
        self._nova_solicitacao("APROVADO")
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin")
        resultados = agenda_service.build_agenda_query(
            user,
            filtro_tipo_agenda=agenda_service.AGENDA_TIPO_AUTO,
            mes=7,
            ano=2026,
        ).order_by(Solicitacao.id.asc()).all()

        self.assertEqual([item.id for item in resultados], [retorno.id])

    def test_agenda_can_filter_automatic_returns_by_lifecycle(self):
        vencido = self._nova_solicitacao(
            "PENDENTE",
            gerada_automaticamente=True,
            data_agendamento=date(2026, 6, 10),
        )
        futuro = self._nova_solicitacao(
            "PENDENTE",
            gerada_automaticamente=True,
            data_agendamento=date(2026, 6, 20),
        )
        concluido = self._nova_solicitacao(
            "CONCLUIDO",
            gerada_automaticamente=True,
            data_agendamento=date(2026, 6, 9),
        )
        self._nova_solicitacao(
            "PENDENTE",
            gerada_automaticamente=False,
            data_agendamento=date(2026, 6, 8),
        )
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="admin")
        with patch.object(agenda_service, "datetime", FixedDatetime):
            pendentes = agenda_service.build_agenda_query(
                user,
                filtro_tipo_agenda=agenda_service.AGENDA_TIPO_AUTO_PENDENTE,
            ).order_by(Solicitacao.id.asc()).all()
            concluidos = agenda_service.build_agenda_query(
                user,
                filtro_tipo_agenda=agenda_service.AGENDA_TIPO_AUTO_CONCLUIDO,
            ).order_by(Solicitacao.id.asc()).all()
            vencidos = agenda_service.build_agenda_query(
                user,
                filtro_tipo_agenda=agenda_service.AGENDA_TIPO_AUTO_VENCIDO,
            ).order_by(Solicitacao.id.asc()).all()
            futuros = agenda_service.build_agenda_query(
                user,
                filtro_tipo_agenda=agenda_service.AGENDA_TIPO_AUTO_FUTURO,
            ).order_by(Solicitacao.id.asc()).all()

        self.assertEqual([item.id for item in pendentes], [vencido.id, futuro.id])
        self.assertEqual([item.id for item in concluidos], [concluido.id])
        self.assertEqual([item.id for item in vencidos], [vencido.id])
        self.assertEqual([item.id for item in futuros], [futuro.id])

    def test_operational_agenda_does_not_list_pending_automatic_returns(self):
        self._nova_solicitacao("PENDENTE", gerada_automaticamente=True, equipe_id=self.equipe.id)
        db.session.commit()

        user = SimpleNamespace(tipo_usuario="equipe_oceano", codigo_setor=str(self.equipe.id))
        resultados = agenda_service.build_agenda_query(
            user,
            mes=7,
            ano=2026,
        ).order_by(Solicitacao.id.asc()).all()

        self.assertEqual(resultados, [])

    def test_automatic_return_event_has_agenda_marker(self):
        retorno = self._nova_solicitacao(
            "PENDENTE",
            gerada_automaticamente=True,
            origem_retorno_id=123,
        )
        db.session.commit()

        evento = agenda_service.build_agenda_eventos([retorno])[0]

        self.assertNotIn("Retorno automatico", evento["title"])
        self.assertIn("Rua Hiroshima", evento["title"])
        self.assertIn("agenda-event-retorno", evento["classNames"])
        self.assertTrue(evento["extendedProps"]["is_retorno_automatico"])
        self.assertEqual(evento["extendedProps"]["tipo_agenda_label"], "Retorno automatico")
        self.assertEqual(evento["extendedProps"]["origem_retorno_id"], 123)


if __name__ == "__main__":
    unittest.main()
