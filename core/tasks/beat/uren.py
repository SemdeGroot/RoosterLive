# core/tasks/beat/uren.py
from __future__ import annotations

import os

from celery import chord, group, shared_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone

from core.views._helpers import wants_email
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
    """
    Draait op de 8e en 9e van elke maand (via celery beat).
    Herinnert oproepmedewerkers als zij vorige maand diensten hadden,
    maar nog geen uren hebben ingediend voor die maand.
    """
    today = timezone.localdate()

    # Deze task wordt op 8e en 9e aangeroepen, dus reminder_date = vandaag.
    reminder_date = today

    # Vorige maand (als month-first date)
    last_month_first = today.replace(day=1) - relativedelta(months=1)
    last_month_year = last_month_first.year
    last_month_month = last_month_first.month

    users_to_notify = UserProfile.objects.select_related("user", "notif_prefs").filter(
        dienstverband=UserProfile.Dienstverband.OPROEP
    )

    for user_profile in users_to_notify:
        user = user_profile.user

        # Heeft user shifts in vorige maand?
        shifts_for_last_month = Shift.objects.filter(
            user=user,
            date__year=last_month_year,
            date__month=last_month_month,
        )

        if not shifts_for_last_month.exists():
            continue

        # Heeft user uren al ingediend voor vorige maand?
        has_uren = UrenInvoer.objects.filter(
            user=user,
            month=last_month_first,
        ).exists()

        if has_uren:
            continue

        prefs = getattr(user_profile, "notif_prefs", None)

        # Pushmelding (push.py checkt pref + permissie)
        send_uren_reminder_push(user.id, reminder_date)

        # E-mail alleen als voorkeur aan staat
        if user.email and wants_email(user, "email_uren_reminder", prefs=prefs):
            send_uren_reminder_email(user.email, user.first_name, reminder_date)
