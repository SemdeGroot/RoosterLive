# core/views/stshalfjes.py
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone

from core.models import STSHalfje, Organization
from core.forms import STSHalfjeForm
from core.views._helpers import can, _static_abs_path, _render_pdf
from core.tasks import send_stshalfjes_pdf_task


@login_required
def stshalfjes(request):
    """
    Beheert het overzicht van onnodig gehalveerde geneesmiddelen.
    """
    if not can(request.user, "can_view_baxter_sts_halfjes"):
        return HttpResponseForbidden("Je hebt geen rechten om deze pagina te bekijken.")

    can_edit = can(request.user, "can_edit_baxter_sts_halfjes")
    can_send = can(request.user, "can_send_baxter_sts_halfjes")

    apotheken = Organization.objects.filter(
        org_type=Organization.ORG_TYPE_APOTHEEK
    ).order_by("name")

    form = STSHalfjeForm()

    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("Je hebt geen rechten om wijzigingen door te voeren.")

        if "btn_delete" in request.POST:
            item_id = request.POST.get("item_id")
            item = get_object_or_404(STSHalfje, id=item_id)
            item.delete()
            messages.success(request, "Melding succesvol verwijderd.")
            return redirect("stshalfjes")

        elif "btn_edit" in request.POST:
            item_id = request.POST.get("item_id")
            instance = get_object_or_404(STSHalfje, id=item_id)

            form = STSHalfjeForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, "Wijziging opgeslagen.")
                return redirect("stshalfjes")
            else:
                messages.error(request, "Controleer de invoer bij het aanpassen.")

        elif "btn_add" in request.POST:
            form = STSHalfjeForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Melding succesvol toegevoegd.")
                return redirect("stshalfjes")
            else:
                messages.error(request, "Controleer de invoer van het formulier.")

    items = STSHalfje.objects.select_related(
        "item_gehalveerd",
        "item_alternatief",
        "apotheek",
    ).all()

    context = {
        "title": "Onnodig gehalveerde geneesmiddelen",
        "items": items,
        "form": form,
        "can_edit": can_edit,
        "can_send": can_send,
        "apotheken": apotheken,
    }
    return render(request, "stshalfjes/index.html", context)


@login_required
def export_stshalfjes_pdf(request):
    """
    Exporteert een PDF.
    Optioneel: ?apotheek=<id> om alleen voor 1 apotheek te exporteren.
    """
    if not can(request.user, "can_send_baxter_sts_halfjes"):
        return HttpResponseForbidden("Geen toegang.")

    apotheek = None
    apotheek_id = request.GET.get("apotheek")
    qs = STSHalfje.objects.select_related("item_gehalveerd", "item_alternatief", "apotheek").order_by("-created_at")

    if apotheek_id and apotheek_id.isdigit():
        apotheek = Organization.objects.filter(pk=int(apotheek_id)).first()
        qs = qs.filter(apotheek_id=int(apotheek_id))

    contact_email = "baxterezorg@apotheekjansen.com"

    context = {
        "items": qs,
        "apotheek": apotheek,  # kan None zijn
        "generated_at": timezone.localtime(timezone.now()),
        "logo_path": _static_abs_path("img/app_icon-1024x1024.png"),
        "signature_path": _static_abs_path("img/handtekening_apotheker.png"),
        "contact_email": contact_email,
    }

    html = render_to_string(
        "stshalfjes/pdf/onnodig_gehalveerde_geneesmiddelen.html",
        context,
        request=request,
    )

    pdf_file = _render_pdf(html, base_url=request.build_absolute_uri("/"))

    filename = f"Onnodig_gehalveerde_geneesmiddelen_{timezone.now().strftime('%d-%m-%Y')}.pdf"
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'  # opent direct
    return response


@login_required
def email_stshalfjes_pdf(request):
    """
    Start celery: verstuurt per geselecteerde apotheek alleen de items van die apotheek.
    """
    if not can(request.user, "can_send_baxter_sts_halfjes"):
        return HttpResponseForbidden("Geen toegang.")

    if request.method == "POST":
        org_ids = request.POST.getlist("recipients")
        org_ids = [int(i) for i in org_ids if str(i).isdigit()]

        if not org_ids:
            messages.warning(request, "Geen ontvangers geselecteerd.")
            return redirect("stshalfjes")

        send_stshalfjes_pdf_task.delay(org_ids)
        messages.success(request, f"De PDF wordt op de achtergrond verstuurd naar {len(org_ids)} ontvangers.")
        return redirect("stshalfjes")

    return redirect("stshalfjes")