from django.utils.text import slugify
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import date

from core.views._helpers import can, _render_pdf, _static_abs_path
from core.decorators import ip_restricted
from core.models import Omzettingslijst, OmzettingslijstEntry, Organization
from core.forms import OmzettingslijstForm, OmzettingslijstEntryForm
from core.tasks import send_omzettingslijst_pdf_task


def _iso_weekday_from_dag(dag_code: str) -> int:
    mapping = {"MA": 1, "DI": 2, "WO": 3, "DO": 4, "VR": 5, "ZA": 6}
    return mapping.get((dag_code or "").upper(), 1)


def _date_from_year_week_dag(jaar: int, week: int, dag_code: str) -> date:
    return date.fromisocalendar(int(jaar), int(week), int(_iso_weekday_from_dag(dag_code)))


@ip_restricted
@login_required
def omzettingslijst(request):
    if not can(request.user, "can_view_baxter_omzettingslijst"):
        return HttpResponseForbidden("Je hebt geen toegang tot deze pagina.")

    can_edit = can(request.user, "can_edit_baxter_omzettingslijst")
    can_send = can(request.user, "can_send_baxter_omzettingslijst")

    apotheken = Organization.objects.all().order_by("name")

    list_form = OmzettingslijstForm()
    entry_form = OmzettingslijstEntryForm()

    selected_list = None
    list_id = request.GET.get("list_id") or request.POST.get("list_id")

    if list_id and str(list_id).isdigit():
        selected_list = Omzettingslijst.objects.select_related("apotheek").filter(pk=int(list_id)).first()
    else:
        selected_list = Omzettingslijst.objects.select_related("apotheek").order_by("-updated_at", "-created_at").first()

    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("Je hebt geen rechten om wijzigingen door te voeren.")

        # 1) Nieuwe lijst
        if "btn_add_list" in request.POST:
            list_form = OmzettingslijstForm(request.POST)
            if list_form.is_valid():
                new_list = list_form.save()
                messages.success(request, "Omzettingslijst succesvol aangemaakt.")
                return redirect(f"{request.path}?list_id={new_list.id}")
            messages.error(request, "Controleer de invoer bij het aanmaken van de omzettingslijst.")

        # 2) Lijst wisselen
        elif "btn_select_list" in request.POST:
            sel = request.POST.get("selected_list_id")
            if sel and str(sel).isdigit():
                sel_obj = Omzettingslijst.objects.filter(pk=int(sel)).first()
                if sel_obj:
                    return redirect(f"{request.path}?list_id={sel_obj.id}")
            messages.warning(request, "Kon de geselecteerde omzettingslijst niet openen.")
            return redirect(request.path)

        # 3) Entry toevoegen
        elif "btn_add_entry" in request.POST:
            if not selected_list:
                messages.warning(request, "Maak eerst een omzettingslijst aan (apotheek/jaar/week/dag).")
                return redirect(request.path)

            entry_form = OmzettingslijstEntryForm(request.POST)
            if entry_form.is_valid():
                entry = entry_form.save(commit=False)
                entry.omzettingslijst = selected_list
                entry.save()
                selected_list.save(update_fields=["updated_at"])

                messages.success(request, "Omzetting succesvol toegevoegd.")
                return redirect(f"{request.path}?list_id={selected_list.id}")
            messages.error(request, "Controleer de invoer van de omzetting.")

        # 4) Entry edit
        elif "btn_edit_entry" in request.POST:
            entry_id = request.POST.get("entry_id")
            if not (entry_id and str(entry_id).isdigit()):
                messages.error(request, "Ongeldige omzetting.")
                return redirect(request.path)

            instance = get_object_or_404(OmzettingslijstEntry, pk=int(entry_id))

            if selected_list and instance.omzettingslijst_id != selected_list.id:
                messages.error(request, "Omzetting hoort niet bij de geselecteerde omzettingslijst.")
                return redirect(f"{request.path}?list_id={selected_list.id}")

            form = OmzettingslijstEntryForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                instance.omzettingslijst.save(update_fields=["updated_at"])
                messages.success(request, "Wijziging opgeslagen.")
                return redirect(f"{request.path}?list_id={selected_list.id}" if selected_list else request.path)
            messages.error(request, "Controleer de invoer bij het aanpassen.")

        # 5) Entry delete
        elif "btn_delete_entry" in request.POST:
            entry_id = request.POST.get("entry_id")
            if not (entry_id and str(entry_id).isdigit()):
                messages.error(request, "Ongeldige omzetting.")
                return redirect(request.path)

            instance = get_object_or_404(OmzettingslijstEntry, pk=int(entry_id))

            if selected_list and instance.omzettingslijst_id != selected_list.id:
                messages.error(request, "Omzetting hoort niet bij de geselecteerde omzettingslijst.")
                return redirect(f"{request.path}?list_id={selected_list.id}")

            lst = instance.omzettingslijst
            instance.delete()
            lst.save(update_fields=["updated_at"])
            messages.success(request, "Omzetting succesvol verwijderd.")
            return redirect(f"{request.path}?list_id={selected_list.id}" if selected_list else request.path)

    recent_lists = list(
        Omzettingslijst.objects.select_related("apotheek").order_by("-updated_at", "-created_at")[:5]
    )

    entries = OmzettingslijstEntry.objects.select_related(
        "omzettingslijst",
        "omzettingslijst__apotheek",
        "gevraagd_geneesmiddel",
        "geleverd_geneesmiddel",
    )
    if selected_list:
        entries = entries.filter(omzettingslijst=selected_list)
    else:
        entries = entries.none()

    context = {
        "title": "Omzettingslijst",
        "page_title": "Omzettingslijst",
        "can_edit": can_edit,
        "can_send": can_send,
        "apotheken": apotheken,

        "selected_list": selected_list,
        "recent_lists": recent_lists,

        "list_form": list_form,
        "entry_form": entry_form,
        "entries": entries,
    }
    return render(request, "omzettingslijst/index.html", context)


