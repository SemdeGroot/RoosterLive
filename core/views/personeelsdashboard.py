import json
from datetime import date, timedelta
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone, translation
from django.utils.formats import date_format
from django.views.decorators.http import require_POST
from django.urls import reverse

from ._helpers import can
from core.models import Availability, Location, Task, Shift
from core.views.mijnbeschikbaarheid import _monday_of_iso_week, _clamp_week


def _user_group(u):
    g = u.groups.first() if hasattr(u, "groups") else None
    return g.name if g else "Onbekend"


def _user_firstname_cap(u):
    fn = (u.first_name or "").strip()
    if fn:
        return fn[:1].upper() + fn[1:].lower()
    un = (getattr(u, "username", "") or "").strip()
    return un[:1].upper() + un[1:].lower() if un else "Onbekend"


@login_required
def personeelsdashboard_view(request):
    if not can(request.user, "can_view_beschikbaarheidsdashboard"):
        return HttpResponseForbidden("Geen toegang.")

    translation.activate("nl")
    today = timezone.localdate()
    WEEKS_AHEAD = 12

    min_monday = _monday_of_iso_week(today)
    max_monday = _monday_of_iso_week(today + timedelta(weeks=WEEKS_AHEAD))

    # ✅ Housekeeping
    Availability.objects.filter(date__lt=min_monday).delete()

    # Weekselectie
    qs_week = request.GET.get("week")
    qs_monday = request.GET.get("monday")

    if qs_monday:
        try:
            y, m, d = map(int, qs_monday.split("-"))
            monday = date(y, m, d)
        except Exception:
            monday = min_monday
    elif qs_week:
        try:
            y_str, w_str = qs_week.split("-W")
            monday = date.fromisocalendar(int(y_str), int(w_str), 1)
        except Exception:
            monday = min_monday
    else:
        monday = min_monday

    monday = _clamp_week(monday, min_monday, max_monday)

    # ✅ Maandag t/m Zaterdag (6 dagen)
    days = [monday + timedelta(days=i) for i in range(6)]
    week_end = monday + timedelta(days=5)

    # Dagselectie: day=0..5 (default 0)
    try:
        selected_day_idx = int(request.GET.get("day", "0"))
    except Exception:
        selected_day_idx = 0
    selected_day_idx = max(0, min(5, selected_day_idx))
    selected_day = monday + timedelta(days=selected_day_idx)

    prev_raw = monday - timedelta(weeks=1)
    next_raw = monday + timedelta(weeks=1)
    has_prev = prev_raw >= min_monday
    has_next = next_raw <= max_monday
    prev_monday = prev_raw if has_prev else min_monday
    next_monday = next_raw if has_next else max_monday

    av_qs = (
        Availability.objects
        .filter(date__in=days)
        .select_related("user")
        .prefetch_related("user__groups")
    )

    users = sorted(
        {av.user for av in av_qs},
        key=lambda u: (_user_group(u).lower(), _user_firstname_cap(u).lower())
    )

    # Matrix: morning/afternoon/evening
    matrix = defaultdict(lambda: {d: {"morning": False, "afternoon": False, "evening": False} for d in days})
    for av in av_qs:
        matrix[av.user][av.date]["morning"] = bool(getattr(av, "morning", False))
        matrix[av.user][av.date]["afternoon"] = bool(getattr(av, "afternoon", False))
        matrix[av.user][av.date]["evening"] = bool(getattr(av, "evening", False))

    # Tellen per dag
    counts = {d: {"morning": 0, "afternoon": 0, "evening": 0} for d in days}
    for u in users:
        for d in days:
            if matrix[u][d]["morning"]:
                counts[d]["morning"] += 1
            if matrix[u][d]["afternoon"]:
                counts[d]["afternoon"] += 1
            if matrix[u][d]["evening"]:
                counts[d]["evening"] += 1

    # Dag dropdown opties (Ma t/m Za)
    day_options = []
    for idx, d in enumerate(days):
        day_options.append({
            "idx": idx,
            "date": d,
            "iso": d.isoformat(),
            "weekday_label": date_format(d, "l").capitalize(),
        })

    selected_day_ctx = {
        "date": selected_day,
        "iso": selected_day.isoformat(),
        "weekday_label": date_format(selected_day, "l").capitalize(),
        "morning_count": counts[selected_day]["morning"],
        "afternoon_count": counts[selected_day]["afternoon"],
        "evening_count": counts[selected_day]["evening"],
    }

    rows = []
    selected_iso = selected_day.strftime("%Y-%m-%d")

    for u in users:
        is_morning = matrix[u][selected_day]["morning"]
        is_afternoon = matrix[u][selected_day]["afternoon"]
        is_evening = matrix[u][selected_day]["evening"]

        if not (is_morning or is_afternoon or is_evening):
            continue

        cell = {
            "date": selected_day,
            "morning": is_morning,
            "afternoon": is_afternoon,
            "evening": is_evening,
        }

        data_attrs_parts = [
            f'data-{selected_iso}-morning="{"1" if is_morning else "0"}"',
            f'data-{selected_iso}-afternoon="{"1" if is_afternoon else "0"}"',
            f'data-{selected_iso}-evening="{"1" if is_evening else "0"}"',
        ]

        rows.append({
            "user_id": u.id,
            "group": _user_group(u),
            "firstname": _user_firstname_cap(u),
            "cell": cell,
            "data_attrs": " ".join(data_attrs_parts),
        })

    # Week dropdown
    week_options = []
    cur = min_monday
    while cur <= max_monday:
        week_options.append({
            "value": cur.isoformat(),
            "start": cur,
            "end": cur + timedelta(days=5),
            "iso_week": cur.isocalendar()[1],
            "iso_year": cur.isocalendar()[0],
        })
        cur += timedelta(weeks=1)

    iso_year, iso_week, _ = monday.isocalendar()
    header_title = f"Week {iso_week} – {iso_year}"
    default_sort_slot = f"{selected_day.isoformat()}|morning"

    # ✅ Locations + Tasks voor actiepaneel
    locations = (
        Location.objects
        .all()
        .order_by("name")
        .prefetch_related("tasks")
    )
    locations_payload = []
    for loc in locations:
        locations_payload.append({
            "id": loc.id,
            "name": loc.name,
            "tasks": [{"id": t.id, "name": t.name} for t in loc.tasks.all().order_by("name")]
        })

    # ✅ Bestaande shifts (concept + accepted) voor geselecteerde dag
    shifts_qs = (
        Shift.objects
        .filter(date=selected_day)
        .select_related("user", "task", "task__location")
        .prefetch_related("user__groups")
        .order_by("period", "user__first_name", "user__username")
    )

    existing_shifts_payload = []
    for s in shifts_qs:
        existing_shifts_payload.append({
            "id": s.id,
            "user_id": s.user_id,
            "group": _user_group(s.user),
            "firstname": _user_firstname_cap(s.user),
            "date": s.date.isoformat(),
            "period": s.period,
            "status": getattr(s, "status", "concept"),
            "task_id": s.task_id,
            "task_name": s.task.name,
            "location_id": s.task.location_id,
            "location_name": s.task.location.name,
        })

    pd_data = {
        "selectedDate": selected_day.isoformat(),
        "locations": locations_payload,
        "existingShifts": existing_shifts_payload,
        "saveConceptUrl": reverse("pd_save_concept"),
        "deleteShiftUrl": reverse("pd_delete_shift"),
    }

    return render(request, "personeelsdashboard/index.html", {
        "monday": monday,
        "week_end": week_end,

        "day_options": day_options,
        "selected_day_idx": selected_day_idx,
        "selected_day_ctx": selected_day_ctx,

        "rows": rows,

        "week_options": week_options,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_monday": prev_monday,
        "next_monday": next_monday,

        "header_title": header_title,
        "default_sort_slot": default_sort_slot,

        "pd_data": pd_data,
    })


