# core/views/whoiswho.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden
from core.views._helpers import can

@login_required
def whoiswho(request):
    if not can(request.user, "can_view_whoiswho"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    return render(request, "whoiswho/index.html", {
        "page_title": "Wie is wie?",
    })