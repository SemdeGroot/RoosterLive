# core/views/push.py
import json
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token
from django.db import transaction

from core.models import PushSubscription

@login_required
@require_POST
def push_subscribe(request):
    try:
        data = json.loads(request.body.decode("utf-8")) or {}
        sub = data.get("subscription", {}) or {}
        endpoint = sub.get("endpoint")
        keys = sub.get("keys", {}) or {}
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")

        if not (endpoint and p256dh and auth):
            return HttpResponseBadRequest("Invalid subscription")

        # device-hash en user-agent (device-hash komt uit de frontend)
        device_hash = (data.get("device_hash") or "").strip()
        user_agent = (data.get("user_agent")
                      or request.META.get("HTTP_USER_AGENT", "")
                      or "")[:300]

        with transaction.atomic():

            # Upsert op endpoint (zoals je al deed)
            obj, created = PushSubscription.objects.update_or_create(
                endpoint=endpoint,
                defaults={
                    "user": request.user,
                    "p256dh": p256dh,
                    "auth": auth,
                    "user_agent": user_agent,
                    "device_hash": device_hash[:64] if device_hash else "",
                },
            )

        return JsonResponse({"ok": True, "created": created})
    except Exception as e:
        return HttpResponseBadRequest(str(e))

@login_required
@require_POST
def push_unsubscribe(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        endpoint = data.get("endpoint")
        if not endpoint:
            return HttpResponseBadRequest("Missing endpoint")
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return JsonResponse({"ok": True})
    except Exception as e:
        return HttpResponseBadRequest(str(e))