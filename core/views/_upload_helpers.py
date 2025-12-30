# core/views/_upload_helpers.py
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image  # pillow

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

MEDIA_ROOT = Path(settings.MEDIA_ROOT)
CACHE_DIR = Path(settings.CACHE_DIR)

# ===== Defaults (geen settings.py afhankelijkheid) =====
DEFAULT_DPI = 220                 # 180–220 is vaak ruim voldoende voor PDF previews
DEFAULT_PREVIEW_FORMAT = "webp"   # "webp" of "png"

# WebP encoding defaults
DEFAULT_WEBP_LOSSLESS = False     # lossy = kleiner + vaak sneller
DEFAULT_WEBP_QUALITY = 85         # 70–85 is meestal prima
DEFAULT_WEBP_METHOD = 4           # 0–6 (lager = sneller, iets groter)

# Legacy support: oude PNG caches blijven werken
ALLOW_LEGACY_PNG = True


def is_local_media() -> bool:
    return bool(getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG)


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def clear_dir(p: Path) -> None:
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
    try:
        rel = target_dir.relative_to(MEDIA_ROOT)
    except ValueError:
        raise ValueError("target_dir moet onder MEDIA_ROOT liggen")
    return str(rel).replace("\\", "/").strip("/")


def read_upload_bytes(uploaded_file) -> bytes:
    """
    Lees bytes uit UploadedFile, en probeer daarna de pointer terug te zetten.
    """
    if hasattr(uploaded_file, "chunks"):
        data = b"".join(uploaded_file.chunks())
    else:
        data = uploaded_file.read()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    return data


def _save_bytes(rel_path: str, data: bytes) -> None:
    """
    rel_path is pad relatief t.o.v. MEDIA_ROOT of storage root.
    In DEV schrijven we fysiek naar MEDIA_ROOT/rel_path.
    In PROD via default_storage.
    """
    if is_local_media():
        abs_path = MEDIA_ROOT / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(data)
    else:
        default_storage.save(rel_path, ContentFile(data))


def _delete_path(rel_path: str) -> None:
    if not rel_path:
        return
    if is_local_media():
        try:
            (MEDIA_ROOT / rel_path).unlink(missing_ok=True)
        except Exception:
            pass
    else:
        try:
            default_storage.delete(rel_path)
        except Exception:
            pass


def _listdir_storage(prefix: str) -> list[str]:
    """
    Geeft alleen bestandsnamen (geen subdirs).
    """
    try:
        _dirs, files = default_storage.listdir(prefix)
    except Exception:
        files = []
    return files


def _cache_rel_str(cache_root: Path) -> str:
    """
    cache_root ligt onder CACHE_DIR (bijv CACHE_DIR/news of CACHE_DIR/rooster/week01).
    Dit geeft rel_str: "news" of "rooster/week01".
    """
    try:
        rel = cache_root.relative_to(CACHE_DIR)
        return str(rel).replace("\\", "/").strip("/")
    except ValueError:
        return ""


def _cache_base_dir(cache_root: Path, file_hash: str) -> str:
    rel_str = _cache_rel_str(cache_root)
    if rel_str:
        return f"cache/{rel_str}/{file_hash}"
    return f"cache/{file_hash}"


def _cache_url(cache_root: Path, file_hash: str, filename: str) -> str:
    rel_str = _cache_rel_str(cache_root)
    if rel_str:
        return f"{settings.MEDIA_URL}cache/{rel_str}/{file_hash}/{filename}"
    return f"{settings.MEDIA_URL}cache/{file_hash}/{filename}"


def _pil_to_webp_bytes(img: Image.Image, *, lossless: bool, quality: int, method: int) -> bytes:
    buf = BytesIO()
    save_kwargs = {"format": "WEBP", "method": method}
    if lossless:
        save_kwargs["lossless"] = True
        # quality wordt genegeerd bij lossless door Pillow, maar is harmless
        save_kwargs["quality"] = quality
    else:
        save_kwargs["lossless"] = False
        save_kwargs["quality"] = quality
    img.save(buf, **save_kwargs)
    return buf.getvalue()


def _image_bytes_to_webp_bytes(image_bytes: bytes, *, lossless: bool, quality: int, method: int) -> bytes:
    with Image.open(BytesIO(image_bytes)) as im:
        # behoud alpha indien aanwezig
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.mode else "RGB")
        return _pil_to_webp_bytes(im, lossless=lossless, quality=quality, method=method)


