# core/views/_helpers.py
from pathlib import Path
import shutil

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.staticfiles import finders
from django.http import HttpRequest

from core.permissions_cache import get_cached_permset

from weasyprint import HTML, CSS

# ===== PATHS =====
MEDIA_ROOT = Path(settings.MEDIA_ROOT)
MEDIA_URL = settings.MEDIA_URL

CACHE_DIR = settings.CACHE_DIR
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_ROSTER_DIR = CACHE_DIR / "rooster"
CACHE_ROSTER_DIR.mkdir(parents=True, exist_ok=True)

ROSTER_DIR = MEDIA_ROOT / "rooster"
ROSTER_DIR.mkdir(parents=True, exist_ok=True)
ROSTER_FILE = ROSTER_DIR / "rooster.pdf"

DB_PATH = settings.BASE_DIR / "lookup.db"

# ===== PERM LABELS =====
PERM_LABELS = {
    "can_access_admin":        "Mag beheer openen",
    "can_access_profiel":        "Mag profiel aanpassen",
    "can_manage_users":        "Mag gebruikers beheren",
    "can_manage_groups":              "Mag groepen beheren",
    "can_manage_afdelingen":              "Mag afdelingen beheren",
    "can_manage_orgs":              "Mag organisaties beheren",
    "can_manage_tasks":              "Mag taken beheren",
    "can_view_agenda":         "Mag agenda bekijken",
    "can_upload_agenda":       "Mag agenda aanpassen",
    "can_view_roster":         "Mag rooster bekijken",
    "can_upload_roster":       "Mag roosters uploaden",
    "can_view_av_medications": "Mag Voorraad zien",
    "can_upload_voorraad":     "Mag Voorraad uploaden",
    "can_view_av_nazendingen": "Mag Nazendingen zien",
    "can_upload_nazendingen":  "Mag Nazendingen uploaden en versturen",
    "can_view_news":           "Mag Nieuws bekijken",
    "can_upload_news":         "Mag Nieuws uploaden",
    "can_view_policies":       "Mag Werkafspraken bekijken",
    "can_upload_werkafspraken":"Mag Werkafspraken uploaden",
    "can_send_beschikbaarheid":  "Mag Beschikbaarheid doorgeven",
    "can_view_beschikbaarheidsdashboard": "Mag Teamdashboard bekijken",
    "can_edit_beschikbaarheidsdashboard": "Mag diensten toewijzen",
    "can_view_medicatiebeoordeling": "Mag Medicatiebeoordeling bekijken",
    "can_perform_medicatiebeoordeling": "Mag Medicatiebeoordeling uitvoeren",
    # Onboarding
    "can_view_onboarding":     "Mag Onboarding openen",
    # Personeel
    "can_view_personeel":      "Mag Personeel openen",
    # Diensten
    "can_view_diensten":       "Mag Diensten bekijken",
    # Uren doorgeven
    "can_view_urendoorgeven":       "Mag uren doorgeven",
    "can_edit_urendoorgeven": "Mag uren toeslag aanpassen",
    # Ziek melden
    "can_view_ziekmelden":       "Mag Ziek Melden bekijken",
    "can_edit_ziekmelden":       "Mag personeel ziek melden",
    # Inschrijven
    "can_view_inschrijven":       "Mag zich inschrijven",
    "can_edit_inschrijven":       "Mag inschrijving formulieren aanpassen",
    # Wie is Wie?
    "can_view_whoiswho":       "Mag Wie is wie? bekijken",
    "can_edit_whoiswho":       "Mag Wie is wie? aanpassen",
    # Forms
    "can_view_forms":          "Mag formulieren bekijken",
    "can_edit_forms":          "Mag formulieren aanpassen",
    # Checklist
    "can_view_checklist":      "Mag checklist bekijken",
    "can_edit_checklist":      "Mag checklist aanpassen",
    "can_view_baxter":                 "Mag Baxter openen",
    "can_view_baxter_omzettingslijst": "Mag Baxter-omzettingslijst bekijken",
    "can_edit_baxter_omzettingslijst": "Mag Baxter-omzettingslijst aanpassen",
    "can_view_baxter_no_delivery":     "Mag 'Geen levering' bekijken",
    "can_edit_baxter_no_delivery":     "Mag 'Geen levering' aanpassen",
    "can_view_baxter_sts_halfjes":     "Mag STS-halfjes bekijken",
    "can_edit_baxter_sts_halfjes":     "Mag STS-halfjes aanpassen",
    "can_view_baxter_laatste_potten":  "Mag laatste potten bekijken",
    "can_edit_baxter_laatste_potten":  "Mag laatste potten aanpassen",
    "can_perform_bestellingen":     "Krijgt een melding bij toevoeging laatste potten",
    "can_view_openbare_apo":    "Mag Openbare apotheek-tegel zien",
    "can_view_instellings_apo": "Mag Instellingsapotheek-tegel zien",
    "can_view_reviewplanner": "Mag Review Planner bekijken",
    "can_edit_reviewplanner": "Mag Review Planner bewerken",
    "can_view_portavita": "Mag Portavita Check bekijken",
    "can_edit_portavita": "Mag Portavita Check uitvoeren",
}

