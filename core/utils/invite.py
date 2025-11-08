# core/utils/invite.py
import os
from email.mime.image import MIMEImage

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

token_generator = PasswordResetTokenGenerator()


def _origin_from_site_domain() -> str:
    raw = (getattr(settings, "SITE_DOMAIN", "") or "").strip().rstrip("/")
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    scheme = "https" if getattr(settings, "USE_HTTPS_IN_EMAIL_LINKS", False) else "http"
    return f"{scheme}://{raw}"


def build_set_password_link(user) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user)
    origin = _origin_from_site_domain()
    return f"{origin}/accounts/set-password/{uidb64}/{token}/"


def send_invite_email(user):
    link = build_set_password_link(user)
    display_name = (user.first_name or user.username or "").strip().title()
    subject = "Welkom bij de Jansen App – stel je wachtwoord in"

    # Pad naar je logo in de static map
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    # ---------- Plaintext (inhoud blijft 1-op-1) ----------
    text_content = (
        f"Hoi {display_name},\n\n"
        "Welkom bij de Apotheek Jansen App! Met deze (web)app bekijk je het actuele rooster, geef je je beschikbaarheid door, kunnen klanten de voorraad inzien en apothekers medicatiebeoordelingen uitvoeren. \n"
        "Stel hieronder je wachtwoord in. Omdat de app persoonlijke informatie bevat, "
        "vragen we je daarna 2-factor authenticatie te activeren.\n\n"
        f"Wachtwoord instellen: {link}\n\n"
        "De link is 3 dagen geldig en kan één keer worden gebruikt.\n\n"
        "Groetjes,\n"
        "Het Apotheek Jansen Team\n"
        "(dit is een no-reply e-mail)"
    )

    # ---------- HTML (alleen layout generiek via mail_base.html) ----------
    html_content_raw = f"""
      <p style="margin:0 0 18px 0;">Hoi <strong>{display_name}</strong>,</p>

      <p style="margin:0 0 12px 0;">
        Welkom bij de <strong>Apotheek Jansen App</strong>! Met deze (web)app bekijk je het actuele rooster, geef je je beschikbaarheid door, kunnen klanten de voorraad inzien en apothekers medicatiebeoordelingen uitvoeren.
      </p>

      <p style="margin:0 0 12px 0;">
        Stel hieronder je wachtwoord in. Omdat de app persoonlijke informatie bevat,
        vragen we je daarna 2-factor authenticatie te activeren.
      </p>

      <p style="margin:0 0 12px 0;">
        <a href="{link}"
           style="background:#072a72;color:#ffffff;text-decoration:none;font-weight:700;
                  padding:12px 20px;border-radius:6px;display:inline-block;">
          Wachtwoord instellen
        </a>
      </p>

      <p style="margin:0 0 18px 0;">
        De link is <strong>3 dagen</strong> geldig en kan één keer worden gebruikt.
      </p>

      <p style="margin:0 0 12px 0;">
        Groetjes,<br>
        Het Apotheek Jansen Team
      </p>
    """

    # Render de generieke layout met jouw eigen content
    html_content = render_to_string("includes/mail_base.html", {"content": html_content_raw})

    # ---------- Mail opbouwen ----------
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_content, "text/html")

    # Logo inline meesturen als image/attachment (CID: logo)
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_data = f.read()
        image = MIMEImage(logo_data)
        image.add_header("Content-ID", "<logo>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(image)

    msg.send()