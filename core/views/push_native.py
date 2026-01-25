# core/views/push_native.py
import json
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.db import transaction

from core.models import NativePushToken

@login_required
@require_POST
def native_push_subscribe(request):
    try:
        data = json.loads(request.body.decode("utf-8")) or {}
        token = (data.get("token") or "").strip()
        platform = (data.get("platform") or "").strip().lower()
        device_id = (data.get("device_id") or "").strip()
        user_agent = (data.get("user_agent") or request.META.get("HTTP_USER_AGENT", "") or "")[:300]

        if not token:
            return HttpResponseBadRequest("Missing token")

        with transaction.atomic():
            # Optioneel: per user+device slechts 1 token “actief”
            if device_id:
                NativePushToken.objects.filter(
                    user=request.user,
                    device_id=device_id,
                ).exclude(token=token).delete()

            obj, created = NativePushToken.objects.update_or_create(
                token=token,
                defaults={
                    "user": request.user,
                    "platform": platform[:20],
                    "device_id": device_id[:128],
                    "user_agent": user_agent,
                },
            )

        return JsonResponse({"ok": True, "created": created})
    except Exception as e:
        return HttpResponseBadRequest(str(e))


@login_required
@require_POST
def native_push_unsubscribe(request):
    try:
        data = json.loads(request.body.decode("utf-8")) or {}
        token = (data.get("token") or "").strip()
        if not token:
            return HttpResponseBadRequest("Missing token")

        NativePushToken.objects.filter(user=request.user, token=token).delete()
        return JsonResponse({"ok": True})
    except Exception as e:
        return HttpResponseBadRequest(str(e))
