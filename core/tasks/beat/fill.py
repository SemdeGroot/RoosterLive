# core/tasks/beat/fill.py

from __future__ import annotations

from celery import shared_task
from celery.schedules import crontab


@shared_task(ignore_result=True)
def weekly_fill_availability_task() -> dict:
    from core.utils.beat.fill import fill_availability_for_all_vast_users

    changed = fill_availability_for_all_vast_users(weeks_ahead=12)
    return {"changed_rows": changed}