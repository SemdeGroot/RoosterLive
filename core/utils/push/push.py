# core/utils/push.py
import os
import json
import base64
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from pywebpush import webpush, WebPushException

from core.models import PushSubscription, NativePushToken
from core.views._helpers import can, wants_push

# ============================================================
# TOGGLES (zet hier aan/uit, zonder settings.py te wijzigen)
# ============================================================
PUSH_ENABLE_WEBPUSH = True
PUSH_ENABLE_NATIVE_FCM = True

# ============================================================
# NATIVE PUSH (FCM) helpers
# ============================================================
try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except Exception:  # pragma: no cover
    firebase_admin = None
    credentials = None
    messaging = None


# Kies 1 vaste channel-id (moet ook in Android bestaan!)
ANDROID_CHANNEL_ID_HIGH = "GENERAL_HIGH"


def _ensure_firebase():
    """
    Init firebase_admin 1x. Service account komt uit ENV:
    FIREBASE_SERVICE_ACCOUNT_B64 = base64(json(serviceAccount))
    """
    if not PUSH_ENABLE_NATIVE_FCM:
        return
    if firebase_admin is None:
        return
    if getattr(firebase_admin, "_apps", None) and firebase_admin._apps:
        return

    b64 = os.environ.get("FIREBASE_SERVICE_ACCOUNT_B64")
    if not b64:
        return

    info = json.loads(base64.b64decode(b64).decode("utf-8"))
    firebase_admin.initialize_app(credentials.Certificate(info))


def _chunked(seq, size=500):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _send_native_push_to_users(payload: dict, users):
    """
    Stuur naar alle NativePushToken van deze users.
    payload verwacht keys: title, body, url, tag
    """
    if not PUSH_ENABLE_NATIVE_FCM:
        return
    _ensure_firebase()
    if firebase_admin is None or not (getattr(firebase_admin, "_apps", None) and firebase_admin._apps):
        return

    title = payload.get("title") or "Melding"
    body = payload.get("body") or ""

    data = {
        "url": str(payload.get("url") or ""),
        "tag": str(payload.get("tag") or ""),
    }

    tokens = list(
        NativePushToken.objects.filter(user__in=users)
        .exclude(token="")
        .values_list("token", flat=True)
        .distinct()
    )
    if not tokens:
        return

    for batch in _chunked(tokens, 500):
        msg = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data,
            tokens=batch,
            android=messaging.AndroidConfig(
                collapse_key=data["tag"] or None,
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id=ANDROID_CHANNEL_ID_HIGH,
                    sound="default",
                    icon="ic_stat_notification",
                ),
            ),
            apns=messaging.APNSConfig(
                headers={"apns-collapse-id": data["tag"]} if data["tag"] else {},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default")
                ),
            ),
        )

        resp = messaging.send_each_for_multicast(msg)

        # ongeldige tokens opruimen
        bad_tokens = []
        for t, r in zip(batch, resp.responses):
            if r.success:
                continue
            exc = r.exception
            msg_l = (str(exc) or "").lower()
            if "not registered" in msg_l or "unregistered" in msg_l:
                bad_tokens.append(t)

        if bad_tokens:
            NativePushToken.objects.filter(token__in=bad_tokens).delete()


# ============================================================
# WEB PUSH helpers (jouw bestaande logica blijft leidend)
# ============================================================
def _build_vapid_claims(endpoint: str) -> dict:
    parsed = urlparse(endpoint)
    aud = f"https://{parsed.netloc}"
    return {"sub": settings.VAPID_SUB, "aud": aud}


def _send_webpush(payload: dict, eligible_subs):
    if not PUSH_ENABLE_WEBPUSH:
        return

    for s in eligible_subs:
        claims = _build_vapid_claims(s.endpoint)
        try:
            webpush(
                subscription_info={
                    "endpoint": s.endpoint,
                    "keys": {"p256dh": s.p256dh, "auth": s.auth},
                },
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims=claims,
            )
        except WebPushException as e:
            status = getattr(e, "response", None).status_code if getattr(e, "response", None) else None
            if status in (404, 410, 403):
                s.delete()


