# core/views/news.py
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from core.models import NewsItem
from core.forms import NewsItemForm
from core.tasks import send_news_uploaded_push_task

from ._helpers import can
from ._upload_helpers import (
    save_upload_with_hash,
    read_storage_bytes,
    ensure_pdf_previews_exist,
    list_pdf_preview_urls,
    delete_pdf_previews,
    DEFAULT_DPI,
    DEFAULT_PREVIEW_FORMAT,
    DEFAULT_WEBP_LOSSLESS,
    DEFAULT_WEBP_QUALITY,
    DEFAULT_WEBP_METHOD,
    ALLOW_LEGACY_PNG,
)

# Directories
NEWS_DIR = Path(settings.MEDIA_ROOT) / "news"
CACHE_NEWS_DIR = Path(settings.CACHE_DIR) / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_NEWS_DIR.mkdir(parents=True, exist_ok=True)

MEDIA_ROOT = Path(settings.MEDIA_ROOT)

# Verlooptijd nieuws
EXPIRE_AFTER = timedelta(days=180)  # ~6 maanden


# -----------------------------
# Reference checks (BUGFIX)
# -----------------------------
def _blob_in_use(*, rel_path: str, file_hash: str | None, exclude_id: int | None) -> bool:
    """
    True als dezelfde blob (hash óf rel_path) nog door een ander NewsItem wordt gebruikt.
    - Bij voorkeur dedupe op file_hash.
    - Fallback op rel_path voor oude records zonder hash.
    """
    qs = NewsItem.objects.all()
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)

    if file_hash:
        return qs.filter(file_hash=file_hash).exists()

    if rel_path:
        return qs.filter(file_path=rel_path).exists()

    return False


def _delete_news_files(*, rel_path: str, file_hash: str | None, exclude_id: int | None = None) -> None:
    """
    Verwijder bronbestand + preview cache, MAAR alleen als niemand anders dezelfde blob gebruikt.
    """
    if not rel_path:
        return

    # === BUGFIX: shared blob -> niet deleten ===
    if _blob_in_use(rel_path=rel_path, file_hash=file_hash, exclude_id=exclude_id):
        return

    ext = Path(rel_path).suffix.lower()

    # ---- bronbestand ----
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        abs_path = MEDIA_ROOT / rel_path
        try:
            abs_path.unlink(missing_ok=True)
        except Exception:
            pass
    else:
        try:
            default_storage.delete(rel_path)
        except Exception:
            pass

    # ---- previews (alleen relevant voor PDF) ----
    if ext == ".pdf" and file_hash:
        delete_pdf_previews(cache_root=CACHE_NEWS_DIR, file_hash=file_hash)


def _delete_news_files_for_item(item: NewsItem) -> None:
    _delete_news_files(rel_path=item.file_path or "", file_hash=item.file_hash or None, exclude_id=item.id)


def _cleanup_expired_news(now: datetime) -> int:
    cutoff = now - EXPIRE_AFTER
    qs = NewsItem.objects.filter(uploaded_at__lt=cutoff)
    removed = 0
    for item in qs:
        _delete_news_files_for_item(item)
        item.delete()
        removed += 1
    return removed


