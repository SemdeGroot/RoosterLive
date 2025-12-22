import shutil
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models.functions import Lower
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from ._helpers import (
    can,
    render_pdf_to_cache,
    save_pdf_or_png_with_hash,
    CACHE_DIR,
)

from core.models import Werkafspraak
from core.forms import WerkafspraakForm


# Directories
WERKAFSPRAKEN_DIR = Path(settings.MEDIA_ROOT) / "werkafspraken"
CACHE_WERKAFSPRAKEN_DIR = Path(CACHE_DIR) / "werkafspraken"
WERKAFSPRAKEN_DIR.mkdir(parents=True, exist_ok=True)
CACHE_WERKAFSPRAKEN_DIR.mkdir(parents=True, exist_ok=True)

MEDIA_ROOT = Path(settings.MEDIA_ROOT)

# Category → permission mapping (pas aan als je meer categorieën hebt)
CATEGORY_VIEW_PERM = {
    "baxter": "can_view_baxter",
    "instelling": "can_view_instellings_apo",
    "openbare": "can_view_openbare_apo",
}


def _user_can_view_item(user, item: Werkafspraak) -> bool:
    perm = CATEGORY_VIEW_PERM.get(item.category)
    if not perm:
        # Als je categorie ontbreekt in mapping: veiligste default = deny
        return False
    return can(user, perm)


def _delete_werkafspraak_files(rel_path: str, category: str, file_hash: str | None) -> None:
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
            cache_path = CACHE_WERKAFSPRAKEN_DIR / category / file_hash
            if cache_path.exists():
                shutil.rmtree(cache_path, ignore_errors=True)
        return

    # PROD / S3
    try:
        default_storage.delete(rel_path)
    except Exception:
        pass

    if ext == ".pdf" and file_hash:
        cache_base = f"cache/werkafspraken/{category}/{file_hash}"
        try:
            _dirs, files = default_storage.listdir(cache_base)
        except Exception:
            files = []
        for name in files:
            try:
                default_storage.delete(f"{cache_base}/{name}")
            except Exception:
                pass


def _delete_werkafspraak_files_for_item(item: Werkafspraak) -> None:
    _delete_werkafspraak_files(item.file_path or "", item.category or "", item.file_hash or None)


def _list_cached_pdf_png_urls(category: str, file_hash: str) -> list[str]:
    if not category or not file_hash:
        return []

    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        folder = CACHE_WERKAFSPRAKEN_DIR / category / file_hash
        if not folder.exists():
            return []
        files = sorted([p.name for p in folder.glob("page_*.png")])
        return [f"{settings.MEDIA_URL}cache/werkafspraken/{category}/{file_hash}/{name}" for name in files]

    base = f"cache/werkafspraken/{category}/{file_hash}"
    try:
        _dirs, files = default_storage.listdir(base)
    except Exception:
        files = []

    pngs = sorted([name for name in files if name.startswith("page_") and name.endswith(".png")])
    return [f"{settings.MEDIA_URL}cache/werkafspraken/{category}/{file_hash}/{name}" for name in pngs]


def _ensure_pdf_cache_exists(rel_path: str, category: str, file_hash: str | None) -> str | None:
    """
    Zorgt dat de PDF naar PNG cache bestaat (lazy).
    Retourneert (mogelijk nieuw) file_hash.
    """
    if not rel_path or not category:
        return file_hash

    ext = Path(rel_path).suffix.lower()
    if ext != ".pdf":
        return file_hash

    if file_hash and _list_cached_pdf_png_urls(category, file_hash):
        return file_hash

    # PDF bytes inlezen
    try:
        if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
            abs_path = MEDIA_ROOT / rel_path
            pdf_bytes = abs_path.read_bytes()
        else:
            with default_storage.open(rel_path, "rb") as f:
                pdf_bytes = f.read()
    except Exception:
        return file_hash

    # Cache root is per category (zelfde structuur als je eerdere code)
    cache_root = CACHE_WERKAFSPRAKEN_DIR / category
    cache_root.mkdir(parents=True, exist_ok=True)

    h, _n_pages = render_pdf_to_cache(pdf_bytes, dpi=300, cache_root=cache_root)
    return h


