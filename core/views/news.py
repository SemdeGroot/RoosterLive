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
    render_pdf_to_cache,
    CACHE_DIR,
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

    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        abs_path = MEDIA_ROOT / rel_path
        try:
            abs_path.unlink(missing_ok=True)
        except Exception:
            pass

        if ext == ".pdf" and file_hash:
            cache_path = CACHE_NEWS_DIR / file_hash
            if cache_path.exists():
                shutil.rmtree(cache_path, ignore_errors=True)
        return

    try:
        default_storage.delete(rel_path)
    except Exception:
        pass

    if ext == ".pdf" and file_hash:
        cache_base = f"cache/news/{file_hash}"
        try:
            _dirs, files = default_storage.listdir(cache_base)
        except Exception:
            files = []
        for name in files:
            try:
                default_storage.delete(f"{cache_base}/{name}")
            except Exception:
                pass


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


def _list_cached_pdf_png_urls(file_hash: str) -> list[str]:
    if not file_hash:
        return []

    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        folder = CACHE_NEWS_DIR / file_hash
        if not folder.exists():
            return []
        files = sorted([p.name for p in folder.glob("page_*.png")])
        return [f"{settings.MEDIA_URL}cache/news/{file_hash}/{name}" for name in files]

    base = f"cache/news/{file_hash}"
    try:
        _dirs, files = default_storage.listdir(base)
    except Exception:
        files = []

    pngs = sorted([name for name in files if name.startswith("page_") and name.endswith(".png")])
    return [f"{settings.MEDIA_URL}cache/news/{file_hash}/{name}" for name in pngs]


def _ensure_pdf_cache_exists(rel_path: str, file_hash: str | None) -> str | None:
    if not rel_path:
        return file_hash

    ext = Path(rel_path).suffix.lower()
    if ext != ".pdf":
        return file_hash

    if file_hash and _list_cached_pdf_png_urls(file_hash):
        return file_hash

    try:
        if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
            abs_path = MEDIA_ROOT / rel_path
            pdf_bytes = abs_path.read_bytes()
        else:
            with default_storage.open(rel_path, "rb") as f:
                pdf_bytes = f.read()
    except Exception:
        return file_hash

    h, _n_pages = render_pdf_to_cache(pdf_bytes, dpi=300, cache_root=CACHE_NEWS_DIR)
    return h


@login_required
def news_media(request, item_id: int):
    if not can(request.user, "can_view_news"):
        return HttpResponseForbidden("Geen toegang.")

    item = get_object_or_404(NewsItem, id=item_id)

    if not item.has_file:
        return JsonResponse({"has_file": False})

    if item.is_pdf:
        urls = _list_cached_pdf_png_urls(item.file_hash or "")
        return JsonResponse({"has_file": True, "type": "pdf", "urls": urls})

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
                from ._helpers import save_pdf_or_png_with_hash

                rel_path, h = save_pdf_or_png_with_hash(
                    uploaded_file=uploaded_file,
                    target_dir=NEWS_DIR,
                    base_name="news",
                )

                h2 = _ensure_pdf_cache_exists(rel_path, h)
                if h2:
                    h = h2

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
                from ._helpers import save_pdf_or_png_with_hash

                rel_path, h = save_pdf_or_png_with_hash(
                    uploaded_file=uploaded_file,
                    target_dir=NEWS_DIR,
                    base_name="news",
                )
                original_name = uploaded_file.name

                h2 = _ensure_pdf_cache_exists(rel_path, h)
                if h2:
                    h = h2

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