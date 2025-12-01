# core/signals.py
from datetime import date

from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import UserProfile


@receiver(post_save, sender=UserProfile)
def invalidate_birthdays_cache_on_profile_change(sender, instance, **kwargs):
    """
    Zodra een UserProfile wordt opgeslagen (nieuwe geboortedatum, wijziging, etc.),
    gooien we de verjaardagen-cache van vandaag weg.

    De volgende request op /agenda zal dan opnieuw de query draaien en de cache vullen.
    """
    org_id = getattr(settings, "APOTHEEK_JANSEN_ORG_ID", 1)

    today_str = date.today().isoformat()
    cache_key = f"agenda_birthdays:{org_id}:{today_str}"

    cache.delete(cache_key)
