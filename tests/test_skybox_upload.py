import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

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

    def test_upload_timeout_override_reaches_http_without_changing_default(self):
        skybox._ensure_parent_collections = lambda remote_path: None
        with patch.object(skybox.requests, 'request', return_value=SimpleNamespace(status_code=201)) as request:
            for options, expected in (({}, skybox.REQUEST_TIMEOUT), ({'timeout': None}, None)):
                storage = FileStorage(stream=BytesIO(b'raster'), filename='mapa.tif')
                skybox.upload_file_to_skybox(storage, 'ortomosaicos/mapa.tif', **options)
                self.assertEqual(request.call_args.kwargs['timeout'], expected)

    def test_only_transient_http_failures_are_retryable(self):
        skybox._ensure_parent_collections = lambda remote_path: None
        for status in (408, 429, 500, 502, 503, 504, 401, 403, 413, 507):
            with self.subTest(status=status):
                skybox._request = lambda *a, **kw: SimpleNamespace(status_code=status, text='')
                storage = FileStorage(stream=BytesIO(b'raster'), filename='mapa.tif')
                with self.assertRaises(skybox.SkyboxError) as raised:
                    skybox.upload_file_to_skybox(storage, 'ortomosaicos/mapa.tif')
                self.assertEqual(isinstance(raised.exception, skybox.SkyboxTemporaryError),
                                 status in (408, 429, 500, 502, 503, 504))

    def test_skybox_roundtrip_checks_upload_confirmation_and_cleanup(self):
        calls = []

        def fake_request(method, remote_path, **kwargs):
            calls.append((method, remote_path))
            if method == "MKCOL":
                return SimpleNamespace(status_code=201, text="")
            if method == "PROPFIND":
                return SimpleNamespace(status_code=207, text="")
            return SimpleNamespace(status_code=204, text="")

        skybox._request = fake_request
        result = skybox.test_skybox_roundtrip()

        self.assertEqual(result["severity"], "success")
        self.assertEqual([step["status"] for step in result["steps"]], ["ok", "ok", "ok"])
        uploaded_path = next(path for method, path in calls if method == "PUT")
        self.assertEqual(
            [path for method, path in calls if method == "DELETE"],
            [uploaded_path, uploaded_path.rsplit("/", 1)[0]],
        )

    def test_skybox_roundtrip_distinguishes_authentication_and_permissions_at_each_stage(self):
        stages = (
            ("MKCOL", "Preparar pasta", 0),
            ("PUT", "Upload de teste", 1),
            ("PROPFIND", "Confirmação WebDAV", 2),
        )
        for failed_method, stage, completed_steps in stages:
            for status in (401, 403):
                with self.subTest(method=failed_method, status=status):
                    calls = []

                    def fake_request(method, remote_path, **kwargs):
                        calls.append((method, remote_path))
                        return SimpleNamespace(
                            status_code=status if method == failed_method else
                            {"MKCOL": 201, "PUT": 201, "PROPFIND": 207, "DELETE": 204}[method],
                            text="upstream-sensitive-body",
                        )

                    skybox._request = fake_request
                    with self.assertLogs(self.app.logger, level="WARNING") as logs:
                        result = skybox.test_skybox_roundtrip()

                    expected_status = "Autenticação rejeitada" if status == 401 else "Acesso negado"
                    self.assertEqual(result["status"], expected_status)
                    self.assertEqual(result["severity"], "danger")
                    self.assertIn(f"HTTP {status}", result["detail"])
                    self.assertIn(f"{stage} ({failed_method})", result["detail"])
                    self.assertEqual(len(result["steps"]), completed_steps)
                    self.assertIn(f"{stage} ({failed_method})", " ".join(logs.output))
                    self.assertIn(f"HTTP {status}", " ".join(logs.output))
                    for output in (str(result), " ".join(logs.output)):
                        self.assertNotIn("upstream-sensitive-body", output)
                        self.assertNotIn(self.app.config["SKYBOX_APP_PASSWORD"], output)
                    if status == 401:
                        self.assertIn("senha principal", result["detail"])
                        self.assertIn("SKYBOX_APP_PASSWORD", result["detail"])
                    else:
                        self.assertIn("permissões", result["detail"])
                        self.assertNotIn("SKYBOX_APP_PASSWORD", result["detail"])
                    # A failed authentication/permission check is never retried.
                    self.assertEqual(sum(method == failed_method for method, _ in calls), 1)
                    if failed_method == "PROPFIND":
                        uploaded_path = next(path for method, path in calls if method == "PUT")
                        self.assertEqual(
                            [path for method, path in calls if method == "DELETE"],
                            [uploaded_path, uploaded_path.rsplit("/", 1)[0]],
                        )
                    else:
                        self.assertFalse(any(method == "DELETE" for method, _ in calls))

    def test_skybox_roundtrip_preserves_http_status_for_other_confirmation_failures(self):
        def fake_request(method, remote_path, **kwargs):
            return SimpleNamespace(status_code={
                "MKCOL": 201, "PUT": 201, "PROPFIND": 503, "DELETE": 204,
            }[method], text="")

        skybox._request = fake_request
        result = skybox.test_skybox_roundtrip()

        self.assertEqual(result["status"], "Falha")
        self.assertEqual(result["severity"], "danger")
        self.assertIn("HTTP 503", result["detail"])
        self.assertIn("Confirmação WebDAV (PROPFIND)", result["detail"])


if __name__ == "__main__":
    unittest.main()
