import uuid
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from core.utils.review_logic import (
    get_review_settings_json, 
    save_review_settings_json, 
    search_atc_icpc,
    hydrate_criteria_with_descriptions
)
from core.views._helpers import can

@login_required
@require_GET
def atc_lookup(request):
    """
    AJAX endpoint.
    ?q=...&len=1 (optioneel)
    """
    query = request.GET.get('q', '')
    length = request.GET.get('len') 
    
    # FIX: Als lengte is opgegeven (bv 1 of 3), mogen we ook lege queries toelaten 
    # zodat de gebruiker direct een lijst (A, B, C...) ziet bij openen.
    if not length and len(query) < 2:
        return JsonResponse({'results': []})
        
    results = search_atc_icpc(query, search_type='ATC', length=length)
    return JsonResponse({'results': results})

@login_required
def standaardvragen(request):
    if not (can(request.user, "can_view_medicatiebeoordeling") or can(request.user, "can_perform_medicatiebeoordeling")):
        return HttpResponseForbidden("Geen toegang.")
    if request.method == 'POST':
        new_data = {"version": "3.0", "criteria": []}
        question_indices = request.POST.getlist('row_index') 
        
        for q_idx in question_indices:
            # ID wordt nu hidden meegegeven, of gegenereerd als fallback
            q_id = request.POST.get(f'id_field_{q_idx}') or str(uuid.uuid4())[:8]

            title = request.POST.get(f'title_{q_idx}')
            category = request.POST.get(f'category_{q_idx}')     
            subcategory = request.POST.get(f'subcategory_{q_idx}') 
            desc = request.POST.get(f'description_{q_idx}')
            amin = request.POST.get(f'age_min_{q_idx}')
            
            primary_triggers = request.POST.getlist(f'primary_triggers_{q_idx}')

            logic_rules = []
            rule_indices = request.POST.getlist(f'rule_indices_{q_idx}')
            for r_idx in rule_indices:
                operator = request.POST.get(f'rule_operator_{q_idx}_{r_idx}')
                codes = request.POST.getlist(f'rule_codes_{q_idx}_{r_idx}')
                
                # Sla ook lege regels op als placeholders (zoals gevraagd in UI logica)
                # of filter ze hier als je geen lege regels in DB wilt. 
                # Voor nu slaan we ze op zodat de structuur behouden blijft.
                logic_rules.append({
                    "type": "ATC",
                    "boolean_operator": operator,
                    "trigger_codes": codes
                })

            new_data['criteria'].append({
                "definition": {
                    "id": q_id,
                    "title": title,
                    "category_atc_code": category, 
                    "subcategory_atc_code": subcategory,
                    "description": desc,
                },
                "activation": { "primary_triggers": primary_triggers },
                "logic_rules": logic_rules,
                "filters": {
                    "age_min": int(amin) if amin and amin.isdigit() else None,
                    "egfr_max": None
                }
            })

        save_review_settings_json(new_data)
        return redirect('standaardvragen_settings')

    # GET
    data = get_review_settings_json()
    return render(request, "medicatiebeoordeling/settings/standaardvragen.html", {
        "criteria": hydrate_criteria_with_descriptions(data.get('criteria', []))
    })