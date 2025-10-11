# core/views/home.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from ._helpers import can, logo_url

@login_required
def home(request):
    tiles = []
    if can(request.user, "can_view_roster"):
        tiles.append({"name": "Rooster", "img": "rooster.png", "url_name": "rooster"})
    if can(request.user, "can_access_availability"):
        tiles.append({"name": "Beschikbaarheid", "img": "beschikbaarheid.png", "url_name": "availability_home"})
    if can(request.user, "can_view_policies"):
        tiles.append({"name": "Werkafspraken", "img": "afspraken.png", "url_name": "policies"})
    if can(request.user, "can_view_news"):
        tiles.append({"name": "Nieuws", "img": "nieuws.png", "url_name": "news"})
    if can(request.user, "can_access_admin"):
        tiles.append({"name": "Beheer", "img": "beheer.png", "url_name": "admin_panel"})
    return render(request, "home.html", {"tiles": tiles, "logo_url": logo_url()})
