# core/views/no_delivery.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404

from core.views._helpers import can
from core.models import NoDeliveryList, NoDeliveryEntry, Organization
from core.forms import NoDeliveryListForm, NoDeliveryEntryForm
from core.decorators import ip_restricted

@ip_restricted
@login_required
def no_delivery(request):
    if not can(request.user, "can_view_baxter_no_delivery"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    can_edit = can(request.user, "can_edit_baxter_no_delivery")

    apotheken = Organization.objects.filter(
        org_type=Organization.ORG_TYPE_APOTHEEK
    ).order_by("name")

    list_form = NoDeliveryListForm()
    entry_form = NoDeliveryEntryForm()

    selected_list = None
    list_id = request.GET.get("list_id") or request.POST.get("list_id")

    # Default selection: meest recent (updated/created)
    if list_id and str(list_id).isdigit():
        selected_list = NoDeliveryList.objects.select_related("apotheek").filter(pk=int(list_id)).first()
    else:
        selected_list = NoDeliveryList.objects.select_related("apotheek").order_by("-updated_at", "-created_at").first()

    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("Je hebt geen rechten om wijzigingen door te voeren.")

        # 1) Nieuwe lijst
        if "btn_add_list" in request.POST:
            list_form = NoDeliveryListForm(request.POST)
            if list_form.is_valid():
                new_list = list_form.save()
                messages.success(request, "Niet-leverlijst succesvol aangemaakt.")
                return redirect(f"{request.path}?list_id={new_list.id}")
            messages.error(request, "Controleer de invoer bij het aanmaken van de niet-leverlijst.")

        # 2) Lijst wisselen (select2)
        elif "btn_select_list" in request.POST:
            sel = request.POST.get("selected_list_id")
            if sel and str(sel).isdigit():
                sel_obj = NoDeliveryList.objects.filter(pk=int(sel)).first()
                if sel_obj:
                    return redirect(f"{request.path}?list_id={sel_obj.id}")
            messages.warning(request, "Kon de geselecteerde niet-leverlijst niet openen.")
            return redirect(request.path)

        # 3) Entry toevoegen
        elif "btn_add_entry" in request.POST:
            if not selected_list:
                messages.warning(request, "Maak eerst een niet-leverlijst aan (apotheek/jaar/week/dag).")
                return redirect(request.path)

            entry_form = NoDeliveryEntryForm(request.POST)
            if entry_form.is_valid():
                entry = entry_form.save(commit=False)
                entry.no_delivery_list = selected_list
                entry.save()
                selected_list.save(update_fields=["updated_at"])

                messages.success(request, "Geneesmiddel succesvol toegevoegd.")
                return redirect(f"{request.path}?list_id={selected_list.id}")
            messages.error(request, "Controleer de invoer van het geneesmiddel.")

        # 4) Entry edit
        elif "btn_edit_entry" in request.POST:
            entry_id = request.POST.get("entry_id")
            if not (entry_id and str(entry_id).isdigit()):
                messages.error(request, "Ongeldig geneesmiddel.")
                return redirect(request.path)

            instance = get_object_or_404(NoDeliveryEntry, pk=int(entry_id))

            if selected_list and instance.no_delivery_list_id != selected_list.id:
                messages.error(request, "Geneesmiddel hoort niet bij de geselecteerde niet-leverlijst.")
                return redirect(f"{request.path}?list_id={selected_list.id}")

            form = NoDeliveryEntryForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                instance.no_delivery_list.save(update_fields=["updated_at"])
                messages.success(request, "Wijziging opgeslagen.")
                return redirect(f"{request.path}?list_id={selected_list.id}" if selected_list else request.path)
            messages.error(request, "Controleer de invoer bij het aanpassen.")

        # 5) Entry delete
        elif "btn_delete_entry" in request.POST:
            entry_id = request.POST.get("entry_id")
            if not (entry_id and str(entry_id).isdigit()):
                messages.error(request, "Ongeldig geneesmiddel.")
                return redirect(request.path)

            instance = get_object_or_404(NoDeliveryEntry, pk=int(entry_id))

            if selected_list and instance.no_delivery_list_id != selected_list.id:
                messages.error(request, "Geneesmiddel hoort niet bij de geselecteerde niet-leverlijst.")
                return redirect(f"{request.path}?list_id={selected_list.id}")

            lst = instance.no_delivery_list
            instance.delete()
            lst.save(update_fields=["updated_at"])
            messages.success(request, "Geneesmiddel succesvol verwijderd.")
            return redirect(f"{request.path}?list_id={selected_list.id}" if selected_list else request.path)

    # “Laatste 5” uit DB (meest recent updated/created)
    recent_lists = list(
        NoDeliveryList.objects.select_related("apotheek").order_by("-updated_at", "-created_at")[:5]
    )

    entries = NoDeliveryEntry.objects.select_related(
        "no_delivery_list",
        "no_delivery_list__apotheek",
        "gevraagd_geneesmiddel",
    )
    if selected_list:
        entries = entries.filter(no_delivery_list=selected_list)
    else:
        entries = entries.none()

    context = {
        "title": "Geen levering",
        "page_title": "Geen levering",
        "can_edit": can_edit,
        "apotheken": apotheken,

        "selected_list": selected_list,
        "recent_lists": recent_lists,

        "list_form": list_form,
        "entry_form": entry_form,
        "entries": entries,
    }
    return render(request, "no_delivery/index.html", context)

@ip_restricted
@login_required
def api_no_delivery_lists(request):
    """
    Select2 endpoint: live search op apotheek + jaar/week + daglabel.
    """
    if not can(request.user, "can_view_baxter_no_delivery"):
        return HttpResponseForbidden("Geen toegang.")

    q = (request.GET.get("q") or "").strip().lower()

    qs = NoDeliveryList.objects.select_related("apotheek").order_by("-updated_at", "-created_at")

    if q:
        filtered = []
        for obj in qs[:800]:
            apo = obj.apotheek.name if obj.apotheek else "-"
            text = f"{apo} - {obj.jaar} - Week {obj.week} - {obj.get_dag_display()}"
            if q in text.lower():
                filtered.append(obj)
        qs = filtered
    else:
        qs = list(qs[:80])

    results = []
    for obj in qs[:50]:
        apo = obj.apotheek.name if obj.apotheek else "-"
        text = f"{apo} - {obj.jaar} - Week {obj.week} - {obj.get_dag_display()}"
        results.append({"id": obj.id, "text": text})

    return JsonResponse({"results": results})
