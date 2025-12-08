from django.shortcuts import render
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required

# Imports van jouw helpers, forms en models
from core.views._helpers import can
from core.tiles import build_tiles

@login_required
def settings_dashboard(request):
    """
    Landingspagina: Toont review settings tiles; voor nu standaardvragen.
    """
    if not (can(request.user, "can_view_medicatiebeoordeling") or can(request.user, "can_perform_medicatiebeoordeling")):
        return HttpResponseForbidden("Geen toegang.")

    tiles = build_tiles(request.user, group="review_settings")
    
    context = {
        "page_title": "Medicatiebeoordeling Instellingen",
        "intro": "Pas de instellingen aan van de medicatiebeoordeling voorbereider",
        "tiles": tiles,
    }
    return render(request, "tiles_page.html", context)

@login_required
def standaardvragen(request):

    if not (can(request.user, "can_view_medicatiebeoordeling") or can(request.user, "can_perform_medicatiebeoordeling")):
        return HttpResponseForbidden("Geen toegang.")

    return render(request, "medicatiebeoordeling/settings/standaardvragen.html", {
        "page_title": "Standaardvragen",
    })