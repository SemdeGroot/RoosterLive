# core/views/twofa.py
from two_factor.views import SetupView, QRGeneratorView
from django.urls import reverse
from two_factor.views.core import LoginView as TwoFALoginView
from two_factor.utils import get_otpauth_url, totp_digits
from core.forms import IdentifierAuthenticationForm, MyAuthenticationTokenForm, MyTOTPDeviceForm
from django.http import HttpRequest 
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import logout, login as auth_login, get_user_model
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.forms.utils import ErrorDict
from django.conf import settings
from base64 import b32encode
from binascii import unhexlify
from base64 import b32encode
from binascii import unhexlify
from two_factor.utils import get_otpauth_url, totp_digits
from urllib.parse import quote, urlencode
from urllib.parse import quote as urlquote  # voor veilige next= urls
from core.models import WebAuthnPasskey, StandaardInlog, NativeBiometricDevice
from core.utils.network import is_in_pharmacy_network
from core.views._helpers import is_mobile_request

from django.contrib.auth import login, get_user_model
from core.models import StandaardInlog

def is_capacitor_request(request):
    # werkt bij POST (login submit)
    if request.method == "POST" and request.POST.get("is_capacitor") == "1":
        return True

    # optioneel: ook bij GET (handig op setup pagina's)
    if request.GET.get("is_capacitor") == "1":
        return True

    return False

def biometric_capable_request(request):
    if request.method == "POST":
        v = request.POST.get("biometric_capable")
        if v in ("0", "1"):
            request.session["biometric_capable"] = (v == "1")
    return bool(request.session.get("biometric_capable"))


class CustomSetupView(SetupView):
    # Geen welkomst- en methodestap
    condition_dict = {"welcome": False, "method": False}

    def get_success_url(self):
        user = self.request.user
        next_url = reverse("home")

        # Geen passkey prompt na 2FA-setup op desktop
        if not is_mobile_request(self.request):
            return next_url

        has_passkey = WebAuthnPasskey.objects.filter(user=user).exists()
        if not has_passkey:
            setup_url = reverse("passkey_setup")
            return f"{setup_url}?next={urlquote(next_url)}"

        return next_url

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
                field.error_messages.update(
                    {"required": _("Voer 6 cijfers in.")}
                )
            if hasattr(form, "error_messages"):
                form.error_messages["invalid_token"] = _(
                    "De code klopt niet. Probeer het nog een keer."
                )
        return form

    # Eén foutmelding “flitsen”, validatie blijft package-default
    def _flash_one_error(self, form):
        if not (form and form.is_bound and not form.is_valid()):
            return
        nf = list(form.non_field_errors())
        if nf:
            messages.error(self.request, nf[0])
        else:
            for _f, errs in getattr(form, "errors", {}).items():
                if errs:
                    messages.error(self.request, errs[0])
                    break
        form._errors = ErrorDict()

    def get_context_data(self, form=None, **kwargs):
        ctx = super().get_context_data(form=form, **kwargs)

        if self.steps.current == "generator":
            b32key = ctx.get("secret_key")

            if b32key:
                user = self.request.user
                first = (getattr(user, "first_name", "") or "").strip()

                # Issuer: altijd "Jansen/u8000/app"
                issuer = "Jansen\u00A0App"
                # Username: first_name van de gebruiker
                username = first.capitalize() if first else "Unknown"

                ctx["otpauth_url"] = get_otpauth_url(
                    accountname=username,
                    secret=b32key,
                    issuer=issuer,
                    digits=totp_digits(),
                )
                ctx["issuer"] = issuer
                ctx["username"] = username

        return ctx

    def render(self, form=None, **kwargs):
        self._flash_one_error(form)
        return super().render(form=form, **kwargs)

class CustomQRGeneratorView(QRGeneratorView):
    setup_view = CustomSetupView

    def get_issuer(self):
        # Issuer = Jansen/u8000/app (vast)
        return "Jansen\u00A0App"

    def get_username(self):
        # Username = first_name van de gebruiker
        user = getattr(self.request, "user", None)
        first = (getattr(user, "first_name", "") or "").strip()
        return first.capitalize() if first else "Unknown"
    
