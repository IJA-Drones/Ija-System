from werkzeug.exceptions import NotFound
import json
import unittest
from datetime import date, time
from unittest.mock import patch

from flask import Blueprint, Flask, g
from flask_login import LoginManager
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Equipe, EquipePiloto, OrdemServico, Pilotos, Prefeitura, Solicitacao, Usuario
from app.modules.dashboard.service import build_uvis_os_form_context
from app.modules.piloto_os import routes as media_routes
from app.modules.piloto_os.service import (
    STATUS_OS_APROVADAS_COM_ACENTO,
    get_os_complementary_image_path_for_user,
    get_os_principal_image_path_for_user,
    get_os_video_path_for_user,
    salvar_piloto_os_form,
)
from app.modules.relatorios.service import (
    build_relatorio_coleta_imagens_export_data,
    registrar_visualizacao_coleta_imagens,
)


class UvisOsMediaAccessTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SERVER_NAME="localhost",
            SECRET_KEY="isolated-uvis-media-tests",
        )
        self.app.add_url_rule(
            "/uvis/os/<int:os_id>",
            endpoint="main.uvis_os_formulario_view",
            view_func=lambda os_id: "",
        )
        manager = LoginManager(self.app)
        manager.user_loader(lambda uid: db.session.get(Usuario, int(uid)))

        @self.app.before_request
        def clear_cached_user():
            g.pop("_login_user", None)

        bp = Blueprint("main", __name__)
        media_routes.register_routes(bp)
        self.app.register_blueprint(bp)
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        prefeitura = Prefeitura(id=1, nome="Prefeitura Teste", slug="prefeitura-teste")
        self.uvis = Usuario(
            nome_uvis="UVIS Teste",
            regiao="OESTE",
            login="uvis_teste",
            senha_hash="hash",
            tipo_usuario="uvis",
            prefeitura_id=1,
        )
        self.outra_uvis = Usuario(
            nome_uvis="Outra UVIS",
            regiao="LESTE",
            login="outra_uvis",
            senha_hash="hash",
            tipo_usuario="uvis",
            prefeitura_id=1,
        )
        db.session.add_all([prefeitura, self.uvis, self.outra_uvis])
        db.session.flush()

        self.equipe_uvis = Usuario(
            nome_uvis="Equipe Operacional",
            regiao="OESTE",
            login="equipe_uvis_teste",
            senha_hash="hash",
            tipo_usuario="equipe_uvis",
            equipe_uvis_uvis_usuario_id=self.uvis.id,
            prefeitura_id=1,
        )
        self.equipe = Equipe(nome_equipe="PLOA 01", regiao="OESTE", ativa=True, prefeitura_id=1)
        db.session.add_all([self.equipe_uvis, self.equipe])
        db.session.commit()

        self.piloto = Pilotos(nome_piloto="Piloto Oficial", regiao="OESTE", prefeitura_id=1)
        self.auxiliar = Pilotos(nome_piloto="Auxiliar Oficial", regiao="OESTE", prefeitura_id=1)
        db.session.add_all([self.piloto, self.auxiliar])
        db.session.flush()
        db.session.add_all([
            EquipePiloto(equipe_id=self.equipe.id, piloto_id=self.piloto.id, papel="piloto"),
            EquipePiloto(equipe_id=self.equipe.id, piloto_id=self.auxiliar.id, papel="auxiliar"),
        ])
        db.session.commit()

        self.solicitacao = Solicitacao(
            data_agendamento=date(2026, 7, 1),
            hora_agendamento=time(9, 0),
            foco="Terreno com Inserviveis",
            cep="05335120",
            logradouro="Rua Teste",
            bairro="Jaguare",
            cidade="Sao Paulo",
            uf="SP",
            status="CONCLU\u00cdDO",
            usuario_id=self.uvis.id,
            equipe_id=self.equipe.id,
            prefeitura_id=1,
        )
        db.session.add(self.solicitacao)
        db.session.commit()

        self.ordem = OrdemServico(
            solicitacao_id=self.solicitacao.id,
            equipe_id=self.equipe.id,
            imagem_principal="webdav://os/1/principal.jpg",
            outras_imagens=json.dumps(["webdav://os/1/extra-1.jpg"]),
            video="webdav://os/1/video.mp4",
        )
        db.session.add(self.ordem)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_uvis_owner_can_resolve_os_media_paths(self):
        self.assertEqual(
            get_os_principal_image_path_for_user(self.uvis, self.solicitacao.id),
            "webdav://os/1/principal.jpg",
        )
        self.assertEqual(
            get_os_complementary_image_path_for_user(self.uvis, self.solicitacao.id, 1),
            "webdav://os/1/extra-1.jpg",
        )
        self.assertEqual(
            get_os_video_path_for_user(self.uvis, self.solicitacao.id),
            "webdav://os/1/video.mp4",
        )

    def media_client(self, user):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return client

    def assert_media_responses(self, user, expected):
        client = self.media_client(user)
        for suffix, path in (
            ("imagem-principal", "webdav://os/1/principal.jpg"),
            ("imagem-complementar/1", "webdav://os/1/extra-1.jpg"),
            ("video", "webdav://os/1/video.mp4"),
        ):
            with self.subTest(user=user.tipo_usuario, media=suffix), patch.object(
                media_routes, "_send_os_media", return_value="media-test"
            ) as storage:
                response = client.get(f"/os/{self.solicitacao.id}/{suffix}")
                self.assertEqual(response.status_code, expected)
                if expected == 200:
                    self.assertEqual(response.data, b"media-test")
                    self.assertEqual(storage.call_args.args[0], path)
                else:
                    storage.assert_not_called()

    def test_owner_and_linked_team_can_read_media_while_approved_or_completed(self):
        for status in (*STATUS_OS_APROVADAS_COM_ACENTO, "CONCLUIDO", "CONCLUÍDO"):
            self.solicitacao.status = status
            db.session.commit()
            with self.subTest(status=status):
                self.assert_media_responses(self.uvis, 200)
                self.assert_media_responses(self.equipe_uvis, 200)

    def test_pending_cancelled_or_unassigned_approved_os_remains_blocked(self):
        for status in ("PENDENTE", "CANCELADO", "REJEITADO", "APROVADO"):
            self.solicitacao.status = status
            if status == "APROVADO":
                self.solicitacao.equipe_id = None
            db.session.commit()
            with self.subTest(status=status):
                self.assert_media_responses(self.uvis, 403)
                self.assert_media_responses(self.equipe_uvis, 403)

    def test_approved_media_stays_private_to_owner_and_municipality(self):
        self.solicitacao.status = "APROVADO"
        db.session.commit()
        self.assert_media_responses(self.outra_uvis, 404)
        self.equipe_uvis.equipe_uvis_uvis_usuario_id = self.outra_uvis.id
        db.session.commit()
        self.assert_media_responses(self.equipe_uvis, 404)
        db.session.add(Prefeitura(id=2, nome="Outra prefeitura", slug="outra-prefeitura"))
        self.uvis.prefeitura_id = 2
        self.equipe_uvis.prefeitura_id = 2
        self.equipe_uvis.equipe_uvis_uvis_usuario_id = self.uvis.id
        db.session.commit()
        self.assert_media_responses(self.uvis, 404)
        self.assert_media_responses(self.equipe_uvis, 404)

    def test_approved_os_without_media_returns_not_found(self):
        self.solicitacao.status = "APROVADO"
        self.ordem.imagem_principal = None
        self.ordem.outras_imagens = None
        self.ordem.video = None
        db.session.commit()
        self.assert_media_responses(self.uvis, 404)

    def test_anonymous_cannot_read_media(self):
        with patch.object(media_routes, "_send_os_media") as storage:
            response = self.app.test_client().get(f"/os/{self.solicitacao.id}/imagem-principal")
            self.assertEqual(response.status_code, 401)
            storage.assert_not_called()

    def test_linked_equipe_uvis_can_resolve_owner_os_media_paths(self):
        self.assertEqual(
            get_os_principal_image_path_for_user(self.equipe_uvis, self.solicitacao.id),
            "webdav://os/1/principal.jpg",
        )

    def test_other_uvis_cannot_resolve_os_media_paths(self):
        with self.assertRaises(NotFound):
            get_os_principal_image_path_for_user(self.outra_uvis, self.solicitacao.id)

    def test_uvis_visual_form_context_includes_saved_media(self):
        context = build_uvis_os_form_context(self.uvis, self.solicitacao.id)

        self.assertEqual(context["imagem_principal_path"], "webdav://os/1/principal.jpg")
        self.assertEqual(context["outras_imagens_paths"], ["webdav://os/1/extra-1.jpg"])
        self.assertEqual(context["video_path"], "webdav://os/1/video.mp4")
        self.assertEqual(context["total_midias_formulario"], 3)

    def test_uvis_can_register_media_report_visualization(self):
        registrar_visualizacao_coleta_imagens(self.uvis, self.solicitacao.id)

        db.session.refresh(self.ordem)
        self.assertTrue(self.ordem.uvis_visualizado)
        self.assertIsNotNone(self.ordem.uvis_visualizado_em)
        self.assertEqual(self.ordem.uvis_visualizado_por_id, self.uvis.id)

    def test_other_uvis_cannot_register_media_report_visualization(self):
        with self.assertRaises(ValueError):
            registrar_visualizacao_coleta_imagens(self.outra_uvis, self.solicitacao.id)

        db.session.refresh(self.ordem)
        self.assertFalse(self.ordem.uvis_visualizado)

    def test_media_report_filters_by_uvis_visualization_status(self):
        pendentes = build_relatorio_coleta_imagens_export_data(
            self.uvis,
            MultiDict({"ok_uvis": "pendente"}),
        )
        com_ok_antes = build_relatorio_coleta_imagens_export_data(
            self.uvis,
            MultiDict({"ok_uvis": "ok"}),
        )

        self.assertEqual(pendentes["total_levantamentos"], 1)
        self.assertEqual(com_ok_antes["total_levantamentos"], 0)

        registrar_visualizacao_coleta_imagens(self.uvis, self.solicitacao.id)

        com_ok_depois = build_relatorio_coleta_imagens_export_data(
            self.uvis,
            MultiDict({"ok_uvis": "ok"}),
        )
        pendentes_depois = build_relatorio_coleta_imagens_export_data(
            self.uvis,
            MultiDict({"ok_uvis": "pendente"}),
        )

        self.assertEqual(com_ok_depois["total_levantamentos"], 1)
        self.assertTrue(com_ok_depois["levantamentos"][0]["uvis_visualizado"])
        self.assertEqual(com_ok_depois["total_ok_uvis"], 1)
        self.assertEqual(pendentes_depois["total_levantamentos"], 0)

    def test_piloto_form_ignores_posted_pilot_and_auxiliary_names(self):
        usuario_piloto = Usuario(
            nome_uvis="Usuario Piloto",
            login="usuario_piloto",
            senha_hash="hash",
            tipo_usuario="piloto",
            piloto_id=self.piloto.id,
            prefeitura_id=1,
        )
        db.session.add(usuario_piloto)
        self.solicitacao.status = "APROVADO"
        db.session.commit()

        salvar_piloto_os_form(
            usuario_piloto,
            self.solicitacao.id,
            MultiDict({
                "piloto": "Nome adulterado",
                "auxiliar": "Auxiliar adulterado",
                "respondido_por": "Usuario Piloto",
                "data_aplicacao": "2026-07-01",
                "hora_inicio_aplicacao": "09:00",
                "hora_termino_aplicacao": "10:00",
            }),
            MultiDict(),
            self.app.root_path,
        )

        db.session.refresh(self.ordem)
        self.assertEqual(self.ordem.piloto, "Piloto Oficial")
        self.assertEqual(self.ordem.auxiliar, "Auxiliar Oficial")


if __name__ == "__main__":
    unittest.main()
