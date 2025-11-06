from django.db.models.signals import m2m_changed, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from .cache import bump_perm_version

User = get_user_model()

@receiver(m2m_changed, sender=User.groups.through)
def _user_groups_changed(sender, instance, **kwargs):
    bump_perm_version(instance.id)

@receiver(m2m_changed, sender=User.user_permissions.through)
def _user_perms_changed(sender, instance, **kwargs):
    bump_perm_version(instance.id)

@receiver(m2m_changed, sender=Group.permissions.through)
def _group_perms_changed(sender, instance, **kwargs):
    for uid in instance.user_set.values_list("id", flat=True):
        bump_perm_version(uid)

@receiver(post_delete, sender=Group)
def _group_deleted(sender, instance, **kwargs):
    # (conservatief) invalideer alle (voormalige) leden
    for uid in instance.user_set.values_list("id", flat=True):
        bump_perm_version(uid)

# Optioneel: bij wijzigingen in Permission zelf (kleine setups)
@receiver(m2m_changed, sender=Permission.user_set.through)
def _permission_user_m2m(sender, **kwargs):
    # vaak niet nodig; kan lawaaiig zijn in grote installs
    pass
