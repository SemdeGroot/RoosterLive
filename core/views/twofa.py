# core/views/twofa.py
from two_factor.views import SetupView, QRGeneratorView
from django.urls import reverse
from two_factor.views.core import LoginView as TwoFALoginView
from two_factor.utils import get_otpauth_url, totp_digits
from core.forms import IdentifierAuthenticationForm, MyAuthenticationTokenForm, MyTOTPDeviceForm 
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.forms.utils import ErrorDict
from base64 import b32encode
from binascii import unhexlify
from base64 import b32encode
from binascii import unhexlify
from two_factor.utils import get_otpauth_url, totp_digits
from urllib.parse import quote, urlencode

class CustomSetupView(SetupView):
    condition_dict = {"welcome": False, "method": False}

    def get_success_url(self):
        return reverse("home")

    def get_form(self, step=None, **kwargs):
        form = super().get_form(step=step, **kwargs)
        if (step or self.steps.current) == "generator":
            field = form.fields.get("token")
            if field:
                field.label = _("6-cijferige code")
                field.widget.attrs.update({
                    "autofocus": "autofocus",
                    "inputmode": "numeric",
                    "autocomplete": "one-time-code",
                })
                field.error_messages.update({"required": _("Voer 6 cijfers in.")})
            if hasattr(form, "error_messages"):
                form.error_messages["invalid_token"] = _("De code klopt niet. Probeer het nog een keer.")
        return form

    def get_context_data(self, form=None, **kwargs):
        ctx = super().get_context_data(form=form, **kwargs)

        if self.steps.current == "generator":
            # 1) Secret uit context; reconstrueer als hij ontbreekt
            b32key = ctx.get("secret_key")
            if not b32key:
                key_hex = self.get_key("generator")
                rawkey = unhexlify(key_hex.encode("ascii"))
                b32key = b32encode(rawkey).decode("utf-8")

            # 2) Issuer + account (gewone spatie gebruiken)
            issuer  = "Jansen App"
            user    = getattr(self.request, "user", None)
            first   = ((getattr(user, "first_name", "") or "").strip())
            try:
                fallback = user.get_username()
            except Exception:
                fallback = getattr(user, "username", "")
            account = (first.capitalize() or fallback)

            # 3) Bouw otpauth-URI volgens de officiële TOTP-standaard (RFC 6238)
            label_enc = quote(f"{issuer}:{account}", safe=":")  # Dubbelpunt behouden
            query = urlencode(
                {
                    "secret": b32key,
                    "issuer": issuer,
                    "digits": totp_digits(),
                    "algorithm": "SHA1",
                    "period": 30,
                },
                quote_via=quote,  # gebruik %20 i.p.v. +
            )

            ctx["otpauth_url"] = f"otpauth://totp/{label_enc}?{query}"

        return ctx

    # Flash de (enige) error i.p.v. inline — verandert validatielogica niet
    def _flash_one_error(self, form):
        if not (form and form.is_bound and not form.is_valid()):
            return
        nf = list(form.non_field_errors())
        if nf:
            messages.error(self.request, nf[0])
        else:
            for _f, errs in getattr(form, 'errors', {}).items():
                if errs:
                    messages.error(self.request, errs[0])
                    break
        form._errors = ErrorDict()

    def render(self, form=None, **kwargs):
        self._flash_one_error(form)
        return super().render(form=form, **kwargs)


class CustomQRGeneratorView(QRGeneratorView):
    setup_view = CustomSetupView

    def get_issuer(self):
        return "Jansen\u00A0App"

    def get_username(self):
        user = getattr(self.request, "user", None)
        first = (getattr(user, "first_name", "") or "").strip()
        return first.capitalize() if first else super().get_username()
    
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