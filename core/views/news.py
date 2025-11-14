# core/views/news.py
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect

from ._helpers import (
    can,
    pdf_hash,
    render_pdf_to_cache,
    hash_from_img_url,
    CACHE_DIR,  # in jouw helpers gedefinieerd als settings.CACHE_DIR
    save_pdf_upload_with_hash, 
)

# Directories (gescheiden van policies)
NEWS_DIR = Path(settings.MEDIA_ROOT) / "news"
CACHE_NEWS_DIR = Path(CACHE_DIR) / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_NEWS_DIR.mkdir(parents=True, exist_ok=True)

# Verlooptijd nieuws
EXPIRE_AFTER = timedelta(days=183)  # ~6 maanden


def _delete_news_by_hash(hash_str: str) -> int:
    """Verwijdert alle nieuws-PDF’s met deze hash + bijbehorende cache-map."""
    removed = 0
    # Cachemap opruimen
    cache_path = CACHE_NEWS_DIR / hash_str
    if cache_path.exists():
        shutil.rmtree(cache_path, ignore_errors=True)
    # Overeenkomstige PDF's verwijderen
    for pdf_fp in list(NEWS_DIR.glob("*.pdf")):
        try:
            if pdf_hash(pdf_fp.read_bytes()) == hash_str:
                pdf_fp.unlink(missing_ok=True)
                removed += 1
        except Exception:
            pass
    return removed


def _cleanup_expired_news(now: datetime) -> int:
    """Verwijdert nieuws-PDF’s + cache ouder dan EXPIRE_AFTER."""
    removed = 0
    cutoff = now - EXPIRE_AFTER
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

    # Nieuwste eerst
    pdf_files = sorted(
        NEWS_DIR.glob("*.pdf"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    # Renderen (cache onder /cache/news/<hash>/page_XXX.png)
    page_urls = []
    for pdf_fp in pdf_files:
        try:
            pdf_bytes = pdf_fp.read_bytes()
        except Exception:
            continue
        h, n = render_pdf_to_cache(pdf_bytes, dpi=300, cache_root=CACHE_NEWS_DIR)
        for i in range(1, n + 1):
            page_urls.append(f"{settings.MEDIA_URL}cache/news/{h}/page_{i:03d}.png")

    return render(request, "news/index.html", {
        "page_urls": page_urls,
    })