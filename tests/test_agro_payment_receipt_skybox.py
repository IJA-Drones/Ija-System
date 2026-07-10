import unittest
from io import BytesIO
from types import SimpleNamespace

from flask import Flask
from werkzeug.datastructures import FileStorage

from app.modules.agro import service as agro_service


class AgroPaymentReceiptSkyboxTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True)
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.original_skybox_enabled = agro_service.skybox_enabled
        self.original_upload_file_to_skybox = agro_service.upload_file_to_skybox

    def tearDown(self):
        agro_service.skybox_enabled = self.original_skybox_enabled
        agro_service.upload_file_to_skybox = self.original_upload_file_to_skybox
        self.ctx.pop()

    def test_save_payment_receipt_uploads_to_comprovantes_agro_folder(self):
        captured = {}

        def fake_upload(file_storage, remote_path):
            captured["remote_path"] = remote_path
            captured["body"] = file_storage.stream.read()
            return f"skybox://{remote_path}"

        agro_service.skybox_enabled = lambda: True
        agro_service.upload_file_to_skybox = fake_upload

        contrato = SimpleNamespace(
            id=42,
            comprovante_pagamento_path=None,
            comprovante_pagamento_nome=None,
            comprovante_pagamento_enviado_em=None,
        )
        storage = FileStorage(
            stream=BytesIO(b"comprovante"),
            filename="comprovante.jfif",
            content_type="image/jpeg",
        )

        saved_name = agro_service.save_contrato_payment_receipt(contrato, storage)

        self.assertEqual(saved_name, "comprovante.jfif")
        self.assertTrue(captured["remote_path"].startswith("Comprovantes Agro/contrato_agro_42_comprovante_"))
        self.assertTrue(captured["remote_path"].endswith(".jfif"))
        self.assertEqual(captured["body"], b"comprovante")
        self.assertEqual(contrato.comprovante_pagamento_path, f"skybox://{captured['remote_path']}")


if __name__ == "__main__":
    unittest.main()
