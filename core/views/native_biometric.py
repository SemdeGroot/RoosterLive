# core/views/native_biometric.py
from __future__ import annotations
from urllib.parse import urlencode
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Optional
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import NativeBiometricDevice
from core.forms import IdentifierAuthenticationForm

# -------------------------
# Config helpers
# -------------------------

def _pepper() -> str:
    """
    Extra server-side 'pepper' bovenop de secret hashing.
    Zet dit als een vaste string in settings.py:
      NATIVE_BIOMETRIC_PEPPER = "..."
    """
    return getattr(settings, "NATIVE_BIOMETRIC_PEPPER", settings.SECRET_KEY)


def _hash_secret(device_secret: str) -> str:
    """
    Hash device_secret met SHA-256 + pepper.
    Output: hex string.
    """
    data = (device_secret or "").encode("utf-8")
    pep = _pepper().encode("utf-8")
    return hashlib.sha256(pep + b"|" + data).hexdigest()


def _safe_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a or "", b or "")


def _client_ip(request: HttpRequest) -> str:
    # Simpel, werkt intern meestal goed. Als je reverse proxy gebruikt: pas aan.
    return request.META.get("REMOTE_ADDR", "") or ""


# -------------------------
# (Heel) simpele rate limit
# -------------------------
# Voor intern is dit vaak genoeg. Als je al django-ratelimit gebruikt: vervang hiermee.

@dataclass
class _RateState:
    count: int
    reset_at_ts: float

def _rate_key(device_id: str, ip: str) -> str:
    return f"nbio:{device_id}:{ip}"

def _rate_limit_ok(request: HttpRequest, device_id: str, window_seconds: int = 60, max_attempts: int = 10) -> bool:
    """
    Max max_attempts per window_seconds per (device_id + ip) in de session.
    (Niet perfect bij multi-process, maar voor intern + simpel ok.)
    """
    ip = _client_ip(request)
    key = _rate_key(device_id, ip)
    now = timezone.now().timestamp()

    st = request.session.get(key)
    if not st:
        request.session[key] = {"count": 1, "reset_at_ts": now + window_seconds}
        return True

    count = int(st.get("count", 0))
    reset_at_ts = float(st.get("reset_at_ts", 0))

    if now >= reset_at_ts:
        request.session[key] = {"count": 1, "reset_at_ts": now + window_seconds}
        return True

    if count >= max_attempts:
        return False

    st["count"] = count + 1
    request.session[key] = st
    return True


# -------------------------
# Endpoint A: Enable / Pair
# -------------------------
@require_POST
@login_required
def native_biometric_enable(request: HttpRequest):
    """
    Koppelt een device aan user voor biometrische login.
    Verwacht JSON:
      {
        "device_id": "...",
        "device_secret": "...",
        "platform": "ios|android|other",
        "nickname": "..."
      }
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    device_id = (body.get("device_id") or "").strip()
    device_secret = (body.get("device_secret") or "").strip()
    platform = (body.get("platform") or "other").strip().lower()
    nickname = (body.get("nickname") or "").strip()

    if not device_id or not device_secret:
        return JsonResponse({"ok": False, "error": "device_id en device_secret zijn verplicht"}, status=400)

    if platform not in {"ios", "android", "other"}:
        platform = "other"

    secret_hash = _hash_secret(device_secret)

    obj, created = NativeBiometricDevice.objects.update_or_create(
        user=request.user,
        device_id=device_id,
        defaults={
            "secret_hash": secret_hash,
            "platform": platform,
            "nickname": nickname,
            "is_active": True,
            "revoked_at": None,
            "last_used_at": timezone.now(),
        },
    )

    # Bij update kun je optioneel secret_version verhogen (rotatie)
    if not created:
        obj.secret_version = (obj.secret_version or 1) + 1
        obj.save(update_fields=["secret_version"])

    return JsonResponse({"ok": True, "created": created})


# -------------------------
# Endpoint B: Login
# -------------------------
@require_POST
def native_biometric_login(request: HttpRequest):
    """
    Biometrische login voor WebView:
    App unlockt secret via biometrie en stuurt device_id + secret.
    Server logt user in (Django session).

    Verwacht JSON:
      {
        "device_id": "...",
        "device_secret": "..."
      }
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    device_id = (body.get("device_id") or "").strip()
    device_secret = (body.get("device_secret") or "").strip()
    next_url = body.get("next") or "/"

    if not device_id or not device_secret:
        return JsonResponse({"ok": False, "error": "device_id en device_secret zijn verplicht"}, status=400)

    # Rate limit (simpel)
    if not _rate_limit_ok(request, device_id=device_id, window_seconds=60, max_attempts=10):
        return JsonResponse({"ok": False, "error": "Te veel pogingen, probeer later opnieuw."}, status=429)

    # Vind actieve device record(s)
    qs = NativeBiometricDevice.objects.select_related("user").filter(device_id=device_id, is_active=True)
    dev: Optional[NativeBiometricDevice] = qs.first()
    if not dev:
        return JsonResponse({"ok": False, "error": "Onbekend device"}, status=400)

    expected = dev.secret_hash
    got = _hash_secret(device_secret)

    if not _safe_equals(expected, got):
        return JsonResponse({"ok": False, "error": "Biometrische login mislukt"}, status=400)

    # Login → session cookie
    user = dev.user
    login(request, user)

    dev.last_used_at = timezone.now()
    dev.save(update_fields=["last_used_at"])

    next_url = body.get("next") or "/"
    return JsonResponse({"ok": True, "redirect_url": next_url})



