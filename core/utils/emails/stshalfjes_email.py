# core/utils/emails/stshalfjes_email.py
import os
from email.mime.image import MIMEImage

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from typing import Iterable
from core.models import STSHalfje

def delete_stshalfjes_by_ids(item_ids: Iterable[int]) -> int:
    """
    Verwijdert STSHalfje regels op basis van IDs.
    Retourneert het aantal verwijderde rows.
    """
    ids = [int(i) for i in item_ids if str(i).isdigit()]
    if not ids:
        return 0
    deleted, _ = STSHalfje.objects.filter(id__in=ids).delete()
    return deleted

def send_single_stshalfjes_email(
    to_email: str,
    name: str,  # <-- org.name (apotheeknaam)
    pdf_content: bytes,
    filename: str,
    logo_path: str,
    contact_email: str,
):
    """
    Verstuurt 1 e-mail naar 1 apotheek met PDF bijlage:
    Overzicht 'geneesmiddelen die onnodig gehalveerd worden' (alleen items van die apotheek).
    """

    subject = "Overzicht geneesmiddelen die onnodig gehalveerd worden - Apotheek Jansen"
    from_email_formatted = f"Apotheek Jansen <{contact_email}>"

    html_body = f"""
    <p style="margin:0 0 18px 0;">Beste {name},</p>

    <p style="margin:0 0 12px 0;">
        In de bijlage vindt u het actuele overzicht van geneesmiddelen waarvan is geconstateerd dat ze <strong>onnodig gehalveerd worden</strong> in de medicatierol. In het overzicht staat per melding het beschikbare alternatief
        vermeld dat u bij ons kunt bestellen.
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
    "U ontvangt dit automatisch gegenereerde overzicht omdat er voor uw apotheek meldingen zijn geregistreerd "
    "van geneesmiddelen die mogelijk onnodig gehalveerd worden."
    )

    html_content = render_to_string(
        "includes/mail_base.html",
        {"content": html_body, "footer_text": footer_text},
    )

    text_content = (
        f"Beste {name},\n\n"
        "In de bijlage vindt u het actuele overzicht van geneesmiddelen waarvan is geconstateerd dat ze "
        "onnodig gehalveerd worden in de medicatierol. In het overzicht staat per melding het beschikbare alternatief vermeld "
        "dat u bij ons kunt bestellen.\n\n"
        "Heeft u vragen naar aanleiding van dit bericht? Neem dan gerust contact op via "
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

    # Inline logo (CID:logo) - moet matchen met <img src="cid:logo"> in mail_base.html
    if logo_path and os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_data = f.read()
        image = MIMEImage(logo_data)
        image.add_header("Content-ID", "<logo>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(image)

    msg.send()
