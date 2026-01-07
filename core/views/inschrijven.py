from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils import timezone

from core.forms import InschrijvingItemForm
from core.models import InschrijvingItem
from ._helpers import can


@login_required
def inschrijvingen(request):
    if not can(request, "can_view_inschrijven"):
        return HttpResponseForbidden("Geen toegang tot inschrijven.")

    today = timezone.localdate()

    # Verwijder verlopen items automatisch bij openen van de view
    InschrijvingItem.objects.filter(verloopdatum__isnull=False, verloopdatum__lt=today).delete()

    can_edit = can(request, "can_edit_inschrijven")

    new_form = InschrijvingItemForm(prefix="new")
    open_edit_id = None
    show_add_form = False  # gebruik dit om add-form open te houden zonder inline errors

    # 1) Verwijderen
    if request.method == "POST" and "delete_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen toegang.")

        item_id = request.POST.get("delete_item")
        deleted_count, _ = InschrijvingItem.objects.filter(id=item_id).delete()

        if deleted_count > 0:
            messages.success(request, "Item verwijderd.")
        else:
            messages.error(request, "Item kon niet worden verwijderd (reeds weg?).")

        return redirect("inschrijvingen")

    # 2) Bewerken
    if request.method == "POST" and "edit_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen toegang.")

        try:
            item_id = int(request.POST.get("edit_item"))
        except (TypeError, ValueError):
            return redirect("inschrijvingen")

        item = InschrijvingItem.objects.filter(id=item_id).first()
        if not item:
            messages.error(request, "Item niet gevonden.")
            return redirect("inschrijvingen")

        open_edit_id = item_id
        edit_form = InschrijvingItemForm(request.POST, prefix=f"edit-{item_id}", instance=item)

        if edit_form.is_valid():
            vd = edit_form.cleaned_data.get("verloopdatum")
            if vd and vd < today:
                messages.error(request, "Verloopdatum mag niet in het verleden liggen.")
                # Niet redirecten: we renderen pagina opnieuw en laten edit-form open
            else:
                edit_form.save()
                messages.success(request, "Wijzigingen opgeslagen.")
                return redirect("inschrijvingen")
        else:
            messages.error(request, "Er staan fouten in het formulier.")

    # 3) Toevoegen
    if request.method == "POST" and "add_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen toegang.")

        new_form = InschrijvingItemForm(request.POST, prefix="new")

        if new_form.is_valid():
            vd = new_form.cleaned_data.get("verloopdatum")
            if vd and vd < today:
                messages.error(request, "Verloopdatum mag niet in het verleden liggen.")
                show_add_form = True  # zodat je add-form open kunt houden zonder inline errors
            else:
                item = new_form.save(commit=False)
                item.created_by = request.user
                item.save()

                messages.success(request, "Nieuw item toegevoegd.")
                return redirect("inschrijvingen")
        else:
            messages.error(request, "Toevoegen mislukt. Controleer de velden.")
            show_add_form = True

    # --- Data ophalen ---
    qs = InschrijvingItem.objects.all().order_by("verloopdatum", "title")

    rows = []
    for item in qs:
        if open_edit_id == item.id and request.method == "POST" and "edit_item" in request.POST:
            form = InschrijvingItemForm(request.POST, prefix=f"edit-{item.id}", instance=item)
        else:
            form = InschrijvingItemForm(prefix=f"edit-{item.id}", instance=item)
        rows.append((item, form))

    context = {
        "rows": rows,
        "items": [i for i, _ in rows],
        "new_form": new_form,
        "open_edit_id": open_edit_id,
        "can_edit": can_edit,
        "show_add_form": show_add_form,
    }
    return render(request, "inschrijven/index.html", context)