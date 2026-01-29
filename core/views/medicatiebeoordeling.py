from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.template.loader import render_to_string
from django.db import transaction

# Imports van jouw helpers, forms en models
from core.views._helpers import can, _static_abs_path, _render_pdf
from core.tiles import build_tiles
from core.forms import MedicatieReviewForm, AfdelingEditForm
from core.models import MedicatieReviewAfdeling, MedicatieReviewPatient, MedicatieReviewComment, MedicatieReviewMedGroupOverride
from core.services.medicatiereview_api import call_review_api, sync_standaardvragen_to_db
from core.utils.medication import group_meds_by_jansen, get_jansen_group_choices
from core.decorators import ip_restricted
from core.views.export_review_pdf import _build_patient_block

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

def _patient_key(naam: str, geboortedatum) -> tuple[str, str]:
    naam_clean = (naam or "").strip().lower()
    dob_str = str(geboortedatum) if geboortedatum else "onbekend"
    return naam_clean, dob_str

def _build_history_map_for_patients(patients_qs):
    """
    Zelfde als jouw afdeling-logica, maar works voor 1 of meerdere patiënten.
    Returns: dict[(naam_clean, dob_str, group_id)] = oude_tekst
    """
    history_map = {}
    patients = patients_qs.prefetch_related("comments")
    for old_pat in patients:
        p_naam_clean, p_dob_str = _patient_key(old_pat.naam, old_pat.geboortedatum)

        for comment in old_pat.comments.all():
            content_to_save = comment.tekst or ""
            if content_to_save:
                key = (p_naam_clean, p_dob_str, comment.jansen_group_id)
                history_map[key] = content_to_save
    return history_map

def _restore_history_comments(new_pat, p_data, history_map, user):
    meds = p_data.get("geneesmiddelen", [])
    grouped_meds = group_meds_by_jansen(meds)

    n_naam_clean, n_dob_str = _patient_key(new_pat.naam, new_pat.geboortedatum)

    restored = 0
    for group_id, group_data in grouped_meds:
        key = (n_naam_clean, n_dob_str, group_id)
        if key in history_map:
            MedicatieReviewComment.objects.update_or_create(
                patient=new_pat,
                jansen_group_id=group_id,
                defaults={
                    "historie": history_map[key],
                    "updated_by": user,
                }
            )
            restored += 1
    return restored

def _find_existing_patient_in_afdeling(selected_afdeling, patient_name, patient_dob):
    """
    patient_dob is date object (preferred), or string.
    Vergelijkt gedecrypteerde waarden via Python.
    """
    target_name = (patient_name or "").strip().lower()
    target_dob_str = str(patient_dob) if patient_dob else "onbekend"

    candidates = selected_afdeling.patienten.all().only("id", "naam", "geboortedatum")
    for pat in candidates:
        p_name, p_dob = _patient_key(pat.naam, pat.geboortedatum)
        if p_name == target_name and p_dob == target_dob_str:
            return pat
    return None

# --- STANDAARD LIST VIEW (Server-side rendered) ---
@ip_restricted
@login_required
def review_list(request):
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden("Geen toegang.")
    
    # FILTER AANPASSING: .filter(patienten__isnull=False).distinct()
    # Hierdoor verdwijnen afdelingen uit de lijst zodra ze geen patiënten meer hebben.
    qs_afd = MedicatieReviewAfdeling.objects.filter(patienten__isnull=False).distinct()
    qs_afd = qs_afd.select_related('created_by', 'updated_by')
    qs_afd = qs_afd.order_by('-updated_at', '-id')
    
    paginator_afd = Paginator(qs_afd, 10)
    afdelingen_page = paginator_afd.get_page(1)

    # Patiënten logica blijft hetzelfde...
    qs_pat = MedicatieReviewPatient.objects.all().select_related('afdeling', 'created_by', 'updated_by')
    qs_pat = qs_pat.order_by('-updated_at', '-id')
    
    paginator_pat = Paginator(qs_pat, 10)
    patienten_page = paginator_pat.get_page(1)

    return render(request, "medicatiebeoordeling/list.html", {
        "afdelingen_page": afdelingen_page,
        "patienten_page": patienten_page
    })

