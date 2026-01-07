from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect

from core.forms import OnboardingFormulierForm
from core.models import OnboardingFormulier
from ._helpers import can


@login_required
def onboarding_formulieren(request):
    if not can(request, "can_view_forms"):
        return HttpResponseForbidden("Geen toegang tot formulieren.")

    can_edit = can(request, "can_edit_forms")

    new_form = OnboardingFormulierForm(prefix="new")
    open_edit_id = None

    # 1) Verwijderen
    if request.method == "POST" and "delete_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen toegang.")

        item_id = request.POST.get("delete_item")
        deleted_count, _ = OnboardingFormulier.objects.filter(id=item_id).delete()

        if deleted_count > 0:
            messages.success(request, "Formulier verwijderd.")
        else:
            messages.error(request, "Formulier kon niet worden verwijderd (reeds weg?).")

        return redirect("onboarding_formulieren")

    # 2) Bewerken
    if request.method == "POST" and "edit_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen toegang.")

        try:
            item_id = int(request.POST.get("edit_item"))
        except (TypeError, ValueError):
            return redirect("onboarding_formulieren")

        item = OnboardingFormulier.objects.filter(id=item_id).first()
        if not item:
            messages.error(request, "Formulier niet gevonden.")
            return redirect("onboarding_formulieren")

        open_edit_id = item_id
        edit_form = OnboardingFormulierForm(request.POST, prefix=f"edit-{item_id}", instance=item)

        if edit_form.is_valid():
            edit_form.save()
            messages.success(request, "Wijzigingen opgeslagen.")
            return redirect("onboarding_formulieren")
        else:
            messages.error(request, "Er staan fouten in het formulier.")

    # 3) Toevoegen
    if request.method == "POST" and "add_item" in request.POST:
        if not can_edit:
            return HttpResponseForbidden("Geen toegang.")

        new_form = OnboardingFormulierForm(request.POST, prefix="new")
        if new_form.is_valid():
            item = new_form.save(commit=False)
            item.created_by = request.user
            item.save()

            messages.success(request, "Nieuw formulier toegevoegd.")
            return redirect("onboarding_formulieren")
        else:
            messages.error(request, "Formulier toevoegen mislukt. Controleer de velden.")

    # --- Data ophalen ---
    qs = OnboardingFormulier.objects.all().order_by("title")

    rows = []
    for item in qs:
        if open_edit_id == item.id and request.method == "POST" and "edit_item" in request.POST:
            form = OnboardingFormulierForm(request.POST, prefix=f"edit-{item.id}", instance=item)
        else:
            form = OnboardingFormulierForm(prefix=f"edit-{item.id}", instance=item)
        rows.append((item, form))

    context = {
        "rows": rows,
        "items": [i for i, _ in rows],
        "new_form": new_form,
        "open_edit_id": open_edit_id,
        "can_edit": can_edit,
    }
    return render(request, "onboarding_formulieren/index.html", context)
