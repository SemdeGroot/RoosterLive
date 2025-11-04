# core/views/account.py
from django.contrib.auth.views import PasswordResetConfirmView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django_otp import devices_for_user
from django.contrib import messages
from django.utils.translation import gettext as _

def _has_confirmed_2fa(user) -> bool:
    for d in devices_for_user(user, confirmed=True):
        return True
    return False

class CustomPasswordConfirmView(PasswordResetConfirmView):
    template_name = "accounts/set_password.html"
    success_url = reverse_lazy("two_factor:setup")

    post_reset_login = True
    post_reset_login_backend = "django.contrib.auth.backends.ModelBackend"

    def dispatch(self, request, *args, **kwargs):
        uidb64 = kwargs.get("uidb64")
        link_user = self.get_user(uidb64)  # kan None zijn (vreemde uid)

        # ✅ Alleen redirecten als de target user al een bruikbaar wachtwoord heeft.
        if link_user and link_user.has_usable_password():
            # Zelfde user met actieve sessie?
            if request.user.is_authenticated and request.user.pk == link_user.pk:
                # forceer 2FA-setup zolang die nog niet rond is
                if not _has_confirmed_2fa(request.user):
                    return redirect(reverse("two_factor:setup"))
                return redirect(reverse("home"))
            # Andere/geen sessie → eerst inloggen
            messages.info(request, _("Je wachtwoord is al ingesteld. Log in om verder te gaan."))
            return redirect(reverse("two_factor:login"))

        # ❗ Wachtwoord nog niet gezet → ALTIJD form tonen (geen pre-token-check!)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # Laat de parent validatie doen → zet self.validlink
        response = super().get(request, *args, **kwargs)
        # Ongeldige of verbruikte token? Dan pas naar login
        if not getattr(self, "validlink", False):
            messages.error(request, _("Deze link is ongeldig of al gebruikt. Log in om verder te gaan."))
            return redirect(reverse("two_factor:login"))
        return response

    def get_success_url(self):
        # Na succesvol instellen + autologin → dwing 2FA setup totdat die rond is
        user = getattr(self.request, "user", None)
        if user and user.is_authenticated and not _has_confirmed_2fa(user):
            return reverse("two_factor:setup")
        return reverse("home")