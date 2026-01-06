# core/tasks/beat/cleanup.py

from __future__ import annotations

from celery import shared_task
from celery.schedules import crontab

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