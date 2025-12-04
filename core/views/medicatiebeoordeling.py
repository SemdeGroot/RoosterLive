from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib import messages

# Imports van jouw helpers, forms en models
from core.views._helpers import can
from core.tiles import build_tiles
from core.forms import MedicatieReviewForm
from core.models import MedicatieReviewAfdeling, MedicatieReviewPatient, MedicatieReviewComment
from core.services.medicatiereview_api import call_review_api
from core.utils.medication import group_meds_by_jansen

@login_required
def dashboard(request):
    """
    Landingspagina: Toont de tiles (Nieuw, Historie, Instellingen).
    """
    if not (can(request.user, "can_view_medicatiebeoordeling") or can(request.user, "can_perform_medicatiebeoordeling")):
        return HttpResponseForbidden("Geen toegang.")

    tiles = build_tiles(request.user, group="medicatiebeoordeling")
    
    context = {
        "page_title": "Medicatiebeoordeling",
        "intro": "Start een nieuwe analyse, bekijk eerdere resultaten of pas instellingen aan.",
        "tiles": tiles,
    }
    return render(request, "tiles_page.html", context)

# --- DELETE VIEWS ---
@login_required
def delete_afdeling(request, pk):
    if not can(request.user, "can_perform_medicatiebeoordeling"):
        return HttpResponseForbidden()
    
    if request.method == "POST":
        afd = get_object_or_404(MedicatieReviewAfdeling, pk=pk)
        naam = afd.afdeling
        afd.delete()
        messages.success(request, f"Afdeling '{naam}' verwijderd.")
    return redirect("medicatiebeoordeling_list")

@login_required
def delete_patient(request, pk):
    if not can(request.user, "can_perform_medicatiebeoordeling"):
        return HttpResponseForbidden()
    
    if request.method == "POST":
        pat = get_object_or_404(MedicatieReviewPatient, pk=pk)
        afd_pk = pat.afdeling.pk
        naam = pat.naam
        pat.delete()
        messages.success(request, f"Patiënt '{naam}' verwijderd.")
        # Terug naar de afdeling als die nog bestaat, anders lijst
        return redirect("medicatiebeoordeling_afdeling_detail", pk=afd_pk)
    return redirect("medicatiebeoordeling_list")

# --- LIST VIEW ---
@login_required
def review_list(request):
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden("Geen toegang.")
    
    # 1. Afdelingen
    afdelingen = MedicatieReviewAfdeling.objects.all().select_related('created_by')
    
    # 2. Alle Patiënten (voor de patiënt-zoekbalk)
    patienten = MedicatieReviewPatient.objects.all().select_related('afdeling')

    return render(request, "medicatiebeoordeling/list.html", {
        "afdelingen": afdelingen,
        "patienten": patienten
    })

@login_required
def review_create(request):
    """
    Formulier om nieuwe review te starten (API call).
    """
    if not can(request.user, "can_perform_medicatiebeoordeling"):
        return HttpResponseForbidden("Geen rechten om uit te voeren.")

    if request.method == "POST":
        form = MedicatieReviewForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data['medimo_text']
            source = form.cleaned_data['source']
            scope = form.cleaned_data['scope']

            # 1. API Call naar Microservice
            result, errors = call_review_api(text, source, scope)

            if errors:
                for e in errors: messages.error(request, e)
            elif result:
                # 2. Opslaan Afdeling
                afdeling_naam = result.get("afdeling", "Onbekend")
                afdeling_obj = MedicatieReviewAfdeling.objects.create(
                    afdeling=afdeling_naam,
                    bron=source,
                    created_by=request.user
                )

                # 3. Opslaan Patiënten
                patients_data = result.get("data", [])
                new_patients = []
                for p_data in patients_data:
                    new_patients.append(MedicatieReviewPatient(
                        afdeling=afdeling_obj,
                        naam=p_data.get("naam", "Onbekend"),
                        geboortedatum=p_data.get("geboortedatum"), # <--- Opslaan!
                        analysis_data=p_data
                    ))
                
                MedicatieReviewPatient.objects.bulk_create(new_patients)
                
                messages.success(request, f"Analyse klaar! {len(new_patients)} patiënten verwerkt.")
                return redirect("medicatiebeoordeling_afdeling_detail", pk=afdeling_obj.pk)
            else:
                messages.error(request, "Geen antwoord van server.")
    else:
        form = MedicatieReviewForm()

    return render(request, "medicatiebeoordeling/create.html", {"form": form})

