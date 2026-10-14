"""Marca municipal desenhada na finalização de cada página, inclusive em jobs.

Os exportadores fornecem o município dos registros. Nunca se escolhe uma
prefeitura pelo nome da região ou pela prefeitura do dev que exportou.
"""
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from flask import has_app_context, has_request_context
from flask_login import current_user
from PIL import Image
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import func, select

from app.extensions import db
from app.models import Prefeitura, PrefeituraDocumentoConfig, Solicitacao, Usuario
from app.modules.configuracoes.service import local_image_path
from app.shared.access import is_admin_global_user
from app.shared.skybox import download_skybox_bytes, is_skybox_path


class WatermarkError(ValueError):
    pass


def solicitacao_prefeitura_id(solicitacao):
    return getattr(solicitacao, "prefeitura_id", None) or getattr(getattr(solicitacao, "usuario", None), "prefeitura_id", None)


def solicitacao_prefeitura_expr():
    # Legacy requests may have only their owning user's municipality populated.
    owner_city = select(Usuario.prefeitura_id).where(Usuario.id == Solicitacao.usuario_id).correlate(Solicitacao).scalar_subquery()
    return func.coalesce(Solicitacao.prefeitura_id, owner_city)


def query_prefeitura_ids(query, expression):
    # Two distinct values already prove that the whole report has no single seal.
    return [row[0] for row in query.order_by(None).with_entities(expression).distinct().limit(2).all()]


def single_prefeitura_id(ids):
    cities = set(ids)
    return next(iter(cities)) if len(cities) == 1 else None


def report_prefeitura_id(ids, user=None):
    cities = list(ids)
    if cities:
        return single_prefeitura_id(cities)
    if user is None and has_request_context():
        user = current_user
    # An empty result can use its enforced municipal scope, but an empty global
    # report must not acquire a seal just because its administrator has a city.
    if user is not None and not is_admin_global_user(user):
        return getattr(user, "prefeitura_id", None)
    return None


def _emitter(user):
    if user is None and has_request_context() and current_user.is_authenticated:
        user = current_user
    if user is None:
        return None
    name = getattr(user, "nome_uvis", None) or getattr(user, "login", None)
    if not name:
        return None
    return f"{name} (ID {user.id})"


class MunicipalWatermarks:
    """Cache por exportação: não compartilha imagens nem identidades entre pedidos."""
    def __init__(self, user=None):
        self.emitter = _emitter(user)
        self.issued_at = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
        self.cache = {}

    def get(self, prefeitura_id):
        if prefeitura_id is None or not has_app_context():
            return None
        if prefeitura_id in self.cache:
            return self.cache[prefeitura_id]
        config = db.session.get(PrefeituraDocumentoConfig, prefeitura_id)
        if config is None or not config.ativo:
            self.cache[prefeitura_id] = None
            return None
        prefeitura = db.session.get(Prefeitura, prefeitura_id)
        if prefeitura is None:
            raise WatermarkError("Prefeitura da marca d’água não encontrada.")
        if config.identificar_usuario and not self.emitter:
            raise WatermarkError("Não foi possível identificar quem solicitou o PDF.")
        image = None
        if config.imagem_path:
            try:
                if is_skybox_path(config.imagem_path):
                    raw = download_skybox_bytes(config.imagem_path, max_bytes=12 * 1024 * 1024)
                else:
                    with local_image_path(config.imagem_path).open("rb") as handle:
                        raw = handle.read(12 * 1024 * 1024 + 1)
                if len(raw) > 12 * 1024 * 1024:
                    raise ValueError("Imagem excede o limite de leitura.")
                with Image.open(BytesIO(raw)) as source:
                    if max(source.size) > 4096 or source.width * source.height > 16_000_000:
                        raise ValueError("Dimensões de imagem inválidas.")
                    image = ImageReader(source.convert("RGBA"))
            except Exception as exc:
                raise WatermarkError("A imagem da marca d’água está indisponível. Confira as configurações da prefeitura e tente novamente.") from exc
        if image is None and not config.identificar_usuario:
            raise WatermarkError("A marca d’água está habilitada sem imagem ou identificação.")
        mark = {
            "image": image, "opacity": config.opacidade / 100,
            "width": config.largura_percentual / 100,
            "lines": [f"Emitido por {self.emitter}", prefeitura.nome, self.issued_at]
                if config.identificar_usuario else [],
        }
        self.cache[prefeitura_id] = mark
        return mark

    def draw(self, canvas, prefeitura_id):
        mark = self.get(prefeitura_id)
        if mark is None:
            return
        page_width, page_height = canvas._pagesize
        width = page_width * mark["width"]
        font_size = 11
        lines = [line for text in mark["lines"] for line in simpleSplit(text, "Helvetica", font_size, width)]
        text_height = len(lines) * 14
        image_width = image_height = 0
        if mark["image"]:
            iw, ih = mark["image"].getSize()
            ratio = min(width / iw, page_height * .55 / ih)
            image_width, image_height = iw * ratio, ih * ratio
        gap = 12 if image_height and lines else 0
        bottom = (page_height - image_height - text_height - gap) / 2
        canvas.saveState()
        try:
            canvas.setFillAlpha(mark["opacity"])
            canvas.setStrokeAlpha(mark["opacity"])
            canvas.setBlendMode("Multiply")
            if mark["image"]:
                canvas.drawImage(mark["image"], (page_width - image_width) / 2,
                                 bottom + text_height + gap, image_width, image_height, mask="auto")
            canvas.setFillColorRGB(.09, .17, .27)
            canvas.setFont("Helvetica", font_size)
            for index, line in enumerate(lines):
                canvas.drawCentredString(page_width / 2, bottom + text_height - 11 - index * 14, line)
        finally:
            canvas.restoreState()


def municipal_canvas(prefeitura_id=None, *, user=None):
    marks = MunicipalWatermarks(user)
    # Resolve before the PDF is created; never silently emit an unmarked document
    # when its configured image is unavailable.
    marks.get(prefeitura_id)

    class MunicipalCanvas(Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.watermark_prefeitura_id = prefeitura_id

        def set_watermark_prefeitura(self, value):
            marks.get(value)
            self.watermark_prefeitura_id = value

        def showPage(self):
            marks.draw(self, self.watermark_prefeitura_id)
            super().showPage()

    return MunicipalCanvas
