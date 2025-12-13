from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.utils import timezone

from weasyprint import HTML, CSS

from core.views._helpers import can
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
def _static_abs_path(static_path: str) -> str:
    path = finders.find(static_path)
    if not path:
        raise FileNotFoundError(f"Static file niet gevonden: {static_path}")
    return path


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


def _render_pdf(html: str, *, base_url: str) -> bytes:
    css = CSS(string="""
        :root { --accent: #0B3D91; }  /* donkerder blauw */

        @page { size: A4; margin: 14mm; }

        body {
          font-family: Arial, sans-serif;
          font-size: 11pt;
          color: #111;
          background: #fff;
        }

        .pdf-header {
          display: flex;
          align-items: center;
          gap: 16px;
          border-bottom: 2px solid var(--accent);
          padding-bottom: 12px;
          margin-bottom: 14px;
        }

        .pdf-logo {
          width: 100px;
          height: auto;
          object-fit: contain;
        }

        .pdf-title {
          font-size: 20pt;
          font-weight: 700;
          margin: 0;
        }

        .pdf-submeta {
          margin-top: 6px;
          font-size: 10pt;
          color: #444;
          line-height: 1.4;
        }

        .prepared-by {
          margin-top: 6px;
          font-size: 10pt;
        }

        .section-title {
          font-size: 13pt;
          font-weight: 700;
          margin: 20px 0 10px;
          color: var(--accent);
        }

        .group-title {
          font-size: 11pt;
          font-weight: 700;
          margin-top: 14px;
          color: var(--accent);
        }

        table {
          width: 100%;
          border-collapse: collapse;
          margin-top: 8px;
        }

        th, td {
          border: 1px solid #ddd;
          padding: 7px 8px;
          vertical-align: top;
        }

        th {
          background: #f4f6fb;
          font-weight: 700;
        }

        .muted { color: #666; }

        .comment-box {
          margin-top: 10px;
          padding: 10px;
          border-left: 4px solid var(--accent);
          background: #f9faff;
        }

        .comment-label {
          font-weight: 700;
          margin-bottom: 4px;
        }

        .divider {
          border-top: 1px solid #eee;
          margin: 18px 0;
        }

        .toc-link {
          color: var(--accent);
          text-decoration: none;
        }

        /* Nieuw: elke patiënt op nieuwe pagina in afdeling export */
        .patient-page {
          page-break-before: always;
        }
        .patient-page.first-patient {
          page-break-before: auto;
        }
    """)

    return HTML(string=html, base_url=base_url).write_pdf(stylesheets=[css])


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