from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET
from django.http import HttpResponseForbidden, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone

# Imports van jouw helpers, forms en models
from core.views._helpers import can
from core.tiles import build_tiles
from core.forms import MedicatieReviewForm
from core.models import MedicatieReviewAfdeling, MedicatieReviewPatient, MedicatieReviewComment
from core.services.medicatiereview_api import call_review_api
from core.utils.medication import group_meds_by_jansen

# --- HELPER FUNCTIE (Voor JSON API) ---
def format_dutch_user_name(user):
    """
    Zet een User object om naar een string: 'Voornaam Achternaam'.
    Eerste letter hoofdletter. Dit doet hetzelfde als je template tag,
    maar dan binnen Python voor de JSON response.
    """
    if not user:
        return "-"
    
    # Probeer first + last name, anders username
    full_name = f"{user.first_name} {user.last_name}".strip()
    if not full_name:
        return user.username

    parts = full_name.split()
    if not parts:
        return full_name
        
    # Eerste woord Hoofdletter
    parts[0] = parts[0].capitalize()
    # Laatste woord Hoofdletter (indien aanwezig)
    if len(parts) > 1:
        parts[-1] = parts[-1].capitalize()
        
    return " ".join(parts)

# --- STANDAARD LIST VIEW (Server-side rendered) ---
@login_required
def review_list(request):
    """
    Toont de pagina met standaard de EERSTE 10 items al ingeladen.
    Dit voorkomt 'layout shift' en is sneller.
    """
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden("Geen toegang.")
    
    # 1. Afdelingen (Eerste 10, gesorteerd op laatst gewijzigd)
    qs_afd = MedicatieReviewAfdeling.objects.all().select_related('created_by', 'updated_by')
    qs_afd = qs_afd.order_by('-updated_at')
    
    paginator_afd = Paginator(qs_afd, 10)
    afdelingen_page = paginator_afd.get_page(1) # We laden initieel altijd pagina 1

    # 2. Patiënten (Eerste 10, gesorteerd op laatst gewijzigd)
    qs_pat = MedicatieReviewPatient.objects.all().select_related('afdeling', 'created_by', 'updated_by')
    qs_pat = qs_pat.order_by('-updated_at')
    
    paginator_pat = Paginator(qs_pat, 10)
    patienten_page = paginator_pat.get_page(1) # We laden initieel altijd pagina 1

    return render(request, "medicatiebeoordeling/list.html", {
        "afdelingen_page": afdelingen_page,
        "patienten_page": patienten_page
    })

