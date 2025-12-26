from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404

# Helpers en Models
from core.models import STSHalfje
from core.forms import STSHalfjeForm
from core.views._helpers import can

@login_required
def stshalfjes(request):
    """
    Beheert het overzicht van geneesmiddelen die onnodig gehalveerd worden.
    """
    # 1. Permissie controle (Pas de strings aan naar jouw permissie-systeem)
    if not can(request.user, "can_view_sts_halfjes"):
        return HttpResponseForbidden("Je hebt geen rechten om deze pagina te bekijken.")
    
    can_edit = can(request.user, "can_edit_sts_halfjes")

    # 2. POST Logica
    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("Je hebt geen rechten om wijzigingen door te voeren.")

        # VERWIJDEREN
        if "btn_delete" in request.POST:
            item_id = request.POST.get("item_id")
            item = get_object_or_404(STSHalfje, id=item_id)
            item.delete()
            messages.success(request, "Melding succesvol verwijderd.")
            return redirect('stshalfjes')

        # AANPASSEN (Edit)
        elif "btn_edit" in request.POST:
            item_id = request.POST.get("item_id")
            instance = get_object_or_404(STSHalfje, id=item_id)
            form = STSHalfjeForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, "Wijziging opgeslagen.")
                return redirect('stshalfjes')
            else:
                messages.error(request, "Er ging iets mis bij het aanpassen.")

        # TOEVOEGEN
        elif "btn_add" in request.POST:
            form = STSHalfjeForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "STS Halfje succesvol toegevoegd.")
                return redirect('stshalfjes')
            else:
                messages.error(request, "Controleer de invoer van het formulier.")

    # 3. GET Logica
    items = STSHalfje.objects.select_related('item_gehalveerd', 'item_alternatief').all()
    form = STSHalfjeForm()

    context = {
        "title": "STS Halfjes",
        "items": items,
        "form": form,
        "can_edit": can_edit,
    }

    return render(request, "stshalfjes/index.html", context)