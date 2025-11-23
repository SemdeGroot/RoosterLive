# core/views/news.py
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.core.files.storage import default_storage

from ._helpers import (
    can,
    pdf_hash,
    render_pdf_to_cache,
    hash_from_img_url,
    CACHE_DIR,  # in jouw helpers gedefinieerd als settings.CACHE_DIR
    save_pdf_upload_with_hash,
    _media_relpath,
)

# Directories (gescheiden van policies)
NEWS_DIR = Path(settings.MEDIA_ROOT) / "news"
CACHE_NEWS_DIR = Path(CACHE_DIR) / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_NEWS_DIR.mkdir(parents=True, exist_ok=True)

# Verlooptijd nieuws
EXPIRE_AFTER = timedelta(days=180)  # ~6 maanden


def _delete_news_by_hash(hash_str: str) -> int:
    """Verwijdert alle nieuws-PDF’s met deze hash + bijbehorende cache-map."""
    removed = 0

    # === DEV: lokaal filesystem ===
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        cache_path = CACHE_NEWS_DIR / hash_str
        if cache_path.exists():
            shutil.rmtree(cache_path, ignore_errors=True)

        for pdf_fp in list(NEWS_DIR.glob("*.pdf")):
            try:
                if pdf_hash(pdf_fp.read_bytes()) == hash_str:
                    pdf_fp.unlink(missing_ok=True)
                    removed += 1
            except Exception:
                pass
        return removed

    # === PROD: S3 ===
    # Cache: cache/news/<hash>/page_*.png
    cache_base = f"cache/news/{hash_str}"
    try:
        _dirs, files = default_storage.listdir(cache_base)
    except FileNotFoundError:
        files = []
    for name in files:
        default_storage.delete(f"{cache_base}/{name}")

    # Nieuws-PDF's in S3: media/news/*.pdf
    rel_dir = _media_relpath(NEWS_DIR)  # "news"
    try:
        _dirs, files = default_storage.listdir(rel_dir)
    except FileNotFoundError:
        files = []

    for name in list(files):
        if not name.lower().endswith(".pdf"):
            continue
        storage_path = f"{rel_dir}/{name}"
        try:
            with default_storage.open(storage_path, "rb") as f:
                raw = f.read()
            if pdf_hash(raw) == hash_str:
                default_storage.delete(storage_path)
                removed += 1
        except Exception:
            continue

    return removed

def _cleanup_expired_news(now: datetime) -> int:
    """Verwijdert nieuws-PDF’s + cache ouder dan EXPIRE_AFTER (DEV + PROD)."""
    removed = 0
    cutoff = now - EXPIRE_AFTER

    # === DEV: lokaal filesystem ===
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        for pdf_fp in list(NEWS_DIR.glob("*.pdf")):
            try:
                mtime = datetime.fromtimestamp(pdf_fp.stat().st_mtime)
                if mtime < cutoff:
                    try:
                        h = pdf_hash(pdf_fp.read_bytes())
                    except Exception:
                        h = None
                    pdf_fp.unlink(missing_ok=True)
                    removed += 1
                    if h:
                        cache_path = CACHE_NEWS_DIR / h
                        if cache_path.exists():
                            shutil.rmtree(cache_path, ignore_errors=True)
            except Exception:
                continue
        return removed

    # === PROD: S3 ===
    rel_dir = _media_relpath(NEWS_DIR)  # "news"
    try:
        _dirs, files = default_storage.listdir(rel_dir)
    except FileNotFoundError:
        files = []

    for name in list(files):
        if not name.lower().endswith(".pdf"):
            continue
        storage_path = f"{rel_dir}/{name}"
        try:
            mtime = default_storage.get_modified_time(storage_path)
            # maak naive voor vergelijking met cutoff
            if getattr(mtime, "tzinfo", None) is not None:
                mtime = mtime.replace(tzinfo=None)
            if mtime < cutoff:
                try:
                    with default_storage.open(storage_path, "rb") as f:
                        raw = f.read()
                    h = pdf_hash(raw)
                except Exception:
                    h = None
                default_storage.delete(storage_path)
                removed += 1
                if h:
                    cache_base = f"cache/news/{h}"
                    try:
                        _cdirs, cfiles = default_storage.listdir(cache_base)
                    except FileNotFoundError:
                        cfiles = []
                    for fname in cfiles:
                        default_storage.delete(f"{cache_base}/{fname}")
        except Exception:
            continue

    return removed

