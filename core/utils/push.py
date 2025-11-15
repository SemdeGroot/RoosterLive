# core/utils/push.py
import json
from datetime import date

from pywebpush import webpush, WebPushException
from django.conf import settings
from core.models import PushSubscription


def send_roster_updated_push(iso_year: int, iso_week: int,
                             monday_str: str, friday_str: str):
    """
    monday_str / friday_str komen binnen als ISO (YYYY-MM-DD).
    Voor de body formatteren we:
    - maandag: dd-mm
    - vrijdag: dd-mm-YYYY
    """
    monday = date.fromisoformat(monday_str)
    friday = date.fromisoformat(friday_str)

    monday_nl = monday.strftime("%d-%m")        # zonder jaar
    friday_nl = friday.strftime("%d-%m-%Y")     # met jaar

    payload = {
        "title": f"Nieuw rooster – week {iso_week}",
        "body": f"Er is een nieuw rooster voor week {iso_week} ({monday_nl}–{friday_nl}) beschikbaar!",
        # URL blijft ISO zodat view 'm goed kan parsen
        "url": f"/rooster/?monday={monday_str}",
        "tag": f"rooster-update-{iso_year}-{iso_week}",
    }

    subs = PushSubscription.objects.select_related("user").all()
    for s in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": s.endpoint,
                    "keys": {"p256dh": s.p256dh, "auth": s.auth},
                },
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims=settings.VAPID_CLAIMS,
            )
        except WebPushException as e:
            if getattr(e, "response", None) and e.response.status_code in (404, 410):
                s.delete()