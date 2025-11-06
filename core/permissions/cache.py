from django.core.cache import cache

# Hoe lang we een geassembleerde permissieset bewaren (TTL)
PERM_TTL = 60 * 60  # 1 uur

def _perm_version_key(user_id: int) -> str:
    return f"user:{user_id}:permver"  # geen TTL; aantal users = aantal keys

def _perm_cache_key(user_id: int) -> str:
    ver = cache.get(_perm_version_key(user_id), 1)
    return f"user:{user_id}:perms:v{ver}"

def bump_perm_version(user_id: int):
    """Invalideer alle perm-caches van deze user (via versie-bump)."""
    vkey = _perm_version_key(user_id)
    if not cache.add(vkey, 1, None):
        try:
            cache.incr(vkey)
        except Exception:
            cache.set(vkey, 1, None)

def get_user_perms(user) -> set[str]:
    """Haal permissieset voor user op, met Redis-cache + request-scope cache."""
    if not user.is_authenticated:
        return set()

    # request-scope cache; voorkomt meerdere Redis hits binnen 1 request
    if hasattr(user, "_perms_cache_set"):
        return user._perms_cache_set

    key = _perm_cache_key(user.id)
    perms = cache.get(key)
    if perms is None:
        # 1 DB-hit: verzamel alles in één keer
        perms = set(user.get_all_permissions())
        cache.set(key, list(perms), PERM_TTL)
    else:
        perms = set(perms)

    user._perms_cache_set = perms
    return perms

def can(user, codename: str) -> bool:
    return bool(user.is_superuser or f"core.{codename}" in get_user_perms(user))
