# core/utils/push.py
import json
from pywebpush import webpush, WebPushException
from django.conf import settings
from core.models import PushSubscription

def send_roster_updated_push():
    payload = {
        "title": "Rooster",
        "body": "Er is een nieuw rooster beschikbaar!",
        "url": "/rooster/",
        "tag": "rooster-update",   # vervangt oudere notificatie met dezelfde tag
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
            # invalid/expired? opruimen
            if getattr(e, "response", None) and e.response.status_code in (404, 410):
                s.delete()
