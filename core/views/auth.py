from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse

from ..forms import EmailOrUsernameLoginForm

User = get_user_model()

def login_view(request):
    # This is an old login view, now the 2fa view is used
    if request.user.is_authenticated:
        return redirect("home")

    form = EmailOrUsernameLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ident = (form.cleaned_data["identifier"] or "").strip().lower()
        pwd = form.cleaned_data["password"]

        username_for_auth = None

        if "@" in ident:
            # Inloggen met e-mail
            u = User.objects.filter(email__iexact=ident).first()
            if u:
                username_for_auth = u.username  # == email
        else:
            # Eerst proberen met username (== email)
            u = User.objects.filter(username__iexact=ident).first()
            if u:
                username_for_auth = u.username
            else:
                # Zo niet: probeer met first_name
                qs = User.objects.filter(first_name__iexact=ident)
                count = qs.count()
                if count == 1:
                    username_for_auth = qs.first().username
                elif count > 1:
                    messages.error(
                        request,
                        "Er zijn meerdere gebruikers met deze voornaam. Log in met je e-mailadres."
                    )
                    return render(request, "auth/login.html", {"form": form})

        user = authenticate(request, username=username_for_auth or ident, password=pwd)
        if user is not None and user.is_active:
            login(request, user)
            request.session.set_expiry(86400)
            request.session["just_logged_in"] = True

            nxt = request.GET.get("next")
            if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
                return redirect(nxt)
            return redirect("home")

        messages.error(request, "Ongeldige inloggegevens.")

    return render(request, "auth/login.html", {"form": form})

@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect(reverse("two_factor:login"))