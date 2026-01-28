# core/views/no_delivery.py
import re
from django.utils.text import slugify
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404

from core.views._helpers import can, _render_pdf, _static_abs_path
from core.models import NoDeliveryList, NoDeliveryEntry, Organization
from core.forms import NoDeliveryListForm, NoDeliveryEntryForm
from core.decorators import ip_restricted
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import date
from core.tasks import send_no_delivery_pdf_task

def _iso_weekday_from_dag(dag_code: str) -> int:
    """
    ISO weekday: maandag=1 ... zondag=7
    Jouw model heeft MA..ZA, dus MA=1..ZA=6
    """
    mapping = {
        "MA": 1,
        "DI": 2,
        "WO": 3,
        "DO": 4,
        "VR": 5,
        "ZA": 6,
    }
    return mapping.get((dag_code or "").upper(), 1)


def _date_from_year_week_dag(jaar: int, week: int, dag_code: str) -> date:
    """
    ISO week date: date.fromisocalendar(year, week, weekday)
    """
    weekday = _iso_weekday_from_dag(dag_code)
    return date.fromisocalendar(int(jaar), int(week), int(weekday))


@ip_restricted
@login_required
def no_delivery(request):
    if not can(request.user, "can_view_baxter_no_delivery"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    can_edit = can(request.user, "can_edit_baxter_no_delivery")
    can_send = can(request.user, "can_send_baxter_no_delivery")

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

                messages.success(request, "Niet geleverd geneesmiddel succesvol toegevoegd.")
                return redirect(f"{request.path}?list_id={selected_list.id}")
            messages.error(request, "Controleer de invoer van het niet geleverde geneesmiddel.")

        # 4) Entry edit
        elif "btn_edit_entry" in request.POST:
            entry_id = request.POST.get("entry_id")
            if not (entry_id and str(entry_id).isdigit()):
                messages.error(request, "Ongeldig niet geleverd geneesmiddel.")
                return redirect(request.path)

            instance = get_object_or_404(NoDeliveryEntry, pk=int(entry_id))

            if selected_list and instance.no_delivery_list_id != selected_list.id:
                messages.error(request, "Niet geleverd geneesmiddel hoort niet bij de geselecteerde niet-leverlijst.")
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
                messages.error(request, "Ongeldig niet geleverd geneesmiddel.")
                return redirect(request.path)

            instance = get_object_or_404(NoDeliveryEntry, pk=int(entry_id))

            if selected_list and instance.no_delivery_list_id != selected_list.id:
                messages.error(request, "Niet geleverd geneesmiddel hoort niet bij de geselecteerde niet-leverlijst.")
                return redirect(f"{request.path}?list_id={selected_list.id}")

            lst = instance.no_delivery_list
            instance.delete()
            lst.save(update_fields=["updated_at"])
            messages.success(request, "Niet geleverd geneesmiddel succesvol verwijderd.")
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
        "can_send": can_send,
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

@ip_restricted
@login_required
def export_no_delivery_pdf(request):
    """
    Exporteert de geselecteerde niet-leverlijst als PDF.
    Vereist: ?list_id=<id>
    """
    if not can(request.user, "can_view_baxter_no_delivery"):
        return HttpResponseForbidden("Geen toegang.")

    list_id = request.GET.get("list_id")
    if not (list_id and str(list_id).isdigit()):
        return HttpResponseForbidden("Geen geldige lijst geselecteerd.")

    selected_list = (
        NoDeliveryList.objects
        .select_related("apotheek")
        .filter(pk=int(list_id))
        .first()
    )
    if not selected_list:
        return HttpResponseForbidden("Lijst niet gevonden.")

    entries = (
        NoDeliveryEntry.objects
        .select_related("gevraagd_geneesmiddel", "no_delivery_list", "no_delivery_list__apotheek")
        .filter(no_delivery_list=selected_list)
        .order_by("-updated_at", "-created_at")
    )

    # Bepaal datum van deze lijst (op basis van jaar/week/dag)
    try:
        dag_datum = _date_from_year_week_dag(selected_list.jaar, selected_list.week, selected_list.dag)
    except Exception:
        dag_datum = None  # fail-safe

    # Zelfde assets als STS halfjes
    from core.views._helpers import _static_abs_path, _render_pdf  # lokaal importeren mag ook
    contact_email = "baxterezorg@apotheekjansen.com"

    context = {
        "selected_list": selected_list,
        "entries": entries,

        "generated_at": timezone.localtime(timezone.now()),
        "dag_datum": dag_datum,

        "logo_path": _static_abs_path("img/app_icon-1024x1024.png"),
        "signature_path": _static_abs_path("img/handtekening_roel.png"),
        "contact_email": contact_email,
    }

    html = render_to_string(
        "no_delivery/pdf/no_delivery_export.html",  # ja: html-template met .pdf naam
        context,
        request=request,
    )

    pdf_file = _render_pdf(html, base_url=request.build_absolute_uri("/"))

    apo_name = selected_list.apotheek.name if selected_list.apotheek else "Apotheek"
    filename = f"Niet-leverlijst_{apo_name}_Week{selected_list.week}_{selected_list.dag}_{timezone.now().strftime('%d-%m-%Y')}.pdf"
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response

@ip_restricted
@login_required
def email_no_delivery_pdf(request):
    """
    Start celery: verstuurt per geselecteerde NoDeliveryList een PDF naar de gekoppelde apotheek.
    """
    if not can(request.user, "can_send_baxter_no_delivery"):
        return HttpResponseForbidden("Geen toegang.")

    if request.method == "POST":
        list_ids = request.POST.getlist("recipients")  # select2 multiple
        list_ids = [int(i) for i in list_ids if str(i).isdigit()]

        if not list_ids:
            messages.warning(request, "Geen lijsten geselecteerd.")
            return redirect("baxter_no_delivery")

        send_no_delivery_pdf_task.delay(list_ids)
        messages.success(request, f"De PDF wordt op de achtergrond verstuurd voor {len(list_ids)} geselecteerde lijst(en).")

        # terug naar huidige lijst (als die open stond)
        current_list_id = request.POST.get("current_list_id")
        if current_list_id and str(current_list_id).isdigit():
            return redirect(f"{request.path}?list_id={int(current_list_id)}")
        return redirect("baxter_no_delivery")

    return redirect("baxter_no_delivery")

@ip_restricted
@login_required
def export_no_delivery_label_pdf(request, entry_id: int):
    if not can(request.user, "can_edit_baxter_no_delivery"):
        return HttpResponseForbidden("Geen toegang.")

    entry = get_object_or_404(
        NoDeliveryEntry.objects.select_related(
            "no_delivery_list",
            "no_delivery_list__apotheek",
            "gevraagd_geneesmiddel",
        ),
        pk=entry_id,
    )

    gm = entry.gevraagd_geneesmiddel
    geneesmiddel = gm.naam if gm else "-"
    vanaf_datum = entry.vanaf_datum

    patient_naam = entry.patient_naam or "-"
    geboortedatum = entry.patient_geboortedatum

    context = {
        "entry": entry,
        "generated_at": timezone.localtime(timezone.now()),
        "geneesmiddel": geneesmiddel,
        "vanaf_datum": vanaf_datum,
        "patient_naam": patient_naam,
        "geboortedatum": geboortedatum,
        "logo_path": _static_abs_path("pwa/icons/favicon-32x32.png"),
    }

    html = render_to_string(
        "no_delivery/pdf/no_delivery_etiket.html",
        context,
        request=request,
    )

    pdf_bytes = _render_pdf(html, base_url=request.build_absolute_uri("/"))

    # --- veilige bestandsnaam (snake_case-ish) ---
    raw_name = entry.patient_naam or f"entry_{entry_id}"

    # slugify maakt "jan jansen" -> "jan-jansen" (veilig)
    safe = slugify(raw_name)

    # jij wil snake_case: vervang '-' door '_'
    safe = safe.replace("-", "_")

    # limit lengte (Windows / printers / mailclients)
    safe = (safe[:40] or "patient").strip("_")

    filename = f"etiket_geen_levering_{safe}.pdf"

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response