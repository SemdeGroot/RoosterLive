# core/utils/emails/urenreminder.py
import os
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from email.mime.image import MIMEImage

def send_uren_reminder_email(to_email, first_name, reminder_date):
    """
    Verstuur een herinnering per e-mail naar de gebruiker om hun uren door te geven.
    """
    # Zorg ervoor dat de voornaam met een hoofdletter begint
    display_name = (first_name or "").strip().capitalize() or "Collega"
    
    subject = f"Herinnering: Uren doorgeven voor {reminder_date.strftime('%B %Y')}"
    
    # Gebruik DEFAULT_FROM_EMAIL vanuit settings.py
    from_email = settings.DEFAULT_FROM_EMAIL
    
    # Logo pad bepalen
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    # 1. De HTML Body met de gecapitaliseerde naam
    html_body = f"""
      <p style="margin:0 0 18px 0;">Beste {display_name},</p>

      <p style="margin:0 0 12px 0;">
        Dit is een herinnering dat u nog geen uren heeft doorgegeven voor <strong>{reminder_date.strftime('%B %Y')}</strong>, terwijl er wel diensten voor u zijn geregistreerd in deze periode.
      </p>

      <p style="margin:0 0 12px 0;">
        Vergeet niet om je uren in te dienen via de app om ervoor te zorgen dat je tijdig wordt vergoed.
      </p>

      <p style="margin:24px 0 12px 0;">
        Met vriendelijke groet,<br>
        Het Apotheek Jansen Team
      </p>
    """
        
    footer_text = (
        "Deze e-mail is verstuurd omdat u nog geen uren heeft doorgegeven, "
        "terwijl er wel diensten voor u geregistreerd staan in de afgelopen maand. "
        "Als u vragen heeft, neem dan contact op met de beheerder. "
        "Dit is een automatische e-mail, antwoorden op dit bericht worden niet gelezen."
    )

    context = {
        "content": html_body,
        "footer_text": footer_text
    }
    html_content = render_to_string("includes/mail_base.html", context)

    # Plaintext fallback
    text_content = (
        f"Beste {display_name},\n\n"
        f"Dit is een herinnering dat je nog geen uren hebt doorgegeven voor {reminder_date.strftime('%B %Y')}, terwijl er wel diensten voor u zijn geregistreerd in deze periode.\n\n"
        "Vergeet niet om je uren in te dienen via de app.\n\n"
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