import base64
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from openai import OpenAIError

from flask import Flask
from werkzeug.datastructures import FileStorage

from app.modules.agro import talent_bank_service as service
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


@pytest.fixture
def analysis_client():
    app = Flask(__name__)
    values = {'OPENAI_API_KEY': 'test-key', 'OPENAI_CHAT_MODEL': 'shared-model'}
    profile = {key: '' for key in service.PROFILE_TEXT_FIELDS}
    profile.update({key: [] for key in service.PROFILE_LIST_FIELDS})
    profile.update(nome='Ana Teste', habilidades_tecnicas=['Python'])
    with app.app_context(), patch.object(service, '_resolve_config_value', side_effect=lambda key: values.get(key, '')), patch.object(service, 'OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status='completed', output_text=json.dumps(profile))
        yield sdk, create, values, profile


def test_analysis_sends_pdf_with_strict_schema_and_no_web(analysis_client):
    sdk, create, _, _ = analysis_client
    profile, model = service.analyze_resume(b'%PDF-test')
    assert profile['nome'] == 'Ana Teste'
    assert profile['habilidades_tecnicas'] == ['Python']
    assert model == 'shared-model'
    args = create.call_args.kwargs
    assert args['store'] is False
    assert not args.get('tools')
    assert args['text']['format']['strict'] is True
    schema = args['text']['format']['schema']
    assert schema['additionalProperties'] is False
    assert set(schema['required']) == set(service.PROFILE_TEXT_FIELDS + service.PROFILE_LIST_FIELDS)
    file = args['input'][0]['content'][0]
    assert base64_decode(file['file_data']) == b'%PDF-test'
    assert sdk.call_args.kwargs['max_retries'] == 0
    assert 'Portal do Cidadão' not in args['instructions']


def base64_decode(data):
    assert data.startswith('data:application/pdf;base64,')
    return base64.b64decode(data.split(',', 1)[1])


def test_analysis_supports_own_model(analysis_client):
    _, _, values, _ = analysis_client
    values['OPENAI_TALENT_MODEL'] = 'talent-model'
    assert service.analyze_resume(b'%PDF-test')[1] == 'talent-model'


def test_analysis_missing_key_does_not_call_provider(analysis_client):
    sdk, _, values, _ = analysis_client
    values['OPENAI_API_KEY'] = ''
    with pytest.raises(RuntimeError, match='OPENAI_API_KEY'):
        service.analyze_resume(b'%PDF-test')
    sdk.assert_not_called()


def test_analysis_provider_error_does_not_expose_provider_details(analysis_client):
    _, create, _, _ = analysis_client
    create.side_effect = OpenAIError('secret-key and private candidate text')
    with pytest.raises(RuntimeError) as error:
        service.analyze_resume(b'%PDF-test')
    assert 'secret-key' not in str(error.value)
    assert 'private candidate' not in str(error.value)


@pytest.mark.parametrize('status,text', [
    ('incomplete', '{}'), ('completed', ''), ('completed', 'not JSON'),
    ('completed', '[]'), ('completed', '{}'),
])
def test_analysis_rejects_invalid_or_incomplete_responses(analysis_client, status, text):
    _, create, _, _ = analysis_client
    create.return_value = SimpleNamespace(status=status, output_text=text)
    with pytest.raises(ValueError):
        service.analyze_resume(b'%PDF-test')


@pytest.mark.parametrize('field,value', [('nome', []), ('idiomas', 'Português'), ('experiencias', [123])])
def test_analysis_rejects_wrong_field_types(analysis_client, field, value):
    _, create, _, profile = analysis_client
    profile[field] = value
    create.return_value.output_text = json.dumps(profile)
    with pytest.raises(ValueError, match='formato invalido'):
        service.analyze_resume(b'%PDF-test')


def test_reprocessing_existing_profile_preserves_pdf_and_recovers_after_failure():
    from app.extensions import db
    from app.models import CurriculoAgro
    from app.modules.agro import talent_bank_routes as routes

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    db.init_app(app)
    with app.app_context():
        db.create_all()
        try:
            resume = CurriculoAgro(
                nome='Nome antigo', arquivo_nome_original='teste.pdf', arquivo_tamanho=10,
                arquivo_sha256='a' * 64, dropbox_path='/agro/banco-de-talentos/teste.pdf',
                gemini_modelo='gemini-2.5-flash', resumo_perfil='Perfil antigo',
                analise_status=CurriculoAgro.ANALISE_CONCLUIDA,
            )
            db.session.add(resume)
            db.session.commit()
            resume_id = resume.id
            with patch.object(routes, 'analyze_resume', side_effect=RuntimeError('secret-key private candidate')):
                success, error = routes._process_resume_analysis(resume, b'%PDF-test')
                assert success is False
                assert 'secret-key' not in error
                assert 'private candidate' not in error
            db.session.expire_all()
            saved = db.session.get(CurriculoAgro, resume_id)
            assert saved.analise_status == CurriculoAgro.ANALISE_ERRO
            assert 'secret-key' not in saved.analise_erro
            assert saved.resumo_perfil == 'Perfil antigo'
            assert saved.gemini_modelo == 'gemini-2.5-flash'

            profile = service.normalize_profile_payload({'nome': 'Nome novo', 'habilidades_tecnicas': ['Excel']})
            with patch.object(routes, 'analyze_resume', return_value=(profile, 'test-openai-model')):
                assert routes._process_resume_analysis(saved, b'%PDF-test') == (True, None)
            db.session.expire_all()
            saved = db.session.get(CurriculoAgro, resume_id)
            assert saved.nome == 'Nome novo'
            assert saved.habilidades_tecnicas == ['Excel']
            assert saved.analise_status == CurriculoAgro.ANALISE_CONCLUIDA
            assert saved.analise_erro is None
            assert saved.gemini_modelo == 'test-openai-model'
            assert saved.dropbox_path == '/agro/banco-de-talentos/teste.pdf'
            assert saved.status == CurriculoAgro.STATUS_NOVO
        finally:
            db.session.remove()
            db.drop_all()
            db.engine.dispose()


def test_oversized_resume_read_is_bounded():
    from unittest.mock import Mock
    upload = Mock(filename='curriculo.pdf')
    with patch.object(service, 'MAX_RESUME_SIZE_BYTES', 16):
        upload.read.return_value = b'%PDF-' + b'x' * 12
        with pytest.raises(ValueError, match='20 MB'):
            validate_resume_pdf(upload)
    upload.read.assert_called_once_with(17)
