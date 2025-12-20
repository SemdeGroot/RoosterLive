# core/views/account.py
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib.auth.forms import PasswordResetForm
from django.utils.translation import gettext as _
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django_otp import devices_for_user
from django.contrib.auth import authenticate, login, get_user_model
from django.forms.utils import ErrorDict
from django_ratelimit.core import is_ratelimited

from core.tasks import send_password_reset_email_task

def _has_confirmed_2fa(user) -> bool:
    for d in devices_for_user(user, confirmed=True):
        return True
    return False


class CustomPasswordConfirmView(PasswordResetConfirmView):
    template_name = "accounts/set_password.html"

    # heel belangrijk: NIET autom. inloggen door Django laten doen
    post_reset_login = False
    post_reset_login_backend = "django.contrib.auth.backends.ModelBackend"

    # ---------- UI ----------
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if "new_password1" in form.fields:
            f1 = form.fields["new_password1"]
            f1.label = _("Nieuw wachtwoord")
            f1.widget.attrs.update({"autocomplete": "off", "autofocus": "autofocus"})
            f1.error_messages.update({
                "required": _("Vul een wachtwoord in."),
                "invalid":  _("Ongeldige invoer."),
            })
        if "new_password2" in form.fields:
            f2 = form.fields["new_password2"]
            f2.label = _("Herhaal nieuw wachtwoord")
            f2.widget.attrs.update({"autocomplete": "off"})
            f2.error_messages.update({
                "required": _("Herhaal je wachtwoord."),
                "invalid":  _("Ongeldige invoer."),
            })
        if hasattr(form, "error_messages"):
            form.error_messages["password_mismatch"] = _("Wachtwoorden komen niet overeen.")
        return form

    # ---------- Flow ----------
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        # Django geeft bij ongeldige/gebruikte link validlink=False mee in de context
        if not context.get("validlink", True):
            messages.error(
                self.request,
                _("Deze link is ongeldig of al gebruikt. Log in of vraag een nieuwe link aan bij de beheerder.")
            )
            return redirect(reverse("two_factor:login"))
        return super().render_to_response(context, **response_kwargs)

    def form_invalid(self, form):
        def msg_from_error(err) -> str:
            code = getattr(err, "code", "") or ""
            params = getattr(err, "params", {}) or {}
            if code == "password_mismatch":
                return _("Wachtwoorden komen niet overeen.")
            if code == "password_too_short":
                n = params.get("min_length")
                return _("Wachtwoord is te kort (minimaal %(n)s tekens).") % {"n": n} if n else _("Wachtwoord is te kort.")
            if code == "password_too_common":
                return _("Wachtwoord is te algemeen.")
            if code == "password_entirely_numeric":
                return _("Wachtwoord mag niet alleen uit cijfers bestaan.")
            if code == "password_too_similar":
                return _("Wachtwoord lijkt te veel op je gegevens.")
            if code == "required":
                return _("Vul alle vereiste velden in.")
            if code == "invalid":
                return _("Ongeldige invoer.")
            return _("Controleer je invoer en probeer het opnieuw.")
        errors_data = form.errors.as_data()
        first_message = None
        for _field, err_list in errors_data.items():
            for err in err_list:
                first_message = msg_from_error(err); break
            if first_message: break
        if not first_message and form.non_field_errors():
            first_message = msg_from_error(form.non_field_errors().as_data()[0])
        if not first_message:
            first_message = _("Er ging iets mis. Probeer het opnieuw.")
        messages.error(self.request, first_message)
        form._errors = ErrorDict()
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        """
        Doet alleen: wachtwoord zetten + eigen redirects.
        GEEN super().form_valid(form) -> voorkomt reverse('password_reset_complete')
        """
        user = self.user  # gezet door de parent view
        # zet het nieuwe wachtwoord en invalideer de token:
        form.save()

        if _has_confirmed_2fa(user):
            messages.success(self.request, _("Je wachtwoord is gewijzigd. Log in met je nieuwe wachtwoord en voer je 2FA-code in."))
            return redirect(reverse("two_factor:login"))

        # geen 2FA → automatisch inloggen en naar setup
        UserModel = get_user_model()
        username_field = UserModel.USERNAME_FIELD
        username = getattr(user, username_field)
        new_password = form.cleaned_data.get("new_password1") or form.cleaned_data.get("new_password2")
        auth_user = authenticate(self.request, **{username_field: username}, password=new_password)
        if auth_user is not None:
            login(self.request, auth_user, backend=self.post_reset_login_backend)
        return redirect(reverse("two_factor:setup"))

class CustomPasswordResetView(PasswordResetView):
    """
    Stuurt resetmail via Celery task. Rate-limited (Redis via Django cache).
    """
    template_name = "accounts/password_reset.html"
    success_url = reverse_lazy("two_factor:login")
    form_class = PasswordResetForm

    email_template_name = None
    subject_template_name = None
    html_email_template_name = None
    extra_email_context = None

    def _get_client_ip(self, request) -> str:
        """
        Gebruik X-Forwarded-For als je achter een proxy/load balancer zit.
        Let op: vertrouw dit alleen als je infra de header “schoon” zet.
        """
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "") or ""

    def _is_limited(self, request) -> bool:
        """
        Meerdere lagen:
        - burst per IP (tegen bots)
        - uur-limiet per IP
        - uur-limiet per (IP + email)
        - dag-limiet per IP
        - dag-limiet per (IP + email)
        """
        if request.method != "POST":
            return False

        ip = self._get_client_ip(request)
        email = (request.POST.get("email") or "").strip().lower()
        ip_email = f"{ip}:{email}"

        # 1) burst per IP
        burst_ip = is_ratelimited(
            request=request,
            group="pwreset_burst_ip",
            key=lambda group, req: ip,
            rate="3/m",
            method="POST",
            increment=True,
        )

        # 2) per uur per IP
        hourly_ip = is_ratelimited(
            request=request,
            group="pwreset_hourly_ip",
            key=lambda group, req: ip,
            rate="10/h",
            method="POST",
            increment=True,
        )

        # 3) per uur per (IP+email)
        hourly_ip_email = is_ratelimited(
            request=request,
            group="pwreset_hourly_ip_email",
            key=lambda group, req: ip_email,
            rate="2/h",
            method="POST",
            increment=True,
        )

        # 4) per dag per IP
        daily_ip = is_ratelimited(
            request=request,
            group="pwreset_daily_ip",
            key=lambda group, req: ip,
            rate="30/d",
            method="POST",
            increment=True,
        )

        # 5) per dag per (IP+email)
        daily_ip_email = is_ratelimited(
            request=request,
            group="pwreset_daily_ip_email",
            key=lambda group, req: ip_email,
            rate="5/d",
            method="POST",
            increment=True,
        )

        return burst_ip or hourly_ip or hourly_ip_email or daily_ip or daily_ip_email

    def post(self, request, *args, **kwargs):
        # Als gelimiteerd: NIET mailen, wel dezelfde “succes” melding.
        if self._is_limited(request):
            messages.success(
                request,
                _("Als dit e-mailadres bij ons bekend is, wordt een e-mail met instructies verstuurd.")
            )
            return redirect(self.get_success_url())

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        email = form.cleaned_data.get("email")
        users = list(form.get_users(email))

        for user in users:
            send_password_reset_email_task.delay(user.pk)

        messages.success(
            self.request,
            _("Als dit e-mailadres bij ons bekend is, wordt een e-mail met instructies verstuurd.")
        )
        return redirect(self.get_success_url())