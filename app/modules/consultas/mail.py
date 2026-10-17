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
    message = EmailMessage()
    message['From'] = current_app.config['REPORT_SMTP_FROM']; message['To'] = recipient
    message['Subject'] = 'IJA System — consulta personalizada'
    message.set_content('Segue a consulta solicitada no IJA System. Os critérios e a data de geração constam no arquivo.')
    message.add_attachment(content, maintype='application', subtype='pdf', filename='consulta.pdf')
    if len(content) > 10*1024*1024: raise ValueError('O PDF excede 10 MB. Restrinja os filtros para enviar por e-mail.')
    host = current_app.config['REPORT_SMTP_HOST']; port = int(current_app.config.get('REPORT_SMTP_PORT',587))
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.ehlo(); smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
        if current_app.config.get('REPORT_SMTP_USERNAME'):
            smtp.login(current_app.config['REPORT_SMTP_USERNAME'], current_app.config.get('REPORT_SMTP_PASSWORD',''))
        refused = smtp.send_message(message)
        if refused: raise smtplib.SMTPRecipientsRefused(refused)
