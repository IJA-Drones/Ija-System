"""Inspect actual PDF pages, per-city scope, async identity and disabled settings."""
from datetime import datetime, time
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import zipfile

from flask import Flask
from PIL import Image
from pypdf import PdfReader
import pytest
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from sqlalchemy import inspect, select
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Prefeitura, Usuario, PrefeituraDocumentoConfig, Solicitacao, OrdemServico, Equipe
from app.shared.pdf_watermark import WatermarkError, municipal_canvas, report_prefeitura_id
from app.modules.configuracoes.service import local_image_path
from app.modules.piloto_os.exporters import build_admin_os_pdf_v2_export
from app.modules.relatorios.exporters import build_relatorio_coleta_imagens_pdf_export, build_relatorio_coleta_imagens_pdf_zip_export, build_relatorio_pdf_export, build_relatorio_os_pdf_export


@pytest.fixture
def database(tmp_path):
    app=Flask(__name__, instance_path=str(tmp_path))
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        for key, name, color in [(1, 'Prefeitura Alfa', 'red'), (2, 'Prefeitura Beta', 'blue')]:
            db.session.add(Prefeitura(id=key,nome=name,slug=f'city-{key}'))
            db.session.add(Usuario(id=key, nome_uvis=f'Unidade {key}',login=f'unit{key}',senha_hash='unused',tipo_usuario='uvis',prefeitura_id=key))
            path=local_image_path(f'{key}.png')
            path.parent.mkdir(parents=True,exist_ok=True)
            Image.new('RGBA',(200,120),color).save(path)
            db.session.add(PrefeituraDocumentoConfig(prefeitura_id=key,ativo=True,imagem_path=f'{key}.png',imagem_nome='brasao.png',identificar_usuario=True,opacidade=14,largura_percentual=55))
        db.session.add(Equipe(id=1, prefeitura_id=1,nome_equipe='Equipe demonstração'))
        db.session.add(Usuario(id=3,nome_uvis='Emissor Dev',login='dev',senha_hash='unused',tipo_usuario='dev'))
        db.session.commit()
        yield app
        db.session.remove()


def emitter(key=3):
    return db.session.get(Usuario,key)


def make_pdf(city=1, user=None, pagesize=A4):
    output=BytesIO()
    styles=getSampleStyleSheet()
    doc=SimpleDocTemplate(output,pagesize=pagesize)
    doc.build([Paragraph('CONTEUDO ORIGINAL PAGINA 1',styles['Normal']),PageBreak(),Paragraph('CONTEUDO ORIGINAL PAGINA 2',styles['Normal'])],canvasmaker=municipal_canvas(city,user=user))
    output.seek(0)
    return PdfReader(output)


def test_unmigrated_database_keeps_original_pdf_and_usable_session(tmp_path):
    app = Flask(__name__, instance_path=str(tmp_path))
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', TESTING=True)
    db.init_app(app)
    with app.app_context():
        # Only the existing municipal table is present; no watermark schema.
        Prefeitura.__table__.create(db.engine)
        db.session.add(Prefeitura(id=1, nome='Prefeitura Alfa', slug='city-1'))
        db.session.commit()

        reader = make_pdf()
        assert len(reader.pages) == 2
        for number, page in enumerate(reader.pages, 1):
            assert f'CONTEUDO ORIGINAL PAGINA {number}' in page.extract_text()
            assert 'Emitido por' not in page.extract_text()
            assert len(page.images) == 0

        # The export must not require rollback or create any missing tables.
        assert db.session.scalar(select(Prefeitura.nome).where(Prefeitura.id == 1)) == 'Prefeitura Alfa'
        db.session.add(Prefeitura(id=2, nome='Prefeitura Beta', slug='city-2'))
        db.session.commit()
        assert db.session.scalar(select(Prefeitura.nome).where(Prefeitura.id == 2)) == 'Prefeitura Beta'
        assert not inspect(db.session.connection()).has_table(PrefeituraDocumentoConfig.__tablename__)


@pytest.mark.parametrize('target', ['inspect', 'db.session.get'])
def test_database_errors_are_not_treated_as_absent_watermark_schema(database, target):
    user = emitter()
    failure = OperationalError('database unavailable', {}, RuntimeError('unavailable'))
    with patch(f'app.shared.pdf_watermark.{target}', side_effect=failure):
        with pytest.raises(OperationalError):
            make_pdf(user=user)


def seed_order(city=1):
    now=datetime.now()
    request=Solicitacao(prefeitura_id=city,usuario_id=city,equipe_id=1,data_agendamento=now.date(),hora_agendamento=time(9),foco='Piscina',tipo_operacao='monitoramento',tipo_visita='Monitoramento',tipo_imovel='Residencial',cep='00000-000',logradouro='Area de demonstracao',numero='1',bairro='Teste',cidade='Cidade Ficticia',uf='SP',status='CONCLUÍDO',data_criacao=now)
    db.session.add(request)
    db.session.flush()
    db.session.add(OrdemServico(solicitacao_id=request.id,equipe_id=1,respondido_em=now,data_aplicacao=now.date(),situacao_aplicacao='REALIZADA',imagem_principal='demo-nao-existente.png'))
    db.session.commit()
    return request.id


