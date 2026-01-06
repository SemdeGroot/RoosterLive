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
    subject = f"Overzicht Nazendingen - Apotheek Jansen"
    
    # De 'friendly' afzender naam
    from_email_formatted = f"Apotheek Jansen <{contact_email}>"
    
    # 1. De HTML Body
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
        <a href="mailto:{contact_email}" style="color:#072a72; font-weight:600;">{contact_email}</a>, 
        bel 033-8700000 (optie 2) of reageer direct op deze e-mail.
      </p>

      <p style="margin:0 0 12px 0;">
        Met vriendelijke groet,<br>
        Het Bestellingen Team van Apotheek Jansen
      </p>
    """
    
    # De footer tekst die in mail_base.html wordt getoond
    footer_text = "U ontvangt dit automatisch gegenereerde overzicht omdat er een aanpassing is doorgevoerd in de geneesmiddelen die bij ons in nazending zijn."

    # Render de 'wrapper' met de content en de aangepaste footer
    context = {
        "content": html_body,
        "footer_text": footer_text
    }
    html_content = render_to_string("includes/mail_base.html", context)

    # Plaintext fallback
    text_content = (
        f"Beste {name},\n\n"
        "Hierbij ontvangt u het actuele overzicht van de geneesmiddelen die momenteel in nazending zijn. "
        "Deze middelen kunnen wij helaas niet in de medicatierol leveren.\n\n"
        "In het overzicht vindt u per middel het eventuele alternatief en de verwachte datum dat het weer leverbaar is. \n\n"
        f"Heeft u vragen? Neem contact op via: {contact_email}, bel 033-8700000 (optie 2) of reageer op deze e-mail.\n\n"
        "Met vriendelijke groet,\n\n"
        "Het Bestellingen Team van Apotheek Jansen"
    )

    # 2. Mail opbouwen
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email_formatted,
        to=[to_email],
        reply_to=[contact_email],  # Zorgt dat replies altijd bij het juiste team komen
    )
    msg.attach_alternative(html_content, "text/html")

    # 3. PDF Bijlage
    # We forceren de mimetype op application/pdf
    if pdf_content:
        msg.attach(filename, pdf_content, "application/pdf")

    # 4. Logo Inline (CID)
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_data = f.read()
        image = MIMEImage(logo_data)
        # De Content-ID moet exact matchen met <img src="cid:logo"> in je mail_base.html
        image.add_header("Content-ID", "<logo>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(image)

    # 5. Verzenden
    msg.send()