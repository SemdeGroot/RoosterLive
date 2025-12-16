# core/utils/push.py
import json
from datetime import date, timedelta
from urllib.parse import urlparse

from pywebpush import webpush, WebPushException
from django.conf import settings
from django.utils import timezone

from core.models import PushSubscription
from core.views._helpers import can


def _build_vapid_claims(endpoint: str) -> dict:
    """
    Maak per subscription de juiste 'aud' claim:
    - FCM: https://fcm.googleapis.com
    - Apple: https://web.push.apple.com
    - generiek: 'https://' + netloc
    'exp' laten we aan pywebpush zelf over.
    """
    parsed = urlparse(endpoint)
    aud = f"https://{parsed.netloc}"  # bv. https://fcm.googleapis.com of https://web.push.apple.com
    return {
        "sub": settings.VAPID_SUB,
        "aud": aud,
    }


def send_roster_updated_push(
    iso_year: int,
    iso_week: int,
    monday_str: str,
    friday_str: str,
):
    """
    Stuur een web-push voor een nieuw rooster.
    - Alleen naar users die can_view_roster hebben.
    - Tekst in de notificatie hangt af van of het deze week, volgende week
      of een andere week is.
    """

    # Bepaal 'deze week' en 'volgende week' in ISO-weeknotatie
    today = timezone.localdate()
    cur_year, cur_week, _ = today.isocalendar()

    next_date = today + timedelta(weeks=1)
    next_year, next_week, _ = next_date.isocalendar()

    # Tekst voor de body afhankelijk van de week
    if iso_year == cur_year and iso_week == cur_week:
        body = "Er is een nieuw rooster voor deze week beschikbaar!"
    elif iso_year == next_year and iso_week == next_week:
        body = "Er is een nieuw rooster voor volgende week beschikbaar!"
    else:
        body = f"Er is een nieuw rooster voor week {iso_week} beschikbaar."

    payload = {
        "title": f"Nieuw rooster – week {iso_week}",
        "body": body,
        # URL blijft ISO zodat de view 'm goed kan parsen
        "url": f"/rooster/?monday={monday_str}",
        "tag": f"rooster-update-{iso_year}-{iso_week}",
    }

    # Alleen subscriptions waarvan de user het rooster mag zien
    subs = PushSubscription.objects.select_related("user").all()
    eligible_subs = [s for s in subs if can(s.user, "can_view_roster")]

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

            # Subscription ongeldig → opruimen
            if status in (404, 410, 403):
                s.delete()

def send_news_upload_push(uploader_first_name: str):
    """
    Stuur een web-push voor een nieuw nieuwsbericht.
    - Alleen naar users die can_view_news hebben.
    - Inclusief naam van uploader.
    """
    
    # Zorg voor een fallback als de naam leeg is, en capitalize zoals gevraagd
    if uploader_first_name:
        formatted_name = uploader_first_name.capitalize()
        body_text = f"Er is een nieuwsbericht geplaatst in de app door {formatted_name}"
    else:
        body_text = "Er is een nieuwsbericht geplaatst in de app."

    payload = {
        "title": "Nieuwtje!",
        "body": body_text,
        "url": "/nieuws/",
        "tag": "news-update",
    }

    # Haal subscriptions op en filter op permissie
    subs = PushSubscription.objects.select_related("user").all()
    eligible_subs = [s for s in subs if can(s.user, "can_view_news")]

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

            # Subscription ongeldig → opruimen
            if status in (404, 410, 403):
                s.delete()


def send_agenda_upload_push(category: str):
    """
    Stuur een web-push voor een nieuw agenda-item.
    - Alleen naar users die can_view_agenda hebben.
    - Tekst verschilt lichtjes per categorie.
    """
    
    # Vriendelijke tekst op basis van categorie
    if category == "outing":
        title = "Nieuw uitje!"
        body = "Er is een nieuw uitje toegevoegd aan de agenda. Ben je erbij?"
    else:
        title = "Nieuw in de agenda!"
        body = "Er is iets nieuws gepland in de agenda."

    payload = {
        "title": title,
        "body": body,
        "url": "/agenda/",
        "tag": "agenda-update",
    }

    # Haal subscriptions op en filter op permissie
    subs = PushSubscription.objects.select_related("user").all()
    eligible_subs = [s for s in subs if can(s.user, "can_view_agenda")]

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

            # Subscription ongeldig → opruimen
            if status in (404, 410, 403):
                s.delete()