@login_required
@require_POST
def save_concept_shifts_api(request):
    """
    Body:
      { "items": [ { "user_id": 1, "date": "2025-12-27", "period": "morning", "task_id": 5 }, ... ] }

    Behaviour:
      - Upsert op (user, date, period)
      - Zet status altijd op 'concept'
      - Als shift eerst 'accepted' was en je wijzigt taak -> wordt concept na save
    """
    if not can(request.user, "can_view_beschikbaarheidsdashboard"):
        return JsonResponse({"ok": False, "error": "Geen toegang."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Ongeldige JSON."}, status=400)

    items = payload.get("items") or []
    if not isinstance(items, list):
        return JsonResponse({"ok": False, "error": "items moet een lijst zijn."}, status=400)

    saved = []
    for it in items:
        try:
            user_id = int(it["user_id"])
            dt = date.fromisoformat(it["date"])
            period = it["period"]
            task_id = int(it["task_id"])
        except Exception:
            continue

        if period not in ("morning", "afternoon", "evening"):
            continue

        obj, _created = Shift.objects.update_or_create(
            user_id=user_id,
            date=dt,
            period=period,
            defaults={
                "task_id": task_id,
                "status": "concept",
            }
        )

        # voor de UI meteen volledige info teruggeven
        obj = (
            Shift.objects
            .select_related("task", "task__location")
            .get(id=obj.id)
        )

        saved.append({
            "shift_id": obj.id,
            "user_id": obj.user_id,
            "date": obj.date.isoformat(),
            "period": obj.period,
            "status": getattr(obj, "status", "concept"),
            "task_id": obj.task_id,
            "task_name": obj.task.name,
            "location_id": obj.task.location_id,
            "location_name": obj.task.location.name,
        })

    return JsonResponse({"ok": True, "saved": saved})


@login_required
@require_POST
def delete_shift_api(request):
    """
    Body:
      { "shift_id": 123 }

    Delete concept/accepted shift.
    """
    if not can(request.user, "can_view_beschikbaarheidsdashboard"):
        return JsonResponse({"ok": False, "error": "Geen toegang."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Ongeldige JSON."}, status=400)

    shift_id = payload.get("shift_id")
    if not shift_id:
        return JsonResponse({"ok": False, "error": "shift_id ontbreekt."}, status=400)

    try:
        s = Shift.objects.get(id=int(shift_id))
    except Shift.DoesNotExist:
        return JsonResponse({"ok": True, "deleted": True})  # idempotent

    s.delete()
    return JsonResponse({"ok": True, "deleted": True, "shift_id": int(shift_id)})