@login_required
def policies_media(request, item_id: int):
    if not can(request.user, "can_view_policies"):
        return HttpResponseForbidden("Geen toegang.")

    item = get_object_or_404(Werkafspraak, id=item_id)

    if not _user_can_view_item(request.user, item):
        return HttpResponseForbidden("Geen toegang.")

    if not item.has_file:
        return JsonResponse({"has_file": False})

    # Alleen PDFs verwacht, maar we ondersteunen image ook (zoals news)
    if item.is_pdf:
        # ensure cache (lazy)
        h2 = _ensure_pdf_cache_exists(item.file_path or "", item.category or "", item.file_hash or None)
        if h2 and h2 != (item.file_hash or ""):
            item.file_hash = h2
            item.save(update_fields=["file_hash"])

        urls = _list_cached_pdf_png_urls(item.category or "", item.file_hash or "")
        return JsonResponse({"has_file": True, "type": "pdf", "urls": urls})

    return JsonResponse({"has_file": True, "type": "image", "url": item.media_url})


@login_required
def policies(request):
    if not can(request.user, "can_view_policies"):
        return HttpResponseForbidden("Geen toegang.")

    open_edit_id = None
    open_add_category = None

    # === DELETE ===
    if request.method == "POST" and "delete_item" in request.POST:
        if not can(request.user, "can_upload_werkafspraken"):
            return HttpResponseForbidden("Geen toegang.")

        item = get_object_or_404(Werkafspraak, id=request.POST.get("delete_item"))
        _delete_werkafspraak_files_for_item(item)
        item.delete()
        messages.success(request, "Werkafspraak verwijderd.")
        return redirect("policies")

    # === EDIT ===
    if request.method == "POST" and "edit_item" in request.POST:
        if not can(request.user, "can_upload_werkafspraken"):
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

        edit_form = WerkafspraakForm(
            request.POST,
            request.FILES,
            prefix=f"edit-{item_id}",
        )

        if edit_form.is_valid():
            uploaded_file = edit_form.cleaned_data.get("file")

            item.title = edit_form.cleaned_data["title"]
            item.short_description = edit_form.cleaned_data.get("short_description", "")

            # category blijft hetzelfde, maar we zetten 'm expliciet (hidden field)
            item.category = edit_form.cleaned_data["category"]

            if uploaded_file:
                category_dir = WERKAFSPRAKEN_DIR / item.category
                rel_path, h = save_pdf_or_png_with_hash(
                    uploaded_file=uploaded_file,
                    target_dir=category_dir,
                    base_name="werkafspraak",
                )

                # geen eager render; cache pas bij lazy media load
                item.file_path = rel_path
                item.file_hash = h
                item.original_filename = uploaded_file.name
                item.save()

                if old_rel_path:
                    _delete_werkafspraak_files(old_rel_path, item.category, old_hash)
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
        if not can(request.user, "can_upload_werkafspraken"):
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
                rel_path, h = save_pdf_or_png_with_hash(
                    uploaded_file=uploaded_file,
                    target_dir=category_dir,
                    base_name="werkafspraak",
                )
                original_name = uploaded_file.name

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
    # Config: voeg hier je categorieën uit als je er meer hebt
    category_configs = [
        {
            "key": "baxter",
            "name": "Baxterproductie",
            "perm": "can_view_baxter",
            "image": "factory.svg",
        },
        {
            "key": "instelling",
            "name": "Instellingsapotheek",
            "perm": "can_view_instellings_apo",
            "image": "instellingsapotheek.svg",
        },
        {
            "key": "openbare",
            "name": "Openbare Apo",
            "perm": "can_view_openbare_apo",
            "image": "openbareapo.svg",
        },
    ]

    categories = []

    for cfg in category_configs:
        cat_key = cfg["key"]
        if not can(request.user, cfg["perm"]):
            continue

        # alfabetisch op titel (case-insensitive)
        items = list(
            Werkafspraak.objects
            .filter(category=cat_key)
            .order_by(Lower("title"))
        )

        # Add form per category (met prefix zodat fields niet botsen)
        if request.method == "POST" and open_add_category == cat_key and "add_item" in request.POST:
            form = WerkafspraakForm(request.POST, request.FILES, prefix=f"add-{cat_key}")
        else:
            form = WerkafspraakForm(
                prefix=f"add-{cat_key}",
                initial={"category": cat_key},
                auto_id=f"id_{cat_key}_%s",
            )

        # Edit forms per item (news-achtig)
        rows = []
        for it in items:
            if open_edit_id == it.id and request.method == "POST" and "edit_item" in request.POST:
                edit_form = WerkafspraakForm(request.POST, request.FILES, prefix=f"edit-{it.id}")
            else:
                edit_form = WerkafspraakForm(
                    prefix=f"edit-{it.id}",
                    auto_id=f"id_edit_{it.id}_%s",
                )
                edit_form.fields["category"].initial = it.category
                edit_form.fields["title"].initial = it.title
                edit_form.fields["short_description"].initial = it.short_description

            rows.append((it, edit_form))

        categories.append(
            {
                "name": cfg["name"],
                "category": cat_key,
                "image": cfg["image"],
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
        },
    )