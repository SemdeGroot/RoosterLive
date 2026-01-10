# core/views/admin.py
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from ._helpers import can
from core.tiles import build_tiles


# ==========================================
# 1. DASHBOARD (TILES)
# ==========================================
@login_required
def bezorgers_tiles(request):
    """
    Landingspagina voor beheer.
    """
    if not can(request.user, "can_view_bezorgers"):
        return HttpResponseForbidden("Geen toegang.")

    tiles = build_tiles(request.user, group="bezorgers")
    
    context = {
        "page_title": "Bezorgers",
        "intro": "Hier komt de implementatie voor bezorgers",
        "tiles": tiles,
        "back_url": "home", 
    }
    return render(request, "tiles_page.html", context)

# === Bakken bezorgen ===

@login_required
def bakkenbezorgen(request):
    if not can(request.user, "can_view_bakkenbezorgen"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    return render(request, "bakkenbezorgen/index.html", {
        "page_title": "Bakken bezorgen",
    })