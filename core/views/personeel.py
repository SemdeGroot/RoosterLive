# core/views/personeel.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.tiles import build_tiles
from core.views._helpers import can
from django.http import HttpResponseForbidden

@login_required
def personeel_tiles(request):

    if not can(request.user, "can_view_onboarding"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    tiles = build_tiles(request.user, group="personeel")
    context = {
        "page_title": "Personeel",
        "intro": "Kies hieronder de personeelsgebonden onderdelen die je wilt openen.",
        "tiles": tiles,
    }
    return render(request, "tiles_page.html", context)
