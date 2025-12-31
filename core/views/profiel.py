# core/views/profiel.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden
from core.views._helpers import can

@login_required
def profiel(request):
    if not can(request.user, "can_access_profiel"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    return render(request, "profiel/index.html", {
        "page_title": "Profiel",
    })