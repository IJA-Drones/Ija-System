import unittest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from flask import Blueprint, Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader
from werkzeug.datastructures import FileStorage, MultiDict

from app.extensions import db
from app.models import Abastecimento, ChecklistSemanalDrone, ChecklistSemanalVeiculo, Drones, Equipe, LogVeiculo, Notificacao, Pilotos, Prefeitura, Usuario, Veiculos
from app.modules.admin_checklists.routes import register_routes as register_admin_checklists_routes
from app.modules.admin_checklists import service as admin_checklists
from app.modules.equipes.routes import register_routes as register_equipes_routes
from app.modules.equipes.service import build_equipes_query
from app.modules.piloto_checklists import service as checklists
from app.modules.usuarios.routes import register_routes as register_usuarios_routes
from app.modules.veiculos.routes import register_routes as register_veiculos_routes
from app.modules.veiculos.service import (
    _operador_log_veiculo, _veiculo_do_operacional_logado, build_piloto_veiculos_context,
    iniciar_turno_piloto, list_equipes_choices, list_supervisores_choices, validate_veiculo_form,
)
from app.shared.access import is_admin_global_user
from app.shared.vehicle_supervisor import get_supervisor_equipe


class SupervisorVeiculosTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / "app/templates"))
        self.app.config.update(TESTING=True, SECRET_KEY="test-key", SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
                               SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(self.app)
        manager = LoginManager(self.app)
        manager.user_loader(lambda user_id: db.session.get(Usuario, int(user_id)))
        bp = Blueprint("main", __name__)
        register_usuarios_routes(bp)
        register_equipes_routes(bp)
        register_veiculos_routes(bp)
        register_admin_checklists_routes(bp)
        bp.add_url_rule("/", "dashboard", lambda: "ok")
        bp.add_url_rule("/piloto-os", "piloto_os", lambda: "ok")
        self.app.register_blueprint(bp)
        self.app.jinja_env.globals["is_admin_global_user"] = is_admin_global_user
        self.app.jinja_loader = ChoiceLoader([
            DictLoader({"base.html": "{% block content %}{% endblock %}{% block scripts %}{% endblock %}"}),
            self.app.jinja_loader,
        ])
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        db.session.add_all([Prefeitura(id=1, nome="Cidade Um", slug="um"),
                            Prefeitura(id=2, nome="Cidade Dois", slug="dois")])
        self.norte = Equipe(nome_equipe="Equipe Norte", regiao="NORTE", prefeitura_id=1, ativa=True)
        self.sul = Equipe(nome_equipe="Equipe Sul", regiao="SUL", prefeitura_id=1, ativa=True)
        self.outra = Equipe(nome_equipe="Outra Cidade", regiao="OESTE", prefeitura_id=2, ativa=True)
        db.session.add_all([self.norte, self.sul, self.outra])
        db.session.flush()
        self.veiculos, self.drones = [], []
        for i, equipe in enumerate((self.norte, self.sul, self.outra), 1):
            veiculo = Veiculos(modelo="Fiorino", renomacao=f"Carro {i}", placa=f"ABC{i}D23",
                               equipe_id=equipe.id, prefeitura_id=equipe.prefeitura_id, status="Ativo",
                               km_atual=1000, frota="PROPRIA", operacao="PMSP")
            drone = Drones(modelo="DJI", renomacao=f"Drone {i}", registro_anac=f"ANAC-{i}",
                           registro_anatel=f"ANATEL-{i}", equipe_id=equipe.id,
                           prefeitura_id=equipe.prefeitura_id, status="Ativo", pmd_kg=25)
            db.session.add_all([veiculo, drone])
            self.veiculos.append(veiculo)
            self.drones.append(drone)
        self.admin = Usuario(nome_uvis="Admin", login="admin", senha_hash="test", tipo_usuario="admin")
        self.supervisor = Usuario(nome_uvis="Supervisor", login="supervisor", senha_hash="test",
                                  tipo_usuario="sup_veiculos", prefeitura_id=1, regiao="SUL",
                                  codigo_setor=str(self.norte.id))
        db.session.add_all([self.admin, self.supervisor])
        db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.admin.id)
            session["_fresh"] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def _vehicle_form(self, veiculo, supervisor_id=None, equipe_id=None):
        return MultiDict({"modelo": veiculo.modelo, "ano_fabricacao": "2024", "frota": "PROPRIA",
                          "operacao": "PMSP", "placa": veiculo.placa,
                          "equipe_id": str(equipe_id or veiculo.equipe_id), "supervisor_id": str(supervisor_id or ""),
                          "km_atual": "1000", "status": "Ativo"})

    def test_team_form_does_not_assign_supervisor_even_if_old_field_is_posted(self):
        for url in ("/equipes/cadastrar", f"/equipes/{self.norte.id}/editar"):
            self.assertNotIn('name="supervisor_ids"', self.client.get(url).get_data(as_text=True))
        response = self.client.post(f"/equipes/{self.sul.id}/editar", data={
            "nome_equipe": self.sul.nome_equipe, "regiao": "SUL", "ativa": "on",
            "supervisor_ids": str(self.supervisor.id), "supervisores_presentes": "1",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(get_supervisor_equipe(self.supervisor))
        self.assertEqual(self.supervisor.codigo_setor, str(self.norte.id))

    def test_vehicle_editor_assigns_supervisor_without_changing_team(self):
        veiculo = self.veiculos[1]
        response = self.client.post(f"/veiculos/{veiculo.id}/editar",
                                    data=self._vehicle_form(veiculo, self.supervisor.id))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(veiculo.equipe_id, self.sul.id)
        self.assertEqual(veiculo.supervisor_usuario_id, self.supervisor.id)
        self.assertEqual(veiculo.responsavel_exibicao, "Supervisor")
        self.assertIsNone(self.supervisor.codigo_setor)

    def test_vehicle_list_assigns_and_moves_supervisor_with_bulk_save(self):
        html = self.client.get("/veiculos").get_data(as_text=True)
        self.assertIn("Supervisor responsável", html)
        self.assertIn(f'name="supervisor_id_{self.veiculos[1].id}"', html)
        self.assertIn(f'data-supervisor-value="{self.supervisor.id}"', html)

        response = self.client.post("/veiculos/equipes", data={
            "veiculo_ids": [str(self.veiculos[0].id), str(self.veiculos[1].id)],
            f"equipe_id_{self.veiculos[0].id}": str(self.norte.id),
            f"equipe_id_{self.veiculos[1].id}": str(self.sul.id),
            f"supervisor_id_{self.veiculos[0].id}": "",
            f"supervisor_id_{self.veiculos[1].id}": str(self.supervisor.id),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.veiculos[1].supervisor_usuario_id, self.supervisor.id)
        self.assertEqual(self.veiculos[1].equipe_id, self.sul.id)
        self.assertIsNone(self.supervisor.codigo_setor)

        response = self.client.post("/veiculos/equipes", data={
            "veiculo_ids": [str(self.veiculos[0].id), str(self.veiculos[1].id)],
            f"equipe_id_{self.veiculos[0].id}": str(self.norte.id),
            f"equipe_id_{self.veiculos[1].id}": str(self.sul.id),
            f"supervisor_id_{self.veiculos[0].id}": str(self.supervisor.id),
            f"supervisor_id_{self.veiculos[1].id}": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.veiculos[0].supervisor_usuario_id, self.supervisor.id)
        self.assertIsNone(self.veiculos[1].supervisor_usuario_id)

    def test_bulk_save_rejects_duplicate_supervisor_without_partial_changes(self):
        response = self.client.post("/veiculos/equipes", data={
            "veiculo_ids": [str(self.veiculos[0].id), str(self.veiculos[1].id)],
            f"equipe_id_{self.veiculos[0].id}": str(self.norte.id),
            f"equipe_id_{self.veiculos[1].id}": str(self.sul.id),
            f"supervisor_id_{self.veiculos[0].id}": str(self.supervisor.id),
            f"supervisor_id_{self.veiculos[1].id}": str(self.supervisor.id),
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.veiculos[0].supervisor_usuario_id)
        self.assertIsNone(self.veiculos[1].supervisor_usuario_id)

    def test_bulk_save_requires_team_for_supervisor(self):
        response = self.client.post("/veiculos/equipes", data={
            "veiculo_ids": str(self.veiculos[0].id),
            f"equipe_id_{self.veiculos[0].id}": "",
            f"supervisor_id_{self.veiculos[0].id}": str(self.supervisor.id),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.veiculos[0].equipe_id, self.norte.id)
        self.assertIsNone(self.veiculos[0].supervisor_usuario_id)

    def test_bulk_save_preserves_legacy_responsible_name_when_unchanged(self):
        veiculo = self.veiculos[0]
        veiculo.responsavel = "Piloto Antigo"
        db.session.commit()
        response = self.client.post("/veiculos/equipes", data={
            "veiculo_ids": str(veiculo.id),
            f"equipe_id_{veiculo.id}": str(self.norte.id),
            f"supervisor_id_{veiculo.id}": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(veiculo.responsavel, "Piloto Antigo")

    def test_assignment_rejects_other_municipality_and_second_vehicle(self):
        veiculo = self.veiculos[1]
        _, _, errors = validate_veiculo_form(self._vehicle_form(veiculo, self.supervisor.id, self.outra.id),
                                             equipes=list_equipes_choices(), supervisores=list_supervisores_choices(),
                                             existing_veiculo=veiculo)
        self.assertIn("supervisor_id", errors)
        veiculo.responsavel = f"sup_veiculos:{self.supervisor.id}"
        db.session.commit()
        _, _, errors = validate_veiculo_form(self._vehicle_form(self.veiculos[0], self.supervisor.id),
                                             equipes=list_equipes_choices(), supervisores=list_supervisores_choices(),
                                             existing_veiculo=self.veiculos[0])
        self.assertIn("supervisor_id", errors)

    def test_assigned_vehicle_appears_first_across_regions_without_a_team_link(self):
        self.veiculos[1].responsavel = f"sup_veiculos:{self.supervisor.id}"
        db.session.commit()
        context = build_piloto_veiculos_context(self.supervisor)
        self.assertEqual([v.id for v in context["veiculos"]], [self.veiculos[1].id, self.veiculos[0].id])
        self.assertEqual(context["veiculos_supervisor_ids"], [self.veiculos[1].id])
        self.assertIsNone(get_supervisor_equipe(self.supervisor))
        checklist = checklists.build_piloto_checklist_context(self.supervisor, MultiDict())
        self.assertEqual(checklist["veiculo_padrao_id"], self.veiculos[1].id)
        self.assertEqual({d.id for d in checklist["drones_equipe"]}, {d.id for d in self.drones[:2]})

    def test_open_shift_page_separates_assigned_vehicle(self):
        self.veiculos[1].responsavel = f"sup_veiculos:{self.supervisor.id}"
        db.session.commit()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.supervisor.id)
        response = self.client.get("/piloto/veiculos?acao=abrir_turno")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Veículo sob sua responsabilidade", html)
        self.assertIn("Demais veículos das equipes", html)
        self.assertLess(html.index(self.veiculos[1].placa), html.index(self.veiculos[0].placa))

    @patch("app.modules.veiculos.service._salvar_upload_veiculo", return_value="painel.jpg")
    def test_turno_uses_supervisor_identity_and_vehicle_team(self, _upload):
        veiculo = self.veiculos[1]
        veiculo.responsavel = f"sup_veiculos:{self.supervisor.id}"
        db.session.commit()
        foto = FileStorage(stream=BytesIO(b"foto"), filename="painel.jpg")
        iniciar_turno_piloto(self.supervisor, veiculo.id, {"assinatura_b64": "assinatura"},
                             {"foto_painel": foto}, "/tmp")
        log = LogVeiculo.query.one()
        self.assertEqual(log.piloto_id, self.supervisor.piloto_id)
        self.assertEqual(log.equipe_id, self.sul.id)
        self.assertEqual(_operador_log_veiculo(log), "Supervisor")

        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.supervisor.id)
        response = self.client.get("/piloto/veiculos")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-km-max="1500.0"', html)
        self.assertIn("KM inicial do turno (primeiro abastecimento)", html)

    @patch.object(checklists, "_sincronizar_pendencias")
    def test_weekly_vehicle_and_drone_checklists_keep_supervisor_as_author(self, _notifications):
        form = MultiDict({"veiculo_id": str(self.veiculos[1].id), "drone_id": str(self.drones[1].id),
                          "assinatura_piloto": "assinatura", "nome_responsavel": "Supervisor"})
        checklists.save_piloto_checklist(self.supervisor, form)
        self.assertEqual(ChecklistSemanalVeiculo.query.one().piloto_id, self.supervisor.piloto_id)
        self.assertEqual(ChecklistSemanalDrone.query.one().piloto_id, self.supervisor.piloto_id)

    def test_access_stays_in_municipality_but_has_no_region_lock(self):
        query = build_equipes_query("sup_veiculos", "", "", "", "", "", "nome_asc", "SUL", self.supervisor)[0]
        self.assertEqual({e.id for e in query.all()}, {self.norte.id, self.sul.id})
        self.assertEqual(_veiculo_do_operacional_logado(self.veiculos[1].id, user=self.supervisor).id,
                         self.veiculos[1].id)
        with self.assertRaises(PermissionError):
            _veiculo_do_operacional_logado(self.veiculos[2].id, user=self.supervisor)

    def _login_as(self, user):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

    def _pilot_records(self, equipment_index=0):
        veiculo = self.veiculos[equipment_index]
        piloto = Pilotos(nome_piloto=f"Piloto {equipment_index}", prefeitura_id=veiculo.prefeitura_id)
        db.session.add(piloto)
        db.session.flush()
        identity = {"piloto_id": piloto.id, "equipe_id": veiculo.equipe_id,
                    "data_registro": datetime(2026, 8, 3, 8), "assinatura_piloto": "assinatura-original"}
        log = LogVeiculo(veiculo_id=veiculo.id, km_inicial=1000, km_final=1100,
                         check_diario=True, **identity)
        vehicle_check = ChecklistSemanalVeiculo(veiculo_id=veiculo.id, km_leitura=1000, **identity)
        drone_check = ChecklistSemanalDrone(drone_id=self.drones[equipment_index].id,
                                            nome_responsavel=piloto.nome_piloto, num_baterias=2,
                                            assinatura_piloto_responsavel="assinatura-original", **identity)
        db.session.add_all([log, vehicle_check, drone_check])
        db.session.flush()
        fuel = Abastecimento(log_veiculo_id=log.id, km_registro=1050, litros=10, valor_total=60,
                              tipo_abastecimento="Veiculo", foto_nf_path="nota.jpg",
                              data_hora=datetime(2026, 8, 3, 9))
        db.session.add(fuel)
        db.session.commit()
        return log, fuel, vehicle_check, drone_check

    def test_supervisor_can_correct_pilot_shift_from_list_and_vehicle_history(self):
        log, fuel, _, _ = self._pilot_records()
        self._login_as(self.supervisor)
        identity = (log.piloto_id, log.equipe_id, log.assinatura_piloto, log.data_registro)
        for url in ("/veiculos/logs", f"/veiculos/logs/veiculo/{log.veiculo_id}"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"/veiculos/logs/{log.id}/corrigir-km", response.get_data(as_text=True))
        response = self.client.post(f"/veiculos/logs/{log.id}/corrigir-km", data={
            "km_inicial": "1010", "km_final": "1150", f"abastecimento_{fuel.id}_km": "1070",
            f"abastecimento_{fuel.id}_litros": "12,5", f"abastecimento_{fuel.id}_valor": "75,50",
        })
        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        self.assertEqual((log.km_inicial, log.km_final, fuel.km_registro, fuel.litros, fuel.valor_total),
                         (1010, 1150, 1070, 12.5, 75.5))
        self.assertEqual(self.veiculos[0].km_atual, 1150)
        self.assertEqual((log.piloto_id, log.equipe_id, log.assinatura_piloto, log.data_registro), identity)
        self.assertEqual(self.client.post(f"/veiculos/logs/{log.id}/deletar").status_code, 403)
        self.assertIsNotNone(db.session.get(LogVeiculo, log.id))

    def test_supervisor_shift_correction_rejects_invalid_km_without_partial_save(self):
        log, fuel, _, _ = self._pilot_records()
        self._login_as(self.supervisor)
        response = self.client.post(f"/veiculos/logs/{log.id}/corrigir-km", data={
            "km_inicial": "1010", "km_final": "1020", f"abastecimento_{fuel.id}_km": "1070",
        })
        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        self.assertEqual((log.km_inicial, log.km_final, fuel.km_registro), (1000, 1100, 1050))

    def test_supervisor_cannot_correct_shift_outside_municipality_or_without_one(self):
        local, _, _, _ = self._pilot_records()
        foreign, _, _, _ = self._pilot_records(2)
        self._login_as(self.supervisor)
        for prefeitura_id, log in ((1, foreign), (None, local)):
            with self.subTest(prefeitura_id=prefeitura_id):
                self.supervisor.prefeitura_id = prefeitura_id
                db.session.commit()
                self.assertEqual(self.client.post(f"/veiculos/logs/{log.id}/corrigir-km",
                                                 data={"km_inicial": "1", "km_final": "2"}).status_code, 403)
                self.assertEqual(log.km_inicial, 1000)

    def test_supervisor_edits_vehicle_checklist_preserving_original_identity(self):
        _, _, checklist, _ = self._pilot_records()
        self._login_as(self.supervisor)
        detail_url = f"/admin/checklists/semanais/piloto/{checklist.piloto_id}/2026-08-03"
        edit_url = f"/admin/checklists/veiculo/{checklist.id}/editar"
        self.assertIn(edit_url, self.client.get(detail_url).get_data(as_text=True))
        self.assertEqual(self.client.get(edit_url).status_code, 200)
        identity = (checklist.piloto_id, checklist.equipe_id, checklist.data_registro, checklist.assinatura_piloto)
        response = self.client.post(edit_url, data={
            "km_leitura": "1020,5", "freio_mao": "0", "condicao_embreagem_freios": "Precisa de ajuste.",
            "piloto_id": "999", "equipe_id": "999", "veiculo_id": str(self.veiculos[2].id),
            "data_registro": "2026-09-25", "assinatura_piloto": "alterada",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith(detail_url))
        db.session.expire_all()
        self.assertEqual(ChecklistSemanalVeiculo.query.count(), 1)
        self.assertEqual(checklist.km_leitura, 1020.5)
        self.assertIs(checklist.freio_mao, False)
        self.assertEqual(checklist.condicao_embreagem_freios, "Precisa de ajuste.")
        self.assertIs(checklist.farois_funcionando, True)
        self.assertEqual(checklist.veiculo_id, self.veiculos[0].id)
        self.assertEqual((checklist.piloto_id, checklist.equipe_id, checklist.data_registro,
                          checklist.assinatura_piloto), identity)
        alert = Notificacao.query.one()
        self.assertIn("2026-08-03", alert.link)
        self.assertIn("Freio de mão", alert.mensagem)
        self.assertIsNone(alert.apagada_em)
        self.client.post(edit_url, data={"freio_mao": "1", "condicao_embreagem_freios": "Texto antigo"})
        db.session.expire_all()
        self.assertIsNone(checklist.condicao_embreagem_freios)
        self.assertIsNotNone(alert.apagada_em)

    def test_supervisor_edits_drone_checklist_and_battery_counts(self):
        _, _, _, checklist = self._pilot_records()
        self._login_as(self.supervisor)
        url = f"/admin/checklists/drone/{checklist.id}/editar"
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, data={
            "num_baterias": "0", "num_baterias_wb": "3", "helices_status": "0",
            "condicao_helices": "Hélice trincada.", "observacoes_equipamento": "Conferido.",
            "nome_responsavel": "Outro nome", "assinatura_piloto_responsavel": "alterada",
        })
        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        self.assertEqual((checklist.num_baterias, checklist.num_baterias_wb), (0, 3))
        self.assertIs(checklist.helices_status, False)
        self.assertEqual(checklist.condicao_helices, "Hélice trincada.")
        self.assertEqual(checklist.observacoes_equipamento, "Conferido.")
        self.assertEqual(checklist.nome_responsavel, "Piloto 0")
        self.assertEqual(checklist.assinatura_piloto_responsavel, "assinatura-original")
        self.assertEqual(ChecklistSemanalDrone.query.count(), 1)

    def test_monitoring_drone_correction_keeps_tank_not_applicable(self):
        _, _, _, checklist = self._pilot_records()
        checklist.drone.categoria = "Monitoramento"
        checklist.tanque = None
        db.session.commit()
        self._login_as(self.supervisor)
        url = f"/admin/checklists/drone/{checklist.id}/editar"
        self.assertNotIn('name="tanque"', self.client.get(url).get_data(as_text=True))
        self.assertEqual(self.client.post(url, data={"tanque": "0"}).status_code, 302)
        self.assertIsNone(checklist.tanque)
        self.assertEqual(Notificacao.query.count(), 0)
        normalized = admin_checklists.normalize_checklist_drone_admin(checklist)
        self.assertEqual((normalized["itens_total"], normalized["falhas"]), (7, 0))

    def test_checklist_correction_rejects_invalid_values_without_partial_save(self):
        _, _, vehicle, drone = self._pilot_records()
        self._login_as(self.supervisor)
        for tipo, checklist, data in (
            ("veiculo", vehicle, {"km_leitura": "nan", "freio_mao": "0"}),
            ("veiculo", vehicle, {"km_leitura": "-1"}),
            ("veiculo", vehicle, {"freio_mao": "desconhecido"}),
            ("drone", drone, {"num_baterias": "1.5", "helices_status": "0"}),
            ("drone", drone, {"num_baterias_wb": "-1"}),
        ):
            with self.subTest(data=data):
                response = self.client.post(f"/admin/checklists/{tipo}/{checklist.id}/editar", data=data)
                self.assertEqual(response.status_code, 400)
                db.session.expire_all()
                self.assertEqual(vehicle.km_leitura, 1000)
                self.assertIs(vehicle.freio_mao, True)
                self.assertIs(drone.helices_status, True)
                self.assertEqual(drone.num_baterias, 2)

    def test_checklist_history_and_corrections_respect_municipality(self):
        _, _, local, local_drone = self._pilot_records()
        _, _, foreign, foreign_drone = self._pilot_records(2)
        self._login_as(self.supervisor)
        html = self.client.get("/admin/checklists/semanais").get_data(as_text=True)
        self.assertIn("Piloto 0", html)
        self.assertNotIn("Piloto 2", html)
        for prefeitura_id, vehicle, drone in ((1, foreign, foreign_drone), (None, local, local_drone)):
            with self.subTest(prefeitura_id=prefeitura_id):
                self.supervisor.prefeitura_id = prefeitura_id
                db.session.commit()
                for detail_url in (
                    f"/admin/checklists/semanais/piloto/{vehicle.piloto_id}/2026-08-03",
                    f"/admin/checklists/semanais/{vehicle.piloto_id}/2026-08-03",
                    f"/admin/checklists/semanais/equipe/{vehicle.equipe_id}/2026-08-03",
                ):
                    self.assertEqual(self.client.get(detail_url).status_code, 404)
                for tipo, checklist in (("veiculo", vehicle), ("drone", drone)):
                    url = f"/admin/checklists/{tipo}/{checklist.id}/editar"
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, data={"km_leitura": "500"}).status_code, 403)
                self.assertEqual(vehicle.km_leitura, 1000)
        html = self.client.get("/admin/checklists/semanais").get_data(as_text=True)
        self.assertNotIn("Piloto 0", html)
        self.assertNotIn("Piloto 2", html)

    def test_pilot_and_viewer_cannot_use_supervisor_corrections(self):
        log, _, checklist, _ = self._pilot_records()
        for role in ("piloto", "visualizar", "equipe_oceano"):
            with self.subTest(role=role):
                self.supervisor.tipo_usuario = role
                db.session.commit()
                self._login_as(self.supervisor)
                url = f"/admin/checklists/veiculo/{checklist.id}/editar"
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, data={"km_leitura": "1"}).status_code, 403)
                with self.assertRaises(PermissionError):
                    admin_checklists.update_admin_checklist(self.supervisor, "veiculo", checklist.id, {})
                self.assertEqual(self.client.post(f"/veiculos/logs/{log.id}/corrigir-km").status_code, 403)

    def test_admin_can_correct_checklists_from_other_municipalities(self):
        _, _, checklist, _ = self._pilot_records(2)
        url = f"/admin/checklists/veiculo/{checklist.id}/editar"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, data={"km_leitura": "1010"}).status_code, 302)
        self.assertEqual(checklist.km_leitura, 1010)
