# core/tasks/beat/birthday.py
from __future__ import annotations
from celery import shared_task
from django.utils import timezone
from datetime import timedelta, date  # Zorg ervoor dat 'date' geïmporteerd is

from core.models import UserProfile
from core.utils.push.push import send_birthday_push_for_user, send_birthday_push_for_others
from core.utils.emails.birthday_email import send_birthday_email

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_birthday_reminder(self):
    """
    Taak om elke ochtend om 7:30 de verjaardagen te controleren
    en notificaties/mail te sturen.
    """
    today = timezone.localdate()

    profiles = UserProfile.objects.filter(
        birth_date__isnull=False, organization_id=1
    )

    # Verjaardagen voor vandaag
    birthday_profiles = []
    for profile in profiles:
        dob = profile.birth_date
        try:
            next_bday = dob.replace(year=today.year)
        except ValueError:
            next_bday = date(today.year, 2, 28)

        if next_bday == today:
            birthday_profiles.append(profile)

    # Als er meerdere mensen jarig zijn, verzamelen we hun namen
    birthday_names = [profile.user.first_name.capitalize() for profile in birthday_profiles]
    
    # Stuur emails en pushmeldingen naar de jarige
    for profile in birthday_profiles:
        # Verjaardagse-mail sturen
        send_birthday_email(profile.user.email, profile.user.first_name)

        # Pushmelding voor de jarige sturen
        send_birthday_push_for_user(profile.user.id, profile.user.first_name.capitalize())

    # Boodschap voor de rest van de organisatie genereren
    if len(birthday_names) > 1:
        # Als er meer dan één jarige is, combineer de namen
        birthday_message = " en ".join([", ".join(birthday_names[:-1]), birthday_names[-1]]) if len(birthday_names) > 2 else " en ".join(birthday_names)
        message_body = f"Hoera! {birthday_message} zijn vandaag jarig!"
    else:
        # Als er maar één jarige is
        birthday_message = birthday_names[0]
        message_body = f"Hoera! {birthday_message} is vandaag jarig!"

    # Pushmelding voor de rest van de organisatie
    birthday_profile_ids = [profile.id for profile in birthday_profiles]  # Verzamel IDs van jarigen
    for other_profile in profiles.exclude(id__in=birthday_profile_ids):
        send_birthday_push_for_others(other_profile.user.id, birthday_names, message_body)