PERM_SECTIONS = [
    ("Agenda",        ["can_view_agenda", "can_upload_agenda"]),
    ("Nieuws",        ["can_view_news", "can_upload_news"]),
    ("Rooster",       ["can_view_roster", "can_upload_roster"]),
    ("Beschikbaarheid",       ["can_send_beschikbaarheid"]),

    ("Personeel", ["can_view_personeel", "can_view_beschikbaarheidsdashboard", "can_edit_beschikbaarheidsdashboard", "can_view_diensten", "can_view_urendoorgeven", "can_edit_urendoorgeven", "can_view_ziekmelden", "can_edit_ziekmelden", "can_view_inschrijven", "can_edit_inschrijven", "can_view_policies", "can_upload_werkafspraken"]),

    ("Onboarding", [
        "can_view_onboarding", "can_view_whoiswho", "can_edit_whoiswho","can_view_forms","can_edit_forms", "can_view_checklist", "can_edit_checklist", ]),

    ("Baxter", [
        "can_view_baxter",
        "can_view_baxter_omzettingslijst", "can_edit_baxter_omzettingslijst",
        "can_view_baxter_no_delivery",     "can_edit_baxter_no_delivery",
        "can_view_baxter_sts_halfjes",     "can_edit_baxter_sts_halfjes",
        "can_view_baxter_laatste_potten",  "can_edit_baxter_laatste_potten", "can_perform_bestellingen",
        "can_view_av_medications", "can_upload_voorraad", "can_view_av_nazendingen", "can_upload_nazendingen"
    ]),

    ("Openbare Apotheek", ["can_view_openbare_apo"]),
    ("Instellingsapotheek", ["can_view_instellings_apo", "can_view_medicatiebeoordeling", "can_perform_medicatiebeoordeling", "can_view_reviewplanner", "can_edit_reviewplanner", "can_view_portavita", "can_edit_portavita"]),
    ("Profiel",        ["can_access_profiel"]),
    ("Beheer",        ["can_access_admin", "can_manage_users", "can_manage_groups", "can_manage_afdelingen", "can_manage_orgs", "can_manage_tasks"]),
]

def sync_custom_permissions():
    """
    Sync auth_permission met PERM_LABELS.
    Mist er één? → aanmaken. Bestaat er één te veel? → verwijderen.
    Gebruikt content type: (app_label='core', model='custompermission').
    """
    ct, _ = ContentType.objects.get_or_create(app_label="core", model="custompermission")
    existing = set(Permission.objects.filter(content_type=ct).values_list("codename", flat=True))
    desired = set(PERM_LABELS.keys())

    # create missing
    for code in desired - existing:
        Permission.objects.create(codename=code, name=PERM_LABELS[code], content_type=ct)

    # delete stale
    stale = existing - desired
    if stale:
        Permission.objects.filter(content_type=ct, codename__in=stale).delete()

