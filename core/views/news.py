# core/views/news.py
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import default_storage
from django.utils import timezone

from ._helpers import (
    can,
    render_pdf_to_cache,
    CACHE_DIR,
)

from core.models import NewsItem
from core.forms import NewsItemForm


# Directories
NEWS_DIR = Path(settings.MEDIA_ROOT) / "news"
CACHE_NEWS_DIR = Path(CACHE_DIR) / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_NEWS_DIR.mkdir(parents=True, exist_ok=True)

# Verlooptijd nieuws
EXPIRE_AFTER = timedelta(days=180)  # ~6 maanden

MEDIA_ROOT = Path(settings.MEDIA_ROOT)


def _delete_news_files_for_item(item: NewsItem) -> None:
    """
    Verwijdert het fysieke nieuwsbestand (PDF/afbeelding) + bijbehorende cache (voor PDF).
    Werkt in DEV (filesystem) en PROD (S3 via default_storage).
    """
    rel_path = item.file_path  # bv. "news/news.<hash>.pdf"
    ext = Path(rel_path).suffix.lower()

    # === DEV / lokaal ===
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        abs_path = MEDIA_ROOT / rel_path
        try:
            abs_path.unlink(missing_ok=True)
        except Exception:
            pass

        # Cache voor PDF op basis van hash
        if ext == ".pdf" and item.file_hash:
            cache_path = CACHE_NEWS_DIR / item.file_hash
            if cache_path.exists():
                shutil.rmtree(cache_path, ignore_errors=True)
        return

    # === PROD / S3 ===
    # origineel bestand
    try:
        default_storage.delete(rel_path)
    except Exception:
        pass

    # Cache: cache/news/<hash>/page_*.png
    if ext == ".pdf" and item.file_hash:
        cache_base = f"cache/news/{item.file_hash}"
        try:
            _dirs, files = default_storage.listdir(cache_base)
        except FileNotFoundError:
            files = []
        for name in files:
            try:
                default_storage.delete(f"{cache_base}/{name}")
            except Exception:
                pass


def _cleanup_expired_news(now: datetime) -> int:
    """
    Verwijdert nieuws-items + bestanden/caches die ouder zijn dan EXPIRE_AFTER
    (gebaseerd op uploaded_at).
    """
    cutoff = now - EXPIRE_AFTER
    qs = NewsItem.objects.filter(uploaded_at__lt=cutoff)
    removed = 0
    for item in qs:
        _delete_news_files_for_item(item)
        item.delete()
        removed += 1
    return removed


@login_required
def news(request):
    if not can(request.user, "can_view_news"):
        return HttpResponseForbidden("Geen toegang.")

    # Automatisch verlopen nieuws opruimen
    _cleanup_expired_news(timezone.now())

    # Verwijderen via kruisje (zelfde patroon als agenda)
    if request.method == "POST" and "delete_item" in request.POST:
        if not can(request.user, "can_upload_news"):
            return HttpResponseForbidden("Geen toegang.")

        item = get_object_or_404(NewsItem, id=request.POST.get("delete_item"))
        _delete_news_files_for_item(item)
        item.delete()
        messages.success(request, "Nieuwsbericht verwijderd.")
        return redirect("news")
    
    form = NewsItemForm()

    # Toevoegen/bewerken via formulier
    if request.method == "POST" and "delete_item" not in request.POST:
        if not can(request.user, "can_upload_news"):
            return HttpResponseForbidden("Geen uploadrechten.")

        form = NewsItemForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data["file"]

            # Generieke helper (gehashed, werkt met S3 + CDN)
            from ._helpers import save_pdf_or_png_with_hash

            rel_path, h = save_pdf_or_png_with_hash(
                uploaded_file=uploaded_file,
                target_dir=NEWS_DIR,
                base_name="news",
            )

            news_item = NewsItem(
                title=form.cleaned_data["title"],
                short_description=form.cleaned_data.get("short_description", ""),
                description=form.cleaned_data.get("description", ""),
                file_path=rel_path,
                file_hash=h,
                original_filename=uploaded_file.name,
            )
            news_item.save()
            messages.success(request, "Nieuwsbericht toegevoegd.")
            return redirect("news")
        else:
            # Toon nette foutmelding (bv. te groot bestand)
            file_errors = form.errors.get("file")
            if file_errors:
                for err in file_errors:
                    messages.error(request, err)
            else:
                messages.error(request, "Het nieuwsformulier bevat fouten. Controleer de invoer.")

    # GET (of invalid POST): items ophalen + previews opbouwen
    items = list(NewsItem.objects.all())  # ordering via Meta in model

    for item in items:
        # URL naar het originele bestand (S3/CDN of lokaal)
        item.file_url = item.media_url
        item.page_urls = []

        if item.is_pdf:
            rel_path = item.file_path

            # bytes inlezen
            if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
                abs_path = MEDIA_ROOT / rel_path
                try:
                    pdf_bytes = abs_path.read_bytes()
                except Exception:
                    continue
            else:
                try:
                    with default_storage.open(rel_path, "rb") as f:
                        pdf_bytes = f.read()
                except Exception:
                    continue

            # PDF → PNG’s in cache/news/<hash>/page_XXX.png
            h, n_pages = render_pdf_to_cache(
                pdf_bytes,
                dpi=300,
                cache_root=CACHE_NEWS_DIR,
            )

            # backfill hash als die nog leeg is (bij migratie)
            if not item.file_hash:
                item.file_hash = h
                item.save(update_fields=["file_hash"])

            item.page_urls = [
                f"{settings.MEDIA_URL}cache/news/{h}/page_{i:03d}.png"
                for i in range(1, n_pages + 1)
            ]

    context = {
        "news_items": items,
        "form": form,
    }
    return render(request, "news/index.html", context)