# core/views/_helpers.py
from pathlib import Path
import shutil
import hashlib

import fitz  # PyMuPDF
import pandas as pd

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

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
    "can_upload_agenda":       "Mag agenda uploaden",
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
    "can_view_beschikbaarheidsdashboard": "Mag Beschikbaarheid Personeel bekijken",
    "can_view_medicatiebeoordeling": "Mag Medicatiebeoordeling bekijken",
    "can_perform_medicatiebeoordeling": "Mag Medicatiebeoordeling uitvoeren",
}

PERM_SECTIONS = [
    ("Agenda",        ["can_view_agenda", "can_upload_agenda"]),
    ("Rooster",       ["can_view_roster", "can_upload_roster"]),
    ("Beschikbaarheid Personeel", ["can_send_beschikbaarheid", "can_view_beschikbaarheidsdashboard"]),
    ("Werkafspraken", ["can_view_policies", "can_upload_werkafspraken"]),
    ("Nieuws",        ["can_view_news", "can_upload_news"]),
    ("Voorraad",      ["can_view_av_medications", "can_upload_voorraad"]),
    ("Nazendingen",   ["can_view_av_nazendingen", "can_upload_nazendingen"]),
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

def render_pdf_to_cache(pdf_bytes: bytes, dpi: int = 300, cache_root: Path = Path("cache")):
    """
    Render PDF -> PNG's in cache_root/<hash>/page_XXX.png met hoge kwaliteit.
    Return (hash, n_pages).
    """
    h = pdf_hash(pdf_bytes)
    out = cache_root / h
    if not out.exists() or not any(out.glob("page_*.png")):
        out.mkdir(parents=True, exist_ok=True)
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                (out / f"page_{i+1:03d}.png").write_bytes(pix.tobytes("png"))
    n_pages = len(list(out.glob("page_*.png")))
    return h, n_pages

def read_table(fp: Path):
    try:
        if fp.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(fp)
        else:
            df = pd.read_csv(fp, sep=None, engine="python", encoding="utf-8-sig")
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

def save_pdf_upload_with_hash(uploaded_file, target_dir: Path, base_name: str, clear_existing: bool = True) -> Path:
    """
    Slaat een geüploade PDF op als <base_name>.<hash>.pdf in target_dir.

    - uploaded_file: Django UploadedFile (request.FILES["file"])
    - target_dir: map waarin de PDF moet komen (bijv. AGENDA_DIR, weekmap voor rooster)
    - base_name: prefix van de naam (bijv. "rooster", "agenda", "nazendingen", "news", "policy")
    - clear_existing: als True → eerst hele target_dir leegmaken

    Retourneert: Path naar het opgeslagen PDF-bestand.
    """
    # PDF in memory lezen (is nodig om te hashen)
    if hasattr(uploaded_file, "chunks"):
        pdf_bytes = b"".join(uploaded_file.chunks())
    else:
        pdf_bytes = uploaded_file.read()

    h = pdf_hash(pdf_bytes)

    target_dir.mkdir(parents=True, exist_ok=True)
    if clear_existing:
        clear_dir(target_dir)

    dest = target_dir / f"{base_name}.{h}.pdf"
    dest.write_bytes(pdf_bytes)
    return dest

def save_table_upload_with_hash(uploaded_file, target_dir: Path, base_name: str, clear_existing: bool = True) -> Path:
    """
    Slaat een geüploade CSV/Excel op als <base_name>.<hash><ext> in target_dir.

    - uploaded_file: Django UploadedFile (request.FILES["file"])
    - target_dir: map waarin het bestand moet komen (bijv. VOORRAAD_DIR)
    - base_name: prefix van de naam (bijv. "medications")
    - clear_existing: als True → bestaande CSV/Excel-bestanden in target_dir verwijderen

    Retourneert: Path naar het opgeslagen bestand.
    """
    # Bestand in memory lezen (voor hashing)
    if hasattr(uploaded_file, "chunks"):
        file_bytes = b"".join(uploaded_file.chunks())
    else:
        file_bytes = uploaded_file.read()

    ext = (Path(uploaded_file.name).suffix or "").lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise ValueError("Unsupported table extension")

    # Zelfde hash-functie als voor PDF
    h = pdf_hash(file_bytes)

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

def is_mobile_request(request) -> bool:
    ua = (request.META.get("HTTP_USER_AGENT") or "").lower()
    # Simpele maar effectieve check, gelijk aan je JS isMobile()
    return any(s in ua for s in ["android", "iphone", "ipad", "ipod"])