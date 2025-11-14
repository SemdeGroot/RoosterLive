# core/views/nazendingen.py
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from ._helpers import (
    can,
    NAZENDINGEN_DIR,
    CACHE_NAZENDINGEN_DIR,
    render_pdf_to_cache,
    clear_dir,
    save_pdf_upload_with_hash,
)

@login_required
def nazendingen_view(request):
    if not can(request.user, "can_view_av_nazendingen"):
        return HttpResponseForbidden("Geen toegang.")

    key = "nazendingen"
    pdf_path = NAZENDINGEN_DIR / f"{key}.pdf"
    cache_root = CACHE_NAZENDINGEN_DIR
    cache_root.mkdir(parents=True, exist_ok=True)

    if request.method == "POST":
        if not can(request.user, "can_upload_nazendingen"):
            return HttpResponseForbidden("Geen uploadrechten.")
        f = request.FILES.get("file")
        if not f or not str(f.name).lower().endswith(".pdf"):
            messages.error(request, "Alleen PDF toegestaan.")
            return redirect(request.path)

        # Nieuwe PDF opslaan als nazendingen.<hash>.pdf (max 1 actief bestand)
        save_pdf_upload_with_hash(
            uploaded_file=f,
            target_dir=NAZENDINGEN_DIR,
            base_name=key,
            clear_existing=True,
        )

        # Cache leegmaken zodat PNG's opnieuw gerenderd worden
        clear_dir(cache_root)
        messages.success(request, f"PDF geüpload: {f.name}")
        return redirect(request.path)

    # Zoek nazendingen.<hash>.pdf, anders legacy nazendingen.pdf
    pdf_path = None
    candidates = sorted(NAZENDINGEN_DIR.glob(f"{key}.*.pdf"))
    if candidates:
        pdf_path = candidates[-1]
    else:
        legacy = NAZENDINGEN_DIR / f"{key}.pdf"
        if legacy.exists():
            pdf_path = legacy

    if not pdf_path or not pdf_path.exists():
        return render(request, "nazendingen/index.html", {
            "title": "Nazendingen",
            "no_nazending": True,
            "page_urls": [],
        })

    pdf_bytes = pdf_path.read_bytes()
    h, n = render_pdf_to_cache(pdf_bytes, dpi=300, cache_root=cache_root)
    page_urls = [
        f"{settings.MEDIA_URL}cache/{key}/{h}/page_{i:03d}.png"
        for i in range(1, n + 1)
    ]

    return render(request, "nazendingen/index.html", {
        "title": "Nazendingen",
        "no_nazending": False,
        "page_urls": page_urls,
    })