def can(obj, codename: str) -> bool:
    """
    Werkt met zowel request als user:
      can(request, "can_access_admin")
      can(request.user, "can_access_admin")
    """
    request = obj if isinstance(obj, HttpRequest) else None
    user = obj.user if request else obj

    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    perm = codename if "." in codename else f"core.{codename}"

    # request-local cache zodat meerdere can() calls in één view niet steeds Redis doen
    if request is not None:
        cached = getattr(request, "_permset_cache", None)
        if cached is None:
            cached = get_cached_permset(user)
            request._permset_cache = cached
        return perm in cached

    return perm in get_cached_permset(user)

# ===== Clear dir voor rooster =====

def clear_dir(p: Path):
    if not p.exists():
        return
    for item in p.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            try:
                item.unlink()
            except Exception:
                pass


# === Mobile check ===

def is_mobile_request(request) -> bool:
    ua = (request.META.get("HTTP_USER_AGENT") or "").lower()
    # Simpele maar effectieve check, gelijk aan je JS isMobile()
    return any(s in ua for s in ["android", "iphone", "ipad", "ipod"])

# === PDF export helpers === 
def _static_abs_path(static_path: str) -> str:
    path = finders.find(static_path)
    if not path:
        raise FileNotFoundError(f"Static file niet gevonden: {static_path}")
    return path

def _render_pdf(html: str, *, base_url: str) -> bytes:
    css = CSS(string="""
        :root { --accent: #062A5E; }  /* donkerder blauw */

        @page { size: A4; margin: 14mm; }

        body {
          font-family: Arial, sans-serif;
          font-size: 11pt;
          color: #111;
          background: #fff;
        }

        .pdf-header {
          display: flex;
          align-items: center;
          gap: 16px;
          border-bottom: 2px solid var(--accent);
          padding-bottom: 12px;
          margin-bottom: 14px;
        }

        .pdf-logo {
          width: 100px;
          height: auto;
          object-fit: contain;
        }

        .pdf-title {
          font-size: 20pt;
          font-weight: 700;
          margin: 0;
        }

        .pdf-submeta {
          margin-top: 6px;
          font-size: 10pt;
          color: #444;
          line-height: 1.4;
        }

        .prepared-by {
          margin-top: 6px;
          font-size: 10pt;
        }

        .section-title {
          font-size: 13pt;
          font-weight: 700;
          margin: 20px 0 10px;
          color: var(--accent);
        }

        .group-title {
          font-size: 11pt;
          font-weight: 700;
          margin-top: 14px;
          color: var(--accent);
        }

        table {
          width: 100%;
          border-collapse: collapse;
          margin-top: 8px;
        }

        th, td {
          border: 1px solid #ddd;
          padding: 7px 8px;
          vertical-align: top;
        }

        th {
          background: #f4f6fb;
          font-weight: 700;
        }

        .muted { color: #666; }

        .comment-box {
          margin-top: 10px;
          padding: 10px;
          border-left: 4px solid var(--accent);
          background: #f9faff;
        }

        .comment-label {
          font-weight: 700;
          margin-bottom: 4px;
        }

        .divider {
          border-top: 1px solid #eee;
          margin: 18px 0;
        }

        .toc-link {
          color: var(--accent);
          text-decoration: none;
        }

        /* Nieuw: elke patiënt op nieuwe pagina in afdeling export */
        .patient-page {
          page-break-before: always;
        }
        .patient-page.first-patient {
          page-break-before: auto;
        }
    """)

    return HTML(string=html, base_url=base_url).write_pdf(stylesheets=[css])