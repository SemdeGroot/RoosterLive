from django.conf import settings
from django.core.cache import caches

SESS_CACHE = caches[getattr(settings, "SESSION_CACHE_ALIAS", "default")]

PERMVER_KEY = "permver:{user_id}"
PERMSET_KEY = "permset:{user_id}:{ver}"

def _perm_ttl():
    return getattr(settings, "PERMISSIONS_CACHE_TTL", settings.SESSION_COOKIE_AGE)

def get_perm_version(user_id: int) -> int:
    v = SESS_CACHE.get(PERMVER_KEY.format(user_id=user_id))
    return int(v) if v else 1

def bump_perm_version(user_id: int) -> int:
    key = PERMVER_KEY.format(user_id=user_id)
    if SESS_CACHE.get(key) is None:
        SESS_CACHE.set(key, 1, timeout=None)
    return int(SESS_CACHE.incr(key))

def delete_permset(user_id: int, ver: int | None = None):
    if ver is None:
        ver = get_perm_version(user_id)
    SESS_CACHE.delete(PERMSET_KEY.format(user_id=user_id, ver=ver))

def build_permset_for_user(user):
    return set(user.get_all_permissions())

def get_cached_permset(user):
    ver = get_perm_version(user.id)
    key = PERMSET_KEY.format(user_id=user.id, ver=ver)

    perms = SESS_CACHE.get(key)
    if perms is None:
        perms = list(build_permset_for_user(user))
        SESS_CACHE.set(key, perms, timeout=_perm_ttl())

    return set(perms)