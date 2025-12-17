# core/utils/nazending_mail.py
import os
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from email.mime.image import MIMEImage

def send_single_nazending_email(to_email, name, pdf_content, filename, logo_path, contact_email):
    """
    Verstuurt 1 email naar 1 apotheek met PDF bijlage.
    """
    subject = "Overzicht Nazendingen - Apotheek Jansen"
    
    # 1. De soepele tekst
    # We gebruiken de naam van de apotheek en het contact emailadres
    html_body = f"""
      <p style="margin:0 0 18px 0;">Beste {name},</p>

      <p style="margin:0 0 12px 0;">
        Hierbij ontvangt u het actuele overzicht van de geneesmiddelen die momenteel in nazending zijn.
        Deze middelen kunnen wij helaas niet in de medicatierol leveren.
      </p>

      <p style="margin:0 0 12px 0;">
        In het overzicht vindt u per middel het eventuele alternatief en de verwachte datum dat het weer leverbaar is.
      </p>

      <p style="margin:0 0 12px 0;">
        Heeft u vragen naar aanleiding van dit overzicht? Neem dan gerust contact op via: 
        <a href="mailto:{contact_email}" style="color:#072a72; font-weight:600;">{contact_email}</a>.
      </p>

      <p style="margin:0 0 12px 0;">
        Met vriendelijke groet,<br>
        Het Apotheek Jansen Team
      </p>
    """
    
    # Render de 'wrapper' (header/footer van je huisstijl)
    html_content = render_to_string("includes/mail_base.html", {"content": html_body})

    # Plaintext fallback (voor mailclients zonder HTML)
    text_content = (
        f"Beste {name},\n\n"
        "Hierbij ontvangt u het actuele overzicht van de geneesmiddelen die momenteel in nazending zijn."
        "Deze middelen kunnen wij helaas niet in de medicatierol leveren.\n\n"
        "In het overzicht vindt u per middel het eventuele alternatief en de verwachte leverdatum.\n\n"
        f"Heeft u vragen? Neem contact op via: {contact_email}.\n\n"
        "Met vriendelijke groet,\n"
        "Het Apotheek Jansen Team"
    )

    # 2. Mail opbouwen
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    msg.attach_alternative(html_content, "text/html")

    # 3. PDF Bijlage
    msg.attach(filename, pdf_content, "application/pdf")

    # 4. Logo Inline (CID)
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_data = f.read()
        image = MIMEImage(logo_data)
        image.add_header("Content-ID", "<logo>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(image)

    msg.send()