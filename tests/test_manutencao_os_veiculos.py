"""Vehicle worksheets, weekly defects and preventive plans in a disposable database."""
from datetime import timedelta
from io import BytesIO
import unittest

from openpyxl import load_workbook
from pypdf import PdfReader
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import (
    ChecklistSemanalVeiculo, Equipe, EstoquePeca, ManutencaoEquipamento, ManutencaoPecaUso,
    Notificacao, PreventivaPlano, PreventivaRegistro, Usuario, Veiculos,
)
from app.modules.equipamentos.preventivas import today_local
from app.modules.piloto_checklists.service import save_piloto_checklist
from tests import test_manutencao_os as fixture
from tests.maintenance_helpers import worksheet_data


OPEN = "/equipamentos/manutencoes/nova"
HISTORY = "/equipamentos/manutencoes/historico"


class VehicleMaintenanceTests(unittest.TestCase):
    configure = fixture.ManutencaoOsTests.configure
    login = fixture.ManutencaoOsTests.login
    tearDown = fixture.ManutencaoOsTests.tearDown

    def setUp(self):
        fixture.ManutencaoOsTests.setUp(self)
        self.configure(self.permissions + ["prefeitura.veiculos.consultar", "prefeitura.veiculos.editar"])
        self.team = Equipe(nome_equipe="Oficina da frota", prefeitura_id=1)
        self.vehicle = Veiculos(
            modelo="Fiorino", renomacao="Frota teste", placa="OSV1A26", frota="PROPRIA",
            operacao="PMSP", prefeitura_id=1, equipe=self.team, km_atual=12345,
        )
        self.foreign = Veiculos(
            modelo="Fiorino", renomacao="Frota de outro município", placa="OSV2A26",
            frota="PROPRIA", operacao="PMSP", prefeitura_id=2,
        )
        self.part = EstoquePeca(
            prefeitura_id=1, modelo_peca="Pastilha", codigo_dji="FREIO-FIORINO",
            modelos_compativeis="FIORINO", quantidade=3,
        )
        db.session.add_all([self.vehicle, self.foreign, self.part])
        db.session.flush()
        self.checklist_user = Usuario(
            login="equipe.os", senha_hash="test-only", nome_uvis="Equipe Checklist",
            tipo_usuario="equipe_oceano", prefeitura_id=1, codigo_setor=str(self.team.id),
        )
        db.session.add(self.checklist_user)
        db.session.commit()

    def open_vehicle_os(self, **form):
        fields = {"equipamento_id": self.vehicle.id, "avarias_identificadas": "Ruído ao frear", **form}
        return self.client.post(OPEN, data=fields)

    def save_weekly_checklist(self, **fields):
        with self.app.test_request_context():
            save_piloto_checklist(self.checklist_user, MultiDict({
                "veiculo_id": str(self.vehicle.id), "assinatura_piloto": "assinatura de teste", **fields,
            }))
        return ChecklistSemanalVeiculo.query.filter_by(veiculo_id=self.vehicle.id).one()

    def test_manual_os_tracks_fleet_stock_and_exports_with_vehicle_scope(self):
        page = self.client.get(OPEN).text
        self.assertIn('label="Veículos"', page)
        self.assertIn(self.vehicle.placa, page)
        self.assertNotIn(self.foreign.placa, page)
        self.assertEqual(self.open_vehicle_os(equipamento_id=self.foreign.id).status_code, 404)

        response = self.open_vehicle_os(tipo_manutencao="corretiva")
        self.assertEqual(response.status_code, 302)
        path = response.location
        order = ManutencaoEquipamento.query.one()
        self.assertEqual(order.veiculo_id, self.vehicle.id)
        self.assertIsNone(order.drone_id)
        self.assertEqual(order.km_recebimento, 12345)
        self.assertEqual(self.vehicle.status, "Em Manutenção")
        self.assertIn("Dados do veículo", self.client.get(path).text)
        self.assertIn(path, self.client.get(f"/equipamentos/em-manutencao?q={self.vehicle.placa}").text)

        repaired = [(self.part, 2, "Par de pastilhas substituído")]
        self.assertEqual(self.client.post(path, data=worksheet_data(
            order, repaired, km_recebimento="12350",
        )).status_code, 302)
        self.assertEqual(self.part.quantidade, 3)
        self.assertEqual(ManutencaoPecaUso.query.count(), 0)
        invalid = self.client.post(path, data=worksheet_data(order, repaired, complete=True, km_recebimento="-1"))
        self.assertIn("quilometragem válida", invalid.text)
        self.assertEqual(self.part.quantidade, 3)

        completion = worksheet_data(order, repaired, complete=True, km_recebimento="12350")
        response = self.client.post(path, data=completion)
        self.assertEqual(response.status_code, 302)
        detail_path = response.location
        self.assertEqual(self.part.quantidade, 1)
        self.assertEqual(ManutencaoPecaUso.query.one().veiculo_id, self.vehicle.id)
        self.assertEqual(order.status, "encerrada")
        self.assertIsNotNone(self.vehicle.ultima_manutencao)
        self.assertEqual(self.vehicle.km_atual, 12345)
        self.assertIn("12350.0 km", self.client.get(detail_path).text)
        self.assertEqual(self.client.post(path, data=completion).location, detail_path)
        self.assertEqual(self.part.quantidade, 1)
        pdf = self.client.get(f"{detail_path}/pdf")
        self.assertEqual(pdf.mimetype, "application/pdf")
        pdf_text = " ".join(page.extract_text() for page in PdfReader(BytesIO(pdf.data)).pages)
        self.assertIn(self.vehicle.placa, pdf_text)
        self.assertIn("12350.0", pdf_text)
        pdf.close()
        export = self.client.get(f"{HISTORY}/excel?equipamento_id={self.vehicle.id}")
        workbook = load_workbook(BytesIO(export.data))
        row = list(workbook.active.values)[2]
        self.assertIn(self.vehicle.placa, row)
        self.assertIn(12350, row)
        workbook.close()

        self.configure(self.permissions)
        self.assertNotIn(self.vehicle.placa, self.client.get(OPEN).text)
        self.assertNotIn(order.numero_os, self.client.get(HISTORY).text)
        self.assertEqual(self.client.get(detail_path).status_code, 404)
        self.assertEqual(self.client.get(detail_path + "/pdf").status_code, 404)

    def test_weekly_defect_notifies_only_maintenance_and_prefills_os_once(self):
        other_maintenance = Usuario(
            nome_uvis="Outra oficina", login="manutencao.outro.municipio", senha_hash="test-only",
            tipo_usuario="manutencao", prefeitura_id=2,
        )
        db.session.add(other_maintenance)
        db.session.commit()
        fields = {"freio_pe": "0", "condicao_embreagem_freios": "Pedal baixo"}
        checklist = self.save_weekly_checklist(**fields)
        self.assertEqual(ManutencaoEquipamento.query.count(), 0)
        alert = Notificacao.query.filter_by(checklist_veiculo_id=checklist.id).one()
        self.assertEqual(alert.usuario_id, self.user.id)
        self.assertIn(self.vehicle.placa, alert.titulo)
        alert_url = f"/notificacoes/{alert.id}/ler"

        self.login("dev")
        self.assertEqual(self.client.get(alert_url).status_code, 404)
        self.login("manutencao")
        self.assertIn(alert.titulo, self.client.get("/notificacoes").text)
        response = self.client.get(alert_url, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Freio do pé", response.text)
        self.assertIn("Pedal baixo", response.text)
        self.assertEqual(ManutencaoEquipamento.query.count(), 0)
        self.save_weekly_checklist(**fields)
        self.assertEqual(Notificacao.query.filter_by(checklist_veiculo_id=checklist.id).count(), 1)
        self.assertIsNotNone(alert.lida_em)

        self.assertEqual(self.open_vehicle_os(
            equipamento_id=self.drones[0].id, checklist_veiculo_id=checklist.id,
        ).status_code, 404)
        order_form = {
            "checklist_veiculo_id": checklist.id, "tipo_manutencao": "corretiva",
            "avarias_identificadas": alert.mensagem,
        }
        self.vehicle.km_atual += 500
        db.session.commit()
        first = self.open_vehicle_os(**order_form)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(self.open_vehicle_os(**order_form).location, first.location)
        order = ManutencaoEquipamento.query.one()
        self.assertEqual(order.checklist_veiculo_id, checklist.id)
        self.assertEqual(order.km_recebimento, 12345)
        self.assertIn("Pedal baixo", order.avarias_identificadas)
        self.save_weekly_checklist()
        self.assertIsNotNone(alert.apagada_em)
        self.assertNotIn(alert.titulo, self.client.get("/notificacoes").text)

    def test_preventive_alert_starts_a_vehicle_or_drone_os_after_confirmation(self):
        today = today_local()
        for equipment in (self.vehicle, self.drones[0]):
            detail = f"/equipamentos/preventivas/{equipment.id}"
            response = self.client.post(detail, data={
                "acao": "configurar", "versao": "0", "intervalo": "60",
                "ultima_realizada_em": (today - timedelta(days=60)).isoformat(),
            })
            self.assertEqual(response.status_code, 302)
            self.client.get("/notificacoes")
            alert = Notificacao.query.filter_by(link=detail, apagada_em=None, usuario_id=self.user.id).one()
            page = self.client.get(f"/notificacoes/{alert.id}/ler", follow_redirects=True)
            self.assertIn("Abrir OS preventiva", page.text)
            self.assertIn(f"{OPEN}?equipamento_id={equipment.id}&amp;tipo_manutencao=preventiva", page.text)
            form = self.client.get(f"{OPEN}?equipamento_id={equipment.id}&tipo_manutencao=preventiva")
            self.assertIn('value="preventiva" selected', form.text)
            self.assertIn("Manutenção preventiva programada.", form.text)
            plan = PreventivaPlano.query.filter_by(equipamento_id=equipment.id).one()
            self.assertEqual(plan.ultima_realizada_em, today - timedelta(days=60))

            order_key = {"veiculo_id": equipment.id} if equipment is self.vehicle else {"drone_id": equipment.id}
            self.assertIsNone(ManutencaoEquipamento.query.filter_by(**order_key).first())
            opened = self.client.post(OPEN, data={
                "equipamento_id": equipment.id, "avarias_identificadas": "Revisão programada",
                "tipo_manutencao": "preventiva",
            })
            self.assertEqual(opened.status_code, 302)
            order = ManutencaoEquipamento.query.filter_by(**order_key).one()
            self.assertEqual(order.tipo_manutencao, "preventiva")
            self.assertEqual(self.client.post(opened.location, data=worksheet_data(
                order, complete=True, tipo_manutencao="preventiva",
            )).status_code, 302)
            self.assertIn(order.numero_os, self.client.get(detail).text)
            response = self.client.post(detail, data={
                "acao": "concluir", "versao": str(plan.versao), "realizada_em": today.isoformat(),
                "descricao": "Revisão programada realizada", "manutencao_id": str(order.id),
            })
            self.assertEqual(response.status_code, 302)
            self.assertEqual(plan.ultima_realizada_em, today)
            self.assertIsNotNone(PreventivaRegistro.query.filter_by(manutencao_id=order.id).first())
