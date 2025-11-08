# core/views/agenda.py
from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect

from ._helpers import (
    can,
    AGENDA_DIR, AGENDA_FILE, CACHE_AGENDA_DIR,
    clear_dir, render_pdf_to_cache
)

@login_required
def agenda(request):
    if not can(request.user, "can_view_agenda"):
        return HttpResponseForbidden("Geen toegang tot agenda.")

    if request.method == "POST":
        if not can(request.user, "can_upload_agenda"):
            return HttpResponseForbidden("Geen uploadrechten.")
        f = request.FILES.get("file")
        if not f or not f.name.lower().endswith(".pdf"):
            messages.error(request, "Upload een PDF-bestand (.pdf).")
            return redirect("agenda")

        clear_dir(AGENDA_DIR)
        clear_dir(CACHE_AGENDA_DIR)

        AGENDA_DIR.mkdir(parents=True, exist_ok=True)
        with open(AGENDA_FILE, "wb") as fh:
            for chunk in f.chunks():
                fh.write(chunk)

        messages.success(request, "Agenda geüpload.")
        return redirect("agenda")

    context = { "year": datetime.now().year }
    if not AGENDA_FILE.exists():
        context["page_urls"] = []
        context["no_agenda"] = True
        return render(request, "agenda/index.html", context)

    pdf_bytes = AGENDA_FILE.read_bytes()
    h, n = render_pdf_to_cache(pdf_bytes, dpi=300, cache_root=CACHE_AGENDA_DIR)
    context["page_urls"] = [
        f"{settings.MEDIA_URL}cache/agenda/{h}/page_{i:03d}.png" for i in range(1, n + 1)
    ]
    return render(request, "agenda/index.html", context)
