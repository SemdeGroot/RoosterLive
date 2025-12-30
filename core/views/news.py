# core/views/news.py
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from ._helpers import (
    can,
    CACHE_DIR,
)

from ._upload_helpers import (
    save_upload_with_hash,
    ensure_pdf_previews_exist,
    list_pdf_preview_urls,
    delete_pdf_previews,
    read_storage_bytes,
)

from core.models import NewsItem
from core.forms import NewsItemForm
from core.tasks import send_news_uploaded_push_task

# Directories
NEWS_DIR = Path(settings.MEDIA_ROOT) / "news"
CACHE_NEWS_DIR = Path(CACHE_DIR) / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_NEWS_DIR.mkdir(parents=True, exist_ok=True)

# Verlooptijd nieuws
EXPIRE_AFTER = timedelta(days=180)  # ~6 maanden

MEDIA_ROOT = Path(settings.MEDIA_ROOT)


def _delete_news_files(rel_path: str, file_hash: str | None) -> None:
    if not rel_path:
        return

    ext = Path(rel_path).suffix.lower()

    # DEV / lokaal
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        abs_path = MEDIA_ROOT / rel_path
        try:
            abs_path.unlink(missing_ok=True)
        except Exception:
            pass

        if ext == ".pdf" and file_hash:
            # Verwijder previews (webp en/of legacy png)
            delete_pdf_previews(cache_root=CACHE_NEWS_DIR, file_hash=file_hash)
        return

    # PROD / S3
    try:
        default_storage.delete(rel_path)
    except Exception:
        pass

    if ext == ".pdf" and file_hash:
        delete_pdf_previews(cache_root=CACHE_NEWS_DIR, file_hash=file_hash)


def _delete_news_files_for_item(item: NewsItem) -> None:
    _delete_news_files(item.file_path or "", item.file_hash or None)


def _cleanup_expired_news(now: datetime) -> int:
    cutoff = now - EXPIRE_AFTER
    qs = NewsItem.objects.filter(uploaded_at__lt=cutoff)
    removed = 0
    for item in qs:
        _delete_news_files_for_item(item)
        item.delete()
        removed += 1
    return removed


@login_required
def news_media(request, item_id: int):
    if not can(request.user, "can_view_news"):
        return HttpResponseForbidden("Geen toegang.")

    item = get_object_or_404(NewsItem, id=item_id)

    if not item.has_file:
        return JsonResponse({"has_file": False})

    # PDF -> altijd previews (webp voorkeur, png fallback)
    if item.is_pdf:
        try:
            pdf_bytes = read_storage_bytes(item.file_path)
            h, _n_pages, _ext = ensure_pdf_previews_exist(
                pdf_bytes=pdf_bytes,
                cache_root=CACHE_NEWS_DIR,
                file_hash=item.file_hash or None,
            )
            if h and h != (item.file_hash or ""):
                item.file_hash = h
                item.save(update_fields=["file_hash"])
        except Exception:
            # Als render faalt, geef lege urls terug (frontend kan dit afvangen)
            pass

        urls, _ext_used = list_pdf_preview_urls(
            cache_root=CACHE_NEWS_DIR,
            file_hash=item.file_hash or "",
        )
        return JsonResponse({"has_file": True, "type": "pdf", "urls": urls})

    # Afbeelding (al webp of legacy png/jpg) -> direct URL
    return JsonResponse({"has_file": True, "type": "image", "url": item.media_url})


@login_required
def news(request):
    if not can(request.user, "can_view_news"):
        return HttpResponseForbidden("Geen toegang.")

    _cleanup_expired_news(timezone.now())

    open_edit_id = None

    # DELETE
    if request.method == "POST" and "delete_item" in request.POST:
        if not can(request.user, "can_upload_news"):
            return HttpResponseForbidden("Geen toegang.")

        item = get_object_or_404(NewsItem, id=request.POST.get("delete_item"))
        _delete_news_files_for_item(item)
        item.delete()
        messages.success(request, "Nieuwsbericht verwijderd.")
        return redirect("news")

    form = NewsItemForm()

    # EDIT
    if request.method == "POST" and "edit_item" in request.POST:
        if not can(request.user, "can_upload_news"):
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

        edit_form = NewsItemForm(
            request.POST,
            request.FILES,
            prefix=f"edit-{item_id}",
        )

        if edit_form.is_valid():
            uploaded_file = edit_form.cleaned_data.get("file")

            item.title = edit_form.cleaned_data["title"]
            item.short_description = edit_form.cleaned_data.get("short_description", "")
            item.description = edit_form.cleaned_data.get("description", "")

            if uploaded_file:
                rel_path, h = save_upload_with_hash(
                    uploaded_file=uploaded_file,
                    target_dir=NEWS_DIR,
                    base_name="news",
                    convert_images_to_webp=True,
                    webp_lossless=True,
                )

                # Eager previews voor PDF zodat media endpoint meteen URLs heeft
                if rel_path.lower().endswith(".pdf"):
                    try:
                        pdf_bytes = read_storage_bytes(rel_path)
                        ensure_pdf_previews_exist(
                            pdf_bytes=pdf_bytes,
                            cache_root=CACHE_NEWS_DIR,
                            file_hash=h,
                        )
                    except Exception:
                        pass

                item.file_path = rel_path
                item.file_hash = h
                item.original_filename = uploaded_file.name
                item.save()

                if old_rel_path:
                    _delete_news_files(old_rel_path, old_hash)

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
        if not can(request.user, "can_upload_news"):
            return HttpResponseForbidden("Geen uploadrechten.")

        form = NewsItemForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data.get("file")

            rel_path = ""
            h = ""
            original_name = ""

            if uploaded_file:
                rel_path, h = save_upload_with_hash(
                    uploaded_file=uploaded_file,
                    target_dir=NEWS_DIR,
                    base_name="news",
                    convert_images_to_webp=True,
                    webp_lossless=True,
                )
                original_name = uploaded_file.name

                if rel_path.lower().endswith(".pdf"):
                    try:
                        pdf_bytes = read_storage_bytes(rel_path)
                        ensure_pdf_previews_exist(
                            pdf_bytes=pdf_bytes,
                            cache_root=CACHE_NEWS_DIR,
                            file_hash=h,
                        )
                    except Exception:
                        pass

            news_item = NewsItem(
                title=form.cleaned_data["title"],
                short_description=form.cleaned_data.get("short_description", ""),
                description=form.cleaned_data.get("description", ""),
                file_path=rel_path,
                file_hash=h,
                original_filename=original_name,
            )
            news_item.save()

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
            edit_form = NewsItemForm(
                request.POST,
                request.FILES,
                prefix=f"edit-{it.id}",
            )
        else:
            edit_form = NewsItemForm(prefix=f"edit-{it.id}")
            edit_form.fields["title"].initial = it.title
            edit_form.fields["short_description"].initial = it.short_description
            edit_form.fields["description"].initial = it.description

        news_rows.append((it, edit_form))

    context = {
        "news_items": items,
        "news_rows": news_rows,
        "form": form,
        "open_edit_id": open_edit_id,
    }
    return render(request, "news/index.html", context)