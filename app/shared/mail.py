"""Envio SMTP único e explícito (REPORT_SMTP_*). Sem fila nem reenvio automático."""

import re
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

_ADDRESS = re.compile(r"[^\s@<>;,\r\n]+@[^\s@<>;,\r\n]+\.[^\s@<>;,\r\n]+")


def available():
    return bool(current_app.config.get("REPORT_SMTP_HOST") and current_app.config.get("REPORT_SMTP_FROM"))


def valid_address(value):
    return isinstance(value, str) and len(value) <= 254 and bool(_ADDRESS.fullmatch(value))


def send(recipients, subject, body, attachments=()):
    """recipients: lista de e-mails; attachments: (bytes, nome, subtype) ex.: (pdf, 'x.pdf', 'pdf')."""
    if not available():
        raise ValueError("Envio por e-mail ainda não configurado (REPORT_SMTP_HOST/REPORT_SMTP_FROM).")
    recipients = [r for r in recipients if valid_address(r)]
    if not recipients:
        raise ValueError("Informe ao menos um endereço de e-mail válido.")
    message = EmailMessage()
    message["From"] = current_app.config["REPORT_SMTP_FROM"]
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)
    for content, filename, subtype in attachments:
        message.add_attachment(content, maintype="application", subtype=subtype, filename=filename)
    host = current_app.config["REPORT_SMTP_HOST"]
    port = int(current_app.config.get("REPORT_SMTP_PORT", 587))
    context = ssl.create_default_context()
    if port == 465:
        smtp = smtplib.SMTP_SSL(host, port, timeout=20, context=context)
    else:
        smtp = smtplib.SMTP(host, port, timeout=20)
    with smtp as conn:
        conn.ehlo()
        if port != 465:
            conn.starttls(context=context)
            conn.ehlo()
        if current_app.config.get("REPORT_SMTP_USERNAME"):
            conn.login(current_app.config["REPORT_SMTP_USERNAME"], current_app.config.get("REPORT_SMTP_PASSWORD", ""))
        refused = conn.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    return len(recipients)
