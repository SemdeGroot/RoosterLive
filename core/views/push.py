# core/views/push.py
import json
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token

from core.models import PushSubscription

@login_required
@require_POST
def push_subscribe(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        sub = data.get("subscription", {})
        endpoint = sub.get("endpoint")
        keys = sub.get("keys", {})
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")
        if not (endpoint and p256dh and auth):
            return HttpResponseBadRequest("Invalid subscription")
        # upsert (zelfde endpoint)
        obj, _created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300],
            },
        )
        return JsonResponse({"ok": True})
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