# ============================================================
# Recipients (belangrijk!): native los van webpush bepalen
# ============================================================
def _eligible_users(permission_key: str, wants_key: str):
    """
    Vind users die OF webpush subs OF native tokens hebben,
    en filter met exact dezelfde checks als je nu gebruikt: can + wants_push.
    """
    User = get_user_model()
    qs = (
        User.objects.filter(
            Q(push_subscriptions__isnull=False) | Q(native_push_tokens__isnull=False)
        )
        .select_related("profile", "profile__notif_prefs")
        .distinct()
    )
    return [u for u in qs if can(u, permission_key) and wants_push(u, wants_key)]


def _send_both(payload: dict, eligible_subs, eligible_users_for_native):
    """
    - Webpush: naar eligible_subs (exact zoals voorheen)
    - Native: naar eligible_users_for_native (nieuw, onafhankelijk van web subs)
    """
    _send_webpush(payload, eligible_subs)
    _send_native_push_to_users(payload, eligible_users_for_native)


# ============================================================
# JOUW BESTAANDE FUNCTIES (logica ongewijzigd),
# alleen versturen gaat nu via _send_both(...)
# ============================================================
def send_roster_updated_push(iso_year: int, iso_week: int, monday_str: str, friday_str: str):
    today = timezone.localdate()
    cur_year, cur_week, _ = today.isocalendar()

    next_date = today + timedelta(weeks=1)
    next_year, next_week, _ = next_date.isocalendar()

    if iso_year == cur_year and iso_week == cur_week:
        body = "Er is een nieuw rooster voor deze week beschikbaar!"
    elif iso_year == next_year and iso_week == next_week:
        body = "Er is een nieuw rooster voor volgende week beschikbaar!"
    else:
        body = f"Er is een nieuw rooster voor week {iso_week} beschikbaar."

    payload = {
        "title": f"Nieuw rooster – week {iso_week}",
        "body": body,
        "url": f"/rooster/?monday={monday_str}",
        "tag": f"rooster-update-{iso_year}-{iso_week}",
    }

    subs = PushSubscription.objects.select_related("user", "user__profile", "user__profile__notif_prefs").all()
    eligible_subs = [s for s in subs if can(s.user, "can_view_roster") and wants_push(s.user, "push_new_roster")]

    eligible_users_native = _eligible_users("can_view_roster", "push_new_roster")
    _send_both(payload, eligible_subs, eligible_users_native)


def send_news_upload_push(uploader_first_name: str):
    if uploader_first_name:
        formatted_name = uploader_first_name.capitalize()
        body_text = f"Er is een nieuwsbericht geplaatst in de app door {formatted_name}."
    else:
        body_text = "Er is een nieuwsbericht geplaatst in de app."

    payload = {"title": "Nieuwtje!", "body": body_text, "url": "/nieuws/", "tag": "news-update"}

    subs = PushSubscription.objects.select_related("user", "user__profile", "user__profile__notif_prefs").all()
    eligible_subs = [s for s in subs if can(s.user, "can_view_news") and wants_push(s.user, "push_news_upload")]

    eligible_users_native = _eligible_users("can_view_news", "push_news_upload")
    _send_both(payload, eligible_subs, eligible_users_native)


def send_agenda_upload_push(category: str):
    if category == "outing":
        title = "Nieuw uitje!"
        body = "Er is een nieuw uitje toegevoegd aan de agenda. Ben je erbij?"
    else:
        title = "Nieuw in de agenda!"
        body = "Er is iets nieuws gepland in de agenda."

    payload = {"title": title, "body": body, "url": "/agenda/", "tag": "agenda-update"}

    subs = PushSubscription.objects.select_related("user", "user__profile", "user__profile__notif_prefs").all()
    eligible_subs = [s for s in subs if can(s.user, "can_view_agenda") and wants_push(s.user, "push_new_agenda")]

    eligible_users_native = _eligible_users("can_view_agenda", "push_new_agenda")
    _send_both(payload, eligible_subs, eligible_users_native)


