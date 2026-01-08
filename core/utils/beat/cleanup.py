# core/utils/beat/cleanup.py

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from django.db import transaction
from django.db.models import Min
from django.utils import timezone

from core.models import ShiftDraft, Availability, UrenInvoer


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def cleanup_shiftdrafts_new_week(*, today: Optional[date] = None) -> int:
    """
    Delete ShiftDraft rows strictly before the current week (before Monday).
    Returns number of deleted rows.
    """
    if today is None:
        today = timezone.localdate()

    cutoff = _monday_of_week(today)

    oldest = ShiftDraft.objects.aggregate(oldest=Min("date"))["oldest"]
    if oldest is None or oldest >= cutoff:
        return 0

    with transaction.atomic():
        deleted, _ = ShiftDraft.objects.filter(date__lt=cutoff).delete()

    return int(deleted)


def cleanup_availability_new_week(*, today: Optional[date] = None) -> int:
    """
    Delete Availability rows strictly before the current week (before Monday).
    Returns number of deleted rows.
    """
    if today is None:
        today = timezone.localdate()

    cutoff = _monday_of_week(today)

    oldest = Availability.objects.aggregate(oldest=Min("date"))["oldest"]
    if oldest is None or oldest >= cutoff:
        return 0

    with transaction.atomic():
        deleted, _ = Availability.objects.filter(date__lt=cutoff).delete()

    return int(deleted)

@transaction.atomic
def delete_ureninvoer_through_month(month_first: date) -> int:
    """
    Verwijdert alle UrenInvoer regels met month <= month_first.
    (Dus: alles t/m en inclusief de verwerkte maand.)

    Return: aantal verwijderde records.
    """
    qs = UrenInvoer.objects.filter(month__lte=month_first)
    count = qs.count()
    qs.delete()
    return count