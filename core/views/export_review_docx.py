from __future__ import annotations

import os
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.utils import timezone

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from core.models import MedicatieReviewAfdeling, MedicatieReviewPatient
from core.views._helpers import _static_abs_path, can
from core.views.export_review_pdf import PdfPatientBlock, _build_patient_block


COL_HEADER_BG = "E8EDF2"  # lichtblauw-grijs voor tabelheaders (zoals PDF)
COL_ROW_ALT = "F0F4F8"  # lichtgrijs alternerende rij
COL_SECTION_FG = "1B3A5C"  # donkerblauw voor titels
COL_MUTED = "555555"  # donkerder muted dan voorheen
COL_DIVIDER = "CCCCCC"  # scheidingslijnen
COL_COMMENT_BG = "F3F6FA"  # comment box achtergrond

PREPARED_BY_EMAIL_FIXED = "instellingen@apotheekjansen.com"


# ── XML helpers ───────────────────────────────────────────────────────────────

def _get_or_create_tblPr(tbl):
    tbl_el = tbl._tbl
    tblPr = tbl_el.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl_el.insert(0, tblPr)
    return tblPr


def _set_tbl_width(tbl, width_dxa: int = 9072) -> None:
    tblPr = _get_or_create_tblPr(tbl)
    for old in tblPr.findall(qn("w:tblW")):
        tblPr.remove(old)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), str(width_dxa))
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)


def _remove_tbl_borders(tbl) -> None:
    tblPr = _get_or_create_tblPr(tbl)
    for old in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(old)
    tbl_borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        el.set(qn("w:color"), "auto")
        tbl_borders.append(el)
    tblPr.append(tbl_borders)


def _set_col_width(cell, width_dxa: int) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcW")):
        tcPr.remove(old)
    tcW = OxmlElement("w:tcW")
    tcW.set(qn("w:w"), str(width_dxa))
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)


def _cell_shading(cell, fill_hex: str) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    tcPr.append(shd)


def _cell_borders(cell, color: str = COL_DIVIDER, size: str = "4") -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcBorders")):
        tcPr.remove(old)
    tcBorders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), size)
        el.set(qn("w:color"), color)
        tcBorders.append(el)
    tcPr.append(tcBorders)


def _cell_borders_none(cell) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcBorders")):
        tcPr.remove(old)
    tcBorders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        el.set(qn("w:color"), "auto")
        tcBorders.append(el)
    tcPr.append(tcBorders)


def _cell_margins(cell, top: int = 80, bottom: int = 80, left: int = 120, right: int = 120) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcMar")):
        tcPr.remove(old)
    mar = OxmlElement("w:tcMar")
    for side, val in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


def _para_spacing(para, before: int = 0, after: int = 0) -> None:
    pPr = para._p.get_or_add_pPr()
    for old in pPr.findall(qn("w:spacing")):
        pPr.remove(old)
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), str(before))
    spacing.set(qn("w:after"), str(after))
    pPr.append(spacing)


def _para_bottom_border(para, color: str = COL_SECTION_FG, size: str = "8") -> None:
    pPr = para._p.get_or_add_pPr()
    for old in pPr.findall(qn("w:pBdr")):
        pPr.remove(old)
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:color"), color)
    bottom.set(qn("w:space"), "4")
    pBdr.append(bottom)
    pPr.append(pBdr)


# ── Styles / Document setup ───────────────────────────────────────────────────

def _ensure_styles(doc: Document) -> None:
    styles = doc.styles

    def _get_or_create(name: str):
        try:
            return styles[name]
        except KeyError:
            return styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)

    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)
    pf = normal.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE

    section = _get_or_create("PdfSectionTitle")
    section.font.name = "Calibri"
    section.font.size = Pt(11)
    section.font.bold = True
    section.font.color.rgb = RGBColor.from_string(COL_SECTION_FG)

    group = _get_or_create("PdfGroupTitle")
    group.font.name = "Calibri"
    group.font.size = Pt(10)
    group.font.bold = True
    group.font.color.rgb = RGBColor.from_string(COL_SECTION_FG)

    muted = _get_or_create("PdfMuted")
    muted.font.name = "Calibri"
    muted.font.size = Pt(8)
    muted.font.color.rgb = RGBColor.from_string(COL_MUTED)