@pytest.mark.parametrize('pagesize',[A4,landscape(A4)])
def test_all_pages_preserve_content_and_have_alpha_image_and_requester(database,pagesize):
    reader=make_pdf(user=emitter(),pagesize=pagesize)
    assert len(reader.pages)==2
    for number,page in enumerate(reader.pages,1):
        text=page.extract_text()
        assert f'CONTEUDO ORIGINAL PAGINA {number}' in text
        assert 'Emitido por Emissor Dev (ID 3)' in text
        assert 'Prefeitura Alfa' in text and 'Prefeitura Beta' not in text
        assert len(page.images)==1
        states=page['/Resources']['/ExtGState'].get_object().values()
        assert any(float(state.get('/ca',1))==.14 for state in states)
        assert float(page.mediabox.width)==pytest.approx(pagesize[0],abs=.01)


def test_image_only_text_only_disabled_and_missing_config(database):
    config=db.session.get(PrefeituraDocumentoConfig,1)
    config.identificar_usuario=False
    db.session.commit()
    page=make_pdf(user=emitter()).pages[0]
    assert len(page.images)==1 and 'Emitido por' not in page.extract_text()
    config.identificar_usuario=True
    config.imagem_path=None
    db.session.commit()
    page=make_pdf(user=emitter()).pages[0]
    assert len(page.images)==0 and 'Emitido por Emissor Dev' in page.extract_text()
    config.ativo=False
    db.session.commit()
    for city in (1,999,None):
        page=make_pdf(city=city,user=emitter()).pages[0]
        assert len(page.images)==0 and 'Emitido por' not in page.extract_text()


def test_failing_image_or_unknown_emitter_never_silently_omits_required_mark(database):
    with pytest.raises(WatermarkError,match='solicitou'):
        make_pdf()
    local_image_path('1.png').unlink()
    with pytest.raises(WatermarkError,match='indisponível'):
        make_pdf(user=emitter())


def test_cache_is_per_export_and_page_scoped(database):
    output=BytesIO()
    with patch('app.shared.pdf_watermark.inspect', wraps=inspect) as schema_inspection:
        canvas=municipal_canvas(user=emitter())(output,pagesize=A4)
        for city in (1,2):
            canvas.set_watermark_prefeitura(city)
            canvas.drawString(30,800,f'Documento {city}')
            canvas.showPage()
        canvas.save()
        schema_inspection.assert_called_once()
    output.seek(0)
    pages=PdfReader(output).pages
    assert 'Prefeitura Alfa' in pages[0].extract_text() and 'Prefeitura Beta' not in pages[0].extract_text()
    assert 'Prefeitura Beta' in pages[1].extract_text() and 'Prefeitura Alfa' not in pages[1].extract_text()
    assert pages[0].images[0].data != pages[1].images[0].data
    assert 'Unidade 1' in make_pdf(user=emitter(1)).pages[0].extract_text()
    assert 'Emissor Dev' not in make_pdf(user=emitter(1)).pages[0].extract_text()


def test_mixed_or_unknown_scope_cannot_use_the_admins_municipality(database):
    admin=emitter()
    admin.prefeitura_id=1
    assert report_prefeitura_id([1,2],admin) is None
    assert report_prefeitura_id([1,None],admin) is None
    assert report_prefeitura_id([],admin) is None
    assert report_prefeitura_id([2],admin)==2
    assert report_prefeitura_id([],emitter(1))==1


def test_background_os_export_uses_requester_not_owner_and_legacy_owner_city(database):
    order_id=seed_order()
    request=db.session.get(Solicitacao,order_id)
    request.prefeitura_id=None
    db.session.commit()
    path,_=build_admin_os_pdf_v2_export(order_id,{},user=emitter())
    try:
        for page in PdfReader(path).pages:
            assert 'Emitido por Emissor Dev' in page.extract_text()
            assert 'Prefeitura Alfa' in page.extract_text()
    finally:
        Path(path).unlink()


@pytest.mark.parametrize('builder',[build_relatorio_pdf_export,build_relatorio_os_pdf_export])
def test_aggregate_export_uses_data_city_and_does_not_brand_mixed_report(database,builder):
    seed_order(1)
    now=datetime.now()
    args=MultiDict({"mes":str(now.month),"ano":str(now.year)})
    with patch('app.modules.relatorios.exporters._get_matplotlib_pyplot',return_value=None):
        path,_=builder(emitter(),args)
        try:
            assert all('Prefeitura Alfa' in p.extract_text() for p in PdfReader(path).pages)
        finally: Path(path).unlink()
        seed_order(2)
        path,_=builder(emitter(),args)
        try:
            assert all('Emitido por' not in p.extract_text() for p in PdfReader(path).pages)
        finally: Path(path).unlink()


