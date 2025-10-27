# core/views/twofa.py
from two_factor.views import SetupView, QRGeneratorView
from django.urls import reverse
from two_factor.views.core import LoginView as TwoFALoginView
from two_factor.forms import AuthenticationTokenForm, BackupTokenForm# jouw bestaande classes
from core.forms import IdentifierAuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import logout
from django.shortcuts import redirect


class CustomSetupView(SetupView):
    condition_dict = {"welcome": False, "method": False}

    def get(self, request, *args, **kwargs):
        self.storage.current_step = "generator"
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.storage.current_step in (None, "welcome", "method"):
            self.storage.current_step = "generator"
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("home")


class CustomQRGeneratorView(QRGeneratorView):
    """Gebruik 'Jansen App' als issuer en de voornaam als accountnaam."""

    def get_issuer(self):
        # Non-breaking space zodat Google Auth geen '+' toont
        return "Jansen\u00A0App"

    def get_username(self):
        user = getattr(self.request, "user", None)
        # Gebruik voornaam (gecapitaliseerd) als die er is
        first = (getattr(user, "first_name", "") or "").strip()
        if first:
            return first.capitalize()
        # Fallback: standaard gedrag (username/e-mail)
        return super().get_username()
    
class CustomLoginView(TwoFALoginView):
    """
    Two-factor login met eigen auth-form die ook first_name en e-mail ondersteunt.
    """
    # Gebruik dezelfde stapnamen als parent:
    # AUTH_STEP = "auth"; TOKEN_STEP = "token"; BACKUP_STEP = "backup"
    form_list = (
        (TwoFALoginView.AUTH_STEP, IdentifierAuthenticationForm),
        (TwoFALoginView.TOKEN_STEP, AuthenticationTokenForm),
        (TwoFALoginView.BACKUP_STEP, BackupTokenForm),
    )

@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect(reverse("two_factor:login"))