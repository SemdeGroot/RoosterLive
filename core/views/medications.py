# core/views/medications.py
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from ..forms import AvailabilityUploadForm
from ._helpers import can, VOORRAAD_DIR, read_table

@login_required
def medications_view(request):
    if not can(request.user, "can_view_av_medications"):
        return HttpResponseForbidden("Geen toegang.")

    key = "medications"
    existing_path = None
    for ext in (".xlsx", ".xls", ".csv"):
        c = VOORRAAD_DIR / f"{key}{ext}"
        if c.exists():
            existing_path = c
            break

    form = AvailabilityUploadForm()
    if request.method == "POST":
        if not can(request.user, "can_upload_voorraad"):
            return HttpResponseForbidden("Geen uploadrechten.")

        form = AvailabilityUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]
            ext = (Path(f.name).suffix or "").lower()
            if ext not in (".xlsx", ".xls", ".csv"):
                messages.error(request, "Alleen CSV of Excel toegestaan.")
                return redirect(request.path)

            for oldext in (".xlsx", ".xls", ".csv"):
                p = VOORRAAD_DIR / f"{key}{oldext}"
                if p.exists():
                    p.unlink()

            dest = VOORRAAD_DIR / f"{key}{ext}"
            with dest.open("wb") as fh:
                for chunk in f.chunks():
                    fh.write(chunk)

            messages.success(request, f"Bestand geüpload: {f.name}")
            return redirect(request.path)

    df, error = None, None
    if existing_path:
        df, error = read_table(existing_path)

    columns, rows = [], None
    if df is not None and error is None:
        columns = [str(c) for c in df.columns]
        rows = df.values.tolist()

    ctx = {
        "form": form,
        "has_file": existing_path is not None,
        "file_name": existing_path.name if existing_path else None,
        "columns": columns,
        "rows": rows,
        "title": "Voorraad",
    }
    return render(request, "voorraad/index.html", ctx)