"""Envio SMTP único e explícito (REPORT_SMTP_*). Sem fila nem reenvio automático."""

import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from html import escape

from flask import current_app, has_request_context, request

_ADDRESS = re.compile(r"[^\s@<>;,\r\n]+@[^\s@<>;,\r\n]+\.[^\s@<>;,\r\n]+")


def available():
    return bool(current_app.config.get("REPORT_SMTP_HOST") and current_app.config.get("REPORT_SMTP_FROM"))


def valid_address(value):
    return isinstance(value, str) and len(value) <= 254 and bool(_ADDRESS.fullmatch(value))


def base_url():
    configured = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if configured:
        return configured
    if has_request_context():
        return request.url_root.rstrip("/")
    return "https://www.system.oceanoazuldrones.com.br"


def render_html(*, title, intro, lines=(), cta_text=None, cta_url=None, footer_note=None, eyebrow="Vigilância em Saúde"):
    """E-mail institucional (Oceano Azul · IJA): cabeçalho no gradiente do portal, cartão branco, botão de ação."""
    base = base_url()
    logo = f"{base}/static/img/logo_oceano_azul_light.png"
    items = "".join(
        f'<tr><td style="padding:6px 0;color:#718096;font-size:13px;width:140px">{escape(str(k))}</td>'
        f'<td style="padding:6px 0;color:#1c2b3f;font-size:14px;font-weight:500">{escape(str(v))}</td></tr>'
        for k, v in lines if v not in (None, ""))
    button = (f'<a href="{escape(cta_url)}" style="display:inline-block;background:#087088;color:#ffffff;text-decoration:none;'
              f'font-weight:600;font-size:15px;padding:14px 28px;border-radius:12px">{escape(cta_text)}</a>') if cta_text and cta_url else ""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!doctype html><html lang="pt-BR"><body style="margin:0;background:#f4f7f9;font-family:Poppins,'Segoe UI',Arial,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f7f9;padding:24px 12px"><tr><td align="center">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%">
<tr><td style="background:#061827;background-image:linear-gradient(135deg,#061827 0%,#083348 48%,#087088 100%);border-radius:16px 16px 0 0;padding:28px 32px">
  <img src="{logo}" alt="Oceano Azul" width="170" style="display:block;max-width:170px;height:auto;margin-bottom:18px">
  <div style="color:#9ef4ff;font-size:12px;letter-spacing:.12em;text-transform:uppercase;font-weight:600">{escape(eyebrow)}</div>
  <div style="color:#ffffff;font-size:22px;font-weight:600;line-height:1.3;margin-top:6px">{escape(title)}</div>
</td></tr>
<tr><td style="background:#ffffff;padding:28px 32px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0">
  <p style="margin:0 0 18px;color:#2d3748;font-size:15px;line-height:1.6">{escape(intro)}</p>
  {'<table role="presentation" cellspacing="0" cellpadding="0" style="width:100%;border-top:1px solid #e8f8fb;border-bottom:1px solid #e8f8fb;margin:4px 0 22px">' + items + '</table>' if items else ''}
  {button}
</td></tr>
<tr><td style="background:#f7fcfd;border:1px solid #e2e8f0;border-top:0;border-radius:0 0 16px 16px;padding:18px 32px;color:#718096;font-size:12px;line-height:1.6">
  {escape(footer_note) + '<br>' if footer_note else ''}Mensagem automática do IJA System · Oceano Azul · IJA Drones. Não responda a este e-mail.<br>Enviado em {now}.
</td></tr>
</table></td></tr></table></body></html>"""


def send(recipients, subject, body, attachments=(), html=None):
    """recipients: lista de e-mails; attachments: (bytes, nome, subtype) ex.: (pdf, 'x.pdf', 'pdf'); html: versão rica opcional."""
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
    if html:
        message.add_alternative(html, subtype="html")
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
