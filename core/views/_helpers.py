# core/views/_helpers.py
from pathlib import Path
import shutil
import hashlib

import fitz  # PyMuPDF
import pandas as pd

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from fnmatch import fnmatch
from io import BytesIO, StringIO

# ===== PATHS =====
MEDIA_ROOT = Path(settings.MEDIA_ROOT)
MEDIA_URL = settings.MEDIA_URL

CACHE_DIR = settings.CACHE_DIR
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_AGENDA_DIR = CACHE_DIR / "agenda"
CACHE_AGENDA_DIR.mkdir(parents=True, exist_ok=True)

CACHE_ROSTER_DIR = CACHE_DIR / "rooster"
CACHE_ROSTER_DIR.mkdir(parents=True, exist_ok=True)

CACHE_VOORRAAD_DIR = CACHE_DIR / "voorraad"
CACHE_VOORRAAD_DIR.mkdir(parents=True, exist_ok=True)

CACHE_NAZENDINGEN_DIR = CACHE_DIR / "nazendingen"
CACHE_NAZENDINGEN_DIR.mkdir(parents=True, exist_ok=True)

POL_DIR = MEDIA_ROOT / "policies"
POL_DIR.mkdir(parents=True, exist_ok=True)

CACHE_POLICIES_DIR = CACHE_DIR / "policies"
CACHE_POLICIES_DIR.mkdir(parents=True, exist_ok=True)

AGENDA_DIR = MEDIA_ROOT / "agenda"
AGENDA_DIR.mkdir(parents=True, exist_ok=True)
AGENDA_FILE = AGENDA_DIR / "agenda.pdf"

ROSTER_DIR = MEDIA_ROOT / "rooster"
ROSTER_DIR.mkdir(parents=True, exist_ok=True)
ROSTER_FILE = ROSTER_DIR / "rooster.pdf"

VOORRAAD_DIR = MEDIA_ROOT / "voorraad"
VOORRAAD_DIR.mkdir(parents=True, exist_ok=True)

NAZENDINGEN_DIR = MEDIA_ROOT / "nazendingen"
NAZENDINGEN_DIR.mkdir(parents=True, exist_ok=True)

# ===== PERM LABELS =====
PERM_LABELS = {
    "can_access_admin":        "Mag beheer openen",
    "can_manage_users":        "Mag gebruikers beheren",
    "can_view_agenda":         "Mag agenda bekijken",
    "can_upload_agenda":       "Mag agenda aanpassen",
    "can_view_roster":         "Mag rooster bekijken",
    "can_upload_roster":       "Mag roosters uploaden",
    "can_view_av_medications": "Mag Voorraad zien",
    "can_upload_voorraad":     "Mag Voorraad uploaden",
    "can_view_av_nazendingen": "Mag Nazendingen zien",
    "can_upload_nazendingen":  "Mag Nazendingen uploaden",
    "can_view_news":           "Mag Nieuws bekijken",
    "can_upload_news":         "Mag Nieuws uploaden",
    "can_view_policies":       "Mag Werkafspraken bekijken",
    "can_upload_werkafspraken":"Mag Werkafspraken uploaden",
    "can_send_beschikbaarheid":  "Mag Beschikbaarheid doorgeven",
    "can_view_beschikbaarheidsdashboard": "Mag Teamdashboard bekijken",
    "can_view_medicatiebeoordeling": "Mag Medicatiebeoordeling bekijken",
    "can_perform_medicatiebeoordeling": "Mag Medicatiebeoordeling uitvoeren",
    # Onboarding
    "can_view_onboarding":     "Mag Onboarding openen",
    # Personeel
    "can_view_personeel":      "Mag Personeel openen",
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
}