def save_upload_with_hash(
    uploaded_file,
    *,
    target_dir: Path,
    base_name: str,
    allowed_exts: Iterable[str] = (".pdf", ".png", ".jpg", ".jpeg", ".webp"),
    clear_existing: bool = False,
    convert_images_to_webp: bool = True,
    webp_lossless: bool = DEFAULT_WEBP_LOSSLESS,
    webp_quality: int = DEFAULT_WEBP_QUALITY,
    webp_method: int = DEFAULT_WEBP_METHOD,
) -> tuple[str, str]:
    """
    Slaat upload gehashed op in target_dir (onder MEDIA_ROOT).

    - PDF: blijft PDF (je wilt PDF bewaren als bron).
    - Image: wordt standaard geconverteerd naar WEBP (lossless nu), tenzij convert_images_to_webp=False.

    Return:
      (rel_path, file_hash)
    """
    raw = read_upload_bytes(uploaded_file)
    ext_in = (Path(uploaded_file.name).suffix or "").lower()

    allowed = {e.lower() for e in allowed_exts}
    if ext_in not in allowed:
        raise ValueError(f"Unsupported file type '{ext_in}'. Toegestaan: {', '.join(sorted(allowed))}")

    h = hash_bytes(raw)

    # optioneel: bestaande in map opruimen (rooster-week: wil je max 1 pdf)
    if clear_existing:
        if is_local_media():
            clear_dir(target_dir)
        else:
            rel_dir = _media_relpath(target_dir)
            try:
                _dirs, files = default_storage.listdir(rel_dir)
            except Exception:
                files = []
            for name in files:
                if name.startswith(f"{base_name}."):
                    try:
                        default_storage.delete(f"{rel_dir}/{name}")
                    except Exception:
                        pass

    # bepaal output bytes/ext
    if ext_in == ".pdf":
        out_bytes = raw
        ext_out = ".pdf"
    else:
        if convert_images_to_webp:
            out_bytes = _image_bytes_to_webp_bytes(
                raw,
                lossless=webp_lossless,
                quality=webp_quality,
                method=webp_method,
            )
            ext_out = ".webp"
        else:
            out_bytes = raw
            ext_out = ext_in

    filename = f"{base_name}.{h}{ext_out}"
    rel_dir = _media_relpath(target_dir)
    rel_path = f"{rel_dir}/{filename}" if rel_dir else filename

    _save_bytes(rel_path, out_bytes)
    return rel_path, h


def render_pdf_to_previews(
    pdf_bytes: bytes,
    *,
    cache_root: Path,
    file_hash: Optional[str] = None,
    dpi: int = DEFAULT_DPI,
    preview_format: str = DEFAULT_PREVIEW_FORMAT,  # "webp" of "png"
    webp_lossless: bool = DEFAULT_WEBP_LOSSLESS,
    webp_quality: int = DEFAULT_WEBP_QUALITY,
    webp_method: int = DEFAULT_WEBP_METHOD,
) -> tuple[str, int, str]:
    """
    Rendert een PDF naar page_XXX.<ext> in cache.

    Return: (hash, n_pages, ext_used)
    """
    h = file_hash or hash_bytes(pdf_bytes)
    fmt = (preview_format or "webp").lower()
    if fmt not in ("webp", "png"):
        fmt = "webp"

    # DEV: filesystem
    if is_local_media():
        out_dir = cache_root / h
        out_dir.mkdir(parents=True, exist_ok=True)

        # skip als al bestaat
        existing = list(out_dir.glob(f"page_*.{fmt}"))
        if existing:
            return h, len(existing), fmt

        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                filename = f"page_{i+1:03d}.{fmt}"
                out_path = out_dir / filename

                if fmt == "png":
                    out_path.write_bytes(pix.tobytes("png"))
                else:
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    out_path.write_bytes(
                        _pil_to_webp_bytes(img, lossless=webp_lossless, quality=webp_quality, method=webp_method)
                    )

        n_pages = len(list(out_dir.glob(f"page_*.{fmt}")))
        return h, n_pages, fmt

    # PROD: S3
    base_dir = _cache_base_dir(cache_root, h)
    files = _listdir_storage(base_dir)
    existing = [f for f in files if f.startswith("page_") and f.endswith(f".{fmt}")]
    if existing:
        return h, len(existing), fmt

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            filename = f"page_{i+1:03d}.{fmt}"
            storage_path = f"{base_dir}/{filename}"

            if fmt == "png":
                default_storage.save(storage_path, ContentFile(pix.tobytes("png")))
            else:
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                default_storage.save(
                    storage_path,
                    ContentFile(_pil_to_webp_bytes(img, lossless=webp_lossless, quality=webp_quality, method=webp_method)),
                )

    files = _listdir_storage(base_dir)
    n_pages = len([f for f in files if f.startswith("page_") and f.endswith(f".{fmt}")])
    return h, n_pages, fmt