def _new_doc() -> Document:
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.5)
    sec.right_margin = Cm(2.5)
    _ensure_styles(doc)
    return doc


# ── Header / Titles ───────────────────────────────────────────────────────────

def _add_logo_and_title(doc: Document, title: str, meta: dict, prepared_by, generated_at) -> None:
    logo_path = _static_abs_path("img/app_icon_trans-512x512.png")

    tbl = doc.add_table(rows=1, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    # Remove borders at both table and cell level; Word applies table-level
    # borders as a fallback even when cell borders are set to none.
    _remove_tbl_borders(tbl)

    logo_cell = tbl.rows[0].cells[0]
    text_cell = tbl.rows[0].cells[1]

    _set_col_width(logo_cell, 1440)
    _set_col_width(text_cell, 7632)

    _cell_borders_none(logo_cell)
    _cell_borders_none(text_cell)

    if logo_path and os.path.exists(logo_path):
        logo_para = logo_cell.paragraphs[0]
        _para_spacing(logo_para, 0, 0)
        logo_para.add_run().add_picture(logo_path, width=Cm(1.8))

    title_para = text_cell.paragraphs[0]
    _para_spacing(title_para, 0, 60)
    tr = title_para.add_run(title)
    tr.bold = True
    tr.font.size = Pt(18)
    tr.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    for label, value in meta.items():
        p = text_cell.add_paragraph()
        _para_spacing(p, 0, 30)
        lr = p.add_run(f"{label}: ")
        lr.bold = True
        lr.font.size = Pt(9)
        vr = p.add_run(str(value))
        vr.font.size = Pt(9)

    p_prep = text_cell.add_paragraph()
    _para_spacing(p_prep, 70, 0)
    lr = p_prep.add_run("Voorbereid door: ")
    lr.bold = True
    lr.font.size = Pt(9)
    name = f"{prepared_by.first_name} {prepared_by.last_name}".strip() or prepared_by.username
    nr = p_prep.add_run(name)
    nr.font.size = Pt(9)

    p_mail = text_cell.add_paragraph(style="PdfMuted")
    _para_spacing(p_mail, 20, 0)
    p_mail.add_run(PREPARED_BY_EMAIL_FIXED)

    p_exp = text_cell.add_paragraph(style="PdfMuted")
    _para_spacing(p_exp, 20, 0)
    p_exp.add_run(f"Export: {generated_at.strftime('%d-%m-%Y %H:%M')}")

    p_line = doc.add_paragraph()
    _para_spacing(p_line, 80, 120)
    _para_bottom_border(p_line, color=COL_SECTION_FG, size="12")


def _add_section_title(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="PdfSectionTitle")
    _para_spacing(p, 80, 50)
    p.add_run(text)
    _para_bottom_border(p, color=COL_SECTION_FG, size="12")


def _add_group_title(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="PdfGroupTitle")
    _para_spacing(p, 120, 20)
    p.paragraph_format.keep_with_next = True
    p.add_run(text)


def _add_divider(doc: Document) -> None:
    p = doc.add_paragraph()
    _para_spacing(p, 120, 120)
    _para_bottom_border(p, color=COL_DIVIDER, size="6")


def _add_patient_heading(doc: Document, naam: str, geboortedatum) -> None:
    p = doc.add_paragraph()
    _para_spacing(p, 180, 50)
    p.paragraph_format.keep_with_next = True

    name_run = p.add_run(naam)
    name_run.bold = True
    name_run.font.size = Pt(13)
    name_run.font.color.rgb = RGBColor.from_string(COL_SECTION_FG)

    dob = geboortedatum.strftime("%d-%m-%Y") if geboortedatum else "Onbekend"
    dob_run = p.add_run(f"  ({dob})")
    dob_run.font.size = Pt(10)
    dob_run.font.color.rgb = RGBColor.from_string(COL_MUTED)


# ── Tables / Comment cards ────────────────────────────────────────────────────

def _add_meds_table(doc: Document, meds: list) -> None:
    """
    Kolommen: Middel 35% | Gebruik 30% | Opmerking 35% van 9072 DXA.
    Header: lichtblauwe achtergrond met zwarte tekst, zoals PDF.
    """
    if not meds:
        return

    col_w = [3175, 2722, 3175]

    tbl = doc.add_table(rows=1, cols=3)
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    _set_tbl_width(tbl, 9072)

    for i, (cell, label) in enumerate(zip(tbl.rows[0].cells, ["Middel", "Gebruik", "Opmerking (Medimo)"])):
        _set_col_width(cell, col_w[i])
        _cell_shading(cell, COL_HEADER_BG)
        _cell_borders(cell, color=COL_DIVIDER)
        _cell_margins(cell, top=90, bottom=90, left=140, right=140)

        run = cell.paragraphs[0].add_run(label)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    for idx, gm in enumerate(meds):
        row = tbl.add_row()
        bg = COL_ROW_ALT if idx % 2 == 1 else "FFFFFF"

        clean = str(gm.get("clean", "") if isinstance(gm, dict) else getattr(gm, "clean", "") or "")
        gebruik = str(gm.get("gebruik", "") if isinstance(gm, dict) else getattr(gm, "gebruik", "") or "")
        opmerking = str(gm.get("opmerking", "") if isinstance(gm, dict) else getattr(gm, "opmerking", "") or "") or "-"

        for i, (cell, val) in enumerate(zip(row.cells, [clean, gebruik, opmerking])):
            _set_col_width(cell, col_w[i])
            _cell_shading(cell, bg)
            _cell_borders(cell, color=COL_DIVIDER)
            _cell_margins(cell, top=90, bottom=90, left=140, right=140)

            run = cell.paragraphs[0].add_run(val)
            run.font.size = Pt(9)
            if i == 0:
                run.bold = True
            if i == 2:
                run.font.color.rgb = RGBColor.from_string(COL_MUTED)


def _comment_card(doc: Document, label: str, lines: list[str]) -> None:
    """Single-cell comment box with subtle background; no accent bar."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    _remove_tbl_borders(tbl)
    _set_tbl_width(tbl, 9072)

    body = tbl.rows[0].cells[0]
    _set_col_width(body, 9072)
    _cell_borders_none(body)
    _cell_shading(body, COL_COMMENT_BG)
    _cell_margins(body, top=140, bottom=140, left=180, right=180)

    p0 = body.paragraphs[0]
    p0.style = doc.styles["PdfMuted"]
    _para_spacing(p0, 0, 60)
    r0 = p0.add_run(label)
    r0.bold = True

    for i, line in enumerate(lines):
        p = body.add_paragraph()
        _para_spacing(p, 0, 0 if i < len(lines) - 1 else 40)
        p.add_run(line).font.size = Pt(9)


def _add_comment_box(doc: Document, label: str, text: str) -> None:
    if not text or not text.strip():
        return
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return
    _comment_card(doc, label, lines)


def _add_empty_comment_box(doc: Document) -> None:
    _comment_card(doc, "Opmerkingen", [""])


def _render_patient_block(doc: Document, block: PdfPatientBlock) -> None:
    for group_id, group_data in block.grouped_meds:
        _add_group_title(doc, group_data["naam"])

        meds = group_data.get("meds", [])
        _add_meds_table(doc, meds)

        comment = block.comments_lookup.get(group_id)
        historie_tekst = comment.historie if comment else ""
        opmerking_tekst = comment.tekst if comment else ""

        if historie_tekst:
            _add_comment_box(doc, "Eerder besproken", historie_tekst)

        if opmerking_tekst:
            _add_comment_box(doc, "Opmerkingen", opmerking_tekst)
        else:
            _add_empty_comment_box(doc)


# ── Responses ─────────────────────────────────────────────────────────────────

def _build_response(doc: Document, filename: str) -> HttpResponse:
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    resp = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _build_patient_docx_response(patient: MedicatieReviewPatient, user) -> HttpResponse:
    block = _build_patient_block(patient)
    doc = _new_doc()
    now = timezone.localtime(timezone.now())
    dob = patient.geboortedatum.strftime("%d-%m-%Y") if patient.geboortedatum else "Onbekend"

    _add_logo_and_title(
        doc,
        "Medicatiebeoordeling",
        {
            "Patiënt": patient.naam,
            "Geboortedatum": dob,
            "Afdeling": block.afdeling_naam or "-",
        },
        user,
        now,
    )

    _add_section_title(doc, "Medicatieoverzicht & Opmerkingen")
    _render_patient_block(doc, block)

    safe_name = (patient.naam or "patient").replace("/", "-")
    return _build_response(doc, f"medicatiebeoordeling_{safe_name}.docx")


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
def export_patient_review_docx(request, pk: int) -> HttpResponse:
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden()

    patient = (
        MedicatieReviewPatient.objects.select_related("afdeling")
        .prefetch_related("comments", "med_group_overrides")
        .filter(pk=pk)
        .first()
    )
    if not patient:
        raise Http404()

    return _build_patient_docx_response(patient, request.user)


@login_required
def export_afdeling_review_docx(request, pk: int) -> HttpResponse:
    if not can(request.user, "can_view_medicatiebeoordeling"):
        return HttpResponseForbidden()

    afdeling = MedicatieReviewAfdeling.objects.filter(pk=pk).first()
    if not afdeling:
        raise Http404()

    patienten = (
        afdeling.patienten.all()
        .select_related("afdeling")
        .prefetch_related("comments", "med_group_overrides")
        .order_by("naam")
    )
    blocks = [_build_patient_block(p) for p in patienten]
    doc = _new_doc()
    now = timezone.localtime(timezone.now())

    _add_logo_and_title(
        doc,
        "Medicatiebeoordeling",
        {
            "Afdeling": afdeling.afdeling,
        },
        request.user,
        now,
    )

    _add_section_title(doc, "Overzicht patiënten")

    tbl = doc.add_table(rows=1, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    _set_tbl_width(tbl, 9072)

    for i, (cell, label) in enumerate(zip(tbl.rows[0].cells, ["Naam", "Geboortedatum"])):
        _set_col_width(cell, 5436 if i == 0 else 3636)
        _cell_shading(cell, COL_HEADER_BG)
        _cell_borders(cell, color=COL_DIVIDER)
        _cell_margins(cell, top=90, bottom=90, left=140, right=140)

        run = cell.paragraphs[0].add_run(label)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    for idx, block in enumerate(blocks):
        row = tbl.add_row()
        bg = COL_ROW_ALT if idx % 2 == 1 else "FFFFFF"
        dob = block.patient.geboortedatum.strftime("%d-%m-%Y") if block.patient.geboortedatum else "Onbekend"

        for i, (cell, val) in enumerate(zip(row.cells, [block.patient.naam, dob])):
            _set_col_width(cell, 5436 if i == 0 else 3636)
            _cell_shading(cell, bg)
            _cell_borders(cell, color=COL_DIVIDER)
            _cell_margins(cell, top=90, bottom=90, left=140, right=140)

            run = cell.paragraphs[0].add_run(val)
            run.font.size = Pt(9)
            if i == 0:
                run.bold = True
            else:
                run.font.color.rgb = RGBColor.from_string(COL_MUTED)

    _add_divider(doc)
    _add_section_title(doc, "Details")

    for block in blocks:
        _add_patient_heading(doc, block.patient.naam, block.patient.geboortedatum)
        _render_patient_block(doc, block)
        _add_divider(doc)

    safe_name = (afdeling.afdeling or "afdeling").replace("/", "-")
    return _build_response(doc, f"medicatiebeoordeling_{safe_name}.docx")