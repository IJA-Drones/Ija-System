import unittest
from io import BytesIO
from types import SimpleNamespace

from flask import Flask
from werkzeug.datastructures import FileStorage

from app.shared import skybox


class SkyboxUploadTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SKYBOX_WEBDAV_URL="https://skybox.example/remote.php/dav/files/user",
            SKYBOX_USERNAME="user",
            SKYBOX_APP_PASSWORD="secret",
        )
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.original_request = skybox._request
        self.original_ensure_parent_collections = skybox._ensure_parent_collections

    def tearDown(self):
        skybox._request = self.original_request
        skybox._ensure_parent_collections = self.original_ensure_parent_collections
        self.ctx.pop()

    def test_upload_file_to_skybox_sends_content_length_and_rewinds_stream(self):
        captured = {}
        skybox._ensure_parent_collections = lambda remote_path: None

        def fake_request(method, remote_path, **kwargs):
            captured["method"] = method
            captured["remote_path"] = remote_path
            captured["headers"] = kwargs.get("headers") or {}
            captured["body"] = kwargs["data"].read()
            return SimpleNamespace(status_code=201, text="")

        skybox._request = fake_request

        storage = FileStorage(
            stream=BytesIO(b"imagem"),
            filename="painel.png",
            content_type="image/png",
        )
        storage.stream.seek(3)

        remote_path = "registros abastecimento/ABC/2026-07-08/foto do painel/painel.png"
        marker = skybox.upload_file_to_skybox(storage, remote_path)

        self.assertEqual(marker, f"skybox://{remote_path}")
        self.assertEqual(captured["method"], "PUT")
        self.assertEqual(captured["remote_path"], remote_path)
        self.assertEqual(captured["headers"]["Content-Type"], "image/png")
        self.assertEqual(captured["headers"]["Content-Length"], "6")
        self.assertEqual(captured["body"], b"imagem")

    def test_build_vehicle_media_remote_path_groups_by_day_and_kind(self):
        self.assertEqual(
            skybox.build_veiculo_media_remote_path(
                "ABC1D23",
                "notas",
                "nf_ABC1D23_2026-07-08_09-23-31-123.png",
                day="2026-07-08",
            ),
            "registros abastecimento/ABC1D23/2026-07-08/nota fiscal/nf_ABC1D23_2026-07-08_09-23-31-123.png",
        )


if __name__ == "__main__":
    unittest.main()