# -----------------------------
# Media endpoint (lazy)
# -----------------------------
@login_required
def news_media(request, item_id: int):
    if not can(request.user, "can_view_news"):
        return HttpResponseForbidden("Geen toegang.")

    item = get_object_or_404(NewsItem, id=item_id)

    if not item.has_file:
        return JsonResponse({"has_file": False})

    # PDF: altijd previews (webp/png) teruggeven
    if item.is_pdf:
        h = item.file_hash or ""
        urls, ext_used = list_pdf_preview_urls(
            cache_root=CACHE_NEWS_DIR,
            file_hash=h,
            prefer_format=DEFAULT_PREVIEW_FORMAT,
            allow_legacy_png=ALLOW_LEGACY_PNG,
        )

        # Als er nog geen cache is: lazy render
        if not urls:
            try:
                pdf_bytes = read_storage_bytes(item.file_path)
            except Exception:
                return JsonResponse({"has_file": True, "type": "pdf", "urls": []})

            h2, _n, _fmt = ensure_pdf_previews_exist(
                pdf_bytes=pdf_bytes,
                cache_root=CACHE_NEWS_DIR,
                file_hash=item.file_hash or None,
                dpi=DEFAULT_DPI,
                prefer_format=DEFAULT_PREVIEW_FORMAT,
                allow_legacy_png=ALLOW_LEGACY_PNG,
                webp_lossless=DEFAULT_WEBP_LOSSLESS,
                webp_quality=DEFAULT_WEBP_QUALITY,
                webp_method=DEFAULT_WEBP_METHOD,
            )

            # hash kan ontbreken in oude records -> opslaan
            if h2 and h2 != (item.file_hash or ""):
                item.file_hash = h2
                item.save(update_fields=["file_hash"])

            urls, _ext_used = list_pdf_preview_urls(
                cache_root=CACHE_NEWS_DIR,
                file_hash=item.file_hash or "",
                prefer_format=DEFAULT_PREVIEW_FORMAT,
                allow_legacy_png=ALLOW_LEGACY_PNG,
            )

        return JsonResponse({"has_file": True, "type": "pdf", "urls": urls})

    # Image: direct url (kan webp/png/jpg zijn)
    return JsonResponse({"has_file": True, "type": "image", "url": item.media_url})