class CustomLoginView(TwoFALoginView):
    form_list = (
        (TwoFALoginView.AUTH_STEP, IdentifierAuthenticationForm),
        (TwoFALoginView.TOKEN_STEP, MyAuthenticationTokenForm),
    )

    def get_success_url(self):
        user = self.get_user()
        base_url = super().get_success_url()

        if not is_mobile_request(self.request):
            return base_url

        has_passkey = WebAuthnPasskey.objects.filter(user=user).exists()
        has_native_bio = NativeBiometricDevice.objects.filter(user=user, is_active=True).exists()

        skip_passkeys = bool(self.request.session.get("webauthn_skip_devices"))
        skip_native_offer = bool(self.request.session.get("native_bio_skip_offer"))

        # Capacitor: alleen offer native biometrics als device biometrie kan
        if is_capacitor_request(self.request):
            bio_capable = biometric_capable_request(self.request)

            # Device zonder biometrie -> NOOIT passkey offer; gewoon door naar base_url (jouw 2FA/home flow)
            if not bio_capable:
                return base_url

            # Device mét biometrie -> alleen offer native setup als nog niet actief en niet geskipt
            if (not has_native_bio) and (not skip_native_offer):
                setup_url = reverse("native_biometric_setup")
                return f"{setup_url}?next={urlquote(base_url)}"

            return base_url

        # Browser/PWA: jouw bestaande passkey logic
        if (not has_passkey) and (not has_native_bio) and (not skip_passkeys):
            setup_url = reverse("passkey_setup")
            return f"{setup_url}?next={urlquote(base_url)}"

        return base_url

    def has_backup_step(self):
        return False

    def get_form(self, step=None, **kwargs):
        current = step or self.steps.current
        if current == self.TOKEN_STEP:
            self.form_list[self.TOKEN_STEP] = MyAuthenticationTokenForm

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
        for msg in form.non_field_errors():
            messages.error(self.request, msg)
        form._errors = ErrorDict()

    def render(self, form=None, **kwargs):
        self._flash_form_errors(form)

        if self.steps.current == self.TOKEN_STEP:
            # Sla de user + next op voor de passkey flow
            try:
                user = self.get_user()
            except Exception:
                user = None

            if user is not None:
                self.request.session["passkey_login_user_id"] = user.pk

            next_url = self.request.GET.get("next") or settings.LOGIN_REDIRECT_URL
            self.request.session["passkey_next_url"] = next_url

            # SMS / voice challenge voor TOTP
            form_with_errors = form and form.is_bound and bool(form.errors)
            if not form_with_errors:
                self.get_device().generate_challenge()

        return super().render(form=form, **kwargs)
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Check of we de snelle inlog knop moeten tonen
        ctx['show_kiosk_login'] = is_in_pharmacy_network(self.request)
        return ctx
    
@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Je bent uitgelogd.")
    return redirect(reverse("two_factor:login"))

@require_POST
def kiosk_login_view(request):
    # We importeren deze hier lokaal om circulaire imports te voorkomen
    from core.utils.network import is_in_pharmacy_network
    from core.models import StandaardInlog
    
    if not is_in_pharmacy_network(request):
        messages.error(request, _("Toegang geweigerd: Je zit niet op het apotheek netwerk."))
        return redirect(reverse("two_factor:login"))

    config = StandaardInlog.load()
    if not config or not config.standaard_rol:
        messages.error(request, _("Kiosk-modus is niet geconfigureerd in de admin."))
        return redirect(reverse("two_factor:login"))

    User = get_user_model()
    kiosk_user, _ = User.objects.get_or_create(
        username="apotheek_kiosk",
        defaults={
            'first_name': 'Apotheek', 
            'last_name': 'Algemeen',
            'is_active': True
        }
    )
    
    # Koppel de rol
    kiosk_user.groups.set([config.standaard_rol])

    # HIER GING HET MIS: We gebruiken nu auth_login i.p.v. login
    auth_login(request, kiosk_user, backend='django.contrib.auth.backends.ModelBackend')
    
    # Markeer sessie voor de 2FA library
    request.session['otp_device_id'] = None 
    request.session['two_factor_auth_complete'] = True
    
    return redirect(reverse("home"))