@login_required
def afdeling_detail(request, pk):
    """
    Detailpagina van een afdeling: Lijst met patiënten.
    """
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden()
    
    afdeling_obj = get_object_or_404(MedicatieReviewAfdeling, pk=pk)
    patienten = afdeling_obj.patienten.all()
    
    return render(request, "medicatiebeoordeling/afdeling_detail.html", {
        "afdeling": afdeling_obj, 
        "patienten": patienten
    })

@login_required
def patient_detail(request, pk):
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden()

    patient = get_object_or_404(MedicatieReviewPatient, pk=pk)
    analysis = patient.analysis_data 
    meds = analysis.get("geneesmiddelen", [])
    vragen = analysis.get("analyses", {}).get("standaardvragen", [])

    # 1. Groeperen op Jansen ID
    grouped_meds = group_meds_by_jansen(meds)

    # --- POST ---
    if request.method == "POST":
        if not can(request.user, "can_perform_medicatiebeoordeling"):
            return HttpResponseForbidden("Alleen bewerken toegestaan.")

        for group_id, group_data in grouped_meds:
            form_key = f"comment_{group_id}"
            if form_key in request.POST:
                tekst = request.POST.get(form_key, "").strip()
                MedicatieReviewComment.objects.update_or_create(
                    patient=patient,
                    jansen_group_id=group_id,
                    defaults={"tekst": tekst, "updated_by": request.user}
                )
        messages.success(request, "Opmerkingen opgeslagen.")
        return redirect("medicatiebeoordeling_patient_detail", pk=pk)

    # --- GET ---
    
    # 2. Haal bestaande comments op
    db_comments = patient.comments.all()
    comments_lookup = {c.jansen_group_id: c.tekst for c in db_comments}

    # 3. Injecteer Standaardvragen in lege comments
    # We moeten weten welk medicijn in welke groep zit.
    # We maken een map: { "Metoprolol": group_id, ... }
    med_to_group = {}
    for gid, gdata in grouped_meds:
        for m in gdata['meds']:
            # We gebruiken de 'clean' naam uit de analyse
            med_to_group[m['clean']] = gid

    for vraag_item in vragen:
        # vraag_item = { "vraag": "...", "betrokken_middelen": "Metoprolol" }
        middelen_str = vraag_item.get("betrokken_middelen", "")
        if not middelen_str: continue
        
        # Soms zijn het meerdere middelen, gescheiden door komma?
        # Laten we simpel beginnen en kijken of de string voorkomt in onze map keys
        target_group_id = None
        
        # Probeer te matchen
        for med_naam, gid in med_to_group.items():
            if med_naam in middelen_str:
                target_group_id = gid
                break
        
        # Als we een groep hebben gevonden én er is nog geen tekst:
        if target_group_id:
            huidige_tekst = comments_lookup.get(target_group_id, "")
            vraag_tekst = f"❓ {vraag_item['vraag']}"
            
            # Voeg alleen toe als hij er nog niet in staat
            if vraag_tekst not in huidige_tekst:
                if huidige_tekst:
                    comments_lookup[target_group_id] = huidige_tekst + "\n" + vraag_tekst
                else:
                    comments_lookup[target_group_id] = vraag_tekst

    return render(request, "medicatiebeoordeling/patient_detail.html", {
        "patient": patient,
        "afdeling": patient.afdeling,
        "analysis": analysis,
        "grouped_meds": grouped_meds,
        "comments_lookup": comments_lookup
    })

@login_required
def settings_view(request):
    """
    Pagina voor instellingen van de medicatiebeoordeling.
    """
    # Check op permissie: Mag de gebruiker reviews uitvoeren?
    if not can(request.user, "can_perform_medicatiebeoordeling"):
        return HttpResponseForbidden("Je hebt geen toegang tot de instellingen.")
    
    return render(request, "medicatiebeoordeling/settings.html")