# core/views/account.py
from django.contrib.auth.views import PasswordResetConfirmView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django_otp import devices_for_user

def _has_confirmed_2fa(user) -> bool:
    # Minimaal en generiek: check op confirmed OTP-device(s)
    for d in devices_for_user(user, confirmed=None):
        try:
            if getattr(d, "confirmed", True):  # sommige device types hebben geen 'confirmed', treat as True
                return True
        except Exception:
            return True
    return False

class CustomPasswordConfirmView(PasswordResetConfirmView):
    template_name = "accounts/set_password.html"
    success_url = reverse_lazy("two_factor:setup")

    # Laat Django het inloggen afhandelen na succesvol resetten
    post_reset_login = True
    post_reset_login_backend = "django.contrib.auth.backends.ModelBackend"

    def dispatch(self, request, *args, **kwargs):
        # 1) Als user al ingelogd is en deze link nog eens klikt:
        if request.user.is_authenticated:
            if not _has_confirmed_2fa(request.user):
                return redirect(reverse("two_factor:setup"))
            return redirect(reverse("home"))

        # 2) Als token ongeldig of al gebruikt is → naar login i.p.v. 'kapotte' confirm-pagina
        user = self.get_user(kwargs.get("uidb64"))
        token = kwargs.get("token")
        # self.token_generator is wat Django zelf gebruikt
        if not user or not self.token_generator.check_token(user, token):
            return redirect(reverse("two_factor:login"))

        # 3) Geldige link en geen sessie → laat Django de standaard confirm-flow doen
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        # Na succesvol instellen EN auto-login → forceer 2FA-setup zolang er geen 2FA is
        user = getattr(self.request, "user", None)
        if user and user.is_authenticated and not _has_confirmed_2fa(user):
            return reverse("two_factor:setup")
        return reverse("home")