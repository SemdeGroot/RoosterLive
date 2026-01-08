# core/utils/beat/uren.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Dict, Optional

from dateutil.relativedelta import relativedelta
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Count, Q
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from core.models import Shift, UrenInvoer


EST_HOURS_MORNING = Decimal("4.5")
EST_HOURS_AFTERNOON = Decimal("4.5")
EST_HOURS_EVENING = Decimal("2.0")


@dataclass(frozen=True)
class UrenExportResult:
    month: date
    xlsx_storage_path: Optional[str]
    filename: Optional[str]
    row_count: int


def _month_first(d: date) -> date:
    return d.replace(day=1)


def _prev_month_first(today: date) -> date:
    return _month_first(today + relativedelta(months=-1))


def _next_month_first(month_first: date) -> date:
    return _month_first(month_first + relativedelta(months=1))


def _display_worker_name(user) -> str:
    first = (getattr(user, "first_name", "") or "").strip()
    if first:
        return first[:1].upper() + first[1:].lower()

    username = (getattr(user, "username", "") or "").strip()
    if username:
        return username

    email = (getattr(user, "email", "") or "").strip()
    return email or f"User {user.pk}"


def _autosize_columns(ws, min_width: int = 12, max_width: int = 45) -> None:
    for col in range(1, ws.max_column + 1):
        letter = get_column_letter(col)
        max_len = 0
        for cell in ws[letter]:
            if cell.value is None:
                continue
            max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[letter].width = max(min_width, min(max_width, max_len + 2))


def export_uren_month_to_storage(today: Optional[date] = None) -> UrenExportResult:
    """
    Genereert Excel-overzicht voor vorige maand en slaat op in default_storage.
    Totaal uren = uren vóór 18:00 + (uren na 18:00 * (1 + toeslag%)).
    Geschat aantal uren = (ochtend*4.5) + (middag*4.5) + (avond*2.0*(1+toeslag%)).
    """
    if today is None:
        today = timezone.localdate()

    month_first = _prev_month_first(today)
    next_month = _next_month_first(month_first)

    uren_qs = (
        UrenInvoer.objects.select_related("user")
        .filter(month=month_first)
        .order_by("user__first_name", "user_id")
    )
    row_count = uren_qs.count()
    if row_count == 0:
        return UrenExportResult(month=month_first, xlsx_storage_path=None, filename=None, row_count=0)

    # Shifts tellen per user (ochtend/middag/avond)
    shift_counts = (
        Shift.objects.filter(date__gte=month_first, date__lt=next_month)
        .values("user_id")
        .annotate(
            morning_count=Count("id", filter=Q(period="morning")),
            afternoon_count=Count("id", filter=Q(period="afternoon")),
            evening_count=Count("id", filter=Q(period="evening")),
        )
    )
    shift_by_user: Dict[int, Dict[str, int]] = {
        row["user_id"]: {
            "morning": int(row.get("morning_count") or 0),
            "afternoon": int(row.get("afternoon_count") or 0),
            "evening": int(row.get("evening_count") or 0),
        }
        for row in shift_counts
    }

    wb = Workbook()
    ws = wb.active
    ws.title = f"Uren {month_first.strftime('%Y-%m')}"

    headers = [
        "Werknemer",
        "Doorgegeven uren voor 18:00",
        "Doorgegeven uren na 18:00",
        "CAO toeslag (%)",
        "(Gewogen) Totaal uren",  # gewogen totaal
        "Gewerkte diensten ochtend",
        "Gewerkte diensten middag",
        "Gewerkte diensten avond",
        "(Gewogen) Geschat aantal uren",  # gewogen schatting
        "Verschil (%)",
    ]
    ws.append(headers)

    header_font = Font(bold=True)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for ui in uren_qs:
        user = ui.user
        name = _display_worker_name(user)

        before_18 = ui.hours_before_18 or Decimal("0.0")
        after_18 = ui.hours_after_18 or Decimal("0.0")

        allow_pct = ui.evening_allowance_pct_used or Decimal("0.00")  # bv 25.00
        factor = Decimal("1.0") + (allow_pct / Decimal("100.0"))      # bv 1.25

        # Totaal uren = vóór 18 + (na 18 * toeslagfactor)
        after_weighted = after_18 * factor
        total = before_18 + after_weighted

        counts = shift_by_user.get(user.id, {"morning": 0, "afternoon": 0, "evening": 0})
        morning = int(counts["morning"])
        afternoon = int(counts["afternoon"])
        evening = int(counts["evening"])

        # Geschatte uren (gewogen): avond-shifts ook * toeslagfactor
        estimated = (
            (Decimal(morning) * EST_HOURS_MORNING)
            + (Decimal(afternoon) * EST_HOURS_AFTERNOON)
            + (Decimal(evening) * EST_HOURS_EVENING * factor)
        )

        # Verschil = (nieuw - oud) / oud * 100, met nieuw=total, oud=estimated
        diff_pct = None
        if estimated and estimated != Decimal("0.0"):
            diff_pct = (total - estimated) / estimated * Decimal("100.0")

        ws.append(
            [
                name,
                float(before_18),
                float(after_18),          # ruwe avond-uren
                float(allow_pct),         # toeslag als 25.0 (dus 25%)
                float(total),             # gewogen totaal
                morning,
                afternoon,
                evening,
                float(estimated),         # gewogen schatting
                (float(diff_pct) if diff_pct is not None else None),
            ]
        )

    # Nettere opmaak
    ws.freeze_panes = "A2"
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            if cell.column == 1:
                cell.alignment = Alignment(horizontal="left")
            else:
                cell.alignment = Alignment(horizontal="center")

    _autosize_columns(ws)

    # Opslaan naar bytes
    bio = BytesIO()
    wb.save(bio)
    xlsx_bytes = bio.getvalue()

    filename = f"Urenoverzicht_{month_first.strftime('%Y-%m')}.xlsx"
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    storage_path = f"tmp/uren_overzicht/{ts}_{filename}"
    storage_path = default_storage.save(storage_path, ContentFile(xlsx_bytes))

    return UrenExportResult(month=month_first, xlsx_storage_path=storage_path, filename=filename, row_count=row_count)
