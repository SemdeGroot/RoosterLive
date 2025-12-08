import json
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_GET

from core.tiles import build_tiles

# Importeer helpers
from core.utils.review_logic import (
    get_review_settings_json, 
    save_review_settings_json, 
    search_atc_icpc,
    hydrate_criteria_with_descriptions
)
from core.views._helpers import can

@login_required
def settings_dashboard(request):
    """
    Landingspagina: Toont review settings tiles; voor nu standaardvragen.
    """
    if not (can(request.user, "can_view_medicatiebeoordeling") or can(request.user, "can_perform_medicatiebeoordeling")):
        return HttpResponseForbidden("Geen toegang.")

    tiles = build_tiles(request.user, group="review_settings")
    
    context = {
        "page_title": "Medicatiebeoordeling Instellingen",
        "intro": "Pas de instellingen aan van de medicatiebeoordeling voorbereider",
        "tiles": tiles,
    }
    return render(request, "tiles_page.html", context)

@login_required
@require_GET
def atc_lookup(request):
    """
    AJAX endpoint voor Select2.
    Verwacht ?q=zoekterm
    """
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})
        
    results = search_atc_icpc(query, search_type='ATC')
    return JsonResponse({'results': results})

@login_required
def standaardvragen(request):
    if request.method == 'POST':
        new_data = {"version": "2.0", "criteria": []}
        row_indices = request.POST.getlist('row_index') # Volgorde bepalen
        
        for idx in row_indices:
            # Check of ID wel is ingevuld, anders skippen
            if not request.POST.getlist('id_field'): break 
            
            # We moeten de index van de lijst (titles[i]) matchen met row_index
            # Maar makkelijker is alles ophalen met f'_{idx}' behalve de tekst velden
            # Oplossing: We loopen over Indices en halen daar de data bij op
            
            # OPMERKING: request.POST.getlist('title') geeft lijst van ALLE titels
            # We moeten weten welke titel bij welke idx hoort. 
            # Omdat HTML form arrays op volgorde stuurt, gebruiken we de loop counter
            pass 

        # BETERE LOOP STRATEGIE VOOR DJANGO POST LIJSTEN:
        titles = request.POST.getlist('title')
        ids = request.POST.getlist('id_field')
        descs = request.POST.getlist('description')
        args = request.POST.getlist('argument')
        cats = request.POST.getlist('category')
        
        for i, row_idx in enumerate(row_indices):
            if i >= len(titles): break
            
            # Filters
            amin = request.POST.get(f'age_min_{row_idx}')

            new_data['criteria'].append({
                "id": ids[i],
                "title": titles[i],
                "category": cats[i],
                "description": descs[i],
                "argument": args[i],
                "logic_rules": {
                    "triggers": request.POST.getlist(f'triggers_{row_idx}'),
                    "required_co_medication": request.POST.getlist(f'required_{row_idx}'),
                    "excluded_co_medication": request.POST.getlist(f'excluded_{row_idx}'),
                    "requires_at_least_one_of": request.POST.getlist(f'one_of_{row_idx}')
                },
                "filters": {
                    "age_min": int(amin) if amin and amin.isdigit() else None,
                    "egfr_max": None
                }
            })

        save_review_settings_json(new_data)
        return redirect('standaardvragen_settings')

    # GET logic
    data = get_review_settings_json()
    return render(request, "medicatiebeoordeling/settings/standaardvragen.html", {
        "criteria": hydrate_criteria_with_descriptions(data.get('criteria', []))
    })