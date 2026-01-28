# core/utils/beat/cleanup.py

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta

from django.db import transaction
from django.db.models import Min
from django.utils import timezone

from core.models import ShiftDraft, Availability, UrenMaand, UrenRegel, UrenDag


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


def _month_first(d: date) -> date:
    return d.replace(day=1)


def _active_month(today: date) -> date:
    """
    Actieve maand voor urenperiode op basis van window 10e->10e:
    - als vandaag dag < 10 => actieve maand = vorige maand
    - anders => actieve maand = huidige maand
    """
    if today.day < 10:
        return _month_first(today + relativedelta(months=-1))
    return _month_first(today)


@transaction.atomic
def delete_uren_through_month(month_first: date) -> dict:
    """
    Verwijdert alle UrenDag, UrenRegel en UrenMaand records met month <= month_first.
    Return: dict met aantallen.
    """
    # UrenDag (nieuw)
    dag_qs = UrenDag.objects.filter(month__lte=month_first)
    dag_count = dag_qs.count()
    dag_qs.delete()

    # UrenRegel
    regels_qs = UrenRegel.objects.filter(month__lte=month_first)
    regels_count = regels_qs.count()
    regels_qs.delete()

    # UrenMaand
    maand_qs = UrenMaand.objects.filter(month__lte=month_first)
    maand_count = maand_qs.count()
    maand_qs.delete()

    return {
        "uren_dag_deleted": int(dag_count),
        "uren_regel_deleted": int(regels_count),
        "uren_maand_deleted": int(maand_count),
    }

def cleanup_uren_retention(
    *,
    today: Optional[date] = None,
    keep_last_n_months: int = 3,
) -> dict:
    """
    Cleanup policy voor nieuwe urenmodellen.

    We houden standaard de laatste N maanden (op basis van 'actieve maand' logic).
    Alles met month <= (active_month - keep_last_n_months) wordt verwijderd.

    Voorbeeld:
    - vandaag 2026-01-20 => active_month = 2026-01-01
      keep_last_n_months=3 => cutoff_month = 2025-10-01
      delete <= 2025-10-01

    Return: dict met cutoff en aantallen.
    """
    if today is None:
        today = timezone.localdate()

    if keep_last_n_months < 1:
        keep_last_n_months = 1

    active = _active_month(today)
    cutoff_month = _month_first(active + relativedelta(months=-keep_last_n_months))

    result = delete_uren_through_month(cutoff_month)
    result["cutoff_month"] = cutoff_month.isoformat()
    result["active_month"] = active.isoformat()
    result["keep_last_n_months"] = int(keep_last_n_months)
    return result


# Backwards-compatible alias (als je celery beat nog deze functie aanroept)
@transaction.atomic
def delete_ureninvoer_through_month(month_first: date) -> int:
    """
    BACKWARDS COMPAT:
    Oud: delete UrenInvoer month <= month_first
    Nieuw: delete UrenRegel + UrenMaand month <= month_first

    Return: totaal aantal verwijderde records (urenregels + maanden).
    """
    res = delete_uren_through_month(month_first)
    return int(res["uren_dag_deleted"] + res["uren_regel_deleted"] + res["uren_maand_deleted"])
