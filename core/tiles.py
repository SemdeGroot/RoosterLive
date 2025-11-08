# core/tiles.py
from core.views._helpers import can

def build_tiles(user):
    tiles = []
    if not user.is_authenticated:
        return tiles

    if can(user, "can_view_agenda"):
        tiles.append({"name": "Agenda", "img": "agenda.png", "url_name": "agenda"})
    if can(user, "can_view_roster"):
        tiles.append({"name": "Rooster", "img": "rooster.png", "url_name": "rooster"})
    if can(user, "can_send_beschikbaarheid"):
        tiles.append({"name": "Beschikbaarheid", "img": "beschikbaarheid_doorgeven.png", "url_name": "mijnbeschikbaarheid"})
    if can(user, "can_view_beschikbaarheidsdashboard"):
        tiles.append({"name": "Teamdashboard", "img": "personeel_dashboard.png", "url_name": "beschikbaarheidpersoneel"})
    if can(user, "can_view_av_medications"):
        tiles.append({"name": "Voorraad", "img": "medicijn_zoeken.png", "url_name": "medications"})
    if can(user, "can_view_av_nazendingen"):
        tiles.append({"name": "Nazendingen", "img": "nazendingen.png", "url_name": "nazendingen"})
    if can(user, "can_view_policies"):
        tiles.append({"name": "Werkafspraken", "img": "afspraken.png", "url_name": "policies"})
    if can(user, "can_view_news"):
        tiles.append({"name": "Nieuws", "img": "nieuws.png", "url_name": "news"})
    if can(user, "can_view_medicatiebeoordeling"):
        tiles.append({"name": "Medicatiebeoordeling", "img": "medicatiebeoordeling.png", "url_name": "medicatiebeoordeling"})
    if can(user, "can_access_admin"):
        tiles.append({"name": "Beheer", "img": "beheer.png", "url_name": "admin_panel"})

    return tiles
