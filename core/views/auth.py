# core/views/auth.py
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.conf import settings

from ..forms import EmailOrUsernameLoginForm
from ._helpers import logo_url

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
            return redirect(request.GET.get("next") or "home")
        messages.error(request, "Ongeldige inloggegevens.")

    ctx = {
        "form": form,
        "logo_url": logo_url(),
        "bg_url": settings.MEDIA_URL + "_data/achtergrond.jpg", 
    }
    return render(request, "auth/login.html", ctx)

@login_required
@require_POST
def logout_view(request): 
    logout(request)
    return redirect("login")
