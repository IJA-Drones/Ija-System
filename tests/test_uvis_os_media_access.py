import json
import unittest
from datetime import date, time

from flask import Flask

from app.extensions import db
from app.models import Equipe, OrdemServico, Prefeitura, Solicitacao, Usuario
from app.modules.dashboard.service import build_uvis_os_form_context
from app.modules.piloto_os.service import (
    PilotoOsError,
    get_os_complementary_image_path_for_user,
    get_os_principal_image_path_for_user,
    get_os_video_path_for_user,
)


class UvisOsMediaAccessTests(unittest.TestCase):
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

    def test_linked_equipe_uvis_can_resolve_owner_os_media_paths(self):
        self.assertEqual(
            get_os_principal_image_path_for_user(self.equipe_uvis, self.solicitacao.id),
            "webdav://os/1/principal.jpg",
        )

    def test_other_uvis_cannot_resolve_os_media_paths(self):
        with self.assertRaises(PilotoOsError):
            get_os_principal_image_path_for_user(self.outra_uvis, self.solicitacao.id)

    def test_uvis_visual_form_context_includes_saved_media(self):
        context = build_uvis_os_form_context(self.uvis, self.solicitacao.id)

        self.assertEqual(context["imagem_principal_path"], "webdav://os/1/principal.jpg")
        self.assertEqual(context["outras_imagens_paths"], ["webdav://os/1/extra-1.jpg"])
        self.assertEqual(context["video_path"], "webdav://os/1/video.mp4")
        self.assertEqual(context["total_midias_formulario"], 3)


if __name__ == "__main__":
    unittest.main()
