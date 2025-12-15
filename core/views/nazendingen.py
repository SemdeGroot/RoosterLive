from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.db import models

from ..models import Nazending, VoorraadItem
from ..forms import NazendingForm
from ._helpers import can 

# --- API ---
@login_required
def medications_search_api(request):
    # 1. Beveiliging
    if not can(request.user, "can_view_av_medications"):
        return JsonResponse({"results": []}, status=403)

    query = request.GET.get('q', '').strip()
    
    # 2. Zoek logica (alleen als er getypt is)
    if not query:
        return JsonResponse({"results": []})

    # Zoek in ZI nummer OF Naam, limit op 20 resultaten voor snelheid
    qs = VoorraadItem.objects.filter(
        models.Q(zi_nummer__icontains=query) | models.Q(naam__icontains=query)
    ).values('zi_nummer', 'naam')[:20] 

    results = [
        {
            "id": item['zi_nummer'],              
            "text": f"{item['zi_nummer']} - {item['naam']}" 
        } 
        for item in qs
    ]

    return JsonResponse({"results": results})

# --- PAGE VIEW ---
@login_required
def nazendingen_view(request):
    if not can(request.user, "can_view_av_nazendingen"):
        return HttpResponseForbidden("Geen toegang.")
    
    can_upload = can(request.user, "can_upload_nazendingen")

    if request.method == "POST":
        if not can_upload:
            messages.error(request, "Geen rechten om te wijzigen.")
            return redirect(request.path)

        if "btn_delete_nazending" in request.POST:
            nazending_id = request.POST.get("nazending_id_delete")
            nazending = get_object_or_404(Nazending, id=nazending_id)
            nazending.delete()
            messages.success(request, "Nazending verwijderd.")
            return redirect(request.path)

        elif "btn_edit_nazending" in request.POST:
            instance_id = request.POST.get("nazending_id_edit")
            instance = get_object_or_404(Nazending, id=instance_id)
            form = NazendingForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, "Nazending gewijzigd.")
                return redirect(request.path)

        elif "btn_add_nazending" in request.POST:
            form = NazendingForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Nazending toegevoegd.")
                return redirect(request.path)
    else:
        form = NazendingForm()

    # --- DATA OPHALEN ---
    nazendingen = Nazending.objects.select_related('voorraad_item').order_by('datum')
    
    # LET OP: Ik heb 'voorraad_items = VoorraadItem.objects.all()' HIER WEGGEHAALD.
    # Reden: Je gebruikt nu de API. Als je hier .all() doet, laad je alsnog alles in.
    # Dat maakt je pagina traag.

    context = {
        "title": "Nazendingen",
        "form": form,
        "nazendingen": nazendingen,
        "can_upload": can_upload,
    }

    return render(request, "nazendingen/index.html", context)