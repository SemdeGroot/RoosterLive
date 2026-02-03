# core/views/profiel.py
from __future__ import annotations
import json
import io

import boto3
from PIL import Image
from django.views.decorators.http import require_POST
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from core.forms import NotificationPreferencesForm
from core.models import NotificationPreferences, UserProfile
from core.views._helpers import can
from core.views._upload_helpers import hash_bytes, read_upload_bytes, _save_bytes, _delete_path
from core.tasks import send_test_push_task

# ===== Rekognition settings =====
REKOGNITION_MIN_CONF = 75

REKOGNITION_BLOCKED_PARENTS = [
    "Explicit Nudity",
    "Suggestive",
    "Violence",
    "Visually Disturbing",
    "Hate Symbols",
    "Drugs",
]

def _rekognition_client():
    region = getattr(settings, "AWS_REKOGNITION_REGION_NAME", "eu-central-1")
    kw = {"region_name": region}

    if getattr(settings, "AWS_REKOGNITION_ACCESS_KEY_ID", "") and getattr(settings, "AWS_REKOGNITION_SECRET_ACCESS_KEY", ""):
        kw.update({
            "aws_access_key_id": settings.AWS_REKOGNITION_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_REKOGNITION_SECRET_ACCESS_KEY,
        })

    return boto3.client("rekognition", **kw)


def _webp_or_any_to_jpeg_bytes(image_bytes: bytes) -> bytes:
    """
    Rekognition Image APIs accepteren JPEG/PNG. WebP dus omzetten.
    """
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        rgb = bg.convert("RGB")

        out = io.BytesIO()
        rgb.save(out, format="JPEG", quality=92, optimize=True)
        return out.getvalue()


