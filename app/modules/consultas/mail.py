"""Explicit send only: no background retry after uncertain SMTP delivery."""
from email.message import EmailMessage
import re
import smtplib
import ssl
from flask import current_app


def available():
    return bool(current_app.config.get('REPORT_SMTP_HOST') and current_app.config.get('REPORT_SMTP_FROM'))


def validate_recipient(recipient):
    if not isinstance(recipient, str) or len(recipient) > 254 or not re.fullmatch(r'[^\s@<>;,\r\n]+@[^\s@<>;,\r\n]+\.[^\s@<>;,\r\n]+', recipient):
        raise ValueError('Informe um único endereço de e-mail válido.')
    return recipient


def send_report(recipient, content):
    if not available(): raise ValueError('Envio por e-mail ainda não configurado. Use PDF ou Excel.')
    validate_recipient(recipient)
    if len(content) > 10*1024*1024: raise ValueError('O PDF excede 10 MB. Restrinja os filtros para enviar por e-mail.')
    from app.shared import mail
    html = mail.render_html(title='Consulta personalizada', eyebrow='Relatório',
                            intro='Segue em anexo (PDF) a consulta solicitada no IJA System. Os critérios e a data de geração constam no arquivo.',
                            lines=[('Arquivo', 'consulta.pdf'), ('Tamanho', f'{len(content) / 1024:.0f} KB')],
                            cta_text='Abrir consultas no IJA System', cta_url=f'{mail.base_url()}/relatorios/consultas')
    mail.send([recipient], 'IJA System — consulta personalizada',
              'Segue a consulta solicitada no IJA System. Os critérios e a data de geração constam no arquivo.',
              attachments=[(content, 'consulta.pdf', 'pdf')], html=html)
