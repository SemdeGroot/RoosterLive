# core/views/onboarding.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.tiles import build_tiles
from core.views._helpers import can
from django.http import HttpResponseForbidden

@login_required
def onboarding_tiles(request):
    # Optioneel: extra permissiecheck
    if not can(request.user, "can_view_onboarding"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    tiles = build_tiles(request.user, group="onboarding")
    context = {
        "page_title": "Onboarding",
        "intro": "Op deze pagina vind je alles om goed van start te gaan. Kies hieronder wat je nodig hebt.",
        "tiles": tiles,
    }
    return render(request, "tiles_page.html", context)