def send_laatste_pot_push(item_naam: str):
    payload = {
        "title": "Laatste pot aangebroken!",
        "body": f"Middel: {item_naam}. Controleer of er besteld moet worden.",
        "url": "/baxter/laatste-potten/",
        "tag": "laatste-pot-update",
    }

    subs = PushSubscription.objects.select_related("user", "user__profile", "user__profile__notif_prefs").all()
    eligible_subs = [s for s in subs if can(s.user, "can_perform_bestellingen")]

    # native wants_push key? (je had hier geen wants_push check)
    # we houden dit exact gelijk: alleen can()
    User = get_user_model()
    qs = (
        User.objects.filter(Q(push_subscriptions__isnull=False) | Q(native_push_tokens__isnull=False))
        .select_related("profile", "profile__notif_prefs")
        .distinct()
    )
    eligible_users_native = [u for u in qs if can(u, "can_perform_bestellingen")]

    _send_both(payload, eligible_subs, eligible_users_native)


def _dienst_word(n: int) -> str:
    return "dienst" if int(n) == 1 else "diensten"


def send_user_shifts_changed_push(user_id: int, iso_year: int, iso_week: int, monday_str: str,
                                  added_count: int, changed_count: int, removed_count: int):
    total = int(added_count or 0) + int(changed_count or 0) + int(removed_count or 0)
    if total <= 0:
        return

    User = get_user_model()
    user = User.objects.filter(id=user_id).select_related("profile", "profile__notif_prefs").first()
    if not user:
        return

    today = timezone.localdate()
    cur_year, cur_week, _ = today.isocalendar()

    next_date = today + timedelta(weeks=1)
    next_year, next_week, _ = next_date.isocalendar()

    if iso_year == cur_year and iso_week == cur_week:
        week_label = "deze week"
    elif iso_year == next_year and iso_week == next_week:
        week_label = "volgende week"
    else:
        week_label = f"week {iso_week}"

    parts = []
    if int(added_count or 0) > 0:
        n = int(added_count)
        parts.append(f"{n} {_dienst_word(n)} toegewezen")
    if int(changed_count or 0) > 0:
        n = int(changed_count)
        parts.append(f"{n} {_dienst_word(n)} aangepast")
    if int(removed_count or 0) > 0:
        n = int(removed_count)
        parts.append(f"{n} {_dienst_word(n)} verwijderd")

    changes_text = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " en " + parts[-1]

    payload = {
        "title": "Diensten bijgewerkt",
        "body": f"Je diensten voor {week_label} zijn bijgewerkt: {changes_text}.",
        "url": f"/personeel/diensten/?monday={monday_str}",
        "tag": f"diensten-update-{iso_year}-{iso_week}-user-{user_id}",
    }

    subs = PushSubscription.objects.select_related("user", "user__profile", "user__profile__notif_prefs").filter(user_id=user_id)
    eligible_subs = [s for s in subs if can(s.user, "can_view_diensten") and wants_push(s.user, "push_dienst_changed")]

    eligible_users_native = []
    if can(user, "can_view_diensten") and wants_push(user, "push_dienst_changed"):
        eligible_users_native = [user]

    _send_both(payload, eligible_subs, eligible_users_native)


