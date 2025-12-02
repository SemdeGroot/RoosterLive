# core/views/onboarding_forms.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden
from core.views._helpers import can

@login_required
def forms(request):
    if not can(request.user, "can_view_forms"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    return render(request, "forms/index.html", {
        "page_title": "Formulieren",
    })