# --- AJAX API VIEW ---
@ip_restricted
@login_required
@require_GET
def review_search_api(request):
    search_type = request.GET.get('type')
    query = request.GET.get('q', '').strip().lower()
    page_number = int(request.GET.get('page', 1))
    
    data = []
    has_next = False
    next_page_num = None

    # =========================================================
    # 1. AFDELINGEN
    # =========================================================
    if search_type == 'afdeling':
        # Alleen afdelingen tonen waar patiënten zijn (zelfde als review_list)
        qs = (
            MedicatieReviewAfdeling.objects
            .filter(patienten__isnull=False)
            .distinct()
            .select_related('organisatie', 'created_by', 'updated_by')
        )
        
        if query:
            qs = qs.filter(afdeling__icontains=query)
        
        qs = qs.order_by('-updated_at', '-id')
        
        paginator = Paginator(qs, 10)
        page_obj = paginator.get_page(page_number)
        
        has_next = page_obj.has_next()
        if has_next:
            next_page_num = page_obj.next_page_number()
        
        for afd in page_obj:
            raw_date = afd.updated_at if afd.updated_at else afd.created_at
            local_date = timezone.localtime(raw_date)
            show_user = afd.updated_by if afd.updated_by else afd.created_by

            data.append({
                "id": afd.pk,
                "naam": afd.afdeling,
                "locatie": afd.locatie or "",
                "organisatie": afd.organisatie.name if afd.organisatie else "",
                "datum": local_date.strftime('%d-%m-%Y %H:%M'),
                "door": format_dutch_user_name(show_user),
                "detail_url": f"/medicatiebeoordeling/afdeling/{afd.pk}/",
            })

    # =========================================================
    # 2. PATIENTEN (Encrypted -> Python search + Memory Opt.)
    # =========================================================
    elif search_type == 'patient':
        all_patients = (
            MedicatieReviewPatient.objects.only(
                'id', 'naam', 'geboortedatum', 'afdeling', 
                'created_at', 'updated_at', 'created_by', 'updated_by'
            )
            .select_related('afdeling', 'afdeling__organisatie', 'created_by', 'updated_by')
            .order_by('-updated_at', '-id')
        )
        
        filtered_results = []

        if query:
            for pat in all_patients:
                naam_l = (pat.naam or "").lower()

                # 1. Naam
                if query in naam_l:
                    filtered_results.append(pat)
                    continue 

                # 2. Geboortedatum
                if pat.geboortedatum:
                    if query in pat.geboortedatum.strftime('%d-%m-%Y'):
                        filtered_results.append(pat)
                        continue

                # 3. Afdeling
                if pat.afdeling and pat.afdeling.afdeling:
                    if query in pat.afdeling.afdeling.lower():
                        filtered_results.append(pat)
                        continue

                # 4. Zorginstelling
                org = getattr(pat.afdeling, "organisatie", None)
                if org and org.name and query in org.name.lower():
                    filtered_results.append(pat)
                    continue
        else:
            filtered_results = all_patients

        paginator = Paginator(filtered_results, 10)
        page_obj = paginator.get_page(page_number)
        
        has_next = page_obj.has_next()
        if has_next:
            next_page_num = page_obj.next_page_number()
        
        for pat in page_obj:
            raw_date = pat.updated_at if pat.updated_at else pat.created_at
            local_date = timezone.localtime(raw_date)
            show_user = pat.updated_by if pat.updated_by else pat.created_by

            geb_datum = pat.geboortedatum.strftime('%d-%m-%Y') if pat.geboortedatum else "-"
            afdeling_naam = pat.afdeling.afdeling if pat.afdeling else "-"
            locatie = pat.afdeling.locatie if pat.afdeling and pat.afdeling.locatie else "-"
            organisatie_naam = (
                pat.afdeling.organisatie.name
                if pat.afdeling and getattr(pat.afdeling, "organisatie", None)
                else "-"
            )

            data.append({
                "id": pat.pk,
                "naam": pat.naam,
                "geboortedatum": geb_datum,
                "afdeling": afdeling_naam,
                "locatie": locatie,
                "organisatie": organisatie_naam,
                "datum": local_date.strftime('%d-%m-%Y %H:%M'),
                "door": format_dutch_user_name(show_user),
                "detail_url": f"/medicatiebeoordeling/patient/{pat.pk}/",
            })

    return JsonResponse({
        "results": data,
        "has_next": has_next,
        "next_page": next_page_num,
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

@ip_restricted
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

# 3. AFDELING DELETE VIEW (Alleen patiënten wissen met reviews)
@ip_restricted
@login_required
def clear_afdeling_review(request, pk):
    """
    Wist ALLE patiënten van een afdeling, maar behoudt de afdeling zelf.
    Hierdoor verdwijnt hij uit de lijst (want geen patiënten meer),
    maar blijft beschikbaar in create.html.
    """
    if not can(request.user, "can_perform_medicatiebeoordeling"):
        return HttpResponseForbidden()
    
    if request.method == "POST":
        afd = get_object_or_404(MedicatieReviewAfdeling, pk=pk)
        aantal = afd.patienten.count()
        
        # We verwijderen de patiënten (Cascade regelt comments)
        afd.patienten.all().delete()
        
        messages.success(request, f"Review van '{afd.afdeling}' gewist. ({aantal} patiënten verwijderd).")
        
    return redirect("medicatiebeoordeling_list")

@ip_restricted
@login_required
def review_create(request):
    """
    Formulier om nieuwe review te starten.
    - scope=afdeling: bestaande flow (alles vervangen)
    - scope=patient: vervang alleen 1 patiënt binnen de gekozen afdeling, met behoud van historie
    """
    if not can(request.user, "can_perform_medicatiebeoordeling"):
        return HttpResponseForbidden("Geen rechten om uit te voeren.")

    all_afdelingen = (
        MedicatieReviewAfdeling.objects
        .select_related("organisatie")
        .order_by("afdeling", "organisatie__name")
    )

    review_form = MedicatieReviewForm()

    if request.method == "POST" and "btn_start_review" in request.POST:
        review_form = MedicatieReviewForm(request.POST)

        if review_form.is_valid():
            selected_afdeling = review_form.cleaned_data["afdeling_id"]
            text = review_form.cleaned_data["medimo_text"]
            source = review_form.cleaned_data["source"]
            scope = review_form.cleaned_data["scope"]

            # Single patient inputs: door Form al opgeschoond/gevalideerd
            patient_name = review_form.cleaned_data.get("patient")  # string (getrimd)
            patient_dob = review_form.cleaned_data.get("patient_geboortedatum")  # date object of None

            # --------------------------
            # API CALL
            # --------------------------
            if scope == "patient":
                # geboortedatum altijd aanwezig door form-validatie (maar check safe)
                result, errors = call_review_api(
                    text, source, scope,
                    geboortedatum=patient_dob.isoformat() if patient_dob else None
                )
            else:
                result, errors = call_review_api(text, source, scope)

            if errors:
                for e in errors:
                    messages.error(request, e)
                return render(request, "medicatiebeoordeling/create.html", {
                    "form": review_form,
                    "afdelingen": all_afdelingen,
                })

            if not result:
                messages.error(request, "Geen antwoord van server.")
                return render(request, "medicatiebeoordeling/create.html", {
                    "form": review_form,
                    "afdelingen": all_afdelingen,
                })

            # --------------------------
            # AFDELING MATCH CHECK
            # --------------------------
            parsed_naam = (result.get("afdeling") or "").strip()
            selected_naam = (selected_afdeling.afdeling or "").strip()

            if scope == "afdeling":
                if parsed_naam and parsed_naam.lower() != selected_naam.lower():
                    messages.error(
                        request,
                        f"⚠️ FOUT: Je selecteerde '{selected_naam}', maar de tekst is van '{parsed_naam}'."
                    )
                    return render(request, "medicatiebeoordeling/create.html", {
                        "form": review_form,
                        "afdelingen": all_afdelingen,
                    })

            patients_data = result.get("data", []) or []

            # ==========================
            # 1) SCOPE: AFDELING
            # ==========================
            if scope == "afdeling":
                with transaction.atomic():
                    history_map = {}

                    current_patients = selected_afdeling.patienten.all().prefetch_related("comments")
                    for old_pat in current_patients:
                        p_naam_clean = old_pat.naam.strip().lower()
                        p_dob_str = str(old_pat.geboortedatum) if old_pat.geboortedatum else "onbekend"

                        for comment in old_pat.comments.all():
                            content_to_save = comment.tekst or ""
                            if content_to_save:
                                key = (p_naam_clean, p_dob_str, comment.jansen_group_id)
                                history_map[key] = content_to_save

                    selected_afdeling.patienten.all().delete()
                    selected_afdeling.updated_by = request.user
                    selected_afdeling.save()

                    new_patients_created = 0
                    comments_restored = 0

                    for p_data in patients_data:
                        new_pat = MedicatieReviewPatient.objects.create(
                            afdeling=selected_afdeling,
                            naam=p_data.get("naam", "Onbekend"),
                            geboortedatum=p_data.get("geboortedatum"),
                            analysis_data=p_data,
                            created_by=request.user,
                            updated_by=request.user
                        )
                        new_patients_created += 1
                        new_pat.refresh_from_db()
                        sync_standaardvragen_to_db(new_pat, request.user)

                        n_naam_clean = new_pat.naam.strip().lower()
                        n_dob_str = str(new_pat.geboortedatum) if new_pat.geboortedatum else "onbekend"

                        meds = p_data.get("geneesmiddelen", [])
                        grouped_meds = group_meds_by_jansen(meds)

                        for group_id, group_data in grouped_meds:
                            key = (n_naam_clean, n_dob_str, group_id)
                            if key in history_map:
                                MedicatieReviewComment.objects.update_or_create(
                                    patient=new_pat,
                                    jansen_group_id=group_id,
                                    defaults={
                                        "historie": history_map[key],
                                        "updated_by": request.user,
                                    }
                                )
                                comments_restored += 1

                messages.success(
                    request,
                    f"Analyse geslaagd. {new_patients_created} patiënten verwerkt "
                    f"({comments_restored} x opmerkingen uit historie toegevoegd)."
                )
                return redirect("medicatiebeoordeling_afdeling_detail", pk=selected_afdeling.pk)

            # ==========================
            # 2) SCOPE: PATIENT
            # ==========================
            if scope == "patient":
                if not patients_data:
                    messages.error(request, "Geen patiënt gevonden in response.")
                    return render(request, "medicatiebeoordeling/create.html", {
                        "form": review_form,
                        "afdelingen": all_afdelingen,
                    })

                p_data = patients_data[0]

                # Matching uitsluitend op form-waarden (jouw waarheid)
                match_name = patient_name
                match_dob = patient_dob

                with transaction.atomic():
                    existing = _find_existing_patient_in_afdeling(
                        selected_afdeling,
                        match_name,
                        match_dob
                    )

                    history_map = {}
                    if existing:
                        history_map = _build_history_map_for_patients(
                            MedicatieReviewPatient.objects.filter(pk=existing.pk)
                        )
                        existing.delete()

                    new_pat = MedicatieReviewPatient.objects.create(
                        afdeling=selected_afdeling,
                        naam=match_name,          # altijd uit form
                        geboortedatum=match_dob,  # altijd uit form (date object)
                        analysis_data=p_data,
                        created_by=request.user,
                        updated_by=request.user
                    )
                    sync_standaardvragen_to_db(new_pat, request.user)
                    restored = _restore_history_comments(new_pat, p_data, history_map, request.user)

                    selected_afdeling.updated_by = request.user
                    selected_afdeling.save()

                if existing:
                    messages.success(request, f"Single patient review bijgewerkt. ({restored} x historie toegevoegd).")
                else:
                    messages.success(request, f"Single patient review toegevoegd. ({restored} x historie toegevoegd).")

                return redirect("medicatiebeoordeling_patient_detail", pk=new_pat.pk)

            messages.error(request, "Onbekende scope.")
            return render(request, "medicatiebeoordeling/create.html", {
                "form": review_form,
                "afdelingen": all_afdelingen,
            })

    return render(request, "medicatiebeoordeling/create.html", {
        "form": review_form,
        "afdelingen": all_afdelingen,
    })

@ip_restricted
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

@ip_restricted
@login_required
def patient_detail(request, pk):
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden()

    patient = (
        MedicatieReviewPatient.objects
        .select_related("afdeling")
        .prefetch_related("comments", "med_group_overrides")
        .get(pk=pk)
    )

    analysis = patient.analysis_data or {}
    meds = analysis.get("geneesmiddelen", [])
    vragen = analysis.get("analyses", {}).get("standaardvragen", [])

    # -----------------------------
    # OVERRIDES LOOKUP
    # -----------------------------
    overrides_qs = patient.med_group_overrides.all()
    overrides_lookup = {(o.med_clean or "").strip(): o.target_jansen_group_id for o in overrides_qs}
    override_name_lookup = {(o.med_clean or "").strip(): (o.override_name or "") for o in overrides_qs}

    grouped_meds = group_meds_by_jansen(meds, overrides_lookup=overrides_lookup)

    # --- POST ---
    if request.method == "POST":
        if not can(request.user, "can_perform_medicatiebeoordeling"):
            return HttpResponseForbidden("Alleen bewerken toegestaan.")

        # A) Comments/historie opslaan (jouw bestaande logic)
        for group_id, group_data in grouped_meds:
            key_tekst = f"comment_{group_id}"
            key_historie = f"historie_{group_id}"

            defaults_data = {"updated_by": request.user}

            if key_tekst in request.POST:
                defaults_data["tekst"] = request.POST.get(key_tekst, "").strip()

            if key_historie in request.POST:
                defaults_data["historie"] = request.POST.get(key_historie, "").strip()

            MedicatieReviewComment.objects.update_or_create(
                patient=patient,
                jansen_group_id=group_id,
                defaults=defaults_data
            )

        # B) Overrides opslaan/verwijderen + override_name
        override_updates = 0
        override_deletes = 0

        for key, med_clean in request.POST.items():
            if not key.startswith("override_med_clean__"):
                continue

            suffix = key.replace("override_med_clean__", "", 1)  # "<gid>__<idx>"
            target_key = f"override_target__{suffix}"
            name_key = f"override_name__{suffix}"

            if target_key not in request.POST:
                continue

            med_clean = (med_clean or "").strip()
            raw_target = (request.POST.get(target_key) or "").strip()
            override_name = (request.POST.get(name_key) or "").strip()

            if not med_clean:
                continue

            # empty target = override verwijderen
            if raw_target == "":
                deleted, _ = MedicatieReviewMedGroupOverride.objects.filter(
                    patient=patient,
                    med_clean=med_clean
                ).delete()
                if deleted:
                    override_deletes += 1
                continue

            try:
                target_gid = int(raw_target)
            except ValueError:
                continue

            # 1/2 NOOIT toestaan
            # 50 WEL toestaan (Buiten formularium)
            if target_gid in (1, 2):
                messages.error(request, "Override niet toegestaan naar Vallen? of Malen?.")
                continue

            MedicatieReviewMedGroupOverride.objects.update_or_create(
                patient=patient,
                med_clean=med_clean,
                defaults={
                    "target_jansen_group_id": target_gid,
                    "override_name": override_name,
                    "updated_by": request.user,
                }
            )
            override_updates += 1

        patient.updated_by = request.user
        patient.save()

        if patient.afdeling:
            patient.afdeling.updated_by = request.user
            patient.afdeling.save()

        # Export
        if request.POST.get("action") == "save_export":
            patient = (
                MedicatieReviewPatient.objects
                .select_related("afdeling")
                .prefetch_related("comments", "med_group_overrides")
                .get(pk=patient.pk)
            )
            block = _build_patient_block(patient)

            context = {
                "block": block,
                "prepared_by_user": request.user,
                "prepared_by_email": "instellingen@apotheekjansen.com",
                "generated_at": timezone.localtime(timezone.now()),
                "logo_path": _static_abs_path("img/app_icon-1024x1024.png"),
                "title": "Medicatiebeoordeling",
            }

            html = render_to_string(
                "medicatiebeoordeling/pdf/patient_review_pdf.html",
                context,
                request=request,
            )

            pdf = _render_pdf(html, base_url=request.build_absolute_uri("/"))

            resp = HttpResponse(pdf, content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="medicatiebeoordeling_{patient.naam}.pdf"'
            return resp

        messages.success(request, "Opmerkingen opgeslagen.")
        return redirect("medicatiebeoordeling_patient_detail", pk=pk)

    # --- GET ---
    db_comments = patient.comments.all()
    comments_lookup = {c.jansen_group_id: c for c in db_comments}

    jansen_choices = [(cid, cname) for cid, cname in get_jansen_group_choices() if cid not in (1, 2)]

    return render(request, "medicatiebeoordeling/patient_detail.html", {
        "patient": patient,
        "afdeling": patient.afdeling,
        "analysis": analysis,
        "grouped_meds": grouped_meds,
        "comments_lookup": comments_lookup,
        "jansen_choices": jansen_choices,
        "overrides_lookup": overrides_lookup,
        "override_name_lookup": override_name_lookup,
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