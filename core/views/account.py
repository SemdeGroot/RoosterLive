# core/views/account.py
from django.contrib.auth.views import PasswordResetConfirmView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django_otp import devices_for_user
from django.contrib import messages
from django.utils.translation import gettext as _
from django.forms.utils import ErrorDict

def _has_confirmed_2fa(user) -> bool:
    for d in devices_for_user(user, confirmed=True):
        return True
    return False


class CustomPasswordConfirmView(PasswordResetConfirmView):
    template_name = "accounts/set_password.html"
    success_url = reverse_lazy("two_factor:setup")

    post_reset_login = True
    post_reset_login_backend = "django.contrib.auth.backends.ModelBackend"

    # ---------- UI: NL labels + 'required' ----------
    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        if "new_password1" in form.fields:
            f1 = form.fields["new_password1"]
            f1.label = _("Nieuw wachtwoord")
            f1.widget.attrs.update({
                "autocomplete": "new-password",
                "autofocus": "autofocus",
            })
            f1.error_messages.update({
                "required": _("Vul een wachtwoord in."),
                "invalid":  _("Ongeldige invoer."),
            })

        if "new_password2" in form.fields:
            f2 = form.fields["new_password2"]
            f2.label = _("Herhaal nieuw wachtwoord")
            f2.widget.attrs.update({"autocomplete": "new-password"})
            f2.error_messages.update({
                "required": _("Herhaal je wachtwoord."),
                "invalid":  _("Ongeldige invoer."),
            })

        if hasattr(form, "error_messages"):
            form.error_messages["password_mismatch"] = _("Wachtwoorden komen niet overeen.")

        return form

    # ---------- Flow-afspraken ----------
    def dispatch(self, request, *args, **kwargs):
        uidb64 = kwargs.get("uidb64")
        link_user = self.get_user(uidb64)
        if link_user and link_user.has_usable_password():
            if request.user.is_authenticated and request.user.pk == link_user.pk:
                if not _has_confirmed_2fa(request.user):
                    return redirect(reverse("two_factor:setup"))
                return redirect(reverse("home"))
            messages.info(request, _("Je wachtwoord is al ingesteld. Log in om verder te gaan."))
            return redirect(reverse("two_factor:login"))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if not getattr(self, "validlink", False):
            messages.error(request, _("Deze link is ongeldig of al gebruikt. Log in om verder te gaan."))
            return redirect(reverse("two_factor:login"))
        return response

    # ---------- NL flash messages (max 1) ----------
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

        # Toon maximaal 1 bericht
        first_message = None
        for field, err_list in errors_data.items():
            for err in err_list:
                first_message = msg_from_error(err)
                break
            if first_message:
                break

        # Non-field fallback
        if not first_message and form.non_field_errors():
            first_message = msg_from_error(form.non_field_errors().as_data()[0])

        if not first_message:
            first_message = _("Er ging iets mis. Probeer het opnieuw.")

        messages.error(self.request, first_message)
        form._errors = ErrorDict()
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        user = getattr(self.request, "user", None)
        if user and user.is_authenticated and not _has_confirmed_2fa(user):
            return reverse("two_factor:setup")
        return reverse("home")