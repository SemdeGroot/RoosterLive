# core/views/policies.py
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models.functions import Lower
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from core.models import Werkafspraak
from core.forms import WerkafspraakForm

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
WERKAFSPRAKEN_DIR = Path(settings.MEDIA_ROOT) / "werkafspraken"
CACHE_WERKAFSPRAKEN_DIR = Path(settings.CACHE_DIR) / "werkafspraken"
WERKAFSPRAKEN_DIR.mkdir(parents=True, exist_ok=True)
CACHE_WERKAFSPRAKEN_DIR.mkdir(parents=True, exist_ok=True)

MEDIA_ROOT = Path(settings.MEDIA_ROOT)

# Category → permission mapping
CATEGORY_VIEW_PERM = {
    "baxter": "can_view_baxter",
    "instelling": "can_view_instellings_apo",
    "openbare": "can_view_openbare_apo",
}


def _user_can_view_item(user, item: Werkafspraak) -> bool:
    perm = CATEGORY_VIEW_PERM.get(item.category)
    if not perm:
        return False
    return can(user, perm)


# -----------------------------
# Reference checks (BUGFIX)
# -----------------------------
def _blob_in_use(*, category: str, rel_path: str, file_hash: str | None, exclude_id: int | None) -> bool:
    """
    True als dezelfde blob (hash óf rel_path) nog door een andere Werkafspraak
    in dezelfde category wordt gebruikt.
    """
    qs = Werkafspraak.objects.filter(category=category)
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)

    if file_hash:
        return qs.filter(file_hash=file_hash).exists()

    if rel_path:
        return qs.filter(file_path=rel_path).exists()

    return False


def _delete_werkafspraak_files(*, rel_path: str, category: str, file_hash: str | None, exclude_id: int | None = None) -> None:
    if not rel_path or not category:
        return

    # === BUGFIX: shared blob -> niet deleten ===
    if _blob_in_use(category=category, rel_path=rel_path, file_hash=file_hash, exclude_id=exclude_id):
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
        cache_root = CACHE_WERKAFSPRAKEN_DIR / category
        delete_pdf_previews(cache_root=cache_root, file_hash=file_hash)


def _delete_werkafspraak_files_for_item(item: Werkafspraak) -> None:
    _delete_werkafspraak_files(
        rel_path=item.file_path or "",
        category=item.category or "",
        file_hash=item.file_hash or None,
        exclude_id=item.id,
    )


# -----------------------------
# Media endpoint (lazy)
# -----------------------------
@login_required
def policies_media(request, item_id: int):
    if not can(request.user, "can_view_policies"):
        return HttpResponseForbidden("Geen toegang.")

    item = get_object_or_404(Werkafspraak, id=item_id)

    if not _user_can_view_item(request.user, item):
        return HttpResponseForbidden("Geen toegang.")

    if not item.has_file:
        return JsonResponse({"has_file": False})

    if item.is_pdf:
        cache_root = CACHE_WERKAFSPRAKEN_DIR / (item.category or "")
        h = item.file_hash or ""

        urls, ext_used = list_pdf_preview_urls(
            cache_root=cache_root,
            file_hash=h,
            prefer_format=DEFAULT_PREVIEW_FORMAT,
            allow_legacy_png=ALLOW_LEGACY_PNG,
        )

        if not urls:
            try:
                pdf_bytes = read_storage_bytes(item.file_path)
            except Exception:
                return JsonResponse({"has_file": True, "type": "pdf", "urls": []})

            h2, _n, _fmt = ensure_pdf_previews_exist(
                pdf_bytes=pdf_bytes,
                cache_root=cache_root,
                file_hash=item.file_hash or None,
                dpi=DEFAULT_DPI,
                prefer_format=DEFAULT_PREVIEW_FORMAT,
                allow_legacy_png=ALLOW_LEGACY_PNG,
                webp_lossless=DEFAULT_WEBP_LOSSLESS,
                webp_quality=DEFAULT_WEBP_QUALITY,
                webp_method=DEFAULT_WEBP_METHOD,
            )

            if h2 and h2 != (item.file_hash or ""):
                item.file_hash = h2
                item.save(update_fields=["file_hash"])

            urls, _ext_used = list_pdf_preview_urls(
                cache_root=cache_root,
                file_hash=item.file_hash or "",
                prefer_format=DEFAULT_PREVIEW_FORMAT,
                allow_legacy_png=ALLOW_LEGACY_PNG,
            )

        return JsonResponse({"has_file": True, "type": "pdf", "urls": urls})

    return JsonResponse({"has_file": True, "type": "image", "url": item.media_url})


