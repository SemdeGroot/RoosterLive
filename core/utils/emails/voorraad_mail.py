import os
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from email.mime.image import MIMEImage

def send_single_voorraad_email(to_email, name, html_bytes, filename, logo_path, contact_email):
    subject = "Overzicht Voorraad - Apotheek Jansen"
    from_email_formatted = f"Apotheek Jansen <{contact_email}>"

    html_body = f"""
      <p style="margin:0 0 18px 0;">Beste {name},</p>

      <p style="margin:0 0 12px 0;">
        Hierbij ontvangt u het actuele overzicht van de geneesmiddelen in onze Baxtervoorraad. Download het bestand en open het in uw browser om het overzicht te bekijken.
      </p>

      <p style="margin:0 0 12px 0;">
        Heeft u vragen? Neem contact op via:
        <a href="mailto:{contact_email}" style="color:#072a72; font-weight:600;">{contact_email}</a>
        of reageer direct op deze e-mail.
      </p>

      <p style="margin:0 0 12px 0;">
        Met vriendelijke groet,<br>
        Het Team van Apotheek Jansen
      </p>
    """

    footer_text = "U ontvangt dit automatisch gegenereerde overzicht omdat er een aanpassing is gedaan aan onze Baxtervoorraad."

    context = {"content": html_body, "footer_text": footer_text}
    html_content = render_to_string("includes/mail_base.html", context)

    text_content = (
        f"Beste {name},\n\n"
        "Hierbij ontvangt u het actuele overzicht van de Baxtervoorraad. Download het bestand en open het in uw browser om het overzicht te bekijken.\n\n"
        f"Heeft u vragen? Neem contact op via: {contact_email}.\n\n"
        "Met vriendelijke groet,\n"
        "Het Team van Apotheek Jansen"
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email_formatted,
        to=[to_email],
        reply_to=[contact_email],
    )
    msg.attach_alternative(html_content, "text/html")

    if html_bytes:
        msg.attach(filename, html_bytes, "text/html")

    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_data = f.read()
        image = MIMEImage(logo_data)
        image.add_header("Content-ID", "<logo>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(image)

    msg.send()
