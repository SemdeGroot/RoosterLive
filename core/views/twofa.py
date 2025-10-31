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
from django.contrib import messages


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
    form_list = (
        (TwoFALoginView.AUTH_STEP, IdentifierAuthenticationForm),
        (TwoFALoginView.TOKEN_STEP, AuthenticationTokenForm),
        (TwoFALoginView.BACKUP_STEP, BackupTokenForm),
    )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # 1) GET
        is_get = (self.request.method == "GET")
        # 2) eerste stap van de wizard
        on_first_step = (self.steps.current == self.AUTH_STEP)
        # 3) geen form-errors
        has_errors = False
        form = ctx.get('form')
        if form is not None and hasattr(form, 'errors'):
            has_errors = bool(form.errors)
        # 4) geen messages (zoals na logout)
        has_messages = any(messages.get_messages(self.request))

        ctx["show_splash"] = (is_get and on_first_step and not has_errors and not has_messages)
        return ctx

@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Je bent uitgelogd.")
    return redirect(reverse("two_factor:login"))