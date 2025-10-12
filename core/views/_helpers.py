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
DATA_DIR = settings.DATA_DIR
MEDIA_ROOT = Path(settings.MEDIA_ROOT)
MEDIA_URL = settings.MEDIA_URL

CACHE_DIR = settings.CACHE_DIR
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_ROSTER_DIR = CACHE_DIR / "rooster"
CACHE_ROSTER_DIR.mkdir(parents=True, exist_ok=True)

CACHE_AVAIL_DIR = CACHE_DIR / "availability"
CACHE_AVAIL_DIR.mkdir(parents=True, exist_ok=True)

POL_DIR = MEDIA_ROOT / "policies"
POL_DIR.mkdir(parents=True, exist_ok=True)

CACHE_POLICIES_DIR = CACHE_DIR / "policies"
CACHE_POLICIES_DIR.mkdir(parents=True, exist_ok=True)

ROSTER_DIR = MEDIA_ROOT / "rooster"
ROSTER_DIR.mkdir(parents=True, exist_ok=True)
ROSTER_FILE = ROSTER_DIR / "rooster.pdf"

AV_DIR = MEDIA_ROOT / "availability"
AV_DIR.mkdir(parents=True, exist_ok=True)

# ===== PERM LABELS =====
PERM_LABELS = {
    "can_access_admin":        "Mag beheer openen",
    "can_manage_users":        "Mag gebruikers beheren",
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
}

PERM_SECTIONS = [
    ("Beheer",        ["can_access_admin", "can_manage_users"]),
    ("Rooster",       ["can_view_roster", "can_upload_roster"]),
    ("Voorraad",      ["can_view_av_medications", "can_upload_voorraad"]),
    ("Nazendingen",   ["can_view_av_nazendingen", "can_upload_nazendingen"]),
    ("Werkafspraken", ["can_view_policies", "can_upload_werkafspraken"]),
    ("Nieuws",        ["can_view_news", "can_upload_news"]),
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

def render_pdf_to_cache(pdf_bytes: bytes, zoom: float, cache_root: Path):
    """
    Render PDF -> PNG's in cache_root/<hash>/page_XXX.png.
    Return (hash, n_pages).
    """
    h = pdf_hash(pdf_bytes)
    out = cache_root / h
    if not out.exists() or not any(out.glob("page_*.png")):
        out.mkdir(parents=True, exist_ok=True)
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            mat = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=mat, alpha=False)
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
    /media/cache/policies/<hash>/page_001.png -> <hash>
    """
    prefix = f"{settings.MEDIA_URL}cache/policies/"
    if not img_url.startswith(prefix):
        return None
    rest = img_url[len(prefix):]
    parts = rest.split("/")
    return parts[0] if parts else None
