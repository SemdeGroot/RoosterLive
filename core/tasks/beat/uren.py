# core/tasks/beat/uren.py
from __future__ import annotations

import os

from celery import chord, group, shared_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone

from core.models import Shift, UrenInvoer, UserProfile
from core.tasks.email_dispatcher import email_dispatcher_task
from core.tasks.beat.cleanup import cleanup_uren_export_task
from core.utils.beat.uren import export_uren_month_to_storage
from core.utils.push.push import send_uren_reminder_push
from core.utils.emails.urenreminder import send_uren_reminder_email

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

@shared_task
def send_uren_reminder():
    today = timezone.localdate()
    first_of_this_month = today.replace(day=1)
    
    # 2 dagen voor de deadline (8e van de maand)
    reminder_date = first_of_this_month + relativedelta(months=1, day=8)

    # 1 dag voor de deadline (9e van de maand)
    second_reminder_date = first_of_this_month + relativedelta(months=1, day=9)

    # Haal oproepmedewerkers op zonder ureninvoer
    users_to_notify = UserProfile.objects.filter(
        dienstverband=UserProfile.Dienstverband.OPROEP
    )

    for user_profile in users_to_notify:
        shifts_for_last_month = Shift.objects.filter(
            user=user_profile.user,
            date__month=(today.month - 1) % 12
        )

        # Check of de gebruiker shifts heeft voor de vorige maand, maar geen uren heeft doorgegeven
        if shifts_for_last_month.exists() and not UrenInvoer.objects.filter(
            user=user_profile.user, month=(today.replace(day=1) - relativedelta(months=1)).date()).exists():
            
            # Pushmelding versturen
            send_uren_reminder_push(user_profile.user.id, reminder_date)
            
            # E-mail sturen
            send_uren_reminder_email(user_profile.user.email, user_profile.user.first_name, reminder_date)
            
            # Tweede herinnering voor de 9e (indien nodig)
            if today == second_reminder_date:
                send_uren_reminder_push(user_profile.user.id, second_reminder_date)
                send_uren_reminder_email(user_profile.user.email, user_profile.user.first_name, second_reminder_date)