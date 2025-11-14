# core/views/policies.py
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect

from ._helpers import (
    can,
    POL_DIR, CACHE_POLICIES_DIR,
    render_pdf_to_cache, hash_from_img_url,
    save_pdf_upload_with_hash,
)

def _delete_policies_by_hash(hash_str: str) -> int:
    removed = 0
    cache_path = (CACHE_POLICIES_DIR / hash_str)
    if cache_path.exists():
        shutil.rmtree(cache_path, ignore_errors=True)
    for pdf_fp in list(POL_DIR.glob("*.pdf")):
        try:
            from ._helpers import pdf_hash
            if pdf_hash(pdf_fp.read_bytes()) == hash_str:
                pdf_fp.unlink(missing_ok=True)
                removed += 1
        except Exception:
            pass
    return removed

@login_required
def policies(request):
    if not can(request.user, "can_view_policies"):
        return HttpResponseForbidden("Geen toegang.")

    # AJAX delete (zoals voorheen)
    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if not can(request.user, "can_upload_werkafspraken"):
            return JsonResponse({"ok": False, "error": "Geen rechten."}, status=403)
        if request.POST.get("action") != "delete":
            return JsonResponse({"ok": False, "error": "Ongeldig verzoek."}, status=400)
        img_url = request.POST.get("img", "")
        h = hash_from_img_url(img_url)
        if not h:
            return JsonResponse({"ok": False, "error": "Ongeldige afbeelding."}, status=400)
        removed = _delete_policies_by_hash(h)
        if removed > 0:
            return JsonResponse({"ok": True, "hash": h, "removed": removed})
        else:
            return JsonResponse({"ok": False, "error": "PDF niet gevonden."}, status=404)

    # Upload (zoals voorheen)
    if request.method == "POST" and "file" in request.FILES:
        if not can(request.user, "can_upload_werkafspraken"):
            return HttpResponseForbidden("Geen uploadrechten.")
        f = request.FILES.get("file")
        if not f or not str(f.name).lower().endswith(".pdf"):
            messages.error(request, "Alleen PDF toegestaan.")
            return redirect("policies")

        # Bewaar werkafspraak als policy.<hash>.pdf (meerdere naast elkaar)
        save_pdf_upload_with_hash(
            uploaded_file=f,
            target_dir=POL_DIR,
            base_name="policy",
            clear_existing=False,   # meerdere werkafspraken
        )
        messages.success(request, f"PDF geüpload: {f.name}")
        return redirect("policies")

    # sorteer op laatst geüpload eerst
    pdf_files = sorted(
        POL_DIR.glob("*.pdf"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    page_urls = []
    for pdf_fp in pdf_files:
        try:
            pdf_bytes = pdf_fp.read_bytes()
        except Exception:
            continue
        h, n = render_pdf_to_cache(pdf_bytes, dpi=300, cache_root=CACHE_POLICIES_DIR)
        for i in range(1, n+1):
            page_urls.append(f"{settings.MEDIA_URL}cache/policies/{h}/page_{i:03d}.png")

    return render(request, "policies/index.html", {
        "page_urls": page_urls,
    })