def send_uren_reminder_push(user_id, reminder_date):
    payload = {
        "title": "Herinnering: Uren doorgeven",
        "body": f"Herinnering: Je hebt nog geen uren doorgegeven voor {reminder_date.strftime('%B %Y')}. Vergeet dit niet in te dienen.",
        "url": "/uren-doorgeven/",
        "tag": f"uren-reminder-{reminder_date.year}-{reminder_date.month}",
    }

    subs = PushSubscription.objects.select_related("user", "user__profile", "user__profile__notif_prefs").filter(user_id=user_id)
    eligible_subs = [s for s in subs if can(s.user, "can_view_urendoorgeven") and wants_push(s.user, "push_uren_reminder")]

    User = get_user_model()
    user = User.objects.filter(id=user_id).select_related("profile", "profile__notif_prefs").first()
    eligible_users_native = []
    if user and can(user, "can_view_urendoorgeven") and wants_push(user, "push_uren_reminder"):
        eligible_users_native = [user]

    _send_both(payload, eligible_subs, eligible_users_native)


def send_birthday_push_for_user(user_id, birthday_name):
    payload = {
        "title": "Gefeliciteerd!",
        "body": f"Beste {birthday_name}, gefeliciteerd met je verjaardag! 🎉",
        "url": "/agenda/",
        "tag": f"birthday-update-{user_id}-user",
    }

    subs = PushSubscription.objects.select_related("user", "user__profile", "user__profile__notif_prefs").filter(user_id=user_id)
    eligible_subs = [s for s in subs if can(s.user, "can_view_agenda") and wants_push(s.user, "push_birthday_self")]

    User = get_user_model()
    user = User.objects.filter(id=user_id).select_related("profile", "profile__notif_prefs").first()
    eligible_users_native = []
    if user and can(user, "can_view_agenda") and wants_push(user, "push_birthday_self"):
        eligible_users_native = [user]

    _send_both(payload, eligible_subs, eligible_users_native)


def human_join(names: list[str]) -> str:
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} en {names[1]}"
    return f"{', '.join(names[:-1])} en {names[-1]}"


def is_zijn(names: list[str]) -> str:
    return "zijn" if len(names) != 1 else "is"


def send_birthday_push_for_others(birthday_user_ids: list[int], birthday_names: list[str]):
    if not birthday_names:
        return

    names_str = human_join(birthday_names)
    verb = is_zijn(birthday_names)

    payload = {
        "title": "Vandaag jarig 🎉",
        "body": f"Hoera! {names_str} {verb} vandaag jarig!",
        "url": "/agenda/",
        "tag": f"birthday-others-{timezone.localdate().isoformat()}",
    }

    subs = PushSubscription.objects.select_related("user", "user__profile", "user__profile__notif_prefs").exclude(user_id__in=birthday_user_ids)
    eligible_subs = [s for s in subs if can(s.user, "can_view_agenda") and wants_push(s.user, "push_birthday_apojansen")]

    eligible_users_native = _eligible_users("can_view_agenda", "push_birthday_apojansen")
    # exclude jarigen
    eligible_users_native = [u for u in eligible_users_native if u.id not in set(birthday_user_ids)]

    _send_both(payload, eligible_subs, eligible_users_native)

def send_test_push(user_id: int):
    User = get_user_model()
    user = User.objects.filter(id=user_id).select_related("profile", "profile__notif_prefs").first()
    if not user:
        return

    if not can(user, "can_access_profiel"):
        return

    prefs = getattr(user.profile, "notif_prefs", None)
    if not prefs or not prefs.push_enabled:
        return

    now = timezone.now()
    payload = {
        "title": "Testnotificatie",
        "body": "Dit is een testnotificatie!",
        "url": "/profiel/",
        "tag": f"test-push-{user_id}-{now.strftime('%Y%m%d%H%M%S')}",
    }

    # webpush: alleen deze user
    subs = PushSubscription.objects.select_related(
        "user", "user__profile", "user__profile__notif_prefs"
    ).filter(user_id=user_id)
    eligible_subs = [s for s in subs if can(s.user, "can_access_profiel") and s.user.profile.notif_prefs.push_enabled]

    # native: alleen deze user
    eligible_users_native = [user] if prefs.push_enabled else []

    _send_both(payload, eligible_subs, eligible_users_native)