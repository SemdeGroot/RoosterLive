# core/tasks/beat/uren.py
from __future__ import annotations

import os

from celery import chord, group, shared_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone

from core.tasks.email_dispatcher import email_dispatcher_task
from core.tasks.beat.cleanup import cleanup_uren_export_task
from core.utils.beat.uren import export_uren_month_to_storage


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def monthly_uren_export_task(self):
    """
    Draait elke 11e van de maand om 09:00.
    Exporteert vorige maand, mailt naar grootrk, en ruimt daarna op (file + db records).
    """
    today = timezone.localdate()
    res = export_uren_month_to_storage(today=today)

    # Idempotent: als er niks is, stop.
    if res.row_count == 0 or not res.xlsx_storage_path or not res.filename:
        return

    to_email = "grootrk@apotheekjansen.com"
    contact_email = settings.DEFAULT_FROM_EMAIL
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    job = {
        "type": "uren_overzicht",
        "payload": {
            "to_email": to_email,
            "month_first": res.month.isoformat(),
            "xlsx_path": res.xlsx_storage_path,
            "filename": res.filename,
            "contact_email": contact_email,
            "logo_path": logo_path,
        },
    }

    mail_sig = email_dispatcher_task.s(job).set(queue="mail")

    # Alleen als mail(s) succesvol zijn => cleanup: storage + uren verwijderen
    chord(group([mail_sig]))(
        cleanup_uren_export_task.s(res.xlsx_storage_path, res.month.isoformat()).set(queue="default")
    )
