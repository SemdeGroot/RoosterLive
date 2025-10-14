# core/tiles.py
from core.views._helpers import can

def build_tiles(user):
    tiles = []
    if not user.is_authenticated:
        return tiles

    if can(user, "can_view_roster"):
        tiles.append({"name": "Rooster", "img": "rooster.png", "url_name": "rooster"})
    if can(user, "can_view_av_medications"):
        tiles.append({"name": "Voorraad", "img": "medicijn_zoeken.png", "url_name": "medications"})
    if can(user, "can_view_av_nazendingen"):
        tiles.append({"name": "Nazendingen", "img": "nazendingen.png", "url_name": "nazendingen"})
    if can(user, "can_view_policies"):
        tiles.append({"name": "Werkafspraken", "img": "afspraken.png", "url_name": "policies"})
    if can(user, "can_view_news"):
        tiles.append({"name": "Nieuws", "img": "nieuws.png", "url_name": "news"})
    if can(user, "can_access_admin"):
        tiles.append({"name": "Beheer", "img": "beheer.png", "url_name": "admin_panel"})

    return tiles
