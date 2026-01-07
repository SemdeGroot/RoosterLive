from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect

from core.forms import InschrijvingItemForm
from core.models import InschrijvingItem
from ._helpers import can


@login_required
def inschrijvingen(request):
    if not can(request, "can_view_inschrijven"):
        return HttpResponseForbidden("Geen toegang tot inschrijvingen.")

    can_edit = can(request, "can_edit_inschrijven")

    new_form = InschrijvingItemForm(prefix="new")
    open_edit_id = None

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
            item = new_form.save(commit=False)
            item.created_by = request.user
            item.save()

            messages.success(request, "Nieuw item toegevoegd.")
            return redirect("inschrijvingen")
        else:
            messages.error(request, "Toevoegen mislukt. Controleer de velden.")

    # --- Data ophalen ---
    qs = InschrijvingItem.objects.all().order_by("title")

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
    }
    return render(request, "inschrijven/index.html", context)
