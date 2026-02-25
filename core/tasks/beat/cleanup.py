# core/tasks/beat/cleanup.py
from __future__ import annotations

from datetime import date
from django.utils import timezone
from celery import shared_task
from celery.schedules import crontab

from django.core.files.storage import default_storage

from core.utils.beat.cleanup import cleanup_uren_retention

@shared_task(ignore_result=True)
def cleanup_baxter_snapshots_task() -> int:
    from core.models import BaxterProductieSnapshotPunt

    today = timezone.localdate()
    deleted, _ = BaxterProductieSnapshotPunt.objects.filter(timestamp__date__lt=today).delete()
    return deleted

@shared_task(ignore_result=True)
def weekly_cleanup_task() -> dict:
    from core.utils.beat.cleanup import (
        cleanup_shiftdrafts_new_week,
        cleanup_availability_new_week,
    )

    return {
        "deleted_shift_drafts": cleanup_shiftdrafts_new_week(),
        "deleted_availability": cleanup_availability_new_week(),
    }

@shared_task(bind=True)
def cleanup_uren_export_task(self, results, xlsx_path: str, month_first_iso: str):
    """
    Callback voor chord: draait alleen na succesvolle verzending.
    - verwijdert excel uit storage
    - verwijdert alle UrenInvoer t/m de verwerkte maand
    """
    month_first = date.fromisoformat(month_first_iso)

    # retention cleanup: bewaar bijv. laatste 3 maanden
    cleanup_uren_retention(today=timezone.localdate(), keep_last_n_months=3)

    # excel weg (best effort)
    try:
        if xlsx_path and default_storage.exists(xlsx_path):
            default_storage.delete(xlsx_path)
    except Exception:
        pass