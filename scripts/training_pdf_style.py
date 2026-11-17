"""Identidade compartilhada dos guias da Central de Treinamentos.

Reproduz a tipografia e as cores do guia de Edição protegida. Este módulo
desenha somente documentos; não importa a aplicação nem acessa o banco.
"""
from pathlib import Path
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph

WIDTH, HEIGHT = 595.2756, 841.8898
MARGIN = 38
CONTENT = WIDTH - 2 * MARGIN
INK = colors.HexColor('#12344a')
ACCENT = colors.HexColor('#008ea4')
MUTED = colors.HexColor('#52697f')
SOFT = colors.HexColor('#eef6fa')
TEAL_SOFT = colors.HexColor('#e8f6f5')
LINE = colors.HexColor('#d5e3ea')


def register_fonts():
    candidates = [Path(os.environ.get('TRAINING_FONT_DIR', '/nonexistent')),
                  Path('/usr/share/fonts/truetype/dejavu'),
                  Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype']
    directory = next((p for p in candidates if (p / 'DejaVuSans.ttf').is_file()
                      and (p / 'DejaVuSans-Bold.ttf').is_file()), None)
    if directory is None:
        raise RuntimeError('Defina TRAINING_FONT_DIR para a pasta com DejaVuSans.ttf e DejaVuSans-Bold.ttf.')
    for name, filename in (('Training', 'DejaVuSans.ttf'), ('Training-Bold', 'DejaVuSans-Bold.ttf')):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, directory / filename))
    pdfmetrics.registerFontFamily('Training', normal='Training', bold='Training-Bold', italic='Training', boldItalic='Training-Bold')


def paragraph(value, width=CONTENT, size=10, leading=15, bold=False, color=INK):
    style = ParagraphStyle('training', fontName='Training-Bold' if bold else 'Training',
                           fontSize=size, leading=leading, textColor=color,
                           alignment=TA_LEFT, splitLongWords=False)
    p = Paragraph(escape(str(value)).replace('\n', '<br/>'), style)
    _, height = p.wrap(width, HEIGHT)
    return p, height


def text(canvas, value, x, top, width=CONTENT, size=10, leading=15, bold=False, color=INK):
    p, height = paragraph(value, width, size, leading, bold, color)
    p.drawOn(canvas, x, top - height)
    return top - height


def panel(canvas, title, body, x, top, width=CONTENT, background=SOFT):
    _, th = paragraph(title, width-24, 10.5, 15, True, ACCENT)
    _, bh = paragraph(body, width-24, 10, 15)
    height = 26 + th + bh
    canvas.setFillColor(background)
    canvas.roundRect(x, top-height, width, height, 9, fill=1, stroke=0)
    y = text(canvas, title, x+12, top-11, width-24, 10.5, 15, True, ACCENT)
    text(canvas, body, x+12, y-4, width-24, 10, 15)
    return top-height


def chrome(canvas, page, total, date_label='17 NOV 2026'):
    canvas.setFillColor(ACCENT)
    canvas.rect(0, HEIGHT-8, WIDTH, 8, fill=1, stroke=0)
    text(canvas, 'IJA SYSTEM / GUIA DA FUNCIONALIDADE', MARGIN, HEIGHT-27,
         350, 8, 11, True, ACCENT)
    canvas.setFont('Training', 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(WIDTH-MARGIN, HEIGHT-35, date_label)
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN, 52, WIDTH-MARGIN, 52)
    text(canvas, 'IJA DRONES  |  OCEANO AZUL', MARGIN, 40, 350, 8, 11, True)
    text(canvas, 'Central de Treinamentos', MARGIN, 25, 350, 7.5, 10, color=MUTED)
    canvas.setFont('Training', 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(WIDTH-MARGIN, 32, f'{page} / {total}')


def heading(canvas, eyebrow, title, subtitle=None):
    y = text(canvas, eyebrow.upper(), MARGIN, HEIGHT-62, size=8.5, leading=12, bold=True, color=ACCENT)
    y = text(canvas, title, MARGIN, y-13, size=25, leading=31, bold=True)
    if subtitle:
        y = text(canvas, subtitle, MARGIN, y-10, size=10.8, leading=16, color=MUTED)
    return y-18
