# core/utils/emails/birthday_email.py
import os
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from email.mime.image import MIMEImage

def send_birthday_email(to_email, first_name):
    """
    Verstuurt een verjaardagsmail naar een medewerker.
    """
    # Zorg dat de voornaam met een hoofdletter begint
    display_name = (first_name or "").strip().capitalize() or "Collega"
    
    subject = f"Gefeliciteerd met je verjaardag, {display_name}!"
    
    # Gebruik DEFAULT_FROM_EMAIL vanuit settings.py
    from_email = settings.DEFAULT_FROM_EMAIL
    
    # Logo pad bepalen
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    # 1. De HTML Body
    html_body = f"""
      <p style="margin:0 0 18px 0;">Beste {display_name},</p>
      <p style="margin:0 0 12px 0;">Van harte gefeliciteerd met je verjaardag!</p>
      <p style="margin:24px 0 12px 0;">Wij wensen je een geweldige dag toe!</p>
      <p style="margin:24px 0 12px 0;">Met vriendelijke groet,<br>Het Apotheek Jansen Team</p>
    """
    
    footer_text = "U ontvangt deze e-mail omdat u deel uitmaakt van Apotheek Jansen en vandaag jarig bent volgens ons systeem."

    context = {
        "content": html_body,
        "footer_text": footer_text
    }
    html_content = render_to_string("includes/mail_base.html", context)

    # Plaintext fallback
    text_content = (
        f"Beste {display_name},\n\n"
        f"Van harte gefeliciteerd met je verjaardag!\n\n"
        "Wij wensen je een geweldige dag toe!\n\n"
        "Met vriendelijke groet,\nHet Apotheek Jansen Team"
    )

    # 2. Mail opbouwen
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[to_email],
    )
    msg.attach_alternative(html_content, "text/html")

    # 3. Logo Inline (CID)
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            image = MIMEImage(f.read())
        image.add_header("Content-ID", "<logo>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(image)

    # 4. Verzenden
    msg.send()
