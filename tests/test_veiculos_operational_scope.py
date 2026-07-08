import unittest
import os
from io import BytesIO
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from flask import Flask
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Abastecimento, Equipe, LogVeiculo, Prefeitura, Veiculos
from app.modules.veiculos import service as veiculos_service
from app.modules.veiculos.service import (
    build_veiculo_media_skybox_path,
    build_piloto_veiculos_context,
    encerrar_turno_piloto,
    registrar_abastecimento_turno_piloto,
    update_veiculo,
)


class VeiculosOperationalScopeTests(unittest.TestCase):
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
        self.equipe = Equipe(nome_equipe="PLOA 23", regiao="SUL", ativa=True, prefeitura_id=1)
        db.session.add_all([prefeitura, self.equipe])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _novo_veiculo(self, **overrides):
        data = {
            "tipo_equipamento": "veiculos",
            "status": "Ativo",
            "modelo": "FIORINO",
            "ano_fabricacao": 2024,
            "renomacao": "ABC1D23",
            "frota": "PROPRIA",
            "operacao": "PMSP",
            "placa": "ABC1D23",
            "km_atual": 1000,
            "equipe_id": self.equipe.id,
            "prefeitura_id": None,
        }
        data.update(overrides)
        veiculo = Veiculos(**data)
        db.session.add(veiculo)
        db.session.commit()
        return veiculo

    def test_equipe_oceano_sees_legacy_vehicle_linked_by_team_id_without_prefeitura(self):
        veiculo = self._novo_veiculo()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )

        context = build_piloto_veiculos_context(user)

        self.assertTrue(context["piloto_vinculado"])
        self.assertEqual([item.id for item in context["veiculos"]], [veiculo.id])

    def test_update_vehicle_inherits_prefeitura_from_selected_team(self):
        veiculo = self._novo_veiculo(equipe_id=None)

        update_veiculo(
            veiculo,
            {
                "modelo": "FIORINO",
                "ano_fabricacao": 2024,
                "frota": "PROPRIA",
                "operacao": "PMSP",
                "placa": "ABC1D23",
                "responsavel": None,
                "equipe_id": self.equipe.id,
                "km_atual": 1000,
                "km_prox_revisao": None,
                "status": "Ativo",
                "revisao_marcada_em": None,
                "revisao_obs": None,
            },
        )

        self.assertEqual(veiculo.prefeitura_id, 1)

    def test_vehicle_local_media_path_resolves_to_skybox_path(self):
        self.assertEqual(
            build_veiculo_media_skybox_path(
                "uploads/veiculos/paineis/painel_inicial_ABC1D23_2026-07-08_09-23-31-123.jpg",
                "ABC1D23",
            ),
            "registros abastecimento/ABC1D23/2026-07-08/foto do painel/painel_inicial_ABC1D23_2026-07-08_09-23-31-123.jpg",
        )

    def test_vehicle_photo_upload_is_copied_to_skybox_when_enabled(self):
        self.app.config.update(
            SKYBOX_WEBDAV_URL="https://skybox.example/remote.php/dav/files/user",
            SKYBOX_USERNAME="user",
            SKYBOX_APP_PASSWORD="secret",
            SKYBOX_BASE_DIR="base",
        )
        captured = []
        original_upload = veiculos_service.upload_file_to_skybox

        def fake_upload(file_storage, remote_path):
            file_storage.stream.seek(0)
            captured.append((remote_path, file_storage.stream.read()))
            return f"skybox://{remote_path}"

        veiculos_service.upload_file_to_skybox = fake_upload
        try:
            with TemporaryDirectory() as tmp_dir:
                storage = FileStorage(
                    stream=BytesIO(b"foto-painel"),
                    filename="painel.jpg",
                    content_type="image/jpeg",
                )

                rel_path = veiculos_service._salvar_upload_veiculo(
                    storage,
                    tmp_dir,
                    "paineis",
                    "painel_inicial",
                    "ABC1D23",
                    copiar_skybox=True,
                )

                self.assertRegex(
                    rel_path,
                    r"^uploads/veiculos/paineis/painel_inicial_ABC1D23_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.jpg$",
                )
                self.assertTrue(os.path.isfile(os.path.join(tmp_dir, "static", rel_path.replace("/", os.sep))))
        finally:
            veiculos_service.upload_file_to_skybox = original_upload

        self.assertEqual(len(captured), 1)
        self.assertRegex(
            captured[0][0],
            r"^registros abastecimento/ABC1D23/\d{4}-\d{2}-\d{2}/foto do painel/painel_inicial_ABC1D23_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.jpg$",
        )
        self.assertEqual(captured[0][1], b"foto-painel")

    def test_fuel_record_requires_and_saves_panel_photo(self):
        veiculo = self._novo_veiculo()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=None,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()

        with TemporaryDirectory() as tmp_dir:
            message = registrar_abastecimento_turno_piloto(
                user,
                veiculo.id,
                {
                    "km_abastecimento": "1010",
                    "litros": "20",
                    "valor_abastecimento": "100",
                    "tipo_abastecimento": "Veiculo",
                },
                {
                    "foto_nf": FileStorage(stream=BytesIO(b"nf"), filename="nf.png", content_type="image/png"),
                    "foto_painel_abastecimento": FileStorage(stream=BytesIO(b"painel"), filename="painel.png", content_type="image/png"),
                },
                tmp_dir,
            )

            abastecimento = Abastecimento.query.one()
            self.assertEqual(message, "Abastecimento registrado com sucesso!")
            self.assertRegex(
                abastecimento.foto_nf_path,
                r"^uploads/veiculos/notas/nf_ABC1D23_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.png$",
            )
            self.assertRegex(
                abastecimento.foto_painel_path,
                r"^uploads/veiculos/paineis/painel_abastecimento_ABC1D23_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.png$",
            )

    def test_closing_shift_requires_and_saves_final_panel_photo(self):
        veiculo = self._novo_veiculo()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=None,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()

        with TemporaryDirectory() as tmp_dir:
            message = encerrar_turno_piloto(
                user,
                veiculo.id,
                {"km_final": "1020", "qtd_fazendas_enderecos": "2", "observacao": ""},
                {
                    "foto_painel_final": FileStorage(stream=BytesIO(b"fim"), filename="fim.png", content_type="image/png"),
                },
                tmp_dir,
            )

            db.session.refresh(log)
            self.assertEqual(message, "Turno encerrado com sucesso!")
            self.assertRegex(
                log.foto_painel_final_path,
                r"^uploads/veiculos/paineis/painel_fechamento_ABC1D23_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.png$",
            )


if __name__ == "__main__":
    unittest.main()
