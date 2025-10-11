# core/views/_helpers.py
from pathlib import Path
import shutil
import hashlib

import fitz  # PyMuPDF
import pandas as pd

from django.conf import settings

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
    "can_view_av_medications": "Mag subtab Voorraad zien",
    "can_upload_voorraad":     "Mag Voorraad uploaden",
    "can_view_av_nazendingen": "Mag subtab Nazendingen zien",
    "can_upload_nazendingen":  "Mag Nazendingen uploaden",
    "can_view_news":           "Mag Nieuws bekijken",
    "can_upload_news":         "Mag Nieuws uploaden",
    "can_view_policies":       "Mag Werkafspraken bekijken",
    "can_upload_werkafspraken":"Mag Werkafspraken uploaden",
}

def can(user, codename: str) -> bool:
    return user.is_superuser or user.has_perm(f"core.{codename}")

def logo_url() -> str | None:
    """Zoekt het logo in MEDIA_ROOT/_data/logo.*"""
    logo_dir = settings.MEDIA_ROOT / "_data"
    for ext in ("png", "jpg", "jpeg", "svg", "webp"):
        p = logo_dir / f"logo.{ext}"
        if p.exists():
            return f"{settings.MEDIA_URL}_data/logo.{ext}"
    return None

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
