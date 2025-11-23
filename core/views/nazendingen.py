# core/views/nazendingen.py
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.core.files.storage import default_storage

from ._helpers import (
    can,
    NAZENDINGEN_DIR,
    CACHE_NAZENDINGEN_DIR,
    render_pdf_to_cache,
    clear_dir,
    save_pdf_upload_with_hash,
    _media_relpath,
)

@login_required
def nazendingen_view(request):
    if not can(request.user, "can_view_av_nazendingen"):
        return HttpResponseForbidden("Geen toegang.")

    key = "nazendingen"
    cache_root = CACHE_NAZENDINGEN_DIR
    cache_root.mkdir(parents=True, exist_ok=True)

    if request.method == "POST":
        if not can(request.user, "can_upload_nazendingen"):
            return HttpResponseForbidden("Geen uploadrechten.")
        f = request.FILES.get("file")
        if not f or not str(f.name).lower().endswith(".pdf"):
            messages.error(request, "Alleen PDF toegestaan.")
            return redirect(request.path)

        save_pdf_upload_with_hash(
            uploaded_file=f,
            target_dir=NAZENDINGEN_DIR,
            base_name=key,
            clear_existing=True,
        )

        clear_dir(cache_root)
        messages.success(request, f"PDF geüpload: {f.name}")
        return redirect(request.path)

    pdf_bytes = None

    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        # DEV: nazendingen.<hash>.pdf of legacy nazendingen.pdf lokaal
        pdf_path = None
        candidates = sorted(NAZENDINGEN_DIR.glob(f"{key}.*.pdf"))
        if candidates:
            pdf_path = candidates[-1]
        else:
            legacy = NAZENDINGEN_DIR / f"{key}.pdf"
            if legacy.exists():
                pdf_path = legacy

        if pdf_path and pdf_path.exists():
            pdf_bytes = pdf_path.read_bytes()
    else:
        # PROD: S3
        rel_dir = _media_relpath(NAZENDINGEN_DIR)  # "nazendingen"
        try:
            _dirs, files = default_storage.listdir(rel_dir)
        except FileNotFoundError:
            files = []

        pdf_storage_path = None
        hashed = sorted(
            name for name in files
            if name.startswith(f"{key}.") and name.endswith(".pdf")
        )
        if hashed:
            pdf_storage_path = f"{rel_dir}/{hashed[-1]}"
        else:
            legacy_name = f"{key}.pdf"
            if legacy_name in files:
                pdf_storage_path = f"{rel_dir}/{legacy_name}"

        if pdf_storage_path and default_storage.exists(pdf_storage_path):
            with default_storage.open(pdf_storage_path, "rb") as f:
                pdf_bytes = f.read()

    if not pdf_bytes:
        return render(request, "nazendingen/index.html", {
            "title": "Nazendingen",
            "no_nazending": True,
            "page_urls": [],
        })

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