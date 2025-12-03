import shutil
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import default_storage

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

def _delete_werkafspraak_files_for_item(item: Werkafspraak) -> None:
    """
    Verwijdert het fysieke werkafspraak bestand (PDF) + bijbehorende cache.
    Werkt in DEV (filesystem) en PROD (S3 via default_storage).
    """
    if not item.file_path:
        return  # niets te verwijderen
    
    rel_path = item.file_path  # bv. "werkafspraken/baxter/werkafspraak.<hash>.pdf"
    ext = Path(rel_path).suffix.lower()

    # === DEV / lokaal ===
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        abs_path = MEDIA_ROOT / rel_path
        try:
            abs_path.unlink(missing_ok=True)
        except Exception:
            pass

        # Cache voor PDF op basis van hash EN categorie
        if ext == ".pdf" and item.file_hash:
            cache_path = CACHE_WERKAFSPRAKEN_DIR / item.category / item.file_hash
            if cache_path.exists():
                shutil.rmtree(cache_path, ignore_errors=True)
        return

    # === PROD / S3 ===
    # origineel bestand
    try:
        default_storage.delete(rel_path)
    except Exception:
        pass

    # Cache: cache/werkafspraken/<category>/<hash>/page_*.png
    if ext == ".pdf" and item.file_hash:
        cache_base = f"cache/werkafspraken/{item.category}/{item.file_hash}"
        try:
            _dirs, files = default_storage.listdir(cache_base)
        except FileNotFoundError:
            files = []
        for name in files:
            try:
                default_storage.delete(f"{cache_base}/{name}")
            except Exception:
                pass

@login_required
def policies(request):
    if not can(request.user, "can_view_policies"):
        return HttpResponseForbidden("Geen toegang.")

    # Verwijderen via kruisje
    if request.method == "POST" and "delete_item" in request.POST:
        if not can(request.user, "can_upload_werkafspraken"):
            return HttpResponseForbidden("Geen toegang.")

        item = get_object_or_404(Werkafspraak, id=request.POST.get("delete_item"))
        _delete_werkafspraak_files_for_item(item)
        item.delete()
        messages.success(request, "Werkafspraak verwijderd.")
        return redirect("policies")

    # Toevoegen via formulier
    if request.method == "POST" and "delete_item" not in request.POST:
        if not can(request.user, "can_upload_werkafspraken"):
            return HttpResponseForbidden("Geen uploadrechten.")

        form = WerkafspraakForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data.get("file")
            category = form.cleaned_data["category"]

            rel_path = ""
            h = ""
            original_name = ""

            if uploaded_file:
                # Subdir per categorie: werkafspraken/baxter/, werkafspraken/instelling/, etc.
                category_dir = WERKAFSPRAKEN_DIR / category
                
                rel_path, h = save_pdf_or_png_with_hash(
                    uploaded_file=uploaded_file,
                    target_dir=category_dir,
                    base_name="werkafspraak",
                )
                original_name = uploaded_file.name

            werkafspraak = Werkafspraak(
                title=form.cleaned_data["title"],
                short_description=form.cleaned_data.get("short_description", ""),
                file_path=rel_path,
                file_hash=h,
                original_filename=original_name,
                category=category,
                created_by=request.user,
            )
            werkafspraak.save()
            messages.success(request, "Werkafspraak succesvol geüpload.")
            return redirect("policies")
        else:
            # Toon nette foutmelding
            file_errors = form.errors.get("file")
            if file_errors:
                for err in file_errors:
                    messages.error(request, err)
            else:
                messages.error(request, "Het formulier bevat fouten. Controleer de invoer.")

    # Helper functie om PDF rendering te doen
    def process_items(items_queryset, category_name):
        """Verwerkt items: laadt PDF bytes en rendert naar cache per categorie"""
        items = list(items_queryset)
        
        # Cache subdir per categorie: cache/werkafspraken/baxter/, etc.
        category_cache_dir = CACHE_WERKAFSPRAKEN_DIR / category_name
        
        for item in items:
            item.file_url = item.media_url
            item.page_urls = []

            if not item.has_file or not item.is_pdf:
                continue

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

            # PDF → PNG's in cache/werkafspraken/<category>/<hash>/page_XXX.png
            h, n_pages = render_pdf_to_cache(
                pdf_bytes,
                dpi=300,
                cache_root=category_cache_dir,
            )

            # backfill hash als die nog leeg is
            if not item.file_hash:
                item.file_hash = h
                item.save(update_fields=["file_hash"])

            item.page_urls = [
                f"{settings.MEDIA_URL}cache/werkafspraken/{category_name}/{h}/page_{i:03d}.png"
                for i in range(1, n_pages + 1)
            ]
        
        return items

   # GET (of invalid POST): items ophalen per categorie + maak forms
    categories = []

    # Voeg werkafspraken per categorie toe als de gebruiker permissies heeft
    if can(request.user, "can_view_baxter"):
        baxter_items = process_items(Werkafspraak.objects.filter(category="baxter"), "baxter")
        # FIX: Voeg auto_id toe zodat ID's uniek zijn (bv. id_baxter_title)
        baxter_form = WerkafspraakForm(
            initial={'category': 'baxter'}, 
            auto_id='id_baxter_%s'
        )
        categories.append({
            "name": "Baxterproductie",
            "permissions": "can_view_baxter",
            "category": "baxter",
            "image": "factory-256x256.png",
            "workafspraken": baxter_items,
            "form": baxter_form
        })
    
    if can(request.user, "can_view_instellings_apo"):
        instelling_items = process_items(Werkafspraak.objects.filter(category="instelling"), "instelling")
        # FIX: Voeg auto_id toe
        instelling_form = WerkafspraakForm(
            initial={'category': 'instelling'}, 
            auto_id='id_instelling_%s'
        )
        categories.append({
            "name": "Instellingsapotheek",
            "permissions": "can_view_instellings_apo",
            "category": "instelling",
            "image": "instellingsapotheek-256x256.png",
            "workafspraken": instelling_items,
            "form": instelling_form
        })
    
    if can(request.user, "can_view_openbare_apo"):
        openbare_items = process_items(Werkafspraak.objects.filter(category="openbare"), "openbare")
        # FIX: Voeg auto_id toe
        openbare_form = WerkafspraakForm(
            initial={'category': 'openbare'}, 
            auto_id='id_openbare_%s'
        )
        categories.append({
            "name": "Openbare Apo",
            "permissions": "can_view_openbare_apo",
            "category": "openbare",
            "image": "openbareapotheek-256x256.png",
            "workafspraken": openbare_items,
            "form": openbare_form
        })

    return render(request, "policies/index.html", {
        "categories": categories,
    })