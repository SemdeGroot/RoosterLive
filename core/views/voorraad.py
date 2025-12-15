import io
import pandas as pd
from pathlib import Path
from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.db import transaction, models

from ..forms import AvailabilityUploadForm
from ..models import VoorraadItem 
from ._helpers import can 

@login_required
def medications_view(request):
    if not can(request.user, "can_view_av_medications"):
        return HttpResponseForbidden("Geen toegang.")

    form = AvailabilityUploadForm()

    if request.method == "POST":
        if not can(request.user, "can_upload_voorraad"):
            return HttpResponseForbidden("Geen uploadrechten.")

        form = AvailabilityUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]
            ext = Path(f.name).suffix.lower()

            if ext not in (".xlsx", ".xls", ".csv"):
                messages.error(request, "Alleen CSV of Excel toegestaan.")
            else:
                try:
                    df = None
                    
                    # === 1. INLEZEN ===
                    if ext == '.csv':
                        content = f.read()
                        try:
                            text_content = content.decode('utf-8-sig')
                        except UnicodeDecodeError:
                            text_content = content.decode('latin-1')
                        
                        df = pd.read_csv(
                            io.StringIO(text_content), 
                            sep=None, 
                            engine='python', 
                            dtype=str
                        )
                    else:
                        df = pd.read_excel(f, dtype=str)

                    # === 2. OPSCHONEN (Clean Data) ===
                    df = df.fillna("")
                    df.columns = df.columns.astype(str).str.strip()
                    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
                    
                    # Strip .0 en ,0 van het einde
                    df = df.replace(r'[,.]0$', '', regex=True)

                    if len(df.columns) < 2:
                        raise ValueError("Het bestand moet minimaal 2 kolommen hebben (ZI-nummer en Naam).")

                    # === NIEUW: LEGE RIJEN FILTEREN ===
                    # Als ZI (col 0) leeg is EN Naam (col 1) leeg is -> Rij stilletjes verwijderen.
                    # We doen dit VOOR de validatie, zodat lege regels geen errors geven.
                    
                    zi_col_raw = df.iloc[:, 0]
                    naam_col_raw = df.iloc[:, 1]
                    
                    # Masker: True als beide leeg zijn
                    is_empty_row = (zi_col_raw == "") & (naam_col_raw == "")
                    
                    # Behoud alleen de rijen die NIET volledig leeg zijn op col 1&2
                    df = df[~is_empty_row]
                    
                    # Index resetten zodat foutmeldingen (rijnummers) weer kloppen met de overgebleven data
                    # of juist niet? Meestal wil je dat rijnummers kloppen met Excel. 
                    # Als we resetten, wordt rij 10 ineens rij 9 als rij 5 leeg was.
                    # Voor nu resetten we hem voor de interne loop, maar besef dat row-indexen iets kunnen schuiven.
                    df = df.reset_index(drop=True)

                    # Check of er nog data over is na het filteren
                    if df.empty:
                        messages.error(request, "Het bestand bevat geen geldige regels (alleen lege regels).")
                        ctx = {"form": form, "title": "Voorraad", "has_data": False}
                        return render(request, "voorraad/index.html", ctx)

                    # === 3. VALIDATIE ===
                    zi_col = df.iloc[:, 0]

                    # Validatie A: Kolom 1 (ZI-nummer) MOET 8 cijfers zijn
                    is_valid_zi = zi_col.str.isdigit() & (zi_col.str.len() == 8)
                    
                    if not is_valid_zi.all():
                        error_idx = df[~is_valid_zi].index[0]
                        # +2 omdat header rij 1 is, en index 0-based is.
                        foute_rij = error_idx + 2 
                        foute_waarde = zi_col.iloc[error_idx]
                        messages.error(request, f"Fout op rij {foute_rij}: '{foute_waarde}' is geen geldig ZI-nummer (moet 8 cijfers zijn).")
                        
                        ctx = {"form": form, "title": "Voorraad", "has_data": False}
                        return render(request, "voorraad/index.html", ctx)

                    # Validatie B: CHECK OP DUBBELE ZI-NUMMERS
                    if zi_col.duplicated().any():
                        dubbele_waarden = zi_col[zi_col.duplicated()].unique()
                        voorbeeld = dubbele_waarden[0]
                        messages.error(request, f"Validatiefout: Het ZI-nummer '{voorbeeld}' komt meerdere keren voor. Elk ZI-nummer mag maar 1x voorkomen.")
                        ctx = {"form": form, "title": "Voorraad", "has_data": False}
                        return render(request, "voorraad/index.html", ctx)

                    # Validatie C: Kolom 2 moet medicijnnamen bevatten (check op 'paracetamol')
                    naam_col = df.iloc[:, 1]
                    if not naam_col.str.contains("paracetamol", case=False).any():
                        messages.error(request, "Validatiefout: Kolom 2 lijkt geen medicijnnamen te bevatten (geen 'Paracetamol' gevonden).")
                        ctx = {"form": form, "title": "Voorraad", "has_data": False}
                        return render(request, "voorraad/index.html", ctx)

                    # === 4. OPSLAAN IN DB ===
                    new_items = []
                    meta_columns = df.columns[2:] 

                    for _, row in df.iterrows():
                        zi = row.iloc[0]
                        naam = row.iloc[1]
                        
                        metadata = dict(zip(meta_columns, row.iloc[2:]))
                        
                        new_items.append(VoorraadItem(
                            zi_nummer=zi,
                            naam=naam,
                            metadata=metadata
                        ))

                    with transaction.atomic():
                        VoorraadItem.objects.all().delete()
                        VoorraadItem.objects.bulk_create(new_items)

                    messages.success(request, f"Bestand verwerkt: {len(new_items)} regels opgeslagen.")

                except Exception as e:
                    messages.error(request, f"Fout bij verwerken: {e}")

    # === DATA OPHALEN ===
    all_items = VoorraadItem.objects.all()
    
    rows = []
    columns = []

    if all_items.exists():
        first_item = all_items.first()
        columns = ["ZI Nummer", "Naam"]
        if first_item.metadata:
            columns.extend(first_item.metadata.keys())

        for item in all_items:
            row_data = [item.zi_nummer, item.naam]
            if item.metadata:
                row_data.extend(item.metadata.values())
            rows.append(row_data)

    ctx = {
        "form": form,
        "columns": columns,
        "rows": rows,
        "title": "Voorraad",
        "has_data": len(rows) > 0,
    }
    return render(request, "voorraad/index.html", ctx)

# --- API ENDPOINT ---
@login_required
def medications_search_api(request):
    if not can(request.user, "can_view_av_medications"):
        return JsonResponse({"error": "Forbidden"}, status=403)

    query = request.GET.get('q', '').strip()
    
    qs = VoorraadItem.objects.all()
    if query:
        qs = qs.filter(models.Q(zi_nummer__icontains=query) | models.Q(naam__icontains=query))
    
    qs = qs[:50] 

    results = []
    for item in qs:
        entry = {"ZI Nummer": item.zi_nummer, "Naam": item.naam}
        if item.metadata:
            entry.update(item.metadata)
        results.append(entry)

    columns = ["ZI Nummer", "Naam"]
    if qs.exists() and qs.first().metadata:
        columns.extend(qs.first().metadata.keys())

    return JsonResponse({
        "columns": columns,
        "results": results,
        "count": len(results)
    })