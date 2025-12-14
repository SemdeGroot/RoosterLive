import io
import pandas as pd
from pathlib import Path
from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse

from ..forms import AvailabilityUploadForm
# Zorg dat je de nieuwe helpers hier import:
from ._helpers import can, save_voorraad_to_db, get_voorraad_rows

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
                    
                    # === CSV PARSING (Robuust voor NL/EN en Encodings) ===
                    if ext == '.csv':
                        # 1. Lees ruwe bytes
                        content = f.read()
                        
                        # 2. Probeer te decoderen naar string
                        # utf-8-sig stript de BOM (Byte Order Mark) die Excel vaak toevoegt
                        # latin-1 is een fallback voor oudere Windows bestanden
                        try:
                            text_content = content.decode('utf-8-sig')
                        except UnicodeDecodeError:
                            text_content = content.decode('latin-1')
                        
                        # 3. Lees in met Pandas
                        # sep=None: laat Python ruiken of het ; of , is
                        # engine='python': is nodig voor sep=None
                        # dtype=str: FORCEER tekst. Dit voorkomt dat 00123 -> 123 wordt, of 10 -> 10.0
                        df = pd.read_csv(
                            io.StringIO(text_content), 
                            sep=None, 
                            engine='python', 
                            dtype=str
                        )
                    
                    # === EXCEL PARSING ===
                    else:
                        # Excel bevat binaire data, mag direct als bytes erin
                        # dtype=str: ook hier alles als tekst houden
                        df = pd.read_excel(f, dtype=str)

                    # === OPSCHONEN ===
                    # Vervang NaN (lege cellen) door lege strings, anders crasht de template of DB soms
                    df = df.fillna("")
                    
                    # Kolomnamen en waarden strippen van spaties (optioneel, maar wel netjes)
                    df.columns = df.columns.astype(str).str.strip()
                    # Pas op: onderstaande regel kan traag zijn bij >100k rijen, maar bij 1000 is het prima
                    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

                    # Opslaan
                    save_voorraad_to_db(df)
                    messages.success(request, f"Bestand verwerkt: {len(df)} regels opgeslagen.")
                    
                except Exception as e:
                    messages.error(request, f"Fout bij verwerken: {e}")

    # Data ophalen (Alles laden voor snelle frontend filter)
    columns, rows = get_voorraad_rows(limit=None)

    ctx = {
        "form": form,
        "columns": columns,
        "rows": rows,
        "title": "Voorraad",
        "has_data": len(columns) > 0,
    }
    return render(request, "voorraad/index.html", ctx)

# --- API ENDPOINT (voor je andere views/lookup tool) ---
@login_required
def medications_search_api(request):
    """
    Geeft JSON terug. Gebruik: /voorraad/api/?q=123456
    """
    if not can(request.user, "can_view_av_medications"):
        return JsonResponse({"error": "Forbidden"}, status=403)

    query = request.GET.get('q', '').strip()
    # Zoek in DB, max 50 resultaten voor de API om het licht te houden
    columns, rows = get_voorraad_rows(query=query, limit=50)

    # Zet rijen om naar dictionaries voor makkelijk gebruik in JSON
    results = []
    for row in rows:
        # zip maakt een dict: {'ZI': 123, 'Naam': 'Para...', ...}
        results.append(dict(zip(columns, row)))

    return JsonResponse({
        "columns": columns,
        "results": results,
        "count": len(results)
    })