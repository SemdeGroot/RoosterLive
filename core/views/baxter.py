# core/views/baxter.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden

from core.tiles import build_tiles
from core.views._helpers import can

@login_required
def baxter_tiles(request):
    if not can(request.user, "can_view_baxter"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    tiles = build_tiles(request.user, group="baxter")
    context = {
        "page_title": "Baxter",
        "intro": "Op deze pagina vind je de Baxter-gerelateerde onderdelen, zoals voorraad en nazendingen.",
        "tiles": tiles,
    }
    return render(request, "tiles_page.html", context)