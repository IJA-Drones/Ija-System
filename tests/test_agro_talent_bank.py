import io
import unittest

from flask import Flask
from werkzeug.datastructures import FileStorage

from app.modules.agro.talent_bank_service import (
    build_dropbox_resume_path,
    normalize_profile_payload,
    validate_resume_pdf,
)


class AgroTalentBankServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_validate_resume_pdf_accepts_pdf_and_hashes_content(self):
        file_storage = FileStorage(
            stream=io.BytesIO(b"%PDF-1.7\nresume"),
            filename="curriculo.pdf",
            content_type="application/pdf",
        )

        result = validate_resume_pdf(file_storage)

        self.assertEqual(result["original_name"], "curriculo.pdf")
        self.assertEqual(result["size"], 15)
        self.assertEqual(len(result["sha256"]), 64)

    def test_validate_resume_pdf_rejects_fake_pdf(self):
        file_storage = FileStorage(
            stream=io.BytesIO(b"not a pdf"),
            filename="curriculo.pdf",
            content_type="application/pdf",
        )

        with self.assertRaisesRegex(ValueError, "assinatura PDF"):
            validate_resume_pdf(file_storage)

    def test_normalize_profile_removes_duplicates_and_unsafe_link(self):
        profile = normalize_profile_payload(
            {
                "nome": "  Ana   Silva ",
                "linkedin": "javascript:alert(1)",
                "habilidades_tecnicas": ["Python", " python ", None, "SQL"],
            }
        )

        self.assertEqual(profile["nome"], "Ana Silva")
        self.assertIsNone(profile["linkedin"])
        self.assertEqual(profile["habilidades_tecnicas"], ["Python", "SQL"])
        self.assertEqual(profile["areas_atuacao"], [])

    def test_build_dropbox_path_is_private_and_scoped(self):
        with self.app.app_context():
            path = build_dropbox_resume_path("../../Curriculo Ana.pdf", prefeitura_id=9)

        self.assertTrue(path.startswith("/agro/banco-de-talentos/prefeitura-9/"))
        self.assertTrue(path.endswith(".pdf"))
        self.assertNotIn("..", path)


if __name__ == "__main__":
    unittest.main()
