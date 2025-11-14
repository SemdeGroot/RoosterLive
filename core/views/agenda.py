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
    clear_dir, render_pdf_to_cache,
    save_pdf_upload_with_hash
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

        # Cache leegmaken (nieuwe images forceren)
        clear_dir(CACHE_AGENDA_DIR)

        # PDF opslaan als agenda.<hash>.pdf, in deze view altijd 1 actief bestand
        save_pdf_upload_with_hash(
            uploaded_file=f,
            target_dir=AGENDA_DIR,
            base_name="agenda",
            clear_existing=True,
        )

        messages.success(request, "Agenda geüpload.")
        return redirect("agenda")

    context = { "year": datetime.now().year }

    # Zoek eerst een gehashte agenda.<hash>.pdf, anders fallback naar legacy agenda.pdf
    pdf_path = None
    candidates = sorted(AGENDA_DIR.glob("agenda.*.pdf"))
    if candidates:
        pdf_path = candidates[-1]  # nieuwste / enige
    elif AGENDA_FILE.exists():
        pdf_path = AGENDA_FILE

    if not pdf_path or not pdf_path.exists():
        context["page_urls"] = []
        context["no_agenda"] = True
        return render(request, "agenda/index.html", context)

    pdf_bytes = pdf_path.read_bytes()
    h, n = render_pdf_to_cache(pdf_bytes, dpi=300, cache_root=CACHE_AGENDA_DIR)
    context["page_urls"] = [
        f"{settings.MEDIA_URL}cache/agenda/{h}/page_{i:03d}.png" for i in range(1, n + 1)
    ]
    return render(request, "agenda/index.html", context)
