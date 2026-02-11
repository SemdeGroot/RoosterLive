# core/tiles.py
from core.views._helpers import can

# Badge classes die in CSS bestaan.
C = {
    "blue": "i-blue",
    "sky": "i-sky",
    "cyan": "i-cyan",
    "teal": "i-teal",
    "emerald": "i-emerald",
    "green": "i-green",
    "lime": "i-lime",
    "amber": "i-amber",
    "orange": "i-orange",
    "red": "i-red",
    "rose": "i-rose",
    "pink": "i-pink",
    "fuchsia": "i-fuchsia",
    "violet": "i-violet",
    "indigo": "i-indigo",
    "slate": "i-slate",
    "yellow": "i-yellow",
    "purple": "i-purple",
    "stone": "i-stone",
    "aqua": "i-aqua",
    "brown": "i-brown", 
}

TILE_GROUPS = {
    "home": [
        {"name": "Agenda", "img": "agenda-lucide.svg", "badge_class": C["sky"], "url_name": "agenda", "perm": "can_view_agenda", "desc": "Bekijk afspraken en planning."},
        {"name": "Nieuws", "img": "nieuws-lucide.svg", "badge_class": C["amber"], "url_name": "news", "perm": "can_view_news", "desc": "Updates en mededelingen."},
        {"name": "Rooster", "img": "rooster-lucide.svg", "badge_class": C["indigo"], "url_name": "rooster", "perm": "can_view_roster", "desc": "Bekijk het algemene rooster."},
        {"name": "Beschikbaarheid", "img": "beschikbaarheid-lucide.svg", "badge_class": C["emerald"], "url_name": "mijnbeschikbaarheid", "perm": "can_send_beschikbaarheid", "desc": "Geef je beschikbaarheid door."},
        {"name": "Onboarding", "img": "onboarding-lucide.svg", "badge_class": C["violet"], "url_name": "onboarding_tiles", "perm": "can_view_onboarding", "desc": "Startinfo, team en checklist."},
        {"name": "Personeel", "img": "personeel.svg", "badge_class": C["teal"], "url_name": "personeel_tiles", "perm": "can_view_personeel", "desc": "Alles rondom personeel."},
        {"name": "Baxterproductie", "img": "baxterproductie-lucide.svg", "badge_class": C["orange"], "url_name": "baxter_tiles", "perm": "can_view_baxter", "desc": "Baxter workflows en lijsten."},
        {"name": "Openbare Apo", "img": "openbareapo-lucide.svg", "badge_class": C["aqua"], "url_name": "openbare_tiles", "perm": "can_view_openbare_apo", "desc": "Tools voor de openbare apotheek."},
        {"name": "Instellingsapotheek", "img": "instellingsapo-lucide.svg", "badge_class": C["green"], "url_name": "instellings_tiles", "perm": "can_view_instellings_apo", "desc": "Intramuraal en controles."},
        {"name": "Bezorgers", "img": "bezorgers-lucide.svg", "badge_class": C["lime"], "url_name": "bezorgers_tiles", "perm": "can_view_bezorgers", "desc": "Bezorgtaken en status."},
        {"name": "Profiel", "img": "profiel-lucide.svg", "badge_class": C["pink"], "url_name": "profiel", "perm": "can_access_profiel", "desc": "Instellingen en gegevens."},
        {"name": "Beheer", "img": "admin-lucide.svg", "badge_class": C["purple"], "url_name": "beheer_tiles", "perm": "can_access_admin", "desc": "Admin en configuratie."},
    ],

    "personeel": [
        {"name": "Teamdashboard", "img": "teamdashboard-lucide.svg", "badge_class": C["slate"], "url_name": "beschikbaarheidpersoneel", "perm": "can_view_beschikbaarheidsdashboard", "desc": "Overzicht van bezetting."},
        {"name": "Diensten", "img": "diensten-lucide.svg", "badge_class": C["sky"], "url_name": "mijndiensten", "perm": "can_view_diensten", "desc": "Bekijk je diensten."},
        {"name": "Uren doorgeven", "img": "clock-lucide.svg", "badge_class": C["yellow"], "url_name": "urendoorgeven", "perm": "can_view_urendoorgeven", "desc": "Registreer je uren."},
        {"name": "Ziek melden", "img": "ziekmelden-lucide.svg", "badge_class": C["red"], "url_name": "ziekmelden", "perm": "can_view_ziekmelden", "desc": "Snel ziekmelding doen."},
        {"name": "Inschrijven", "img": "inschrijven-lucide.svg", "badge_class": C["teal"], "url_name": "inschrijvingen", "perm": "can_view_inschrijven", "desc": "Schrijf je in op diensten."},
    ],

    "onboarding": [
        {"name": "Team", "img": "team-lucide.svg", "badge_class": C["teal"], "url_name": "whoiswho", "perm": "can_view_whoiswho", "desc": "Wie is wie in het team."},
        {"name": "Formulieren", "img": "onboarding_forms-lucide.svg", "badge_class": C["stone"], "url_name": "onboarding_formulieren", "perm": "can_view_forms", "desc": "Belangrijke formulieren."},
        {"name": "Checklist", "img": "checklist-lucide.svg", "badge_class": C["lime"], "url_name": "checklist", "perm": "can_view_checklist", "desc": "Alles stap voor stap."},
    ],

    "baxter": [
        {"name": "Voorraad", "img": "voorraad-lucide.svg", "badge_class": C["blue"], "url_name": "medications", "perm": "can_view_av_medications", "desc": "Zoek en beheer voorraad."},
        {"name": "Nazendingen", "img": "nazendingen-lucide.svg", "badge_class": C["amber"], "url_name": "nazendingen", "perm": "can_view_av_nazendingen", "desc": "Nazendingen verwerken."},
        {"name": "Omzettingslijst", "img": "omzettingslijst-lucide.svg", "badge_class": C["indigo"], "url_name": "baxter_omzettingslijst", "perm": "can_view_baxter_omzettingslijst", "desc": "Omzettingen en alternatieven."},
        {"name": "Geen levering", "img": "geenlevering-lucide.svg", "badge_class": C["red"], "url_name": "baxter_no_delivery", "perm": "can_view_baxter_no_delivery", "desc": "Signalering bij ontbrekende levering."},
        {"name": "STS halfjes", "img": "stshalfje-lucide.svg", "badge_class": C["pink"], "url_name": "stshalfjes", "perm": "can_view_baxter_sts_halfjes", "desc": "STS halfjes beheren."},
        {"name": "Laatste potten", "img": "laatstepotten-lucide.svg", "badge_class": C["teal"], "url_name": "laatstepotten", "perm": "can_view_baxter_laatste_potten", "desc": "Overzicht laatste potten."},
        {"name": "Werkafspraken", "img": "werkafspraken-lucide.svg", "badge_class": C["stone"], "url_name": "policies", "perm": "can_view_policies", "desc": "Afspraken en beleid."},
    ],

    "openbare": [
        {"name": "Medicatiereview", "img": "medicatiebeoordeling-lucide.svg", "badge_class": C["indigo"], "url_name": "medicatiebeoordeling_tiles", "perm": "can_view_medicatiebeoordeling", "desc": "Start of beheer reviews."},
        {"name": "Review planner", "img": "reviewplanner-lucide.svg", "badge_class": C["sky"], "url_name": "reviewplanner", "perm": "can_view_reviewplanner", "desc": "Plan en volg reviews."},
        {"name": "KompasGPT", "img": "kompasgpt-lucide.svg", "badge_class": C["fuchsia"], "url_name": "kompasgpt", "perm": "can_view_kompasgpt", "desc": "Snel zoeken in info."},
        {"name": "Houdbaarheidscheck", "img": "houdbaarheidcheck-lucide.svg", "badge_class": C["orange"], "url_name": "houdbaarheidcheck", "perm": "can_edit_houdbaarheidcheck", "desc": "Controleer houdbaarheid."},
        {"name": "Werkafspraken", "img": "werkafspraken-lucide.svg", "badge_class": C["stone"], "url_name": "policies", "perm": "can_view_policies", "desc": "Afspraken en beleid."},
    ],

    "instellings": [
        {"name": "Medicatiereview", "img": "medicatiebeoordeling-lucide.svg", "badge_class": C["violet"], "url_name": "medicatiebeoordeling_tiles", "perm": "can_view_medicatiebeoordeling", "desc": "Reviews voor intramuraal."},
        {"name": "Review planner", "img": "reviewplanner-lucide.svg", "badge_class": C["sky"], "url_name": "reviewplanner", "perm": "can_view_reviewplanner", "desc": "Plannen en opvolgen."},
        {"name": "KompasGPT", "img": "kompasgpt-lucide.svg", "badge_class": C["fuchsia"], "url_name": "kompasgpt", "perm": "can_view_kompasgpt", "desc": "Snel beslisondersteuning."},
        {"name": "Portavita check", "img": "portavitacheck-lucide.svg", "badge_class": C["rose"], "url_name": "portavita-check", "perm": "can_view_portavita", "desc": "Controleer Portavita."},
        {"name": "Werkafspraken", "img": "werkafspraken-lucide.svg", "badge_class": C["stone"], "url_name": "policies", "perm": "can_view_policies", "desc": "Afspraken en beleid."},
    ],

    "bezorgers": [
        {"name": "Bakken bezorgen", "img": "bakkenbezorgen-lucide.svg", "badge_class": C["orange"], "url_name": "bakkenbezorgen", "perm": "can_view_bakkenbezorgen", "desc": "Ritten en bakkenbeheer."},
        {"name": "Afleverstatus", "img": "afleverstatus-lucide.svg", "badge_class": C["green"], "url_name": "afleverstatus", "perm": "can_view_afleverstatus", "desc": "Status per aflevering."},
    ],

    "medicatiebeoordeling": [
        {"name": "Nieuwe Review", "img": "nieuwereview-lucide.svg", "badge_class": C["emerald"], "url_name": "medicatiebeoordeling_create", "perm": "can_perform_medicatiebeoordeling", "desc": "Maak een nieuwe review."},
        {"name": "Historie", "img": "historie-lucide.svg", "badge_class": C["slate"], "url_name": "medicatiebeoordeling_list", "perm": "can_view_medicatiebeoordeling", "desc": "Bekijk afgeronde reviews."},
        {"name": "Instellingen", "img": "standaardvragen-lucide.svg", "badge_class": C["purple"], "url_name": "medicatiebeoordeling_settings", "perm": "can_perform_medicatiebeoordeling", "desc": "Standaardvragen en opties."},
    ],

    "beheer": [
        {"name": "Gebruikers", "img": "admin-user-lucide.svg", "badge_class": C["violet"], "url_name": "admin_users", "perm": "can_access_admin", "desc": "Beheer gebruikersaccounts."},
        {"name": "Groepen", "img": "team-lucide.svg", "badge_class": C["teal"], "url_name": "admin_groups", "perm": "can_access_admin", "desc": "Groepen en rechten."},
        {"name": "Afdelingen", "img": "admin-afdelingen-lucide.svg", "badge_class": C["indigo"], "url_name": "admin_afdelingen", "perm": "can_access_admin", "desc": "Afdelingen beheren."},
        {"name": "Organisaties", "img": "admin-organisaties-lucide.svg", "badge_class": C["sky"], "url_name": "admin_orgs", "perm": "can_access_admin", "desc": "Organisaties beheren."},
        {"name": "Taken", "img": "admin_taken-lucide.svg", "badge_class": C["amber"], "url_name": "admin_taken", "perm": "can_access_admin", "desc": "Taken en checklist items."},
        {"name": "Functies", "img": "admin-functies-lucide.svg", "badge_class": C["pink"], "url_name": "admin_functies", "perm": "can_access_admin", "desc": "Functies en rollen."},
        {"name": "Bezorgen", "img": "bezorgers-lucide.svg", "badge_class": C["orange"], "url_name": "admin_bezorgen", "perm": "can_access_admin", "desc": "Instellingen voor bezorging."},
    ],
}

def build_tiles(user, group="home"):
    """
    Geef tiles terug voor een bepaalde groep, gefilterd op permissies.
    """
    if not user.is_authenticated:
        return []

    tiles = []
    for t in TILE_GROUPS.get(group, []):
        perm = t.get("perm")
        if perm is None or can(user, perm):
            tiles.append({
                "name": t["name"],
                "desc": t.get("desc", ""),
                "img": t["img"],
                "badge_class": t.get("badge_class", C["indigo"]),
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
    """
    if max_depth <= 0:
        return []

    root_items = build_tiles(user, group=root_group)

    for item in root_items:
        child_group = _resolve_child_group(item.get("url_name"))
        if child_group:
            item["children"] = build_nav_tree_recursive(
                user, root_group=child_group, max_depth=max_depth - 1
            )
        else:
            item["children"] = []

    return root_items