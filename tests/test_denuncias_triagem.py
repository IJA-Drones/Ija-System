import unittest
from datetime import date, timedelta
from types import SimpleNamespace

from app.models import Denuncia
from app.modules.denuncias import service as denuncias_service
from app.modules.solicitacoes import service as solicitacoes_service
from app.modules.solicitacoes.service import NovoCadastroValidationError


class DenunciasTriagemTests(unittest.TestCase):
    def setUp(self):
        self.original_commit = denuncias_service.db.session.commit
        self.original_usuario_model = denuncias_service.Usuario
        denuncias_service.db.session.commit = lambda: None

    def tearDown(self):
        denuncias_service.db.session.commit = self.original_commit
        denuncias_service.Usuario = self.original_usuario_model

    def test_encaminhar_denuncia_updates_status_and_coordenadoria(self):
        denuncia = Denuncia(status=Denuncia.STATUS_RECEBIDA)
        user = SimpleNamespace(id=42)

        denuncias_service.encaminhar_denuncia_para_coordenadoria(denuncia, "norte", user)

        self.assertEqual(denuncia.coordenadoria, "NORTE")
        self.assertEqual(denuncia.status, Denuncia.STATUS_ENCAMINHADA_COORDENADORIA)
        self.assertEqual(denuncia.triado_por_id, 42)
        self.assertIsNotNone(denuncia.encaminhado_em)
        self.assertIsNone(denuncia.arquivado_motivo)

    def test_arquivar_denuncia_requires_meaningful_reason(self):
        denuncia = Denuncia(status=Denuncia.STATUS_RECEBIDA)
        user = SimpleNamespace(id=42)

        with self.assertRaises(ValueError):
            denuncias_service.arquivar_denuncia(denuncia, "trote", user)

    def test_arquivar_denuncia_updates_status_and_reason(self):
        denuncia = Denuncia(status=Denuncia.STATUS_RECEBIDA)
        user = SimpleNamespace(id=42)

        denuncias_service.arquivar_denuncia(denuncia, "Relato duplicado e sem evidencias", user)

        self.assertEqual(denuncia.status, Denuncia.STATUS_ARQUIVADA)
        self.assertEqual(denuncia.triado_por_id, 42)
        self.assertIsNotNone(denuncia.arquivado_em)
        self.assertEqual(denuncia.arquivado_motivo, "Relato duplicado e sem evidencias")

    def test_designar_denuncia_para_uvis_updates_status_when_uvis_matches_region(self):
        class FakeQuery:
            def filter(self, *args):
                return self

            def first(self):
                return SimpleNamespace(id=9, tipo_usuario="uvis", regiao="NORTE")

        denuncias_service.Usuario = SimpleNamespace(id=0, tipo_usuario="", query=FakeQuery())
        denuncia = Denuncia(
            status=Denuncia.STATUS_ENCAMINHADA_COORDENADORIA,
            coordenadoria="NORTE",
        )
        user = SimpleNamespace(id=42, tipo_usuario="regional", regiao="NORTE")

        denuncias_service.designar_denuncia_para_uvis(denuncia, 9, user)

        self.assertEqual(denuncia.uvis_usuario_id, 9)
        self.assertEqual(denuncia.status, Denuncia.STATUS_ENCAMINHADA_UVIS)
        self.assertEqual(denuncia.triado_por_id, 42)

    def test_designar_denuncia_para_uvis_rejects_uvis_from_other_region(self):
        class FakeQuery:
            def filter(self, *args):
                return self

            def first(self):
                return SimpleNamespace(id=9, tipo_usuario="uvis", regiao="SUL")

        denuncias_service.Usuario = SimpleNamespace(id=0, tipo_usuario="", query=FakeQuery())
        denuncia = Denuncia(
            status=Denuncia.STATUS_ENCAMINHADA_COORDENADORIA,
            coordenadoria="NORTE",
        )
        user = SimpleNamespace(id=42, tipo_usuario="regional", regiao="NORTE")

        with self.assertRaises(ValueError):
            denuncias_service.designar_denuncia_para_uvis(denuncia, 9, user)

    def test_uvis_can_access_only_assigned_denuncia(self):
        user = SimpleNamespace(id=7, tipo_usuario="uvis", regiao="NORTE")
        assigned = Denuncia(uvis_usuario_id=7)
        other = Denuncia(uvis_usuario_id=8)

        self.assertTrue(denuncias_service.can_access_denuncia(user, assigned))
        self.assertFalse(denuncias_service.can_access_denuncia(user, other))

    def test_solicitacao_form_is_prefilled_from_denuncia(self):
        denuncia = Denuncia(
            protocolo="DEN-20260915-ABC",
            cep="01001-000",
            logradouro="Praca da Se",
            numero="1",
            bairro="Se",
            cidade="Sao Paulo",
            uf="SP",
            latitude="-23.55",
            longitude="-46.63",
            tipo_visita="Culex",
            foco="Corrego",
            descricao="Mosquitos no local",
        )

        form = denuncias_service.build_solicitacao_form_from_denuncia(denuncia)

        self.assertEqual(form["logradouro"], "Praca da Se")
        self.assertEqual(form["foco"], "Corrego")
        self.assertIn("DEN-20260915-ABC", form["observacao"])

    def test_create_solicitacao_rejects_retroactive_date(self):
        user = SimpleNamespace(id=7, tipo_usuario="uvis", prefeitura_id=None)
        form = {
            "logradouro": "Rua Teste",
            "numero": "10",
            "data": (date.today() - timedelta(days=1)).isoformat(),
            "hora": "09:00",
        }

        with self.assertRaises(NovoCadastroValidationError) as ctx:
            solicitacoes_service.create_nova_solicitacao(user, form)

        self.assertIn("retroativa", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