def _normalize_avatar_to_webp_256(image_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = im.convert("RGBA")
        w, h = im.size

        # Alleen croppen als het niet al vierkant is (zodat client-crop intact blijft)
        if w != h:
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            im = im.crop((left, top, left + side, top + side))

        im = im.resize((256, 256), Image.LANCZOS)

        bg = Image.new("RGBA", (256, 256), (255, 255, 255, 255))
        bg.alpha_composite(im)
        rgb = bg.convert("RGB")

        out = io.BytesIO()
        rgb.save(out, format="WEBP", quality=85, method=4)
        return out.getvalue()

def _is_allowed_by_rekognition(image_bytes_any: bytes) -> tuple[bool, list[str]]:
    """
    Returns: (allowed, reasons)
    """
    jpeg = _webp_or_any_to_jpeg_bytes(image_bytes_any)
    client = _rekognition_client()

    resp = client.detect_moderation_labels(
        Image={"Bytes": jpeg},
        MinConfidence=REKOGNITION_MIN_CONF,
    )

    labels = resp.get("ModerationLabels", []) or []
    hits: list[str] = []

    for lb in labels:
        parent = (lb.get("ParentName") or "").strip()
        name = (lb.get("Name") or "").strip()
        conf = lb.get("Confidence")

        if parent in REKOGNITION_BLOCKED_PARENTS or name in REKOGNITION_BLOCKED_PARENTS:
            if conf is not None:
                hits.append(f"{parent or name} ({conf:.1f}%)")
            else:
                hits.append(parent or name)

    return (len(hits) == 0), hits


@login_required
def profiel_index(request):
    if not can(request.user, "can_access_profiel"):
        return HttpResponseForbidden("Geen toegang.")

    profile: UserProfile = request.user.profile
    prefs, _ = NotificationPreferences.objects.get_or_create(profile=profile)

    if request.method == "POST":
        form_kind = (request.POST.get("form_kind") or "").strip()

        if form_kind == "prefs":
            form = NotificationPreferencesForm(request.POST, instance=prefs)
            if form.is_valid():
                form.save()
                messages.success(request, "Notificatievoorkeuren opgeslagen.")
                return redirect(request.path)
            else:
                messages.error(request, "Kon notificatievoorkeuren niet opslaan.")

        elif form_kind == "test_push":
            if not prefs.push_enabled:
                messages.error(request, "Push meldingen staan uit. Zet ze aan om een testnotificatie te ontvangen.")
                return redirect(request.path)

            from core.tasks import send_test_push_task
            send_test_push_task.delay(request.user.id)

            messages.success(request, "Testnotificatie is verstuurd (queued).")
            return redirect(request.path)

        else:
            form = NotificationPreferencesForm(instance=prefs)
    else:
        form = NotificationPreferencesForm(instance=prefs)

    return render(request, "profiel/index.html", {
        "profile": profile,
        "user": request.user,
        "prefs": prefs,
        "prefs_form": form,
    })

@login_required
def avatar_upload(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed.", "flash": {"level": "error", "text": "Ongeldige methode."}}, status=405)

    if not can(request.user, "can_access_profiel"):
        return JsonResponse({"error": "Geen rechten.", "flash": {"level": "error", "text": "Geen rechten om profiel te wijzigen."}}, status=403)

    f = request.FILES.get("avatar")
    if not f:
        return JsonResponse({"error": "Geen bestand ontvangen.", "flash": {"level": "error", "text": "Geen bestand ontvangen."}}, status=400)

    if f.size > 5 * 1024 * 1024:
        return JsonResponse({"error": "Bestand te groot (max 5MB).", "flash": {"level": "error", "text": "Bestand te groot (max 5MB)."}}, status=400)

    raw = read_upload_bytes(f)

    # 1) Normaliseer server-side naar 256x256 WEBP
    try:
        webp_256 = _normalize_avatar_to_webp_256(raw)
    except Exception:
        return JsonResponse({"error": "Ongeldig afbeeldingsbestand.", "flash": {"level": "error", "text": "Ongeldig afbeeldingsbestand."}}, status=400)

    # 2) Moderation check (Rekognition)
    try:
        ok, reasons = _is_allowed_by_rekognition(webp_256)
        if not ok:
            return JsonResponse({
                "error": "Profielfoto afgekeurd (ongepaste content).",
                "details": reasons[:5],
                "flash": {"level": "error", "text": "Profielfoto afgekeurd (ongepaste content)."},
            }, status=400)
    except Exception:
        return JsonResponse({"error": "Moderatie-check mislukt.", "flash": {"level": "error", "text": "Moderatie-check mislukt. Probeer later opnieuw."}}, status=500)

    # 3) Content hash → immutable caching
    h = hash_bytes(webp_256)
    user_id = request.user.id
    rel_path = f"avatars/u{user_id}/avatar.{h}.webp"

    profile: UserProfile = request.user.profile

    # 4) Oude file verwijderen
    if profile.avatar and profile.avatar.name and profile.avatar.name != rel_path:
        _delete_path(profile.avatar.name)

    # 5) Save bytes
    _save_bytes(rel_path, webp_256)

    # 6) Model updaten
    profile.avatar.name = rel_path
    profile.avatar_hash = h
    profile.avatar_updated_at = timezone.now()
    profile.save(update_fields=["avatar", "avatar_hash", "avatar_updated_at"])

    return JsonResponse({
        "avatar_url": profile.avatar.url,
        "flash": {"level": "success", "text": "Profielfoto opgeslagen."},
    })


@login_required
def avatar_remove(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed.", "flash": {"level": "error", "text": "Ongeldige methode."}}, status=405)

    if not can(request.user, "can_access_profiel"):
        return JsonResponse({"error": "Geen rechten.", "flash": {"level": "error", "text": "Geen rechten om profiel te wijzigen."}}, status=403)

    profile: UserProfile = request.user.profile
    if profile.avatar and profile.avatar.name:
        _delete_path(profile.avatar.name)

    profile.avatar = None
    profile.avatar_hash = ""
    profile.avatar_updated_at = timezone.now()
    profile.save(update_fields=["avatar", "avatar_hash", "avatar_updated_at"])

    return JsonResponse({
        "avatar_url": settings.STATIC_URL + "img/user.svg",
        "flash": {"level": "success", "text": "Profielfoto verwijderd."},
    })

@require_POST
@login_required
def profiel_update_settings(request):
    if not can(request.user, "can_access_profiel"):
        return JsonResponse({"error": "Geen toegang."}, status=403)

    profile: UserProfile = request.user.profile
    prefs, _ = NotificationPreferences.objects.get_or_create(profile=profile)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Ongeldige JSON."}, status=400)

    key = (payload.get("key") or "").strip()
    value = payload.get("value")

    # Only allow boolean toggles
    if not isinstance(value, bool):
        return JsonResponse({"error": "Value must be boolean."}, status=400)

    # Map keys -> model fields
    PROFILE_FIELDS = {"haptics_enabled"}
    PREF_FIELDS = {
        "push_enabled", "push_new_roster", "push_new_agenda", "push_news_upload",
        "push_dienst_changed", "push_birthday_self", "push_birthday_apojansen",
        "push_uren_reminder",
        "email_enabled", "email_birthday_self", "email_uren_reminder",
        "email_diensten_overzicht",
    }

    if key in PROFILE_FIELDS:
        setattr(profile, key, value)
        profile.save(update_fields=[key])
        return JsonResponse({"ok": True})

    if key in PREF_FIELDS:
        setattr(prefs, key, value)
        prefs.save(update_fields=[key])
        return JsonResponse({"ok": True})

    return JsonResponse({"error": "Onbekende setting."}, status=400)