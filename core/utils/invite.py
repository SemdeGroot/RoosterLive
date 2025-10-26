# core/utils/invite.py
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings

token_generator = PasswordResetTokenGenerator()

def build_set_password_link(user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user)
    scheme = "https" if getattr(settings, "USE_HTTPS_IN_EMAIL_LINKS", False) else "http"
    return f"{scheme}://{settings.SITE_DOMAIN}/accounts/set-password/{uidb64}/{token}/"

def send_invite_email(user):
    link = build_set_password_link(user)
    subject = "Stel je wachtwoord in"
    text = (
        f"Hi {user.first_name or ''},\n\n"
        f"Welkom! Klik op de volgende link om je wachtwoord in te stellen:\n{link}\n\n"
        f"De link is eenmalig en verloopt automatisch.\n"
        f"Groet!"
    )
    send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email])
