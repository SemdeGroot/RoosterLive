from datetime import timedelta, datetime, date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from core.models import LaatstePot, VoorraadItem
from core.forms import LaatstePotForm
from core.views._helpers import can

from core.tasks import send_laatste_pot_push_task, send_laatste_pot_email_task


@login_required
def laatstepotten(request):
    """
    Beheert het overzicht, toevoegen en verwijderen van 'Laatste Potten'.
    Stuurt een pushmelding en e-mail naar bestellers bij een nieuwe invoer.
    Verwijdert automatisch items ouder dan 30 dagen (op basis van created_at).
    """
    # Permissie controle
    if not can(request.user, "can_view_baxter_laatste_potten"):
        return HttpResponseForbidden("Je hebt geen rechten om deze pagina te bekijken.")

    can_edit = can(request.user, "can_edit_baxter_laatste_potten")

    # Automatische opschoning: verwijder items ouder dan 30 dagen
    cutoff = timezone.now() - timedelta(days=30)
    LaatstePot.objects.filter(created_at__lt=cutoff).delete()

    def _get_submitted_date_field_and_value(bound_form):
        # Eerst veelvoorkomende veldnamen proberen
        for fname in ("datum", "date", "datum_tijd", "datetime", "created_at"):
            if fname in bound_form.cleaned_data and bound_form.cleaned_data.get(fname):
                return fname, bound_form.cleaned_data.get(fname)

        # Fallback: eerste datum/datetime-achtige waarde in cleaned_data
        for fname, val in bound_form.cleaned_data.items():
            if isinstance(val, (datetime, date)):
                return fname, val

        return None, None

    def _date_not_older_than_30_days(bound_form):
        submitted_field, submitted_value = _get_submitted_date_field_and_value(bound_form)
        if not submitted_value:
            return True

        # Normaliseer naar aware datetime voor vergelijking
        if isinstance(submitted_value, date) and not isinstance(submitted_value, datetime):
            submitted_dt = datetime.combine(submitted_value, datetime.min.time())
            submitted_dt = timezone.make_aware(submitted_dt, timezone.get_current_timezone())
        else:
            submitted_dt = submitted_value
            if timezone.is_naive(submitted_dt):
                submitted_dt = timezone.make_aware(submitted_dt, timezone.get_current_timezone())

        local_cutoff = timezone.now() - timedelta(days=30)
        if submitted_dt < local_cutoff:
            msg = "De datum mag niet ouder zijn dan 30 dagen."
            if submitted_field:
                bound_form.add_error(submitted_field, msg)
            else:
                bound_form.add_error(None, msg)
            return False

        return True

    form = None

    # POST logica (Toevoegen, Aanpassen, Verwijderen)
    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("Je hebt geen rechten om wijzigingen door te voeren.")

        # Verwijderen
        if "btn_delete" in request.POST:
            item_id = request.POST.get("item_id")
            item = get_object_or_404(LaatstePot, id=item_id)
            item.delete()
            messages.success(request, "Melding succesvol verwijderd.")
            return redirect("laatstepotten")

        # Aanpassen (Edit)
        if "btn_edit" in request.POST:
            item_id = request.POST.get("item_id")
            instance = get_object_or_404(LaatstePot, id=item_id)
            form = LaatstePotForm(request.POST, instance=instance)
            if form.is_valid():
                if not _date_not_older_than_30_days(form):
                    messages.error(request, "De datum mag niet ouder zijn dan 30 dagen.")
                else:
                    form.save()
                    messages.success(request, "Wijziging opgeslagen.")
                    return redirect("laatstepotten")
            else:
                messages.error(request, "Er ging iets mis bij het aanpassen.")

        # Toevoegen
        elif "btn_add" in request.POST:
            form = LaatstePotForm(request.POST)
            if form.is_valid():
                if not _date_not_older_than_30_days(form):
                    messages.error(request, "De datum mag niet ouder zijn dan 30 dagen.")
                else:
                    new_item = form.save()
                    item_naam = new_item.voorraad_item.naam

                    send_laatste_pot_push_task.delay(item_naam)
                    send_laatste_pot_email_task.delay(item_naam)

                    messages.success(
                        request,
                        "Melding opgeslagen. Bestellers zijn per push en e-mail geïnformeerd.",
                    )
                    return redirect("laatstepotten")
            else:
                messages.error(request, "Controleer de invoer van het formulier.")

    # GET logica (Data ophalen)
    items = LaatstePot.objects.select_related("voorraad_item").all()
    if form is None:
        form = LaatstePotForm()

    context = {
        "title": "Laatste Potten",
        "items": items,
        "form": form,
        "can_edit": can_edit,
    }

    return render(request, "laatstepotten/index.html", context)