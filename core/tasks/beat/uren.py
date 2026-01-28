# core/tasks/beat/uren.py
from __future__ import annotations

import os

from celery import chord, group, shared_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone
from datetime import date

from core.views._helpers import wants_email
from core.models import Shift, UrenRegel, UserProfile
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

    to_email = "semdegroot2003@gmail.com"
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


def _month_first(d: date) -> date:
    return d.replace(day=1)


@shared_task
def send_uren_reminder():
    """
    Draait op de 8e en 9e van elke maand (via celery beat).

    Herinnert oproepmedewerkers als zij diensten hadden in de *vorige kalendermaand*
    (1e t/m laatste dag), maar nog geen uren hebben ingevoerd voor die maand.

    Uren-invoer = bestaan van minstens 1 UrenRegel met actual_hours != None voor month=last_month_first.
    Kilometers worden genegeerd.
    """
    today = timezone.localdate()
    reminder_date = today  # alleen 'vandaag' voor de push dispatcher; inhoud sturen we op basis van last_month_first

    # Vorige kalendermaand
    last_month_first = _month_first(today) + relativedelta(months=-1)
    last_month_end = _month_first(today)  # exclusive (1e van deze maand)

    users_qs = UserProfile.objects.select_related("user", "notif_prefs").filter(
        dienstverband=UserProfile.Dienstverband.OPROEP
    )

    user_ids = list(users_qs.values_list("user_id", flat=True))
    if not user_ids:
        return

    # 1) Alleen oproepers met shifts in vorige kalendermaand
    shift_user_ids = set(
        Shift.objects.filter(
            user_id__in=user_ids,
            date__gte=last_month_first,
            date__lt=last_month_end,
        ).values_list("user_id", flat=True).distinct()
    )
    if not shift_user_ids:
        return

    # 2) Uren al ingevuld? (minstens 1 regel met actual_hours) voor month=last_month_first
    users_with_hours = set(
        UrenRegel.objects.filter(
            user_id__in=shift_user_ids,
            month=last_month_first,
            actual_hours__isnull=False,
        ).values_list("user_id", flat=True).distinct()
    )

    # 3) Notificeren: shifts wél, uren níet
    users_to_remind = shift_user_ids - users_with_hours
    if not users_to_remind:
        return

    # Maak mapping user_id -> profile (zodat we prefs/email niet opnieuw hoeven te query’en)
    profiles_by_user_id = {p.user_id: p for p in users_qs}

    for uid in users_to_remind:
        prof = profiles_by_user_id.get(uid)
        if not prof:
            continue
        user = prof.user
        prefs = getattr(prof, "notif_prefs", None)

        # Pushmelding (push.py checkt pref + permissie)
        # NB: push/email tekst gebruikt reminder_date.strftime('%B %Y').
        # We willen dat dat de *vorige maand* is, dus geven last_month_first mee.
        send_uren_reminder_push(user.id, last_month_first)

        if user.email and wants_email(user, "email_uren_reminder", prefs=prefs):
            job = {
                "type": "uren_reminder",
                "payload": {
                    "to_email": user.email,
                    "first_name": user.first_name or "",
                    "month_first": last_month_first.isoformat(),
                },
            }
            email_dispatcher_task.delay(job)