# core/tiles.py
from core.views._helpers import can

TILE_GROUPS = {
    "home": [
        {"name": "Agenda", "img": "agenda-256x256.png", "url_name": "agenda", "perm": "can_view_agenda"},
        {"name": "Nieuws", "img": "nieuws-256x256.png", "url_name": "news", "perm": "can_view_news"},
        {"name": "Rooster", "img": "rooster-256x256.png", "url_name": "rooster", "perm": "can_view_roster"},
        {"name": "Beschikbaarheid", "img": "beschikbaarheid-256x256.png", "url_name": "mijnbeschikbaarheid", "perm": "can_send_beschikbaarheid"},
        {"name": "Onboarding", "img": "onboarding-256x256.png", "url_name": "onboarding_tiles", "perm": "can_view_onboarding"},
        {"name": "Personeel", "img": "personeel-256x256.png", "url_name": "personeel_tiles", "perm": "can_view_personeel"},
        {"name": "Werkafspraken", "img": "afspraken-256x256.png", "url_name": "policies", "perm": "can_view_policies"},
        {"name": "Voorraad", "img": "medicijn_zoeken-256x256.png", "url_name": "medications", "perm": "can_view_av_medications"},
        {"name": "Nazendingen", "img": "nazendingen-256x256.png", "url_name": "nazendingen", "perm": "can_view_av_nazendingen"},
        {"name": "Medicatiereview", "img": "medicatiebeoordeling-256x256.png", "url_name": "medicatiebeoordeling", "perm": "can_view_medicatiebeoordeling"},
        {"name": "Beheer", "img": "beheer-256x256.png", "url_name": "admin_panel", "perm": "can_access_admin"},
    ],

    "personeel": [
        {"name": "Teamdashboard", "img": "personeel_dashboard-256x256.png", "url_name": "beschikbaarheidpersoneel", "perm": "can_view_beschikbaarheidsdashboard"},
    ],

    "onboarding": [
        {"name": "Wie is wie?", "img": "who_is_who-256x256.png", "url_name": "whoiswho", "perm": "can_view_whoiswho"},
        {"name": "Formulieren", "img": "forms-256x256.png", "url_name": "forms", "perm": "can_view_forms"},
        {"name": "Checklist", "img": "checklist-256x256.png", "url_name": "checklist", "perm": "can_view_checklist"},
    ],
}


def build_tiles(user, group="home"):
    """
    Geef tiles terug voor een bepaalde groep (home, personnel, ...),
    gefilterd op permissies.
    """
    tiles = []
    if not user.is_authenticated:
        return tiles

    for t in TILE_GROUPS.get(group, []):
        perm = t.get("perm")
        if perm is None or can(user, perm):
            # alleen velden teruggeven die de templates gebruiken
            tiles.append({
                "name": t["name"],
                "img": t["img"],
                "url_name": t["url_name"],
            })

    return tiles