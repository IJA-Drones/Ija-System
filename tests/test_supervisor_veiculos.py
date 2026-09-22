import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Blueprint, Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import ChecklistSemanalDrone, ChecklistSemanalVeiculo, Drones, Equipe, Prefeitura, Usuario, Veiculos
from app.modules.equipes.service import build_equipes_query
from app.modules.equipes.routes import register_routes as register_equipes_routes
from app.modules.uvis_equipes.routes import register_routes as register_uvis_equipes_routes
from app.shared.access import is_admin_global_user
from app.modules.piloto_checklists import service as checklists
from app.modules.usuarios.routes import register_routes
from app.modules.usuarios.service import build_admin_users_query
from app.modules.veiculos.service import build_piloto_veiculos_context, _veiculo_do_operacional_logado
from app.shared.vehicle_supervisor import get_supervisor_equipe


class SupervisorVeiculosTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / "app/templates"))
        self.app.config.update(
            TESTING=True, SECRET_KEY="test-key", SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        manager = LoginManager(self.app)
        manager.user_loader(lambda user_id: db.session.get(Usuario, int(user_id)))
        bp = Blueprint("main", __name__)
        register_routes(bp)
        register_equipes_routes(bp)
        register_uvis_equipes_routes(bp)
        self.app.jinja_env.globals["is_admin_global_user"] = is_admin_global_user
        bp.add_url_rule("/", "dashboard", lambda: "ok")
        self.app.register_blueprint(bp)
        self.app.jinja_loader = ChoiceLoader([
            DictLoader({"base.html": "{% block content %}{% endblock %}{% block scripts %}{% endblock %}"}),
            self.app.jinja_loader,
        ])
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.assertEqual(db.engine.url.database, ":memory:")
        db.create_all()
        db.session.add_all([
            Prefeitura(id=1, nome="Cidade Um", slug="um"),
            Prefeitura(id=2, nome="Cidade Dois", slug="dois"),
        ])
        self.norte = Equipe(nome_equipe="Equipe Norte", regiao="NORTE", prefeitura_id=1, ativa=True)
        self.sul = Equipe(nome_equipe="Equipe Sul", regiao="SUL", prefeitura_id=1, ativa=True)
        self.outra = Equipe(nome_equipe="Outra cidade", regiao="OESTE", prefeitura_id=2, ativa=True)
        self.inativa = Equipe(nome_equipe="Inativa", regiao="LESTE", prefeitura_id=1, ativa=False)
        db.session.add_all([self.norte, self.sul, self.outra, self.inativa])
        db.session.flush()
        self.veiculos = []
        self.drones = []
        for i, equipe in enumerate([self.norte, self.sul, self.outra], 1):
            # Legacy equipment has a team but no direct municipality link.
            prefeitura_id = None if i == 1 else equipe.prefeitura_id
            veiculo = Veiculos(modelo="Fiorino", renomacao=f"Carro {i}", placa=f"ABC{i}D23",
                               equipe_id=equipe.id, prefeitura_id=prefeitura_id, status="Ativo", km_atual=1000,
                               frota="PROPRIA", operacao="PMSP")
            drone = Drones(modelo="DJI", renomacao=f"Drone {i}", registro_anac=f"ANAC-{i}",
                           registro_anatel=f"ANATEL-{i}", equipe_id=equipe.id,
                           prefeitura_id=prefeitura_id, status="Ativo", pmd_kg=25)
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

    def _edit(self, equipe_id, **overrides):
        data = dict(nome_uvis="Supervisor", login="supervisor", tipo_usuario="sup_veiculos",
                    prefeitura_id="1", regiao="SUL", supervisor_equipe_id=str(equipe_id))
        data.update(overrides)
        return self.client.post(f"/admin/usuarios/{self.supervisor.id}/editar", data=data)

    def _edit_team(self, team, supervisor_ids=None, **overrides):
        data = dict(nome_equipe=team.nome_equipe, regiao=team.regiao, ativa="on", supervisores_presentes="1")
        if supervisor_ids is not None:
            data["supervisor_ids"] = [str(value) for value in supervisor_ids]
        data.update(overrides)
        return self.client.post(f"/equipes/{team.id}/editar", data=data)

    def test_user_creation_has_no_team_link_even_with_old_fields(self):
        response = self.client.post("/admin/usuarios/novo", data={
            "nome": "Novo Supervisor", "login": "novo.supervisor", "tipo_usuario": "sup_veiculos",
            "prefeitura_id": "1", "regiao": "SUL", "supervisor_equipe_id": str(self.norte.id),
            "codigo_setor": str(self.norte.id), "senha": "SenhaDeTeste123!", "senha2": "SenhaDeTeste123!",
        })
        self.assertEqual(response.status_code, 302)
        novo = Usuario.query.filter_by(login="novo.supervisor").one()
        self.assertIsNone(novo.codigo_setor)
        self.assertIn(novo, build_admin_users_query("", "sup_veiculos").all())

    def test_user_forms_have_no_team_field_and_edit_preserves_team_link(self):
        for url in ("/admin/usuarios/novo", f"/admin/usuarios/{self.supervisor.id}/editar"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('name="supervisor_equipe_id"', response.get_data(as_text=True))
            self.assertNotIn("Equipe principal do supervisor", response.get_data(as_text=True))
        self.assertEqual(self._edit(self.sul.id, codigo_setor=str(self.sul.id)).status_code, 302)
        self.assertEqual(get_supervisor_equipe(self.supervisor).id, self.norte.id)

    def test_team_forms_show_only_supervisors_and_preserve_current_selection(self):
        for url in ("/equipes/cadastrar", f"/equipes/{self.norte.id}/editar"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn("Supervisor de veículos (opcional)", html)
            self.assertIn(f'id="supervisor-{self.supervisor.id}"', html)
            self.assertNotIn(f'id="supervisor-{self.admin.id}"', html)
        self.assertIn('value="' + str(self.supervisor.id) + '"\n        checked', html)

    def test_create_team_links_supervisor_without_a_pilot_and_inherits_municipality(self):
        response = self.client.post("/equipes/cadastrar", data={
            "nome_equipe": "Equipe do supervisor", "regiao": "NORTE",
            "supervisor_ids": str(self.supervisor.id), "supervisores_presentes": "1",
        })
        self.assertEqual(response.status_code, 302)
        team = Equipe.query.filter_by(nome_equipe="Equipe do supervisor").one()
        self.assertEqual(team.prefeitura_id, self.supervisor.prefeitura_id)
        self.assertEqual(team.membros, [])
        self.assertEqual(get_supervisor_equipe(self.supervisor).id, team.id)
        self.assertEqual(self.supervisor.regiao, "SUL")
        response = self.client.get("/equipes")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Supervisor de veículos: Supervisor", response.get_data(as_text=True))

    def test_team_editor_can_move_and_remove_supervisor(self):
        self.assertEqual(self._edit_team(self.sul, [self.supervisor.id]).status_code, 302)
        self.assertEqual(get_supervisor_equipe(self.supervisor).id, self.sul.id)
        self.assertEqual(self._edit_team(self.sul, []).status_code, 302)
        self.assertIsNone(self.supervisor.codigo_setor)

    def test_team_editor_rejects_invalid_users_and_other_user_types(self):
        for value in ("invalid", "999999", "99999999999999999999", self.admin.id):
            with self.subTest(value=value):
                response = self._edit_team(self.sul, [value])
                self.assertEqual(response.status_code, 200)
                self.assertIn("text-danger small mt-1", response.get_data(as_text=True))
                db.session.refresh(self.supervisor)
                self.assertEqual(self.supervisor.codigo_setor, str(self.norte.id))

    def test_supervisor_cannot_be_linked_to_another_municipality(self):
        response = self._edit_team(self.outra, [self.supervisor.id])
        self.assertEqual(response.status_code, 200)
        self.assertIn("mesma prefeitura", response.get_data(as_text=True))
        self.assertEqual(get_supervisor_equipe(self.supervisor).id, self.norte.id)

    def test_other_team_validation_errors_preserve_link(self):
        response = self._edit_team(self.sul, [self.supervisor.id], nome_equipe="")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_supervisor_equipe(self.supervisor).id, self.norte.id)
        self.assertIn('value="' + str(self.supervisor.id) + '"\n        checked', response.get_data(as_text=True))

    def test_older_team_forms_do_not_erase_supervisor_link(self):
        response = self.client.post(f"/equipes/{self.norte.id}/editar", data={
            "nome_equipe": self.norte.nome_equipe, "regiao": "NORTE", "ativa": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_supervisor_equipe(self.supervisor).id, self.norte.id)

    def test_municipality_admin_cannot_select_supervisor_from_another_municipality(self):
        self.admin.tipo_usuario = "prefeitura_admin"
        self.admin.prefeitura_id = 2
        db.session.commit()
        response = self.client.get("/equipes/cadastrar")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(f'id="supervisor-{self.supervisor.id}"', response.get_data(as_text=True))
        response = self._edit_team(self.outra, [self.supervisor.id])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_supervisor_equipe(self.supervisor).id, self.norte.id)

    def test_team_creation_rejects_other_roles_without_creating_team(self):
        response = self.client.post("/equipes/cadastrar", data={
            "nome_equipe": "Equipe inválida", "regiao": "NORTE", "supervisor_ids": str(self.admin.id),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(Equipe.query.filter_by(nome_equipe="Equipe inválida").first())
        self.assertIsNone(self.admin.codigo_setor)

    def test_deleting_team_clears_supervisor_link(self):
        team = Equipe(nome_equipe="Temporária", regiao="NORTE", prefeitura_id=1, ativa=True)
        db.session.add(team)
        db.session.flush()
        self.supervisor.codigo_setor = str(team.id)
        db.session.commit()
        response = self.client.post(f"/equipes/{team.id}/deletar")
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.supervisor.codigo_setor)

    def test_regular_admin_fields_do_not_create_supervisor_link(self):
        self.assertEqual(self._edit(self.norte.id, tipo_usuario="operario").status_code, 302)
        self.assertIsNone(self.supervisor.codigo_setor)

    def test_supervisor_cannot_edit_own_administrative_account(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.supervisor.id)
        self.assertEqual(self._edit(self.sul.id).status_code, 403)
        self.assertEqual(self.supervisor.codigo_setor, str(self.norte.id))

    def test_supervisor_cannot_access_or_manage_uvis_teams(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.supervisor.id)
        for role in ("sup_veiculos", "sup_veiculo"):
            self.supervisor.tipo_usuario = role
            for method, path in (
                ("GET", "/admin/uvis/equipes"),
                ("GET", "/admin/uvis/1/equipes/Equipe"),
                ("POST", "/admin/uvis/1/acesso-operacional"),
                ("GET", "/uvis/equipes"),
                ("GET", "/uvis/equipes/nova"),
                ("POST", "/uvis/equipes/nova"),
                ("GET", "/uvis/equipes/Equipe"),
                ("POST", "/uvis/equipes/Equipe/credenciais"),
                ("POST", "/uvis/equipes/Equipe/adicionar"),
                ("POST", "/uvis/equipe-membro/1/editar"),
                ("POST", "/uvis/equipe-membro/1/deletar"),
                ("POST", "/uvis/acesso-operacional"),
                ("POST", "/solicitacao/1/atribuir-equipe-uvis"),
            ):
                with self.subTest(role=role, method=method, path=path):
                    self.assertEqual(self.client.open(path, method=method).status_code, 403)
        self.assertEqual(get_supervisor_equipe(self.supervisor).id, self.norte.id)

    def test_equipes_are_not_locked_to_supervisor_region(self):
        def query(tipo, regiao=""):
            return build_equipes_query(tipo, regiao, "", "", "", "", "nome_asc", "SUL", self.supervisor)[0]
        self.assertEqual({e.id for e in query("sup_veiculos").all()}, {self.norte.id, self.sul.id, self.inativa.id})
        self.assertEqual([e.id for e in query("sup_veiculos", "NORTE").all()], [self.norte.id])
        self.assertEqual([e.id for e in query("regional").all()], [self.sul.id])

    def test_operational_assets_cover_all_regions_and_prioritize_linked_team(self):
        vehicles = build_piloto_veiculos_context(self.supervisor)["veiculos"]
        self.assertEqual([v.id for v in vehicles], [v.id for v in self.veiculos[:2]])
        context = checklists.build_piloto_checklist_context(self.supervisor, MultiDict())
        self.assertEqual(context["equipe"].id, self.norte.id)
        self.assertEqual(context["veiculo_padrao_id"], self.veiculos[0].id)
        self.assertEqual(context["drone_padrao_id"], self.drones[0].id)
        self.assertEqual({d.id for d in context["drones_equipe"]}, {d.id for d in self.drones[:2]})
        self.assertEqual(_veiculo_do_operacional_logado(self.veiculos[1].id, user=self.supervisor).id, self.veiculos[1].id)
        with self.assertRaises(PermissionError):
            _veiculo_do_operacional_logado(self.veiculos[2].id, user=self.supervisor)

    def test_supervisor_without_municipality_can_use_all_teams_and_assets(self):
        self.supervisor.prefeitura_id = None
        self.assertEqual(len(build_piloto_veiculos_context(self.supervisor)["veiculos"]), 3)
        context = checklists.build_piloto_checklist_context(self.supervisor, MultiDict())
        self.assertEqual(len(context["drones_equipe"]), 3)

    @patch.object(checklists, "_sincronizar_pendencias")
    def test_checklists_save_other_region_team_and_update_without_duplicates(self, _notifications):
        form = MultiDict({"veiculo_id": str(self.veiculos[1].id), "drone_id": str(self.drones[1].id),
                          "assinatura_piloto": "assinatura", "nome_responsavel": "Supervisor"})
        checklists.save_piloto_checklist(self.supervisor, form)
        checklists.save_piloto_checklist(self.supervisor, form)
        vehicle = ChecklistSemanalVeiculo.query.one()
        drone = ChecklistSemanalDrone.query.one()
        self.assertEqual(vehicle.equipe_id, self.sul.id)
        self.assertEqual(drone.equipe_id, self.sul.id)
        self.assertIsNone(drone.piloto_id)

    def test_forged_checklist_for_another_municipality_is_rejected(self):
        form = MultiDict({"drone_id": str(self.drones[2].id), "assinatura_piloto": "assinatura"})
        with self.assertRaises(checklists.PilotoChecklistError):
            checklists.save_piloto_checklist(self.supervisor, form)
        self.assertEqual(ChecklistSemanalDrone.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
