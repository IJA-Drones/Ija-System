import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import ChecklistSemanalVeiculo, Equipe, Prefeitura, Veiculos
from app.modules.admin_checklists import service as admin_service
from app.modules.piloto_checklists import service as piloto_service


class ChecklistEmbreagemFreiosTests(unittest.TestCase):
    def setUp(self):
        # Never load the app factory or its configured database for these tests.
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.assertEqual(db.engine.url.database, ":memory:")
        db.create_all()

        self.agora = datetime(2026, 9, 10, 10, 0)
        clock = patch.object(piloto_service, "agora_brasilia_naive", return_value=self.agora)
        clock.start()
        self.addCleanup(clock.stop)
        notifications = patch.object(piloto_service, "_sincronizar_pendencias")
        notifications.start()
        self.addCleanup(notifications.stop)

        prefeitura = Prefeitura(id=1, nome="Prefeitura Teste", slug="prefeitura-teste")
        self.equipe = Equipe(nome_equipe="Equipe Teste", ativa=True, prefeitura_id=1)
        db.session.add_all([prefeitura, self.equipe])
        db.session.flush()
        self.veiculo = Veiculos(
            tipo_equipamento="veiculos",
            status="Ativo",
            modelo="FIORINO",
            ano_fabricacao=2024,
            renomacao="ABC1D23",
            frota="PROPRIA",
            operacao="PMSP",
            placa="ABC1D23",
            km_atual=1000,
            equipe_id=self.equipe.id,
            prefeitura_id=1,
        )
        db.session.add(self.veiculo)
        db.session.commit()
        self.user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
            piloto_id=None,
        )

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def _save(self, **fields):
        data = {
            "veiculo_id": str(self.veiculo.id),
            "assinatura_piloto": "assinatura-teste",
        }
        data.update(fields)
        result = piloto_service.save_piloto_checklist(self.user, MultiDict(data))
        db.session.expire_all()
        checklist = ChecklistSemanalVeiculo.query.order_by(
            ChecklistSemanalVeiculo.data_registro.desc()
        ).first()
        return checklist, result

    def _prefill(self):
        context = piloto_service.build_piloto_checklist_context(self.user, MultiDict())
        return context["veiculo_prefill"][str(self.veiculo.id)]

    def test_save_and_prefill_preserve_statuses_and_section_observation(self):
        checklist, _ = self._save(
            embreagem="0",
            freio_mao="1",
            freio_pe="0",
            condicao_embreagem_freios="  Embreagem patina e pedal está baixo.  ",
        )

        self.assertIs(checklist.embreagem, False)
        self.assertIs(checklist.freio_mao, True)
        self.assertIs(checklist.freio_pe, False)
        self.assertEqual(
            checklist.condicao_embreagem_freios,
            "Embreagem patina e pedal está baixo.",
        )
        prefill = self._prefill()
        self.assertIs(prefill["embreagem"], False)
        self.assertIs(prefill["freio_mao"], True)
        self.assertIs(prefill["freio_pe"], False)
        self.assertEqual(prefill["condicao_embreagem_freios"], checklist.condicao_embreagem_freios)
        admin = admin_service.normalize_checklist_veiculo_admin(checklist)
        self.assertIn(
            checklist.condicao_embreagem_freios,
            [item["value"] for item in admin["observacoes"]],
        )

    def test_edit_same_week_updates_statuses_without_duplicate(self):
        original, _ = self._save(
            embreagem="0",
            freio_mao="1",
            freio_pe="0",
            condicao_embreagem_freios="Inspeção inicial.",
        )
        original_id = original.id

        updated, result = self._save(
            embreagem="1",
            freio_mao="0",
            freio_pe="1",
            condicao_embreagem_freios="Freio de mão precisa de ajuste.",
        )

        self.assertEqual(updated.id, original_id)
        self.assertEqual(ChecklistSemanalVeiculo.query.count(), 1)
        self.assertIs(updated.embreagem, True)
        self.assertIs(updated.freio_mao, False)
        self.assertIs(updated.freio_pe, True)
        self.assertEqual(updated.condicao_embreagem_freios, "Freio de mão precisa de ajuste.")
        self.assertEqual(result["pendencias_semanais"], ["Veiculo ABC1D23: Freio de mão"])
        self.assertEqual(self._prefill()["condicao_embreagem_freios"], updated.condicao_embreagem_freios)

    def test_each_new_defect_appears_in_weekly_pending_and_admin_details(self):
        for field, label in (
            ("embreagem", "Embreagem"),
            ("freio_mao", "Freio de mão"),
            ("freio_pe", "Freio do pé"),
        ):
            with self.subTest(field=field):
                fields = {"embreagem": "1", "freio_mao": "1", "freio_pe": "1"}
                fields[field] = "0"
                checklist, result = self._save(**fields)

                self.assertEqual(result["pendencias_semanais"], [f"Veiculo ABC1D23: {label}"])
                admin = admin_service.normalize_checklist_veiculo_admin(checklist)
                self.assertEqual(admin["falhas"], 1)
                self.assertEqual(admin["itens_total"], 35)
                self.assertEqual(admin["itens_ok"], 34)
                self.assertEqual(
                    [item["label"] for item in admin["detalhes_itens"] if item["ok"] is False],
                    [label],
                )

    def test_defaults_and_omitted_answers_follow_existing_items(self):
        checklist = ChecklistSemanalVeiculo(
            veiculo_id=self.veiculo.id,
            equipe_id=self.equipe.id,
            data_registro=self.agora,
            km_leitura=1000,
        )
        db.session.add(checklist)
        db.session.commit()

        self.assertIs(checklist.farois_funcionando, True)
        for field in ("embreagem", "freio_mao", "freio_pe"):
            self.assertIs(getattr(checklist, field), checklist.farois_funcionando)

        self._save(
            farois_funcionando="0",
            condicao_luzes_direcao="Revisão pendente.",
            embreagem="0",
            freio_mao="0",
            freio_pe="0",
            condicao_embreagem_freios="Revisão pendente.",
        )
        updated, result = self._save()

        self.assertIs(updated.farois_funcionando, True)
        for field in ("embreagem", "freio_mao", "freio_pe"):
            self.assertIs(getattr(updated, field), updated.farois_funcionando)
        self.assertEqual(updated.condicao_luzes_direcao, "")
        self.assertEqual(
            updated.condicao_embreagem_freios,
            updated.condicao_luzes_direcao,
        )
        self.assertEqual(result["pendencias_semanais"], [])


if __name__ == "__main__":
    unittest.main()