# -----------------------------
# Main view
# -----------------------------
@login_required
def news(request):
    if not can(request.user, "can_view_news"):
        return HttpResponseForbidden("Geen toegang.")
    
    can_edit = can(request, "can_upload_news")

    _cleanup_expired_news(timezone.now())

    open_edit_id = None

    # DELETE
    if request.method == "POST" and "delete_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen toegang.")

        item = get_object_or_404(NewsItem, id=request.POST.get("delete_item"))
        _delete_news_files_for_item(item)
        item.delete()
        messages.success(request, "Nieuwsbericht verwijderd.")
        return redirect("news")

    form = NewsItemForm()

    # EDIT
    if request.method == "POST" and "edit_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen uploadrechten.")

        try:
            item_id = int(request.POST.get("edit_item"))
        except (TypeError, ValueError):
            return redirect("news")

        item = get_object_or_404(NewsItem, id=item_id)
        open_edit_id = item_id

        old_rel_path = item.file_path or ""
        old_hash = item.file_hash or None
        old_original = item.original_filename or ""

        edit_form = NewsItemForm(request.POST, request.FILES, prefix=f"edit-{item_id}")

        if edit_form.is_valid():
            uploaded_file = edit_form.cleaned_data.get("file")

            item.title = edit_form.cleaned_data["title"]
            item.short_description = edit_form.cleaned_data.get("short_description", "")
            item.description = edit_form.cleaned_data.get("description", "")

            if uploaded_file:
                # Upload opslaan (PDF blijft PDF; images -> webp)
                rel_path, h = save_upload_with_hash(
                    uploaded_file,
                    target_dir=NEWS_DIR,
                    base_name="news",
                    allowed_exts=(".pdf", ".png", ".jpg", ".jpeg", ".webp"),
                    clear_existing=False,
                    convert_images_to_webp=True,
                    webp_lossless=DEFAULT_WEBP_LOSSLESS,
                    webp_quality=DEFAULT_WEBP_QUALITY,
                    webp_method=DEFAULT_WEBP_METHOD,
                )

                # Eager render bij PDF zodat meteen zichtbaar is
                if rel_path.lower().endswith(".pdf"):
                    try:
                        pdf_bytes = read_storage_bytes(rel_path)
                        h2, _n, _fmt = ensure_pdf_previews_exist(
                            pdf_bytes=pdf_bytes,
                            cache_root=CACHE_NEWS_DIR,
                            file_hash=h,
                            dpi=DEFAULT_DPI,
                            prefer_format=DEFAULT_PREVIEW_FORMAT,
                            allow_legacy_png=ALLOW_LEGACY_PNG,
                            webp_lossless=DEFAULT_WEBP_LOSSLESS,
                            webp_quality=DEFAULT_WEBP_QUALITY,
                            webp_method=DEFAULT_WEBP_METHOD,
                        )
                        if h2:
                            h = h2
                    except Exception:
                        pass

                item.file_path = rel_path
                item.file_hash = h
                item.original_filename = uploaded_file.name
                item.save()

                # === BUGFIX: alleen old blob deleten als het echt anders is ===
                if old_rel_path and (old_rel_path != rel_path or (old_hash or "") != (h or "")):
                    _delete_news_files(rel_path=old_rel_path, file_hash=old_hash, exclude_id=item.id)

            else:
                item.original_filename = old_original
                item.save()

            messages.success(request, "Nieuwsbericht bijgewerkt.")
            return redirect("news")

        else:
            file_errors = edit_form.errors.get("file")
            if file_errors:
                for err in file_errors:
                    messages.error(request, err)
            else:
                messages.error(request, "Het nieuwsformulier bevat fouten.")

    # ADD
    if request.method == "POST" and "add_news" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen uploadrechten.")

        form = NewsItemForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data.get("file")

            rel_path = ""
            h = ""
            original_name = ""

            if uploaded_file:
                rel_path, h = save_upload_with_hash(
                    uploaded_file,
                    target_dir=NEWS_DIR,
                    base_name="news",
                    allowed_exts=(".pdf", ".png", ".jpg", ".jpeg", ".webp"),
                    clear_existing=False,
                    convert_images_to_webp=True,
                    webp_lossless=DEFAULT_WEBP_LOSSLESS,
                    webp_quality=DEFAULT_WEBP_QUALITY,
                    webp_method=DEFAULT_WEBP_METHOD,
                )
                original_name = uploaded_file.name

                # eager render bij pdf
                if rel_path.lower().endswith(".pdf"):
                    try:
                        pdf_bytes = read_storage_bytes(rel_path)
                        h2, _n, _fmt = ensure_pdf_previews_exist(
                            pdf_bytes=pdf_bytes,
                            cache_root=CACHE_NEWS_DIR,
                            file_hash=h,
                            dpi=DEFAULT_DPI,
                            prefer_format=DEFAULT_PREVIEW_FORMAT,
                            allow_legacy_png=ALLOW_LEGACY_PNG,
                            webp_lossless=DEFAULT_WEBP_LOSSLESS,
                            webp_quality=DEFAULT_WEBP_QUALITY,
                            webp_method=DEFAULT_WEBP_METHOD,
                        )
                        if h2:
                            h = h2
                    except Exception:
                        pass

            NewsItem.objects.create(
                title=form.cleaned_data["title"],
                short_description=form.cleaned_data.get("short_description", ""),
                description=form.cleaned_data.get("description", ""),
                file_path=rel_path,
                file_hash=h,
                original_filename=original_name,
            )

            send_news_uploaded_push_task.delay(request.user.first_name)
            messages.success(request, "Nieuwsbericht toegevoegd.")
            return redirect("news")
        else:
            file_errors = form.errors.get("file")
            if file_errors:
                for err in file_errors:
                    messages.error(request, err)
            else:
                messages.error(request, "Het nieuwsformulier bevat fouten.")

    items = list(NewsItem.objects.all())

    news_rows = []
    for it in items:
        if open_edit_id == it.id and request.method == "POST" and "edit_item" in request.POST:
            edit_form = NewsItemForm(request.POST, request.FILES, prefix=f"edit-{it.id}")
        else:
            edit_form = NewsItemForm(prefix=f"edit-{it.id}")
            edit_form.fields["title"].initial = it.title
            edit_form.fields["short_description"].initial = it.short_description
            edit_form.fields["description"].initial = it.description

        news_rows.append((it, edit_form))

    context = {
        "can_edit": can_edit,
        "news_items": items,
        "news_rows": news_rows,
        "form": form,
        "open_edit_id": open_edit_id,
    }
    return render(request, "news/index.html", context)