# core/views/availability.py
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect

from ..forms import AvailabilityUploadForm
from ._helpers import (
    can, logo_url, AV_DIR, CACHE_AVAIL_DIR,
    read_table, filter_and_limit, render_pdf_to_cache, clear_dir
)

@login_required
def availability_home(request):
    if not can(request.user, "can_access_availability"):
        return HttpResponseForbidden("Geen toegang.")
    subtiles = []
    if can(request.user, "can_view_av_medications"):
        subtiles.append({"name": "Voorraad", "img": "medicijn_zoeken.png", "url_name": "availability_medications"})
    if can(request.user, "can_view_av_nazendingen"):
        subtiles.append({"name": "Nazendingen", "img": "nazendingen.png", "url_name": "availability_nazendingen"})
    return render(request, "availability/home.html", {"tiles": subtiles, "logo_url": logo_url()})

def _availability_table_view(request, key: str, page_title: str, can_view_perm: str):
    if not can(request.user, "can_access_availability") or not can(request.user, can_view_perm):
        return HttpResponseForbidden("Geen toegang.")

    existing_path = None
    for ext in (".xlsx", ".xls", ".csv"):
        c = AV_DIR / f"{key}{ext}"
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
                messages.error(request, "Alleen CSV of Excel (XLSX/XLS) toegestaan.")
                return redirect(request.path)

            for oldext in (".xlsx", ".xls", ".csv"):
                p = AV_DIR / f"{key}{oldext}"
                if p.exists():
                    p.unlink()

            dest = AV_DIR / f"{key}{ext}"
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
        "logo_url": logo_url(),
        "form": form,
        "has_file": existing_path is not None,
        "file_name": existing_path.name if existing_path else None,
        "columns": columns,
        "rows": rows,
        "title": page_title,
    }
    return render(request, f"availability/{key}.html", ctx)

@login_required
def availability_medications(request):
    return _availability_table_view(request, "medications", "Voorraad", "can_view_av_medications")

@login_required
def _availability_pdf_view(request, key: str, page_title: str, can_view_perm: str):
    if not can(request.user, "can_access_availability") or not can(request.user, can_view_perm):
        return HttpResponseForbidden("Geen toegang.")

    pdf_path = AV_DIR / f"{key}.pdf"
    cache_root = CACHE_AVAIL_DIR / key
    cache_root.mkdir(parents=True, exist_ok=True)

    if request.method == "POST":
        if not can(request.user, "can_upload_nazendingen"):
            return HttpResponseForbidden("Geen uploadrechten.")
        f = request.FILES.get("file")
        if not f or not str(f.name).lower().endswith(".pdf"):
            messages.error(request, "Alleen PDF-bestanden toegestaan.")
            return redirect(request.path)

        with pdf_path.open("wb") as fh:
            for chunk in f.chunks():
                fh.write(chunk)

        clear_dir(cache_root)
        messages.success(request, f"PDF geüpload: {f.name}")
        return redirect(request.path)

    if not pdf_path.exists():
        return render(request, f"availability/{key}.html", {
            "logo_url": logo_url(),
            "title": page_title,
            "no_nazending": True,
            "page_urls": [],
        })

    pdf_bytes = pdf_path.read_bytes()
    h, n = render_pdf_to_cache(pdf_bytes, zoom=2.0, cache_root=cache_root)
    page_urls = [
        f"{settings.MEDIA_URL}cache/availability/{key}/{h}/page_{i:03d}.png"
        for i in range(1, n+1)
    ]

    return render(request, f"availability/{key}.html", {
        "logo_url": logo_url(),
        "title": page_title,
        "no_nazending": False,
        "page_urls": page_urls,
    })

@login_required
def availability_nazendingen(request):
    return _availability_pdf_view(request, "nazendingen", "Nazendingen", "can_view_av_nazendingen")