@ip_restricted
@login_required
def api_omzettingslijsten(request):
    if not can(request.user, "can_view_baxter_omzettingslijst"):
        return HttpResponseForbidden("Geen toegang.")

    q = (request.GET.get("q") or "").strip().lower()

    qs = Omzettingslijst.objects.select_related("apotheek").order_by("-updated_at", "-created_at")

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
def export_omzettingslijst_pdf(request):
    if not can(request.user, "can_view_baxter_omzettingslijst"):
        return HttpResponseForbidden("Geen toegang.")

    list_id = request.GET.get("list_id")
    if not (list_id and str(list_id).isdigit()):
        return HttpResponseForbidden("Geen geldige lijst geselecteerd.")

    selected_list = (
        Omzettingslijst.objects
        .select_related("apotheek")
        .filter(pk=int(list_id))
        .first()
    )
    if not selected_list:
        return HttpResponseForbidden("Lijst niet gevonden.")

    entries = (
        OmzettingslijstEntry.objects
        .select_related("gevraagd_geneesmiddel", "geleverd_geneesmiddel", "omzettingslijst", "omzettingslijst__apotheek")
        .filter(omzettingslijst=selected_list)
        .order_by("-updated_at", "-created_at")
    )

    try:
        dag_datum = _date_from_year_week_dag(selected_list.jaar, selected_list.week, selected_list.dag)
    except Exception:
        dag_datum = None

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
        "omzettingslijst/pdf/omzettingslijst_export.html",
        context,
        request=request,
    )

    pdf_file = _render_pdf(html, base_url=request.build_absolute_uri("/"))

    apo_name = selected_list.apotheek.name if selected_list.apotheek else "Apotheek"
    filename = f"Omzettingslijst_{apo_name}_Week{selected_list.week}_{selected_list.dag}_{timezone.now().strftime('%d-%m-%Y')}.pdf"
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@ip_restricted
@login_required
def email_omzettingslijst_pdf(request):
    if not can(request.user, "can_send_baxter_omzettingslijst"):
        return HttpResponseForbidden("Geen toegang.")

    if request.method == "POST":
        list_ids = request.POST.getlist("recipients")
        list_ids = [int(i) for i in list_ids if str(i).isdigit()]

        if not list_ids:
            messages.warning(request, "Geen lijsten geselecteerd.")
            return redirect("baxter_omzettingslijst")

        send_omzettingslijst_pdf_task.delay(list_ids)
        messages.success(request, f"De PDF wordt op de achtergrond verstuurd voor {len(list_ids)} geselecteerde lijst(en).")

        current_list_id = request.POST.get("current_list_id")
        if current_list_id and str(current_list_id).isdigit():
            return redirect(f"{request.path}?list_id={int(current_list_id)}")
        return redirect("baxter_omzettingslijst")

    return redirect("baxter_omzettingslijst")


@ip_restricted
@login_required
def export_omzettingslijst_label_pdf(request, entry_id: int):
    if not can(request.user, "can_edit_baxter_omzettingslijst"):
        return HttpResponseForbidden("Geen toegang.")

    entry = get_object_or_404(
        OmzettingslijstEntry.objects.select_related(
            "omzettingslijst",
            "omzettingslijst__apotheek",
            "gevraagd_geneesmiddel",
            "geleverd_geneesmiddel",
        ),
        pk=entry_id,
    )

    gm_v = entry.gevraagd_geneesmiddel
    gm_g = entry.geleverd_geneesmiddel

    gevraagd = gm_v.naam if gm_v else "-"
    geleverd = gm_g.naam if gm_g else "-"
    omschrijving = entry.omschrijving_geneesmiddel or "-"

    vanaf_datum = entry.vanaf_datum
    patient_naam = entry.patient_naam or "-"
    geboortedatum = entry.patient_geboortedatum

    context = {
        "entry": entry,
        "generated_at": timezone.localtime(timezone.now()),
        "gevraagd": gevraagd,
        "geleverd": geleverd,
        "omschrijving": omschrijving,
        "vanaf_datum": vanaf_datum,
        "patient_naam": patient_naam,
        "geboortedatum": geboortedatum,
        "logo_path": _static_abs_path("img/app_icon_black_trans-512x512.png"),
    }

    html = render_to_string(
        "omzettingslijst/pdf/omzettingslijst_etiket.html",
        context,
        request=request,
    )

    pdf_bytes = _render_pdf(html, base_url=request.build_absolute_uri("/"))

    raw_name = entry.patient_naam or f"entry_{entry_id}"
    safe = slugify(raw_name).replace("-", "_")
    safe = (safe[:40] or "patient").strip("_")

    filename = f"etiket_omzettingslijst_{safe}.pdf"

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
