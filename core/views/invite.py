# core/views/invite.py
from django.shortcuts import render, redirect
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth import get_user_model, login
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_decode
from django.contrib import messages
from django.urls import reverse

User = get_user_model()
token_generator = PasswordResetTokenGenerator()

def set_password(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user is None or not token_generator.check_token(user, token):
        messages.error(request, "De link is ongeldig of verlopen.")
        return redirect("login")

    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            # direct inloggen en door naar 2FA-setup
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Wachtwoord ingesteld. Stel nu je 2FA in.")
            return redirect(reverse("two_factor:setup"))
    else:
        form = SetPasswordForm(user)

    return render(request, "accounts/set_password.html", {"form": form})
