import os
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from email.mime.image import MIMEImage

def send_laatste_pot_email(to_email, first_name, item_naam):
    """
    Verstuurt een e-mail naar een medewerker wanneer een laatste pot is aangebroken.
    """
    # Zorg dat de voornaam met een hoofdletter begint
    display_name = (first_name or "").strip().capitalize() or "Collega"
    
    subject = f"Laatste pot aangebroken - {item_naam}"
    
    # Gebruik DEFAULT_FROM_EMAIL vanuit settings.py
    from_email = settings.DEFAULT_FROM_EMAIL
    
    # Logo pad bepalen (gelijk aan nazendingen)
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    # 1. De HTML Body met de gecapitaliseerde naam
    html_body = f"""
      <p style="margin:0 0 18px 0;">Beste {display_name},</p>

      <p style="margin:0 0 12px 0;">
        Er is zojuist een melding gemaakt in de app dat de <strong>laatste pot</strong> van het volgende geneesmiddel is aangebroken:
      </p>

      <p style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #072a72; font-size: 1.1em; margin: 18px 0;">
        <strong>{item_naam}</strong>
      </p>

      <p style="margin:0 0 12px 0;">
        Controleer de voorraad en de lopende bestellingen om te voorkomen dat dit middel niet meer geleverd kan worden in de medicatierol.
      </p>

      <p style="margin:24px 0 12px 0;">
        Met vriendelijke groet,<br>
        de Baxter Medewerkers
      </p>
    """
    
    footer_text = "U ontvangt deze e-mail omdat u de rechten heeft om bestellingen te beheren."

    context = {
        "content": html_body,
        "footer_text": footer_text
    }
    html_content = render_to_string("includes/mail_base.html", context)

    # Plaintext fallback
    text_content = (
        f"Beste {display_name},\n\n"
        f"Er is een melding gemaakt dat de laatste pot van {item_naam} is aangebroken.\n\n"
        "Controleer de voorraad en bestellingen.\n\n"
        "Met vriendelijke groet,\nde Baxter Medewerkers"
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