PERM_SECTIONS = [
    ("Agenda",        ["can_view_agenda", "can_upload_agenda"]),
    ("Nieuws",        ["can_view_news", "can_upload_news"]),
    ("Rooster",       ["can_view_roster", "can_upload_roster"]),
    ("Beschikbaarheid",       ["can_send_beschikbaarheid"]),

    ("Personeel", ["can_view_personeel", "can_view_beschikbaarheidsdashboard",]),

    ("Onboarding", [
        "can_view_onboarding", "can_view_whoiswho", "can_edit_whoiswho","can_view_forms","can_edit_forms", "can_view_checklist", "can_edit_checklist", ]),

    ("Baxter", [
        "can_view_baxter",
        "can_view_baxter_omzettingslijst", "can_edit_baxter_omzettingslijst",
        "can_view_baxter_no_delivery",     "can_edit_baxter_no_delivery",
        "can_view_baxter_sts_halfjes",     "can_edit_baxter_sts_halfjes",
        "can_view_baxter_laatste_potten",  "can_edit_baxter_laatste_potten",
        "can_view_av_medications", "can_upload_voorraad", "can_view_av_nazendingen", "can_upload_nazendingen"
    ]),

    ("Werkafspraken", ["can_view_policies", "can_upload_werkafspraken"]),
    ("Medicatiereview", ["can_view_medicatiebeoordeling", "can_perform_medicatiebeoordeling"]),
    ("Beheer",        ["can_access_admin", "can_manage_users"]),
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

def can(user, codename: str) -> bool:
    return user.is_superuser or user.has_perm(f"core.{codename}")

# ===== Generieke helpers =====
def pdf_hash(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()[:16]

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

def _media_relpath(target_dir: Path) -> str:
    """
    Geeft het pad van target_dir relatief t.o.v. MEDIA_ROOT, als 'subdir/subdir2'.
    """
    try:
        rel = target_dir.relative_to(MEDIA_ROOT)
    except ValueError:
        raise ValueError("target_dir moet onder MEDIA_ROOT liggen")
    return str(rel).replace("\\", "/").strip("/")

def render_pdf_to_cache(pdf_bytes: bytes, dpi: int = 300, cache_root: Path | None = None):
    """
    Render PDF -> PNG's in media/cache/<subdir>/<hash>/page_XXX.png.

    - In DEV (of als SERVE_MEDIA_LOCALLY=True): schrijf naar het lokale filesystem
      onder settings.CACHE_DIR.
    - In PROD: schrijf naar S3 via default_storage, zodat CloudFront/CDN ze kan serveren.

    Parameters
    ----------
    pdf_bytes : bytes
        De inhoud van de PDF.
    dpi : int
        Resolutie van gerenderde PNG's.
    cache_root : Path | None
        Lokale map onder CACHE_DIR voor deze cache:
          bijv. CACHE_AGENDA_DIR (= CACHE_DIR / "agenda")
                CACHE_NEWS_DIR   (= CACHE_DIR / "news")
                week_cache_dir   (= CACHE_DIR / "rooster" / "weekNN")
        In DEV gebruiken we dit als echte directory.
        In PROD gebruiken we het alleen om de S3-prefix te bepalen
        (relatief pad t.o.v. CACHE_DIR).
    """
    h = pdf_hash(pdf_bytes)

    # Standaard: direct onder CACHE_DIR
    if cache_root is None:
        cache_root = CACHE_DIR

    # === DEV / lokaal cache ===
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        out_dir = cache_root / h
        out_dir.mkdir(parents=True, exist_ok=True)

        if not any(out_dir.glob("page_*.png")):
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=dpi, alpha=False)
                    (out_dir / f"page_{i+1:03d}.png").write_bytes(pix.tobytes("png"))

        n_pages = len(list(out_dir.glob("page_*.png")))
        return h, n_pages

    # === PROD / S3 cache ===
    # Bepaal relatieve subdir t.o.v. CACHE_DIR, bijv.:
    #   cache_root = CACHE_DIR / "agenda"        -> rel = "agenda"
    #   cache_root = CACHE_DIR / "news"          -> rel = "news"
    #   cache_root = CACHE_DIR / "rooster/week01"-> rel = "rooster/week01"
    try:
        rel = cache_root.relative_to(CACHE_DIR)
        rel_str = str(rel).replace("\\", "/").strip("/")
    except ValueError:
        # fallback: als cache_root niet onder CACHE_DIR ligt
        rel_str = ""

    if rel_str:
        base_dir = f"cache/{rel_str}/{h}"
    else:
        base_dir = f"cache/{h}"

    # Kijk of er al PNG's zijn in S3
    try:
        _, files = default_storage.listdir(base_dir)
    except FileNotFoundError:
        files = []

    png_files = [f for f in files if f.startswith("page_") and f.endswith(".png")]

    if not png_files:
        # Nog niet gerenderd → render naar S3
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                file_path = f"{base_dir}/page_{i+1:03d}.png"
                default_storage.save(file_path, ContentFile(pix.tobytes("png")))

        # opnieuw ophalen voor het aantal pagina's
        _, files = default_storage.listdir(base_dir)
        png_files = [f for f in files if f.startswith("page_") and f.endswith(".png")]

    n_pages = len(png_files)
    return h, n_pages

def read_table(fp):
    """
    Leest een CSV/Excel:

    - DEV: fp is meestal een Path op het filesystem.
    - PROD: fp is een storage-pad (string) voor default_storage (S3).

    Retourneert (df, error).
    """
    try:
        if isinstance(fp, Path):
            suffix = fp.suffix.lower()
            if suffix in (".xlsx", ".xls"):
                df = pd.read_excel(fp)
            else:
                df = pd.read_csv(fp, sep=None, engine="python", encoding="utf-8-sig")
        else:
            # String-pad voor storage (S3 of FileSystemStorage)
            suffix = Path(str(fp)).suffix.lower()
            with default_storage.open(fp, "rb") as f:
                raw = f.read()

            if suffix in (".xlsx", ".xls"):
                df = pd.read_excel(BytesIO(raw))
            else:
                text = raw.decode("utf-8-sig", errors="replace")
                df = pd.read_csv(StringIO(text), sep=None, engine="python")
        df.columns = [str(c) for c in df.columns]
        return df, None
    except Exception as e:
        return None, f"Kon bestand niet lezen: {e}"

def filter_and_limit(df, q, limit):
    if df is None:
        return df
    work = df
    if q:
        ql = q.lower()
        mask = pd.Series(False, index=work.index)
        for col in work.columns:
            try:
                mask = mask | work[col].astype(str).str.lower().str.contains(ql, na=False)
            except Exception:
                pass
        work = work[mask]
    if limit and limit > 0:
        work = work.head(limit)
    return work

def hash_from_img_url(img_url: str) -> str | None:
    """
    Haalt de hash uit een image-URL van het type:
      /media/cache/<subdir>/<hash>/page_001.png

    Werkt voor alle cache-submappen (bv. policies, news, voorraad, nazendingen, enz.).
    Verwacht dat MEDIA_URL correct eindigt met een '/'.
    """
    prefix = f"{settings.MEDIA_URL}cache/"
    if not img_url.startswith(prefix):
        return None

    rest = img_url[len(prefix):]  # bv. "policies/<hash>/page_001.png"
    parts = rest.split("/")
    if len(parts) >= 2:
        # parts[0] = subdir (policies, news, etc.)
        # parts[1] = hash
        return parts[1]
    return None

def save_pdf_upload_with_hash(uploaded_file, target_dir: Path, base_name: str, clear_existing: bool = True):
    """
    Slaat een geüploade PDF op als <base_name>.<hash>.pdf.

    DEV (SERVE_MEDIA_LOCALLY=True of DEBUG=True):
        - Schrijft direct naar filesystem onder target_dir (Path).
    PROD:
        - Schrijft naar S3 via default_storage, onder 'media/<subdir>/<base_name>.<hash>.pdf'.

    Retourneert:
        DEV: Path naar lokaal bestand
        PROD: storage-pad (string) relatief t.o.v. 'media' locatie, bv. 'agenda/agenda.<hash>.pdf'
    """
    # PDF in memory lezen (is nodig om te hashen)
    if hasattr(uploaded_file, "chunks"):
        pdf_bytes = b"".join(uploaded_file.chunks())
    else:
        pdf_bytes = uploaded_file.read()

    h = pdf_hash(pdf_bytes)

    # === DEV / lokaal ===
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        target_dir.mkdir(parents=True, exist_ok=True)
        if clear_existing:
            clear_dir(target_dir)

        dest = target_dir / f"{base_name}.{h}.pdf"
        dest.write_bytes(pdf_bytes)
        return dest

    # === PROD / S3 ===
    rel_dir = _media_relpath(target_dir)  # bv. "agenda", "policies", "nazendingen"
    # bestaande bestanden opruimen als clear_existing=True
    if clear_existing:
        try:
            _, files = default_storage.listdir(rel_dir)
        except FileNotFoundError:
            files = []
        for name in files:
            if name.startswith(f"{base_name}.") and name.endswith(".pdf"):
                default_storage.delete(f"{rel_dir}/{name}")

    filename = f"{base_name}.{h}.pdf"
    storage_path = f"{rel_dir}/{filename}" if rel_dir else filename
    default_storage.save(storage_path, ContentFile(pdf_bytes))
    return storage_path

def save_table_upload_with_hash(uploaded_file, target_dir: Path, base_name: str, clear_existing: bool = True):
    """
    Slaat een geüploade CSV/Excel op als <base_name>.<hash><ext> in target_dir.

    DEV:
        - Lokaal filesystem.
    PROD:
        - S3 via default_storage onder 'media/<subdir>/<base_name>.<hash><ext>'.

    Retourneert:
        DEV: Path object
        PROD: storage-pad (string) relatief t.o.v. 'media'.
    """
    # Bestand in memory lezen (voor hashing)
    if hasattr(uploaded_file, "chunks"):
        file_bytes = b"".join(uploaded_file.chunks())
    else:
        file_bytes = uploaded_file.read()

    ext = (Path(uploaded_file.name).suffix or "").lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise ValueError("Unsupported table extension")

    h = pdf_hash(file_bytes)

    # === DEV / lokaal ===
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        target_dir.mkdir(parents=True, exist_ok=True)

        if clear_existing:
            # Alleen bestaande CSV/Excel-bestanden weghalen
            for p in target_dir.iterdir():
                if p.is_file() and p.suffix.lower() in (".csv", ".xlsx", ".xls"):
                    try:
                        p.unlink()
                    except Exception:
                        pass

        dest = target_dir / f"{base_name}.{h}{ext}"
        dest.write_bytes(file_bytes)
        return dest

    # === PROD / S3 ===
    rel_dir = _media_relpath(target_dir)  # bv. "voorraad"

    if clear_existing:
        try:
            _, files = default_storage.listdir(rel_dir)
        except FileNotFoundError:
            files = []
        for name in files:
            if name.startswith(f"{base_name}.") and Path(name).suffix.lower() in (".csv", ".xlsx", ".xls"):
                default_storage.delete(f"{rel_dir}/{name}")

    filename = f"{base_name}.{h}{ext}"
    storage_path = f"{rel_dir}/{filename}" if rel_dir else filename
    default_storage.save(storage_path, ContentFile(file_bytes))
    return storage_path

def is_mobile_request(request) -> bool:
    ua = (request.META.get("HTTP_USER_AGENT") or "").lower()
    # Simpele maar effectieve check, gelijk aan je JS isMobile()
    return any(s in ua for s in ["android", "iphone", "ipad", "ipod"])