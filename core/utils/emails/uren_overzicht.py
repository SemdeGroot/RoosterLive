# core/utils/emails/uren_overzicht.py
import os
from datetime import date

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from email.mime.image import MIMEImage


XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def send_uren_overzicht_email(
    *,
    to_email: str,
    month_first: date,
    xlsx_content: bytes,
    filename: str,
    contact_email: str,
    logo_path: str | None = None,
):
    subject = f"Urenoverzicht {month_first.strftime('%Y-%m')} - Apotheek Jansen"
    from_email_formatted = contact_email

    html_body = f"""
      <p style="margin:0 0 18px 0;">Beste Roel,</p>

      <p style="margin:0 0 12px 0;">
        In de bijlage vind je het urenoverzicht voor <b>{month_first.strftime('%m-%Y')}</b>.
      </p>

      <p style="margin:0 0 12px 0;">
        Dit overzicht is automatisch gegenereerd op basis van de doorgegeven uren.
      </p>

      <p style="margin:0 0 12px 0;">
        Met vriendelijke groet,<br>
        Apotheek Jansen
      </p>
    """

    footer_text = "U ontvangt dit automatisch gegenereerde overzicht op de 11e van de maand."

    context = {
        "content": html_body,
        "footer_text": footer_text,
    }
    html_content = render_to_string("includes/mail_base.html", context)

    text_content = (
        "Beste Roel,\n\n"
        f"In de bijlage vind je het urenoverzicht voor {month_first.strftime('%m-%Y')}.\n\n"
        "Met vriendelijke groet,\n"
        "Apotheek Jansen\n"
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email_formatted,
        to=[to_email],
        reply_to=[contact_email],
    )
    msg.attach_alternative(html_content, "text/html")

    if xlsx_content:
        msg.attach(filename, xlsx_content, XLSX_MIMETYPE)

    if logo_path and os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_data = f.read()
        image = MIMEImage(logo_data)
        image.add_header("Content-ID", "<logo>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(image)

    msg.send()