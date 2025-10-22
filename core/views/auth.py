# core/views/auth.py
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.utils.http import url_has_allowed_host_and_scheme  # (optioneel, voor veilige next)
from django.conf import settings

from ..forms import EmailOrUsernameLoginForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = EmailOrUsernameLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ident = form.cleaned_data["identifier"].strip().lower()
        pwd = form.cleaned_data["password"]
        username = ident
        if "@" in ident:
            u = User.objects.filter(email__iexact=ident).first()
            if u:
                username = u.username

        user = authenticate(request, username=username, password=pwd)
        if user is not None and user.is_active:
            login(request, user)

            # ✅ BELANGRIJK: markeer 'net ingelogd' voor de biometrie-prompt
            request.session["just_logged_in"] = True

            # (optioneel) veilige 'next' afhandeling
            nxt = request.GET.get("next")
            if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
                return redirect(nxt)
            return redirect("home")

        messages.error(request, "Ongeldige inloggegevens.")

    ctx = {"form": form}
    return render(request, "auth/login.html", ctx)


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")