def test_photo_report_and_zip_work_without_request_context(database):
    seed_order(1)
    seed_order(2)
    now=datetime.now()
    args=MultiDict({"mes":str(now.month),"ano":str(now.year)})
    path,_=build_relatorio_coleta_imagens_pdf_export(emitter(),args)
    try:
        pages=PdfReader(path).pages
        assert len(pages)==2
        texts=[p.extract_text() for p in pages]
        assert sum('Prefeitura Alfa' in t for t in texts)==1
        assert sum('Prefeitura Beta' in t for t in texts)==1
        assert all('Emitido por Emissor Dev' in t for t in texts)
    finally: Path(path).unlink()
    path,_=build_relatorio_coleta_imagens_pdf_zip_export(emitter(),args)
    try:
        with zipfile.ZipFile(path) as archive:
            assert len(archive.namelist())==2
            for name in archive.namelist():
                assert 'Emitido por Emissor Dev' in PdfReader(BytesIO(archive.read(name))).pages[0].extract_text()
    finally: Path(path).unlink()


def test_skybox_asset_loaded_once_for_multi_page_export(database):
    config=db.session.get(PrefeituraDocumentoConfig,1)
    config.imagem_path='skybox://municipal.png'
    db.session.commit()
    with patch('app.shared.pdf_watermark.download_skybox_bytes',return_value=local_image_path('1.png').read_bytes()) as download:
        assert len(make_pdf(user=emitter()).pages)==2
        download.assert_called_once()


def test_equipment_and_agro_exporters_apply_their_document_city(database):
    from types import SimpleNamespace
    from app.models import OrcamentoAgro, ContratoAgro, OrdemServicoAgro
    from app.modules.equipamentos.exporters import build_manutencao_pdf
    from app.modules.agro.exporters import build_orcamento_agro_pdf, build_contrato_agro_pdf, build_ordem_servico_agro_pdf, build_agro_relatorio_contas_pdf_export
    from app.modules.agro.routes import _build_agro_relatorio_contas_summary
    # Image-only settings also work for generated/stored documents without an
    # HTTP context. The municipality comes from each document, not the operator.
    db.session.get(PrefeituraDocumentoConfig,1).identificar_usuario=False
    db.session.commit()
    drone=SimpleNamespace(prefeitura_id=1,renomacao='DEMO',modelo='Drone teste',numero_serie='FICTICIO',status='Disponivel',equipe=None)
    path=build_manutencao_pdf(drone,[])
    try:
        assert all(any(image.image.size == (200,120) for image in p.images) for p in PdfReader(path).pages)
    finally: Path(path).unlink()
    orcamento=OrcamentoAgro(id=100,prefeitura_id=1,cliente_nome='Cliente DEMO',nome_fazenda='Fazenda DEMO',servico='Mapeamento',area_ha=1,preco_base=10,preco_mapeamento=10,preco_pulverizacao=0,preco_pulverizacao_adicional=0)
    contrato=ContratoAgro(id=100,prefeitura_id=1,orcamento=orcamento,contratante_nome='Cliente DEMO',valor_total=10)
    os=OrdemServicoAgro(id=100,prefeitura_id=1,cliente_nome='Cliente DEMO',identificador_os='DEMO',contrato=contrato,orcamento=orcamento)
    for buffer in [build_orcamento_agro_pdf(orcamento),build_contrato_agro_pdf(contrato),build_ordem_servico_agro_pdf(os)]:
        assert all(any(image.image.size == (200,120) for image in p.images) for p in PdfReader(buffer).pages)
    # A consolidated finance PDF with no municipal records has no seal.
    buffer,_=build_agro_relatorio_contas_pdf_export([], _build_agro_relatorio_contas_summary([]),{})
    assert all('Emitido por' not in p.extract_text() for p in PdfReader(buffer).pages)


def test_bounded_skybox_download_rejects_oversized_image():
    from unittest.mock import MagicMock
    from app.shared.skybox import download_skybox_bytes, SkyboxError
    response=MagicMock()
    response.__enter__.return_value=response
    response.status_code=200
    response.iter_content.return_value=[b'123',b'456']
    with patch('app.shared.skybox.skybox_enabled',return_value=True),patch('app.shared.skybox._request',return_value=response):
        with pytest.raises(SkyboxError,match='limite'):
            download_skybox_bytes('skybox://image.png',max_bytes=5)
    response.__exit__.assert_called_once()


def test_request_export_identifies_logged_in_user(database):
    from flask_login import LoginManager, login_user
    database.secret_key='isolated-pdf-test-only'
    LoginManager(database)
    with database.test_request_context('/'):
        login_user(emitter())
        assert 'Emitido por Emissor Dev (ID 3)' in make_pdf().pages[0].extract_text()


def test_pdf_failure_returns_explanatory_503(database):
    from flask import Blueprint
    from app.core.errors import register_error_handlers
    bp=Blueprint('test_errors',__name__)
    register_error_handlers(bp)
    @bp.get('/export.pdf')
    def failed_export():
        raise WatermarkError('A imagem da marca d’água está indisponível.')
    database.register_blueprint(bp)
    response=database.test_client().get('/export.pdf',headers={'Accept':'application/json'})
    assert response.status_code==503
    assert 'marca d’água' in response.json['error']
