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
from core.utils.medication import group_meds_by_jansen, get_jansen_group_choices


@dataclass
class PdfPatientBlock:
    patient: MedicatieReviewPatient
    afdeling_naam: str
    grouped_meds: List[Tuple[str, Dict[str, Any]]]
    comments_lookup: Dict[str, MedicatieReviewComment]

def _merge_manual_comment_groups(grouped_meds, comments_lookup):
    group_name_by_id = {
        group_id: group_name
        for group_id, group_name in get_jansen_group_choices()
    }
    excluded_group_ids = {-1, 0, 1, 2}

    existing_group_ids = {group_id for group_id, _ in grouped_meds}
    manual_groups = []

    for group_id in comments_lookup.keys():
        if group_id in excluded_group_ids:
            continue
        if group_id in existing_group_ids:
            continue
        if group_id not in group_name_by_id:
            continue

        manual_groups.append((
            group_id,
            {
                "naam": group_name_by_id[group_id],
                "meds": [],
                "is_manual": True,
            }
        ))

    merged = list(grouped_meds) + manual_groups
    merged.sort(key=lambda item: item[0])
    return merged

def _build_patient_block(patient: MedicatieReviewPatient) -> PdfPatientBlock:
    analysis = patient.analysis_data or {}
    meds = analysis.get("geneesmiddelen", [])

    overrides_qs = patient.med_group_overrides.all()

    overrides_lookup = {
        ((o.med_clean or "").strip(), (o.med_gebruik or "").strip()): o.target_jansen_group_id
        for o in overrides_qs
    }

    override_name_lookup = {
        ((o.med_clean or "").strip(), (o.med_gebruik or "").strip()): (o.override_name or "").strip()
        for o in overrides_qs
        if (o.override_name or "").strip()
    }

    grouped_meds = group_meds_by_jansen(meds, overrides_lookup=overrides_lookup)
    db_comments = patient.comments.all()
    comments_lookup = {c.jansen_group_id: c for c in db_comments}

    if override_name_lookup:
        for _, group_data in grouped_meds:
            for gm in group_data.get("meds", []):
                if not isinstance(gm, dict):
                    continue
                med_clean = (gm.get("clean") or "").strip()
                gebruik = (gm.get("gebruik") or "").strip()
                override_name = override_name_lookup.get((med_clean, gebruik))
                if override_name:
                    gm["clean"] = override_name

    grouped_meds = _merge_manual_comment_groups(grouped_meds, comments_lookup)

    return PdfPatientBlock(
        patient=patient,
        afdeling_naam=patient.afdeling.afdeling if patient.afdeling else "",
        grouped_meds=grouped_meds,
        comments_lookup=comments_lookup,
    )

@login_required
def export_patient_review_pdf(request, pk: int) -> HttpResponse:
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden()

    patient = (
        MedicatieReviewPatient.objects
        .select_related("afdeling")
        .prefetch_related("comments", "med_group_overrides")  # <- belangrijk
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
        .prefetch_related("comments", "med_group_overrides")  # <- belangrijk
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