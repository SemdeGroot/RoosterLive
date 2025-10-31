# core/views/twofa.py
from two_factor.views import SetupView, QRGeneratorView
from django.urls import reverse
from two_factor.views.core import LoginView as TwoFALoginView
from core.forms import IdentifierAuthenticationForm, MyAuthenticationTokenForm, MyTOTPDeviceForm 
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.forms.utils import ErrorDict

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

    # >>> Belangrijk: zet in de SETUP-wizard de 'generator' stap op jouw form
    def get_form_list(self):
        form_list = super().get_form_list()
        if 'generator' in form_list:
            form_list['generator'] = MyTOTPDeviceForm
        return form_list

    # Toon maximaal 1 flash en maak inline errors stil
    def _flash_one_error(self, form):
        if not (form and form.is_bound and not form.is_valid()):
            return
        # Pak eerst non-field errors (onze form produceert alleen non-field)
        nf = list(form.non_field_errors())
        if nf:
            messages.error(self.request, nf[0])
        else:
            # Fallback: eerste field error (zou normaliter niet gebeuren met onze form)
            for _f, errs in getattr(form, 'errors', {}).items():
                if errs:
                    messages.error(self.request, errs[0])
                    break
        form._errors = ErrorDict()

    def render(self, form=None, **kwargs):
        self._flash_one_error(form)
        return super().render(form=form, **kwargs)


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
        (TwoFALoginView.TOKEN_STEP, MyAuthenticationTokenForm),
    )

    def has_backup_step(self):
        return False

    def get_form(self, step=None, **kwargs):
        current = step or self.steps.current
        if current == self.TOKEN_STEP:
            self.form_list[self.TOKEN_STEP] = MyAuthenticationTokenForm

        # Belangrijk: direct de wizard-form ophalen (zorgt voor binden), niet de override die je form vervangt
        from two_factor.views.utils import IdempotentSessionWizardView
        form = IdempotentSessionWizardView.get_form(self, step=step, **kwargs)

        if getattr(self, "show_timeout_error", False):
            messages.error(self.request, _("Je sessie is verlopen. Log opnieuw in."))
            self.show_timeout_error = False
            form._errors = ErrorDict()
        return form

    def _flash_form_errors(self, form):
        if not (form and form.is_bound and not form.is_valid()):
            return
        # Alleen non-field errors fl itsen (onze MyAuthenticationTokenForm geeft enkel non-field)
        for msg in form.non_field_errors():
            messages.error(self.request, msg)
        form._errors = ErrorDict()

    def render(self, form=None, **kwargs):
        self._flash_form_errors(form)

        if self.steps.current == self.TOKEN_STEP:
            form_with_errors = form and form.is_bound and bool(form.errors)
            if not form_with_errors:
                self.get_device().generate_challenge()

        return super().render(form=form, **kwargs)
    
@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Je bent uitgelogd.")
    return redirect(reverse("two_factor:login"))