from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.utils import timezone

from core.views._helpers import can, _static_abs_path, _render_pdf
from core.models import (
    MedicatieReviewAfdeling,
    MedicatieReviewPatient,
    MedicatieReviewComment,
)
from core.utils.medication import group_meds_by_jansen


# =========================
# Datacontainer
# =========================
@dataclass
class PdfPatientBlock:
    patient: MedicatieReviewPatient
    afdeling_naam: str
    grouped_meds: List[Tuple[str, Dict[str, Any]]]
    comments_lookup: Dict[str, MedicatieReviewComment]


# =========================
# Helpers
# =========================

def _build_patient_block(patient: MedicatieReviewPatient) -> PdfPatientBlock:
    """
    Exact dezelfde logica als patient_detail,
    maar zonder analyses renderen.
    """
    analysis = patient.analysis_data or {}
    meds = analysis.get("geneesmiddelen", [])
    vragen = analysis.get("analyses", {}).get("standaardvragen", [])

    grouped_meds = group_meds_by_jansen(meds)

    # Comments ophalen
    db_comments = patient.comments.all()
    comments_lookup: Dict[str, MedicatieReviewComment] = {
        c.jansen_group_id: c for c in db_comments
    }

    # Injecteer standaardvragen
    med_to_group = {}
    for gid, gdata in grouped_meds:
        for m in gdata.get("meds", []):
            med_to_group[m.get("clean")] = gid

    for vraag in vragen:
        middelen = vraag.get("betrokken_middelen", "")
        if not middelen:
            continue

        target_gid = None
        for med, gid in med_to_group.items():
            if med and med in middelen:
                target_gid = gid
                break

        if not target_gid:
            continue

        vraag_tekst = vraag.get("vraag", "").strip()
        if not vraag_tekst:
            continue

        if target_gid in comments_lookup:
            c = comments_lookup[target_gid]
            if vraag_tekst not in (c.tekst or ""):
                c.tekst = (c.tekst + "\n" + vraag_tekst).strip() if c.tekst else vraag_tekst
        else:
            comments_lookup[target_gid] = MedicatieReviewComment(
                patient=patient,
                jansen_group_id=target_gid,
                tekst=vraag_tekst,
                historie=""
            )

    return PdfPatientBlock(
        patient=patient,
        afdeling_naam=patient.afdeling.afdeling if patient.afdeling else "",
        grouped_meds=grouped_meds,
        comments_lookup=comments_lookup,
    )

# =========================
# Views
# =========================
@login_required
def export_patient_review_pdf(request, pk: int) -> HttpResponse:
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden()

    patient = (
        MedicatieReviewPatient.objects
        .select_related("afdeling")
        .prefetch_related("comments")
        .filter(pk=pk)
        .first()
    )
    if not patient:
        raise Http404()

    block = _build_patient_block(patient)

    context = {
        "block": block,
        "prepared_by_user": request.user,
        "prepared_by_email": "instellingen@apotheekjansen.com",
        "generated_at": timezone.localtime(timezone.now()),
        "logo_path": _static_abs_path("img/app_icon-1024x1024.png"),
        "title": "Medicatiebeoordeling",
    }

    html = render_to_string(
        "medicatiebeoordeling/pdf/patient_review_pdf.html",
        context,
        request=request,
    )

    pdf = _render_pdf(html, base_url=request.build_absolute_uri("/"))

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="medicatiebeoordeling_{patient.naam}.pdf"'
    return resp


@login_required
def export_afdeling_review_pdf(request, pk: int) -> HttpResponse:
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden()

    afdeling = MedicatieReviewAfdeling.objects.filter(pk=pk).first()
    if not afdeling:
        raise Http404()

    patienten = (
        afdeling.patienten
        .all()
        .select_related("afdeling")
        .prefetch_related("comments")
        .order_by("naam")
    )

    blocks = [_build_patient_block(p) for p in patienten]

    context = {
        "blocks": blocks,
        "afdeling": afdeling,
        "prepared_by_user": request.user,
        "prepared_by_email": "instellingen@apotheekjansen.com",
        "generated_at": timezone.localtime(timezone.now()),
        "logo_path": _static_abs_path("img/app_icon-1024x1024.png"),
        "title": "Medicatiebeoordeling",
    }

    html = render_to_string(
        "medicatiebeoordeling/pdf/afdeling_review_pdf.html",
        context,
        request=request,
    )

    pdf = _render_pdf(html, base_url=request.build_absolute_uri("/"))

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="medicatiebeoordeling_{afdeling.afdeling}.pdf"'
    return resp