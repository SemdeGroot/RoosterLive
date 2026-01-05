# core/utils/reset.py
import os
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from core.utils.emails.invite import build_set_password_link


def send_password_reset_email(user):
    """
    Verstuur een 'wachtwoord vergeten' e-mail met set-password link.
    Gebruikt dezelfde mail-base als invite.py (includes/mail_base.html).
    """
    reset_link = build_set_password_link(user) + "?reset=1"
    display_name = (user.first_name or user.username or "").strip().title()
    subject = "Wachtwoord opnieuw instellen – Apotheek Jansen App"

    # Plaintext
    text_content = (
        f"Hoi {display_name},\n\n"
        "Er is een verzoek ontvangen om je wachtwoord opnieuw in te stellen.\n"
        "Gebruik onderstaande link om een nieuw wachtwoord te kiezen.\n\n"
        f"Wachtwoord opnieuw instellen: {reset_link}\n\n"
        "Na het instellen log je in met je nieuwe wachtwoord.\n\n"
        "Heb je dit verzoek niet zelf gedaan? Negeer dan deze e-mail.\n\n"
        "Groetjes,\n"
        "Het Apotheek Jansen Team"
    )

    # HTML
    html_content_raw = f"""
      <p>Hoi <strong>{display_name}</strong>,</p>
      <p>Er is een verzoek ontvangen om je wachtwoord opnieuw in te stellen.</p>
      <p>
        Klik hieronder om een nieuw wachtwoord te kiezen. 
        Na het instellen log je in met je nieuwe wachtwoord.
      </p>
      <p>
        <a href="{reset_link}"
           style="background:#072a72;color:#ffffff;text-decoration:none;font-weight:700;
                  padding:12px 20px;border-radius:6px;display:inline-block;
                  font-size:14px;line-height:18px;min-width:220px;text-align:center;">
          Wachtwoord opnieuw instellen
        </a>
      </p>
      <p>Heb je dit verzoek niet zelf gedaan? Negeer dan deze e-mail.</p>
      <p>Groetjes,<br>Het Apotheek Jansen Team</p>
    """
    html_content = render_to_string("includes/mail_base.html", {"content": html_content_raw})

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_content, "text/html")

    # Inline logo (zelfde pad als invite.py)
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            img = MIMEImage(f.read())
        img.add_header("Content-ID", "<logo>")
        img.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(img)

    msg.send()