# -------------------------
# Endpoint C: Revoke device (optioneel maar aan te raden)
# -------------------------
@require_POST
@login_required
def native_biometric_revoke(request: HttpRequest):
    """
    User kan een gekoppeld device intrekken.
    Verwacht JSON: {"device_id":"..."}
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    device_id = (body.get("device_id") or "").strip()
    if not device_id:
        return JsonResponse({"ok": False, "error": "device_id is verplicht"}, status=400)

    try:
        dev = NativeBiometricDevice.objects.get(user=request.user, device_id=device_id, is_active=True)
    except NativeBiometricDevice.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Device niet gevonden"}, status=404)

    dev.revoke()
    return JsonResponse({"ok": True})

@require_POST
@login_required
def native_biometric_skip(request: HttpRequest):
    # 1x per sessie niet meer offeren
    request.session["native_bio_skip_offer"] = True

    # (optioneel) je device_id stuff mag blijven, maar is niet nodig voor session-only
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": True})

    device_id = (body.get("device_id") or "").strip()
    if device_id:
        skipped = request.session.get("native_bio_skip_devices", {})
        skipped[device_id] = True
        request.session["native_bio_skip_devices"] = skipped

    return JsonResponse({"ok": True})

@require_POST
def native_biometric_password_login(request: HttpRequest):
    """
    Stap 1 zoals passkeys:
    - valideert username + password
    - checkt of er een actieve NativeBiometricDevice bestaat voor (user, device_id)
    - retourneert of we native bio flow moeten starten

    Verwacht JSON:
      {
        "username": "...",
        "password": "...",
        "device_id": "...",
        "next": "/..."
      }
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    device_id = (body.get("device_id") or "").strip()
    next_url = body.get("next") or "/"

    if not username or not password:
        return JsonResponse({"ok": False, "error": "Onjuiste gebruikersnaam of wachtwoord"}, status=400)

    # valideer credentials via jouw IdentifierAuthenticationForm (zelfde stijl als passkeys)
    form = IdentifierAuthenticationForm(
        request=request,
        data={"username": username, "password": password},
    )
    if not form.is_valid():
        return JsonResponse({"ok": False, "error": "Onjuiste gebruikersnaam of wachtwoord"}, status=400)

    user = form.get_user()
    if user is None:
        return JsonResponse({"ok": False, "error": "Onjuiste gebruikersnaam of wachtwoord"}, status=400)

    # Als geen device_id → kunnen we niet native bio doen
    if not device_id:
        return JsonResponse({"ok": True, "has_native_bio": False, "redirect_url": next_url})

    has_native_bio = NativeBiometricDevice.objects.filter(
        user=user,
        device_id=device_id,
        is_active=True
    ).exists()

    return JsonResponse({"ok": True, "has_native_bio": bool(has_native_bio), "redirect_url": next_url})
