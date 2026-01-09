# core/tasks/beat/birthday.py
from __future__ import annotations
from celery import shared_task
from django.utils import timezone
from datetime import date

from core.models import UserProfile
from core.utils.push.push import send_birthday_push_for_user, send_birthday_push_for_others
from core.tasks.email_dispatcher import email_dispatcher_task

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_birthday_reminder(self):
    today = timezone.localdate()

    profiles = UserProfile.objects.filter(birth_date__isnull=False, organization_id=1)

    birthday_profiles = []
    for profile in profiles:
        dob = profile.birth_date
        try:
            next_bday = dob.replace(year=today.year)
        except ValueError:
            next_bday = date(today.year, 2, 28)

        if next_bday == today:
            birthday_profiles.append(profile)

    # niks jarig? stop
    if not birthday_profiles:
        return

    birthday_names = [profile.user.first_name.capitalize() for profile in birthday_profiles]
    birthday_user_ids = [profile.user_id for profile in birthday_profiles]

    # Persoonlijk naar elke jarige
    for profile in birthday_profiles:
        email_dispatcher_task.apply_async(
            args=[{
                "type": "birthday",
                "payload": {
                    "to_email": profile.user.email,
                    "first_name": profile.user.first_name or "Collega",
                }
            }],
            queue="mail",
        )
        send_birthday_push_for_user(profile.user_id, profile.user.first_name.capitalize())

    # Eén keer naar alle anderen (exclude alle jarigen)
    send_birthday_push_for_others(birthday_user_ids=birthday_user_ids, birthday_names=birthday_names)