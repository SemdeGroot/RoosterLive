# core/tiles.py
from core.views._helpers import can

TILE_GROUPS = {
    "home": [
        {"name": "Agenda", "img": "agenda.svg", "url_name": "agenda", "perm": "can_view_agenda"},
        {"name": "Nieuws", "img": "nieuws.svg", "url_name": "news", "perm": "can_view_news"},
        {"name": "Rooster", "img": "rooster_large.svg", "url_name": "rooster", "perm": "can_view_roster"},
        {"name": "Beschikbaarheid", "img": "beschikbaarheid.svg", "url_name": "mijnbeschikbaarheid", "perm": "can_send_beschikbaarheid"},
        {"name": "Onboarding", "img": "onboarding.svg", "url_name": "onboarding_tiles", "perm": "can_view_onboarding"},
        {"name": "Personeel", "img": "personeel.svg", "url_name": "personeel_tiles", "perm": "can_view_personeel"},
        {"name": "Baxterproductie", "img": "factory.svg", "url_name": "baxter_tiles", "perm": "can_view_baxter"},
        {"name": "Openbare Apo",    "img": "openbareapo.svg", "url_name": "openbare_tiles", "perm": "can_view_openbare_apo"},
        {"name": "Instellingsapotheek", "img": "instellingsapotheek.svg", "url_name": "instellings_tiles", "perm": "can_view_instellings_apo"},
        {"name": "Profiel", "img": "profile.svg", "url_name": "profiel", "perm": "can_access_profiel"},
        {"name": "Beheer", "img": "beheer.svg", "url_name": "beheer_tiles", "perm": "can_access_admin"},
    ],

    "personeel": [
        {"name": "Teamdashboard", "img": "teamdashboard.svg", "url_name": "beschikbaarheidpersoneel", "perm": "can_view_beschikbaarheidsdashboard"},
        {"name": "Diensten", "img": "diensten.svg", "url_name": "mijndiensten", "perm": "can_view_diensten"},
        {"name": "Uren doorgeven", "img": "uren_doorgeven.svg", "url_name": "urendoorgeven", "perm": "can_view_urendoorgeven"},
        {"name": "Ziek melden", "img": "ziek.svg", "url_name": "ziekmelden", "perm": "can_view_ziekmelden"},
        {"name": "Werkafspraken", "img": "werkafspraken.svg", "url_name": "policies", "perm": "can_view_policies"},
        {"name": "Inschrijven", "img": "inschrijven.svg", "url_name": "inschrijvingen", "perm": "can_view_inschrijven"},
    ],

    "onboarding": [
        {"name": "Wie is wie?", "img": "wieiswie.svg", "url_name": "whoiswho", "perm": "can_view_whoiswho"},
        {"name": "Formulieren", "img": "formulieren.svg", "url_name": "onboarding_formulieren", "perm": "can_view_forms"},
        {"name": "Checklist", "img": "checklist.svg", "url_name": "checklist", "perm": "can_view_checklist"},
    ],

    "baxter": [
        {"name": "Voorraad",        "img": "voorraad.svg", "url_name": "medications",              "perm": "can_view_av_medications"},
        {"name": "Nazendingen",     "img": "nazendingen.svg",     "url_name": "nazendingen",              "perm": "can_view_av_nazendingen"},
        {"name": "Omzettingslijst", "img": "omzettingslijst.svg", "url_name": "baxter_omzettingslijst",   "perm": "can_view_baxter_omzettingslijst"},
        {"name": "Geen levering",   "img": "no-delivery.svg",     "url_name": "baxter_no_delivery",       "perm": "can_view_baxter_no_delivery"},
        {"name": "STS halfjes",     "img": "sts_halfjes.svg",       "url_name": "stshalfjes",       "perm": "can_view_baxter_sts_halfjes"},
        {"name": "Laatste potten",  "img": "laatstepotten.svg",    "url_name": "laatstepotten",    "perm": "can_view_baxter_laatste_potten"},
    ],

       "openbare": [
        # Deze verwijst naar de dashboard view
        {"name": "Medicatiereview", "img": "medicatiebeoordeling.svg",
         "url_name": "medicatiebeoordeling_tiles", "perm": "can_view_medicatiebeoordeling"},
        {"name": "Review Planner", "img": "reviewplanner.svg",
         "url_name": "reviewplanner", "perm": "can_view_reviewplanner"},
        {"name": "Werkafspraken", "img": "werkafspraken.svg", "url_name": "policies", "perm": "can_view_policies"},
    ],

    "instellings": [
        # Deze verwijst ook naar de dashboard view
        {"name": "Medicatiereview", "img": "medicatiebeoordeling.svg",
         "url_name": "medicatiebeoordeling_tiles", "perm": "can_view_medicatiebeoordeling"},
        {"name": "Review Planner", "img": "reviewplanner.svg",
         "url_name": "reviewplanner", "perm": "can_view_reviewplanner"},
        {"name": "Portavita Check", "img": "portavita.svg",
         "url_name": "portavita-check", "perm": "can_view_portavita"},
        {"name": "Werkafspraken", "img": "werkafspraken.svg", "url_name": "policies", "perm": "can_view_policies"},
    ],

    # De subtiles voor Medicatiebeoordeling
    "medicatiebeoordeling": [
        {
            "name": "Nieuwe Review",
            "img": "createreview.svg",
            "url_name": "medicatiebeoordeling_create",
            "perm": "can_perform_medicatiebeoordeling"
        },
        {
            "name": "Historie",
            "img": "history.svg",
            "url_name": "medicatiebeoordeling_list",
            "perm": "can_view_medicatiebeoordeling"
        },
        {
            "name": "Instellingen",
            "img": "reviewsettings.svg",
            "url_name": "medicatiebeoordeling_settings", # Placeholder URL
            "perm": "can_perform_medicatiebeoordeling"
        },
    ],
    "beheer": [
        {
            "name": "Gebruikers", 
            "img": "user.svg",
            "url_name": "admin_users", 
            "perm": "can_access_admin"
        },
        {
            "name": "Groepen", 
            "img": "group.svg",
            "url_name": "admin_groups", 
            "perm": "can_access_admin"
        },
        {
            "name": "Afdelingen", 
            "img": "afdeling.svg",
            "url_name": "admin_afdelingen", 
            "perm": "can_access_admin"
        },
        {
            "name": "Organisaties", 
            "img": "organisatie.svg",
            "url_name": "admin_orgs", 
            "perm": "can_access_admin"
        },
        {
            "name": "Taken", 
            "img": "taken.svg",
            "url_name": "admin_taken", 
            "perm": "can_access_admin"
        },
        {
            "name": "Functies", 
            "img": "functies.svg",
            "url_name": "admin_functies", 
            "perm": "can_access_admin"
        },
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

# --- NAV TREE EXTENSIONS (non-breaking) ---

def _resolve_child_group(url_name: str):
    """
    Bepaal of een tile children heeft.
    Regels:
    - eindigt op _tiles -> group = prefix (onboarding_tiles -> onboarding)
    - url_name zelf is een TILE_GROUPS key -> group = url_name
    """
    if not url_name:
        return None

    if url_name.endswith("_tiles"):
        return url_name.replace("_tiles", "")

    if url_name in TILE_GROUPS:
        return url_name

    return None


def build_nav_tree_recursive(user, root_group="home", max_depth=10):
    """
    Bouw een recursieve navigatieboom op basis van TILE_GROUPS.
    Elk item krijgt: children = [...]
    max_depth beschermt tegen loops.
    """
    if max_depth <= 0:
        return []

    root_items = build_tiles(user, group=root_group)

    for item in root_items:
        child_group = _resolve_child_group(item.get("url_name"))
        if child_group:
            # Recursief children opbouwen
            item["children"] = build_nav_tree_recursive(
                user,
                root_group=child_group,
                max_depth=max_depth - 1
            )
        else:
            item["children"] = []

    return root_items