@login_required
def news(request):
    if not can(request.user, "can_view_news"):
        return HttpResponseForbidden("Geen toegang.")

    # AJAX delete (exacte flow als policies)
    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if not can(request.user, "can_upload_news"):
            return JsonResponse({"ok": False, "error": "Geen rechten."}, status=403)
        if request.POST.get("action") != "delete":
            return JsonResponse({"ok": False, "error": "Ongeldig verzoek."}, status=400)
        img_url = request.POST.get("img", "")
        h = hash_from_img_url(img_url)  # generiek: pakt /cache/<subdir>/<hash>/...
        if not h:
            return JsonResponse({"ok": False, "error": "Ongeldige afbeelding."}, status=400)
        removed = _delete_news_by_hash(h)
        if removed > 0:
            return JsonResponse({"ok": True, "hash": h, "removed": removed})
        else:
            return JsonResponse({"ok": False, "error": "PDF niet gevonden."}, status=404)

    # Upload PDF
    if request.method == "POST" and "file" in request.FILES:
        if not can(request.user, "can_upload_news"):
            return HttpResponseForbidden("Geen uploadrechten.")
        f = request.FILES.get("file")
        if not f or not str(f.name).lower().endswith(".pdf"):
            messages.error(request, "Alleen PDF toegestaan.")
            return redirect("news")
        # Bewaar nieuws als news.<hash>.pdf (meerdere naast elkaar)
        save_pdf_upload_with_hash(
            uploaded_file=f,
            target_dir=NEWS_DIR,
            base_name="news",
            clear_existing=False,   # meerdere nieuwsberichten
        )
        messages.success(request, f"PDF geüpload: {f.name}")
        return redirect("news")

    # Opruimen verlopen nieuws vóór renderen
    _cleanup_expired_news(datetime.now())

    page_urls = []

    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        # Nieuwste eerst op basis van mtime
        pdf_files = sorted(
            NEWS_DIR.glob("*.pdf"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for pdf_fp in pdf_files:
            try:
                pdf_bytes = pdf_fp.read_bytes()
            except Exception:
                continue
            h, n = render_pdf_to_cache(pdf_bytes, dpi=300, cache_root=CACHE_NEWS_DIR)
            for i in range(1, n + 1):
                page_urls.append(f"{settings.MEDIA_URL}cache/news/{h}/page_{i:03d}.png")
    else:
        # PROD: S3
        rel_dir = _media_relpath(NEWS_DIR)  # "news"
        try:
            _dirs, files = default_storage.listdir(rel_dir)
        except FileNotFoundError:
            files = []

        pdf_infos = []
        for name in files:
            if not name.lower().endswith(".pdf"):
                continue
            storage_path = f"{rel_dir}/{name}"
            try:
                mtime = default_storage.get_modified_time(storage_path)
            except Exception:
                mtime = None
            pdf_infos.append((name, mtime))

        # sorteer op mtime aflopend (onbekende tijden laatst)
        pdf_infos.sort(key=lambda t: (t[1] or datetime.min), reverse=True)

        for name, _mtime in pdf_infos:
            storage_path = f"{rel_dir}/{name}"
            try:
                with default_storage.open(storage_path, "rb") as f:
                    pdf_bytes = f.read()
            except Exception:
                continue

            h, n = render_pdf_to_cache(pdf_bytes, dpi=300, cache_root=CACHE_NEWS_DIR)
            for i in range(1, n + 1):
                page_urls.append(f"{settings.MEDIA_URL}cache/news/{h}/page_{i:03d}.png")

    return render(request, "news/index.html", {
        "page_urls": page_urls,
    })