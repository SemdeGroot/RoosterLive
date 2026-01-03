import json
from datetime import date, timedelta
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone, translation
from django.utils.formats import date_format
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.db.models import Prefetch
from django.db import transaction
from django.core.cache import cache

from ._helpers import can
from core.models import Availability, Location, Task, Shift, ShiftDraft
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

_DAY_PREFIX = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat"}

def _task_min_for(task, dt, period: str) -> int:
    """
    Return minimale bezetting voor task op datum dt voor period.
    """
    prefix = _DAY_PREFIX.get(dt.weekday())
    if not prefix:
        return 0
    return int(getattr(task, f"min_{prefix}_{period}", 0) or 0)

@login_required
def personeelsdashboard_view(request):
    if not can(request.user, "can_view_beschikbaarheidsdashboard"):
        return HttpResponseForbidden("Geen toegang.")

    translation.activate("nl")
    today = timezone.localdate()
    WEEKS_AHEAD = 12

    min_monday = _monday_of_iso_week(today)
    max_monday = _monday_of_iso_week(today + timedelta(weeks=WEEKS_AHEAD))

    Availability.objects.filter(date__lt=min_monday).delete()

    # Weekselectie (ongewijzigd) ...
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

    days = [monday + timedelta(days=i) for i in range(6)]
    week_end = monday + timedelta(days=5)

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

    matrix = defaultdict(lambda: {d: {"morning": False, "afternoon": False, "evening": False} for d in days})
    for av in av_qs:
        matrix[av.user][av.date]["morning"] = bool(getattr(av, "morning", False))
        matrix[av.user][av.date]["afternoon"] = bool(getattr(av, "afternoon", False))
        matrix[av.user][av.date]["evening"] = bool(getattr(av, "evening", False))

    counts = {d: {"morning": 0, "afternoon": 0, "evening": 0} for d in days}
    for u in users:
        for d in days:
            if matrix[u][d]["morning"]:
                counts[d]["morning"] += 1
            if matrix[u][d]["afternoon"]:
                counts[d]["afternoon"] += 1
            if matrix[u][d]["evening"]:
                counts[d]["evening"] += 1

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

        data_attrs_parts = [
            f'data-{selected_iso}-morning="{"1" if is_morning else "0"}"',
            f'data-{selected_iso}-afternoon="{"1" if is_afternoon else "0"}"',
            f'data-{selected_iso}-evening="{"1" if is_evening else "0"}"',
        ]

        rows.append({
            "user_id": u.id,
            "group": _user_group(u),
            "firstname": _user_firstname_cap(u),
            "cell": {"date": selected_day, "morning": is_morning, "afternoon": is_afternoon, "evening": is_evening},
            "data_attrs": " ".join(data_attrs_parts),
        })

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

    locations = (
        Location.objects
        .all()
        .order_by("name")
        .prefetch_related(Prefetch("tasks", queryset=Task.objects.order_by("name")))
    )

    overall_min = {"morning": 0, "afternoon": 0, "evening": 0}
    locations_payload = []
    for loc in locations:
        tasks_payload = []
        loc_min = {"morning": 0, "afternoon": 0, "evening": 0}

        for t in loc.tasks.all():
            tmin = {
                "morning": _task_min_for(t, selected_day, "morning"),
                "afternoon": _task_min_for(t, selected_day, "afternoon"),
                "evening": _task_min_for(t, selected_day, "evening"),
            }
            loc_min["morning"] += tmin["morning"]
            loc_min["afternoon"] += tmin["afternoon"]
            loc_min["evening"] += tmin["evening"]

            tasks_payload.append({"id": t.id, "name": t.name, "min": tmin})

        locations_payload.append({"id": loc.id, "name": loc.name, "min": loc_min, "tasks": tasks_payload})

    # Published shifts voor geselecteerde dag (bron voor users)
    published_qs = (
        Shift.objects
        .filter(date=selected_day)
        .select_related("user", "task", "task__location")
        .prefetch_related("user__groups")
        .order_by("period", "user__first_name", "user__username")
    )

    published_payload = []
    for s in published_qs:
        published_payload.append({
            "id": s.id,
            "user_id": s.user_id,
            "group": _user_group(s.user),
            "firstname": _user_firstname_cap(s.user),
            "date": s.date.isoformat(),
            "period": s.period,
            "task_id": s.task_id,
            "task_name": s.task.name,
            "location_id": s.task.location_id,
            "location_name": s.task.location.name,
        })

    # Draft shifts voor geselecteerde dag (wat admin nog niet gepubliceerd heeft)
    drafts_qs = (
        ShiftDraft.objects
        .filter(date=selected_day)
        .select_related("user", "task", "task__location")
        .prefetch_related("user__groups")
        .order_by("period", "user__first_name", "user__username")
    )

    draft_payload = []
    for d in drafts_qs:
        task = d.task
        draft_payload.append({
            "id": d.id,
            "user_id": d.user_id,
            "group": _user_group(d.user),
            "firstname": _user_firstname_cap(d.user),
            "date": d.date.isoformat(),
            "period": d.period,
            "action": d.action,              # "upsert" | "delete"
            "task_id": task.id if task else None,
            "task_name": task.name if task else None,
            "location_id": task.location_id if task else None,
            "location_name": task.location.name if task else None,
        })

    pd_data = {
        "selectedDate": selected_day.isoformat(),
        "weekStart": monday.isoformat(),
        "weekEnd": week_end.isoformat(),

        "locations": locations_payload,
        "overallMin": overall_min,

        "publishedShifts": published_payload,
        "draftShifts": draft_payload,

        "saveConceptUrl": reverse("pd_save_concept"),
        "deleteShiftUrl": reverse("pd_delete_shift"),
        "publishUrl": reverse("pd_publish_shifts"),
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

        obj, _ = ShiftDraft.objects.update_or_create(
            user_id=user_id,
            date=dt,
            period=period,
            defaults={
                "task_id": task_id,
                "action": "upsert",
            }
        )

        obj = (
            ShiftDraft.objects
            .select_related("task", "task__location", "user")
            .get(id=obj.id)
        )

        saved.append({
            "draft_id": obj.id,
            "user_id": obj.user_id,
            "date": obj.date.isoformat(),
            "period": obj.period,
            "action": obj.action,
            "task_id": obj.task_id,
            "task_name": obj.task.name if obj.task else None,
            "location_id": obj.task.location_id if obj.task else None,
            "location_name": obj.task.location.name if obj.task else None,
        })

    return JsonResponse({"ok": True, "saved": saved})

@login_required
@require_POST
def delete_shift_api(request):
    """
    Body: { "user_id": 1, "date": "YYYY-MM-DD", "period": "morning" }
    Behaviour:
      - als er al een draft bestaat (upsert of delete) -> draft verwijderen (undo)
      - anders -> draft delete maken (pending delete van published)
    """
    if not can(request.user, "can_view_beschikbaarheidsdashboard"):
        return JsonResponse({"ok": False, "error": "Geen toegang."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Ongeldige JSON."}, status=400)

    try:
        user_id = int(payload.get("user_id"))
        d = date.fromisoformat(payload.get("date"))
        period = str(payload.get("period") or "")
    except Exception:
        return JsonResponse({"ok": False, "error": "user_id/date/period ongeldig."}, status=400)

    if period not in ("morning", "afternoon", "evening"):
        return JsonResponse({"ok": False, "error": "Ongeldige period."}, status=400)

    draft = ShiftDraft.objects.filter(user_id=user_id, date=d, period=period).first()

    if draft:
        # undo draft
        draft.delete()
        return JsonResponse({"ok": True, "mode": "undone"})
    else:
        # mark pending delete (published blijft bestaan totdat publish)
        obj, _ = ShiftDraft.objects.update_or_create(
            user_id=user_id,
            date=d,
            period=period,
            defaults={"action": "delete", "task": None}
        )
        return JsonResponse({"ok": True, "mode": "marked_delete", "draft_id": obj.id})

@login_required
@require_POST
def publish_shifts_api(request):
    if not can(request.user, "can_view_beschikbaarheidsdashboard"):
        return JsonResponse({"ok": False, "error": "Geen toegang."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Ongeldige JSON."}, status=400)

    ws = payload.get("week_start")
    we = payload.get("week_end")
    if not ws or not we:
        return JsonResponse({"ok": False, "error": "week_start/week_end ontbreekt."}, status=400)

    try:
        week_start = date.fromisoformat(ws)
        week_end = date.fromisoformat(we)
    except Exception:
        return JsonResponse({"ok": False, "error": "Ongeldige datum."}, status=400)

    if week_end < week_start:
        return JsonResponse({"ok": False, "error": "week_end mag niet vóór week_start liggen."}, status=400)

    with transaction.atomic():
        drafts = (
            ShiftDraft.objects
            .filter(date__gte=week_start, date__lte=week_end)
            .select_related("task")
        )

        affected_user_ids = set(drafts.values_list("user_id", flat=True))

        deletes = drafts.filter(action="delete").values_list("user_id", "date", "period")
        for (uid, d, p) in deletes:
            Shift.objects.filter(user_id=uid, date=d, period=p).delete()

        upserts = drafts.filter(action="upsert")
        for dr in upserts:
            Shift.objects.update_or_create(
                user_id=dr.user_id,
                date=dr.date,
                period=dr.period,
                defaults={"task_id": dr.task_id}
            )

        changed_count = drafts.count()
        drafts.delete()

        def _delete_keys():
            keys = [f"diensten_ics:{uid}" for uid in affected_user_ids]
            cache.delete_many(keys)

        transaction.on_commit(_delete_keys)

    iso_week = week_start.isocalendar().week
    messages.success(
        request,
        f"{int(changed_count)} wijziging(en) gepubliceerd voor week {iso_week} "
        f"({week_start:%d-%m} t/m {week_end:%d-%m})."
    )

    return JsonResponse({"ok": True, "changed_count": int(changed_count)})