def list_pdf_preview_urls(
    *,
    cache_root: Path,
    file_hash: str,
    prefer_format: str = DEFAULT_PREVIEW_FORMAT,
    allow_legacy_png: bool = ALLOW_LEGACY_PNG,
) -> tuple[list[str], str]:
    """
    Return: (urls, ext_used)

    Prefereer webp, maar als er alleen legacy png bestaat: return png urls.
    """
    if not file_hash:
        return [], ""

    prefer = (prefer_format or "webp").lower()
    candidates = [prefer]
    if allow_legacy_png and prefer != "png":
        candidates.append("png")

    # DEV
    if is_local_media():
        folder = cache_root / file_hash
        if not folder.exists():
            return [], ""

        for ext in candidates:
            files = sorted([p.name for p in folder.glob(f"page_*.{ext}")])
            if files:
                return ([_cache_url(cache_root, file_hash, name) for name in files], ext)
        return [], ""

    # PROD
    base_dir = _cache_base_dir(cache_root, file_hash)
    files = _listdir_storage(base_dir)

    for ext in candidates:
        pages = sorted([name for name in files if name.startswith("page_") and name.endswith(f".{ext}")])
        if pages:
            return ([_cache_url(cache_root, file_hash, name) for name in pages], ext)

    return [], ""


def ensure_pdf_previews_exist(
    *,
    pdf_bytes: bytes,
    cache_root: Path,
    file_hash: Optional[str] = None,
    dpi: int = DEFAULT_DPI,
    prefer_format: str = DEFAULT_PREVIEW_FORMAT,
    allow_legacy_png: bool = ALLOW_LEGACY_PNG,
    webp_lossless: bool = DEFAULT_WEBP_LOSSLESS,
    webp_quality: int = DEFAULT_WEBP_QUALITY,
    webp_method: int = DEFAULT_WEBP_METHOD,
) -> tuple[str, int, str]:
    """
    Zorgt dat previews bestaan. Als legacy png bestaat en toegestaan: gebruik die.
    Anders render naar prefer_format.
    """
    h = file_hash or hash_bytes(pdf_bytes)

    urls, ext = list_pdf_preview_urls(cache_root=cache_root, file_hash=h, prefer_format=prefer_format, allow_legacy_png=allow_legacy_png)
    if urls and ext:
        return h, len(urls), ext

    return render_pdf_to_previews(
        pdf_bytes,
        cache_root=cache_root,
        file_hash=h,
        dpi=dpi,
        preview_format=prefer_format,
        webp_lossless=webp_lossless,
        webp_quality=webp_quality,
        webp_method=webp_method,
    )


def delete_pdf_previews(*, cache_root: Path, file_hash: str) -> None:
    """
    Verwijdert zowel webp als png previews voor deze hash.
    """
    if not file_hash:
        return

    if is_local_media():
        folder = cache_root / file_hash
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
        return

    base_dir = _cache_base_dir(cache_root, file_hash)
    files = _listdir_storage(base_dir)
    for name in files:
        if name.startswith("page_") and (name.endswith(".webp") or name.endswith(".png")):
            try:
                default_storage.delete(f"{base_dir}/{name}")
            except Exception:
                pass


def read_storage_bytes(rel_path: str) -> bytes:
    """
    Lees bytes uit opgeslagen file (DEV of PROD).
    """
    if is_local_media():
        return (MEDIA_ROOT / rel_path).read_bytes()
    with default_storage.open(rel_path, "rb") as f:
        return f.read()