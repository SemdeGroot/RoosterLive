from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db.models.signals import post_save, m2m_changed, post_delete
from django.db import transaction
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in, user_logged_out
from core.models import Shift

from core.models import UserProfile
from core.permissions_cache import bump_perm_version, delete_permset, get_cached_permset

User = get_user_model()


@receiver(post_save, sender=UserProfile)
def invalidate_birthdays_cache_on_profile_change(sender, instance, **kwargs):
    org_id = getattr(instance.organization, "id", None) or getattr(settings, "APOTHEEK_JANSEN_ORG_ID", 1)
    today_str = timezone.localdate().isoformat()
    cache_key = f"agenda_birthdays:{org_id}:{today_str}"
    cache.delete(cache_key)


@receiver(user_logged_in)
def warm_permissions_cache_on_login(sender, request, user, **kwargs):
    get_cached_permset(user)


@receiver(user_logged_out)
def drop_permissions_cache_on_logout(sender, request, user, **kwargs):
    if user and getattr(user, "is_authenticated", False):
        delete_permset(user.id)

@receiver(m2m_changed, sender=User.groups.through)
def invalidate_on_user_groups_change(sender, instance, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear"):
        bump_perm_version(instance.id)


@receiver(m2m_changed, sender=User.user_permissions.through)
def invalidate_on_user_permissions_change(sender, instance, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear"):
        bump_perm_version(instance.id)


@receiver(m2m_changed, sender=Group.permissions.through)
def invalidate_on_group_permissions_change(sender, instance, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear"):
        user_ids = list(instance.user_set.values_list("id", flat=True))
        for uid in user_ids:
            bump_perm_version(uid)

def _ics_cache_key(user_id: int) -> str:
    return f"diensten_ics:{user_id}"


@receiver(post_save, sender=Shift)
def invalidate_diensten_ics_on_shift_save(sender, instance, **kwargs):
    # delete na commit, zodat calendar fetch nooit “tussen” jouw publish-transaction door
    uid = instance.user_id
    transaction.on_commit(lambda: cache.delete(_ics_cache_key(uid)))


@receiver(post_delete, sender=Shift)
def invalidate_diensten_ics_on_shift_delete(sender, instance, **kwargs):
    uid = instance.user_id
    transaction.on_commit(lambda: cache.delete(_ics_cache_key(uid)))