# --- AJAX API VIEW ---
@login_required
@require_GET
def review_search_api(request):
    """
    API endpoint voor AJAX search & load more.
    Geeft JSON terug met geformatteerde data.
    Handelt encryptie af door memory-optimized Python search.
    """
    search_type = request.GET.get('type') # 'afdeling' of 'patient'
    query = request.GET.get('q', '').strip().lower()
    page_number = int(request.GET.get('page', 1))
    
    data = []
    has_next = False
    next_page_num = None

    # =========================================================
    # 1. AFDELINGEN (Niet encrypted -> Database search)
    # =========================================================
    if search_type == 'afdeling':
        qs = MedicatieReviewAfdeling.objects.all().select_related('created_by', 'updated_by')
        
        if query:
            qs = qs.filter(afdeling__icontains=query)
        
        qs = qs.order_by('-updated_at')
        
        paginator = Paginator(qs, 10)
        page_obj = paginator.get_page(page_number)
        
        has_next = page_obj.has_next()
        if has_next:
            next_page_num = page_obj.next_page_number()
        
        for afd in page_obj:
            # Tijdzone conversie
            raw_date = afd.updated_at if afd.updated_at else afd.created_at
            local_date = timezone.localtime(raw_date)
            
            show_user = afd.updated_by if afd.updated_by else afd.created_by
            
            data.append({
                'id': afd.pk,
                'naam': afd.afdeling,
                'datum': local_date.strftime('%d-%m-%Y %H:%M'),
                'door': format_dutch_user_name(show_user),
                'detail_url': f"/medicatiebeoordeling/afdeling/{afd.pk}/"
            })

    # =========================================================
    # 2. PATIENTEN (Encrypted -> Python search + Memory Opt.)
    # =========================================================
    elif search_type == 'patient':
        # STAP A: OPTIMALISATIE
        # We halen ALLEEN de velden op die we nodig hebben voor de lijst en het zoeken.
        # De zware 'analysis_data' JSON wordt NIET ingeladen. Dit bespaart enorm veel RAM.
        all_patients = MedicatieReviewPatient.objects.only(
            'id', 'naam', 'geboortedatum', 'afdeling', 
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ).select_related('afdeling', 'created_by', 'updated_by').order_by('-updated_at')
        
        filtered_results = []

        # STAP B: Zoeken in Python (Decryptie vindt hier plaats)
        if query:
            for pat in all_patients:
                # 1. Check Naam
                if query in pat.naam.lower():
                    filtered_results.append(pat)
                    continue 

                # 2. Check Geboortedatum
                if pat.geboortedatum:
                    if query in pat.geboortedatum.strftime('%d-%m-%Y'):
                        filtered_results.append(pat)
        else:
            # Geen zoekterm? Dan tonen we gewoon alles (Paginator pakt dit op)
            filtered_results = all_patients

        # STAP C: Paginatie
        paginator = Paginator(filtered_results, 10)
        page_obj = paginator.get_page(page_number)
        
        has_next = page_obj.has_next()
        if has_next:
            next_page_num = page_obj.next_page_number()
        
        for pat in page_obj:
            # Tijdzone conversie
            raw_date = pat.updated_at if pat.updated_at else pat.created_at
            local_date = timezone.localtime(raw_date)
            
            show_user = pat.updated_by if pat.updated_by else pat.created_by
            geb_datum = pat.geboortedatum.strftime('%d-%m-%Y') if pat.geboortedatum else "-"
            
            data.append({
                'id': pat.pk,
                'naam': pat.naam,
                'geboortedatum': geb_datum,
                'afdeling': pat.afdeling.afdeling,
                'datum': local_date.strftime('%d-%m-%Y %H:%M'),
                'door': format_dutch_user_name(show_user),
                'detail_url': f"/medicatiebeoordeling/patient/{pat.pk}/"
            })

    return JsonResponse({
        'results': data,
        'has_next': has_next,
        'next_page': next_page_num
    })

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
                    created_by=request.user,
                    updated_by=request.user
                )

                # 3. Opslaan Patiënten
                patients_data = result.get("data", [])
                new_patients = []
                for p_data in patients_data:
                    new_patients.append(MedicatieReviewPatient(
                        afdeling=afdeling_obj,
                        naam=p_data.get("naam", "Onbekend"),
                        geboortedatum=p_data.get("geboortedatum"),
                        analysis_data=p_data,
                        created_by=request.user,
                        updated_by=request.user
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

        # 1. Loop door de comments en sla ze op
        # We houden bij of er iets is gebeurd, al is dat bij een save-knop altijd 'waar'
        for group_id, group_data in grouped_meds:
            form_key = f"comment_{group_id}"
            if form_key in request.POST:
                tekst = request.POST.get(form_key, "").strip()
                MedicatieReviewComment.objects.update_or_create(
                    patient=patient,
                    jansen_group_id=group_id,
                    defaults={"tekst": tekst, "updated_by": request.user}
                )
        
        # 2. UPDATE DE PATIËNT (De fix)
        # Door save() aan te roepen, wordt updated_at automatisch op nu() gezet
        patient.updated_by = request.user
        patient.save()

        # 3. UPDATE DE AFDELING (De fix voor de parent)
        # Zodat de afdeling ook bovenaan komt te staan in de lijst met 'laatst gewijzigd'
        afdeling = patient.afdeling
        afdeling.updated_by = request.user
        afdeling.save()

        messages.success(request, "Opmerkingen opgeslagen.")
        return redirect("medicatiebeoordeling_patient_detail", pk=pk)

    # --- GET ---
    
    # 2. Haal bestaande comments op
    db_comments = patient.comments.all()
    comments_lookup = {c.jansen_group_id: c.tekst for c in db_comments}

    # 3. Injecteer Standaardvragen in lege comments
    med_to_group = {}
    for gid, gdata in grouped_meds:
        for m in gdata['meds']:
            med_to_group[m['clean']] = gid

    for vraag_item in vragen:
        middelen_str = vraag_item.get("betrokken_middelen", "")
        if not middelen_str: continue
        
        target_group_id = None
        for med_naam, gid in med_to_group.items():
            if med_naam in middelen_str:
                target_group_id = gid
                break
        
        if target_group_id:
            huidige_tekst = comments_lookup.get(target_group_id, "")
            vraag_tekst = f"❓ {vraag_item['vraag']}"
            
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