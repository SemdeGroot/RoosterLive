# core/signals.py
from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from core.models import UserProfile


@receiver(post_save, sender=UserProfile)
def invalidate_birthdays_cache_on_profile_change(sender, instance, **kwargs):
    """
    Zodra een UserProfile wordt opgeslagen (nieuwe geboortedatum, wijziging, etc.),
    gooien we de verjaardagen-cache voor vandaag weg (alleen voor deze organisatie).
    """

    # Als je ooit meerdere organisaties wilt ondersteunen, is dit alvast goed:
    org_id = getattr(instance.organization, "id", None)
    if org_id is None:
        # fallback naar Jansen constant
        org_id = getattr(settings, "APOTHEEK_JANSEN_ORG_ID", 1)

    today_str = timezone.localdate().isoformat()
    cache_key = f"agenda_birthdays:{org_id}:{today_str}"

    cache.delete(cache_key)