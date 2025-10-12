# core/views/roster.py
from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect

from ._helpers import (
    can,
    ROSTER_DIR, ROSTER_FILE, CACHE_ROSTER_DIR,
    clear_dir, render_pdf_to_cache
)

@login_required
def rooster(request):
    if not can(request.user, "can_view_roster"):
        return HttpResponseForbidden("Geen toegang tot rooster.")

    if request.method == "POST":
        if not can(request.user, "can_upload_roster"):
            return HttpResponseForbidden("Geen uploadrechten.")
        f = request.FILES.get("file")
        if not f or not f.name.lower().endswith(".pdf"):
            messages.error(request, "Upload een PDF-bestand (.pdf).")
            return redirect("rooster")

        clear_dir(ROSTER_DIR)
        clear_dir(CACHE_ROSTER_DIR)

        ROSTER_DIR.mkdir(parents=True, exist_ok=True)
        with open(ROSTER_FILE, "wb") as fh:
            for chunk in f.chunks():
                fh.write(chunk)

        messages.success(request, "Rooster geüpload.")
        return redirect("rooster")

    context = { "year": datetime.now().year}
    if not ROSTER_FILE.exists():
        context["page_urls"] = []
        context["no_roster"] = True
        return render(request, "rooster/index.html", context)

    pdf_bytes = ROSTER_FILE.read_bytes()
    h, n = render_pdf_to_cache(pdf_bytes, dpi=200, cache_root=CACHE_ROSTER_DIR)
    context["page_urls"] = [
        f"{settings.MEDIA_URL}cache/rooster/{h}/page_{i:03d}.png" for i in range(1, n + 1)
    ]
    return render(request, "rooster/index.html", context)

@login_required
def upload_roster(request):
    if not can(request.user, "can_upload_roster"):
        return HttpResponseForbidden("Geen uploadrechten.")
    if request.method == "POST":
        f = request.FILES.get("file")
        if not f or not f.name.lower().endswith(".pdf"):
            messages.error(request, "Upload een PDF-bestand.")
            return redirect("upload_roster")

        clear_dir(ROSTER_DIR)
        clear_dir(CACHE_ROSTER_DIR)

        ROSTER_DIR.mkdir(parents=True, exist_ok=True)
        with open(ROSTER_FILE, "wb") as fh:
            for chunk in f.chunks():
                fh.write(chunk)

        messages.success(request, "Rooster geüpload.")
        return redirect("rooster")
    return render(request, "rooster/upload.html")
