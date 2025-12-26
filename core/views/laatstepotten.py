from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

# Helpers en Models
from core.models import LaatstePot, VoorraadItem
# Let op: ik ga ervan uit dat je de form hebt toegevoegd aan core/forms.py
from core.forms import LaatstePotForm
from core.views._helpers import can

# Celery task voor de pushmeldingen
from core.tasks import send_laatste_pot_push_task, send_laatste_pot_email_task

@login_required
def laatstepotten(request):
    """
    Beheert het overzicht, toevoegen en verwijderen van 'Laatste Potten'.
    Stuurt een pushmelding naar bestellers bij een nieuwe invoer.
    """
    # 1. Permissie controle
    if not can(request.user, "can_view_baxter_laatste_potten"):
        return HttpResponseForbidden("Je hebt geen rechten om deze pagina te bekijken.")
    
    can_edit = can(request.user, "can_edit_baxter_laatste_potten")

    # 2. POST Logica (Toevoegen, Aanpassen, Verwijderen)
    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("Je hebt geen rechten om wijzigingen door te voeren.")

        # VERWIJDEREN
        if "btn_delete" in request.POST:
            item_id = request.POST.get("item_id")
            item = get_object_or_404(LaatstePot, id=item_id)
            item.delete()
            messages.success(request, "Melding succesvol verwijderd.")
            return redirect('laatstepotten')

        # AANPASSEN (Edit)
        elif "btn_edit" in request.POST:
            item_id = request.POST.get("item_id")
            instance = get_object_or_404(LaatstePot, id=item_id)
            form = LaatstePotForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, "Wijziging opgeslagen.")
                return redirect('laatstepotten')
            else:
                messages.error(request, "Er ging iets mis bij het aanpassen.")

        # TOEVOEGEN
        elif "btn_add" in request.POST:
            form = LaatstePotForm(request.POST)
            if form.is_valid():
                new_item = form.save()
                item_naam = new_item.voorraad_item.naam
                
                # 1. Trigger Push Melding
                send_laatste_pot_push_task.delay(item_naam)
                
                # 2. Trigger Email Melding (Nieuw)
                send_laatste_pot_email_task.delay(item_naam)
                
                messages.success(request, f"Melding opgeslagen. Bestellers zijn per push en e-mail geïnformeerd.")
                return redirect('laatste_potten')
            else:
                messages.error(request, "Controleer de invoer van het formulier.")

    # 3. GET Logica (Data ophalen)
    # We gebruiken select_related om het aantal database queries te beperken (voorraad_item info)
    items = LaatstePot.objects.select_related('voorraad_item').all()
    form = LaatstePotForm()

    context = {
        "title": "Laatste Potten",
        "items": items,
        "form": form,
        "can_edit": can_edit,
    }

    return render(request, "laatstepotten/index.html", context)