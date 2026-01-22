import os
from email.mime.image import MIMEImage

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_single_no_delivery_email(
    to_email: str,
    name: str,
    pdf_content: bytes,
    filename: str,
    logo_path: str,
    contact_email: str,
    week: int,
    dag_label: str,
):
    subject = f"Niet-leverlijst (week {week} - {dag_label}) - Apotheek Jansen"
    from_email_formatted = f"Apotheek Jansen <{contact_email}>"

    html_body = f"""
    <p style="margin:0 0 18px 0;">Beste {name},</p>

    <p style="margin:0 0 12px 0;">
        In de bijlage vindt u de <strong>niet-leverlijst</strong> voor <strong>week {week}</strong> ({dag_label}).
        Het overzicht bevat per patiënt de geneesmiddelen die niet geleverd konden worden.
    </p>

    <p style="margin:0 0 12px 0;">
        Heeft u vragen naar aanleiding van dit bericht? Neem dan gerust contact op via
        <a href="mailto:{contact_email}" style="color:#072a72; font-weight:600;">{contact_email}</a>,
        bel 033-8700000 (optie 2) of reageer op deze e-mail.
    </p>

    <p style="margin:0 0 12px 0;">
        Met vriendelijke groet,<br>
        Het Apotheek Jansen Team
    </p>
    """

    footer_text = (
        "U ontvangt dit automatisch gegenereerde overzicht omdat er voor uw apotheek een "
        "niet-leverlijst is geregistreerd."
    )

    html_content = render_to_string(
        "includes/mail_base.html",
        {"content": html_body, "footer_text": footer_text},
    )

    text_content = (
        f"Beste {name},\n\n"
        f"In de bijlage vindt u de niet-leverlijst voor week {week} ({dag_label}).\n"
        "Het overzicht bevat per patiënt de geneesmiddelen die niet geleverd konden worden.\n\n"
        "Heeft u vragen? Neem contact op via "
        f"{contact_email}, bel 033-8700000 (optie 2) of reageer op deze e-mail.\n\n"
        "Met vriendelijke groet,\n"
        "Het Apotheek Jansen Team\n"
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email_formatted,
        to=[to_email],
        reply_to=[contact_email],
    )
    msg.attach_alternative(html_content, "text/html")

    if pdf_content:
        msg.attach(filename, pdf_content, "application/pdf")

    # Inline logo (CID:logo) - matcht <img src="cid:logo"> in mail_base.html
    if logo_path and os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_data = f.read()
        image = MIMEImage(logo_data)
        image.add_header("Content-ID", "<logo>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(image)

    msg.send()
