# core/views/baxter.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden

from core.tiles import build_tiles
from core.views._helpers import can

@login_required
def statistieken_tiles(request):
    if not can(request.user, "can_view_statistieken"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    tiles = build_tiles(request.user, group="statistieken")
    context = {
        "page_title": "Statistieken",
        "intro": "Op deze pagina vind je een overzicht van relevante statistieken.",
        "tiles": tiles,
    }
    return render(request, "tiles_page.html", context)