# core/views/medications.py
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.core.files.storage import default_storage

from ..forms import AvailabilityUploadForm
from ._helpers import can, VOORRAAD_DIR, read_table, save_table_upload_with_hash

@login_required
def medications_view(request):
    if not can(request.user, "can_view_av_medications"):
        return HttpResponseForbidden("Geen toegang.")

    key = "medications"
    existing_path = None

    # Bestaand bestand zoeken
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        # DEV: lokaal
        for ext in (".xlsx", ".xls", ".csv"):
            matches = sorted(VOORRAAD_DIR.glob(f"{key}.*{ext}"))
            if matches:
                existing_path = matches[-1]
                break

            legacy = VOORRAAD_DIR / f"{key}{ext}"
            if legacy.exists():
                existing_path = legacy
                break
    else:
        # PROD: S3
        rel_dir = "voorraad"
        try:
            _dirs, files = default_storage.listdir(rel_dir)
        except FileNotFoundError:
            files = []

        for ext in (".xlsx", ".xls", ".csv"):
            hashed = sorted(
                name for name in files
                if name.startswith(f"{key}.") and name.endswith(ext)
            )
            if hashed:
                existing_path = f"{rel_dir}/{hashed[-1]}"
                break

            legacy_name = f"{key}{ext}"
            if legacy_name in files:
                existing_path = f"{rel_dir}/{legacy_name}"
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

            try:
                save_table_upload_with_hash(f, VOORRAAD_DIR, key, clear_existing=True)
            except ValueError:
                messages.error(request, "Alleen CSV of Excel toegestaan.")
                return redirect(request.path)

            messages.success(request, f"Bestand geüpload: {f.name}")
            return redirect(request.path)

    df, error = None, None
    if existing_path:
        df, error = read_table(existing_path)

    columns, rows = [], None
    if df is not None and error is None:
        columns = [str(c) for c in df.columns]
        rows = df.values.tolist()

    file_name = None
    if existing_path:
        file_name = Path(str(existing_path)).name  # Path of string → altijd .name

    ctx = {
        "form": form,
        "has_file": existing_path is not None,
        "file_name": file_name,
        "columns": columns,
        "rows": rows,
        "title": "Voorraad",
    }
    return render(request, "voorraad/index.html", ctx)