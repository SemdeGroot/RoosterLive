import io
import pandas as pd
from pathlib import Path
from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db import transaction

# Pas de imports aan naar jouw mappenstructuur
from ..forms import AvailabilityUploadForm
from ..models import VoorraadItem 
from ._helpers import can 

@login_required
def medications_view(request):
    # 1. Check Rechten
    if not can(request.user, "can_view_av_medications"):
        return HttpResponseForbidden("Geen toegang.")

    form = AvailabilityUploadForm()

    # === UPLOAD VERWERKING ===
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
                    
                    # --- A. BESTAND INLEZEN ---
                    if ext == '.csv':
                        content = f.read()
                        try:
                            text_content = content.decode('utf-8-sig')
                        except UnicodeDecodeError:
                            text_content = content.decode('latin-1')
                        
                        # dtype=str is cruciaal om voorloopnullen in ZI te behouden
                        df = pd.read_csv(
                            io.StringIO(text_content), 
                            sep=None, 
                            engine='python', 
                            dtype=str
                        )
                    else:
                        df = pd.read_excel(f, dtype=str)

                    # --- B. OPSCHONEN ---
                    df = df.fillna("")
                    df.columns = df.columns.astype(str).str.strip()
                    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
                    # Strip .0 en ,0 van het einde (Excel artifacten)
                    df = df.replace(r'[,.]0$', '', regex=True)

                    if len(df.columns) < 2:
                        raise ValueError("Het bestand moet minimaal 2 kolommen hebben (ZI-nummer en Naam).")

                    # Lege rijen verwijderen
                    zi_col_raw = df.iloc[:, 0]
                    naam_col_raw = df.iloc[:, 1]
                    is_empty_row = (zi_col_raw == "") & (naam_col_raw == "")
                    df = df[~is_empty_row].reset_index(drop=True)

                    if df.empty:
                        messages.error(request, "Het bestand bevat geen geldige regels.")
                        # Render opnieuw om errors te tonen
                        ctx = {"form": form, "title": "Voorraad", "has_data": False}
                        return render(request, "voorraad/index.html", ctx)

                    # --- C. VALIDATIE ---
                    zi_col = df.iloc[:, 0]

                    # 1. ZI moet 8 cijfers zijn
                    is_valid_zi = zi_col.str.isdigit() & (zi_col.str.len() == 8)
                    if not is_valid_zi.all():
                        error_idx = df[~is_valid_zi].index[0]
                        foute_rij = error_idx + 2 
                        foute_waarde = zi_col.iloc[error_idx]
                        messages.error(request, f"Fout op rij {foute_rij}: '{foute_waarde}' is geen geldig ZI-nummer (moet 8 cijfers zijn).")
                        ctx = {"form": form, "title": "Voorraad", "has_data": False}
                        return render(request, "voorraad/index.html", ctx)

                    # 2. Geen dubbele ZI-nummers in bestand
                    if zi_col.duplicated().any():
                        dubbele = zi_col[zi_col.duplicated()].unique()[0]
                        messages.error(request, f"Validatiefout: ZI-nummer '{dubbele}' komt meerdere keren voor in het bestand.")
                        ctx = {"form": form, "title": "Voorraad", "has_data": False}
                        return render(request, "voorraad/index.html", ctx)

                    # 3. Check medicijnnaam (optioneel, warning)
                    naam_col = df.iloc[:, 1]
                    if not naam_col.str.contains("paracetamol", case=False).any():
                        messages.warning(request, "Let op: Geen 'Paracetamol' gevonden. Weet je zeker dat de kolommen goed staan?")

                    # --- D. SYNC LOGICA (VEILIG OPSLAAN) ---
                    
                    # Set maken van nieuwe ZI's voor latere delete-check
                    file_zi_set = set()

                    # Huidige DB inladen voor snelle lookup
                    existing_items_map = {
                        item.zi_nummer: item 
                        for item in VoorraadItem.objects.all()
                    }

                    to_create = []
                    to_update = []
                    meta_columns = df.columns[2:] 

                    for _, row in df.iterrows():
                        zi = str(row.iloc[0]).strip()
                        naam = row.iloc[1]
                        metadata = dict(zip(meta_columns, row.iloc[2:]))
                        
                        file_zi_set.add(zi)

                        if zi in existing_items_map:
                            # ITEM BESTAAT: Update velden (ID blijft behouden -> Nazending blijft veilig!)
                            item = existing_items_map[zi]
                            # Alleen updaten als er iets gewijzigd is (kleine optimalisatie)
                            if item.naam != naam or item.metadata != metadata:
                                item.naam = naam
                                item.metadata = metadata
                                to_update.append(item)
                        else:
                            # ITEM NIEUW: Toevoegen aan create lijst
                            to_create.append(VoorraadItem(
                                zi_nummer=zi,
                                naam=naam,
                                metadata=metadata
                            ))

                    with transaction.atomic():
                        # 1. Nieuwe items aanmaken
                        if to_create:
                            VoorraadItem.objects.bulk_create(to_create)
                        
                        # 2. Bestaande items updaten
                        if to_update:
                            VoorraadItem.objects.bulk_update(to_update, ['naam', 'metadata'])
                        
                        # 3. Opschonen (Delete items die NIET meer in bestand staan)
                        # Let op: Dit verwijdert items (en hun nazendingen via Cascade) die uit het bestand zijn verdwenen.
                        items_to_delete = VoorraadItem.objects.exclude(zi_nummer__in=file_zi_set)
                        deleted_count, _ = items_to_delete.delete()

                    messages.success(
                        request, 
                        f"Verwerking gereed: {len(to_create)} toegevoegd, {len(to_update)} geüpdatet, {deleted_count} verwijderd."
                    )

                except Exception as e:
                    messages.error(request, f"Fout bij verwerken: {e}")

    # === DATA OPHALEN VOOR TABEL ===
    # We laden alles, client-side pagination/filter kan dit aan tot een paar duizend regels.
    all_items = VoorraadItem.objects.all()
    
    rows = []
    columns = []

    if all_items.exists():
        # Kolommen bepalen obv eerste item
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