import unittest
from io import BytesIO
from types import SimpleNamespace

from flask import Flask
from werkzeug.datastructures import FileStorage, MultiDict

from app.clients import cep_client
from app.modules.portal_cidadao import service as portal_service


class PortalCidadaoDenunciaServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True)
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.original_skybox_enabled = portal_service.skybox_enabled
        self.original_upload_file_to_skybox = portal_service.upload_file_to_skybox

    def tearDown(self):
        portal_service.skybox_enabled = self.original_skybox_enabled
        portal_service.upload_file_to_skybox = self.original_upload_file_to_skybox
        self.ctx.pop()

    def test_parse_denuncia_requires_valid_cpf_and_phone(self):
        data = portal_service._parse_denuncia_form(MultiDict({
            "tipo_visita": "Aedes",
            "tipo_imovel": "Imovel Geral",
            "foco": "Piscina",
            "cep": "01001-000",
            "logradouro": "Praca da Se",
            "numero": "1",
            "bairro": "Se",
            "cidade": "Sao Paulo",
            "nome": "Cidadao Teste",
            "cpf": "111.111.111-11",
            "rg": "12.345.678-9",
            "telefone": "1234",
            "consentimento": "1",
        }))
        errors = portal_service._validate_denuncia_data(data)

        self.assertEqual(data["cep"], "01001-000")
        self.assertEqual(errors["cpf"], "Informe um CPF valido.")
        self.assertEqual(errors["telefone"], "Informe um telefone com DDD.")

    def test_parse_denuncia_formats_valid_identity_fields(self):
        data = portal_service._parse_denuncia_form(MultiDict({
            "tipo_visita": "Culex",
            "foco": "Corrego",
            "cep": "01001000",
            "logradouro": "Praca da Se",
            "numero": "1",
            "bairro": "Se",
            "cidade": "Sao Paulo",
            "nome": "Cidadao Teste",
            "cpf": "52998224725",
            "rg": "123456789",
            "telefone": "11987654321",
            "consentimento": "true",
        }))
        errors = portal_service._validate_denuncia_data(data)

        self.assertEqual(errors, {})
        self.assertEqual(data["cpf"], "529.982.247-25")
        self.assertEqual(data["telefone"], "(11) 98765-4321")

    def test_denuncia_accepts_address_without_cep(self):
        data = portal_service._parse_denuncia_form(MultiDict({
            "tipo_visita": "Outro",
            "foco": "Outro",
            "logradouro": "Rua Teste",
            "numero": "10",
            "bairro": "Centro",
            "cidade": "Sao Paulo",
            "nome": "Cidadao Teste",
            "cpf": "52998224725",
            "rg": "123456789",
            "telefone": "11987654321",
            "consentimento": "1",
        }))
        errors = portal_service._validate_denuncia_data(data)

        self.assertEqual(data["cep"], "")
        self.assertNotIn("cep", errors)

    def test_address_geocode_overwrites_browser_location_coordinates(self):
        original_geocode = portal_service.geocode_endereco_google
        try:
            portal_service.geocode_endereco_google = lambda **kwargs: (-23.55052, -46.633308, "place-address")
            data = {
                "cep": "",
                "logradouro": "Praca da Se",
                "numero": "1",
                "bairro": "Se",
                "cidade": "Sao Paulo",
                "uf": "SP",
                "latitude": "-22.0",
                "longitude": "-43.0",
                "place_id": "place-browser",
            }

            portal_service._try_geocode_address(data)

            self.assertEqual(data["latitude"], "-23.55052")
            self.assertEqual(data["longitude"], "-46.633308")
            self.assertEqual(data["place_id"], "place-address")
        finally:
            portal_service.geocode_endereco_google = original_geocode

    def test_save_denuncia_media_uses_skybox_denuncias_folder(self):
        captured = {}

        def fake_upload(file_storage, remote_path):
            captured["remote_path"] = remote_path
            captured["body"] = file_storage.stream.read()
            return f"skybox://{remote_path}"

        portal_service.skybox_enabled = lambda: True
        portal_service.upload_file_to_skybox = fake_upload

        denuncia = SimpleNamespace(id=77)
        storage = FileStorage(
            stream=BytesIO(b"video"),
            filename="foco.mp4",
            content_type="video/mp4",
        )

        anexo = portal_service._save_denuncia_media(denuncia, storage)

        self.assertTrue(captured["remote_path"].startswith("denuncias/77/video/denuncia_77_"))
        self.assertTrue(captured["remote_path"].endswith(".mp4"))
        self.assertEqual(captured["body"], b"video")
        self.assertEqual(anexo.arquivo_path, f"skybox://{captured['remote_path']}")
        self.assertEqual(anexo.tipo_midia, "video")

    def test_correios_address_payload_is_normalized(self):
        payload = cep_client._normalize_correios_address({
            "cep": "01001001",
            "uf": "SP",
            "localidade": "Sao Paulo",
            "logradouro": "Praca da Se",
            "complemento": "- lado par",
            "bairro": "Se",
        })

        self.assertEqual(payload["cep"], "01001-001")
        self.assertEqual(payload["logradouro"], "Praca da Se")
        self.assertEqual(payload["cidade"], "Sao Paulo")


if __name__ == "__main__":
    unittest.main()
