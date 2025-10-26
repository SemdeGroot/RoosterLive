# core/views/account.py
from django.contrib.auth.views import PasswordResetConfirmView
from django.urls import reverse_lazy

class CustomPasswordConfirmView(PasswordResetConfirmView):
    template_name = "accounts/set_password.html"
    success_url = reverse_lazy("two_factor:setup")

    # Laat Django het inloggen afhandelen
    post_reset_login = True
    post_reset_login_backend = "django.contrib.auth.backends.ModelBackend"