# -----------------------------
# Main view
# -----------------------------
@login_required
def policies(request):
    if not can(request.user, "can_view_policies"):
        return HttpResponseForbidden("Geen toegang.")
    can_edit = can(request, "can_upload_werkafspraken")

    open_edit_id = None
    open_add_category = None

    # === DELETE ===
    if request.method == "POST" and "delete_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen toegang.")

        item = get_object_or_404(Werkafspraak, id=request.POST.get("delete_item"))
        _delete_werkafspraak_files_for_item(item)
        item.delete()
        messages.success(request, "Werkafspraak verwijderd.")
        return redirect("policies")

    # === EDIT ===
    if request.method == "POST" and "edit_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen uploadrechten.")

        try:
            item_id = int(request.POST.get("edit_item"))
        except (TypeError, ValueError):
            return redirect("policies")

        item = get_object_or_404(Werkafspraak, id=item_id)
        open_edit_id = item_id

        old_rel_path = item.file_path or ""
        old_hash = item.file_hash or None
        old_original = item.original_filename or ""
        old_category = item.category or ""  # voor het geval category ooit wijzigt

        edit_form = WerkafspraakForm(request.POST, request.FILES, prefix=f"edit-{item_id}")

        if edit_form.is_valid():
            uploaded_file = edit_form.cleaned_data.get("file")

            item.title = edit_form.cleaned_data["title"]
            item.short_description = edit_form.cleaned_data.get("short_description", "")

            # category blijft hetzelfde, maar we zetten 'm expliciet (hidden field)
            item.category = edit_form.cleaned_data["category"]

            if uploaded_file:
                category_dir = WERKAFSPRAKEN_DIR / item.category
                rel_path, h = save_upload_with_hash(
                    uploaded_file,
                    target_dir=category_dir,
                    base_name="werkafspraak",
                    allowed_exts=(".pdf", ".png", ".jpg", ".jpeg", ".webp"),
                    clear_existing=False,
                    convert_images_to_webp=True,
                    webp_lossless=DEFAULT_WEBP_LOSSLESS,
                    webp_quality=DEFAULT_WEBP_QUALITY,
                    webp_method=DEFAULT_WEBP_METHOD,
                )

                # eager render bij pdf
                if rel_path.lower().endswith(".pdf"):
                    try:
                        pdf_bytes = read_storage_bytes(rel_path)
                        cache_root = CACHE_WERKAFSPRAKEN_DIR / item.category
                        h2, _n, _fmt = ensure_pdf_previews_exist(
                            pdf_bytes=pdf_bytes,
                            cache_root=cache_root,
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

                # === BUGFIX: alleen oude blob deleten als hij echt anders is ===
                if old_rel_path and (old_rel_path != rel_path or (old_hash or "") != (h or "")):
                    _delete_werkafspraak_files(
                        rel_path=old_rel_path,
                        category=old_category,   # verwijder in de juiste oude category
                        file_hash=old_hash,
                        exclude_id=item.id,
                    )

            else:
                item.original_filename = old_original
                item.save()

            messages.success(request, "Werkafspraak bijgewerkt.")
            return redirect("policies")

        else:
            file_errors = edit_form.errors.get("file")
            if file_errors:
                for err in file_errors:
                    messages.error(request, err)
            else:
                messages.error(request, "Het bewerkformulier bevat fouten.")

    # === ADD ===
    if request.method == "POST" and "add_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen uploadrechten.")

        open_add_category = request.POST.get("add_item") or None

        add_form = WerkafspraakForm(
            request.POST,
            request.FILES,
            prefix=f"add-{open_add_category}" if open_add_category else None,
        )

        if add_form.is_valid():
            uploaded_file = add_form.cleaned_data.get("file")
            category = add_form.cleaned_data["category"]

            rel_path = ""
            h = ""
            original_name = ""

            if uploaded_file:
                category_dir = WERKAFSPRAKEN_DIR / category
                rel_path, h = save_upload_with_hash(
                    uploaded_file,
                    target_dir=category_dir,
                    base_name="werkafspraak",
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
                        cache_root = CACHE_WERKAFSPRAKEN_DIR / category
                        h2, _n, _fmt = ensure_pdf_previews_exist(
                            pdf_bytes=pdf_bytes,
                            cache_root=cache_root,
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

            Werkafspraak.objects.create(
                title=add_form.cleaned_data["title"],
                short_description=add_form.cleaned_data.get("short_description", ""),
                file_path=rel_path,
                file_hash=h,
                original_filename=original_name,
                category=category,
                created_by=request.user,
            )

            messages.success(request, "Werkafspraak succesvol geüpload.")
            return redirect("policies")

        else:
            file_errors = add_form.errors.get("file")
            if file_errors:
                for err in file_errors:
                    messages.error(request, err)
            else:
                messages.error(request, "Het uploadformulier bevat fouten.")

    # === GET / render context ===
    category_configs = [
        {
            "key": "baxter",
            "name": "Baxterproductie",
            "perm": "can_view_baxter",
            "image": "baxterproductie-lucide.svg",
            "badge_class": "i-orange",
        },
        {
            "key": "instelling",
            "name": "Instellingsapotheek",
            "perm": "can_view_instellings_apo",
            "image": "instellingsapo-lucide.svg",
            "badge_class": "i-green",
        },
        {
            "key": "openbare",
            "name": "Openbare Apo",
            "perm": "can_view_openbare_apo",
            "image": "openbareapo-lucide.svg",
            "badge_class": "i-aqua",
        },
    ]

    categories = []

    for cfg in category_configs:
        cat_key = cfg["key"]
        if not can(request.user, cfg["perm"]):
            continue

        items = list(Werkafspraak.objects.filter(category=cat_key).order_by(Lower("title")))

        if request.method == "POST" and open_add_category == cat_key and "add_item" in request.POST:
            form = WerkafspraakForm(request.POST, request.FILES, prefix=f"add-{cat_key}")
        else:
            form = WerkafspraakForm(
                prefix=f"add-{cat_key}",
                initial={"category": cat_key},
                auto_id=f"id_{cat_key}_%s",
            )

        rows = []
        for it in items:
            if open_edit_id == it.id and request.method == "POST" and "edit_item" in request.POST:
                edit_form = WerkafspraakForm(request.POST, request.FILES, prefix=f"edit-{it.id}")
            else:
                edit_form = WerkafspraakForm(prefix=f"edit-{it.id}", auto_id=f"id_edit_{it.id}_%s")
                edit_form.fields["category"].initial = it.category
                edit_form.fields["title"].initial = it.title
                edit_form.fields["short_description"].initial = it.short_description

            rows.append((it, edit_form))

        categories.append(
            {
                "name": cfg["name"],
                "category": cat_key,
                "image": cfg["image"],
                "badge_class": cfg.get("badge_class", "i-indigo"),
                "items": items,
                "rows": rows,
                "form": form,
            }
        )

    return render(
        request,
        "policies/index.html",
        {
            "categories": categories,
            "open_edit_id": open_edit_id,
            "can_edit": can_edit,
        },
    )