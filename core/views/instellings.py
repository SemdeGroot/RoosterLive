# core/views/instellings.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden

from core.tiles import build_tiles
from core.views._helpers import can

@login_required
def instellings_tiles(request):
    if not can(request.user, "can_view_instellings_apo"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    tiles = build_tiles(request.user, group="instellings")
    context = {
        "page_title": "Instellingsapotheek",
        "intro": "Op deze pagina vind je de onderdelen voor de instellingsapotheek.",
        "tiles": tiles,
    }
    return render(request, "tiles_page.html", context)
