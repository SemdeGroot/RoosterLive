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
from django.views.decorators.cache import never_cache

from ._helpers import can
from core.models import Availability, Location, Task, Shift, ShiftDraft, Dagdeel
from core.views.mijnbeschikbaarheid import _monday_of_iso_week, _clamp_week

PERIOD_TO_DAGDEEL_CODE = {
    "morning": Dagdeel.CODE_MORNING,
    "afternoon": Dagdeel.CODE_AFTERNOON,
    "evening": Dagdeel.CODE_PRE_EVENING,
}

def _user_function_title(u):
    prof = getattr(u, "profile", None)
    fn = getattr(prof, "function", None) if prof else None
    return fn.title if fn else "Functie onbekend"

def _user_function_rank(u):
    prof = getattr(u, "profile", None)
    fn = getattr(prof, "function", None) if prof else None
    return int(fn.ranking) if fn else 9999

def _user_dienstverband(u):
    prof = getattr(u, "profile", None)
    return getattr(prof, "dienstverband", None) if prof else None

def _user_firstname_cap(u):
    fn = (u.first_name or "").strip()
    if fn:
        return fn[:1].upper() + fn[1:].lower()
    un = (getattr(u, "username", "") or "").strip()
    return un[:1].upper() + un[1:].lower() if un else "Onbekend"

def _user_lastname_cap(u):
    ln = (u.last_name or "").strip()
    return ln[:1].upper() + ln[1:].lower() if ln else ""

_DAY_PREFIX = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat"}

def _task_min_for(task, dt, period: str) -> int:
    prefix = _DAY_PREFIX.get(dt.weekday())
    if not prefix:
        return 0
    return int(getattr(task, f"min_{prefix}_{period}", 0) or 0)


@login_required
@never_cache
def personeelsdashboard_view(request):
    if not can(request.user, "can_view_beschikbaarheidsdashboard"):
        return HttpResponseForbidden("Geen toegang.")

    translation.activate("nl")
    today = timezone.localdate()
    WEEKS_AHEAD = 12

    min_monday = _monday_of_iso_week(today)
    max_monday = _monday_of_iso_week(today + timedelta(weeks=WEEKS_AHEAD))

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

    prev_raw = monday - timedelta(weeks=1)
    next_raw = monday + timedelta(weeks=1)
    has_prev = prev_raw >= min_monday
    has_next = next_raw <= max_monday
    prev_monday = prev_raw if has_prev else min_monday
    next_monday = next_raw if has_next else max_monday

    # --- Availability for entire week ---
    av_qs = (
        Availability.objects
        .filter(date__in=days)
        .select_related("user", "user__profile", "user__profile__function")
        .prefetch_related("dagdelen", "user__groups")
    )

    avail_map = defaultdict(lambda: defaultdict(lambda: {"morning": False, "afternoon": False, "evening": False}))
    users_with_avail = {}
    for av in av_qs:
        codes = set(av.dagdelen.values_list("code", flat=True))
        avail_map[av.user_id][av.date]["morning"] = Dagdeel.CODE_MORNING in codes
        avail_map[av.user_id][av.date]["afternoon"] = Dagdeel.CODE_AFTERNOON in codes
        avail_map[av.user_id][av.date]["evening"] = Dagdeel.CODE_PRE_EVENING in codes
        users_with_avail[av.user_id] = av.user

    # Detect duplicate firstnames for display name logic
    firstnames = defaultdict(list)
    for uid, u in users_with_avail.items():
        firstnames[_user_firstname_cap(u)].append(uid)
    duplicate_firstnames = {fn for fn, uids in firstnames.items() if len(uids) > 1}

    def _display_name(u):
        fn = _user_firstname_cap(u)
        if fn not in duplicate_firstnames:
            return fn
        ln = _user_lastname_cap(u)
        if not ln:
            return fn
        group_others = [users_with_avail[uid] for uid in firstnames[fn] if uid != u.id]
        other_lns = [_user_lastname_cap(gu).lower() for gu in group_others if _user_lastname_cap(gu)]
        ln_lower = ln.lower()
        # Find shortest prefix of ln that is not a prefix of any other in the group
        n = len(ln)
        for i in range(1, len(ln) + 1):
            if not any(o.startswith(ln_lower[:i]) for o in other_lns):
                n = i
                break
        abbrev = ln[:n]
        return f"{fn} {abbrev}." if n < len(ln) else f"{fn} {abbrev}"

    users_sorted = sorted(
        users_with_avail.values(),
        key=lambda u: (
            _user_function_rank(u),
            _user_function_title(u).lower(),
            _user_firstname_cap(u).lower(),
        )
    )

    users_payload = []
    for u in users_sorted:
        avail_by_date = {}
        for d in days:
            avail_by_date[d.isoformat()] = avail_map[u.id][d]
        users_payload.append({
            "id": u.id,
            "displayName": _display_name(u),
            "firstname": _user_firstname_cap(u),
            "function": _user_function_title(u),
            "function_rank": _user_function_rank(u),
            "dienstverband": _user_dienstverband(u) or "oproep",
            "availability": avail_by_date,
        })

    # --- Locations + Tasks with per-day min values ---
    locations = (
        Location.objects.all()
        .order_by("name")
        .prefetch_related(Prefetch("tasks", queryset=Task.objects.order_by("name")))
    )

    locations_payload = []
    for loc in locations:
        tasks_payload = []
        for t in loc.tasks.all():
            min_by_date = {}
            for d in days:
                min_by_date[d.isoformat()] = {
                    "morning": _task_min_for(t, d, "morning"),
                    "afternoon": _task_min_for(t, d, "afternoon"),
                    "evening": _task_min_for(t, d, "evening"),
                }
            tasks_payload.append({
                "id": t.id,
                "name": t.name,
                "location_id": loc.id,
                "min": min_by_date,
            })
        if tasks_payload:
            locations_payload.append({
                "id": loc.id,
                "name": loc.name,
                "color": loc.color,
                "tasks": tasks_payload,
            })

    # --- Published shifts for the whole week ---
    published_qs = (
        Shift.objects
        .filter(date__in=days)
        .values("user_id", "date", "period", "task_id")
    )
    published_payload = [
        {
            "user_id": s["user_id"],
            "date": s["date"].isoformat(),
            "period": s["period"],
            "task_id": s["task_id"],
        }
        for s in published_qs
    ]

    # --- Draft shifts for the whole week ---
    drafts_qs = (
        ShiftDraft.objects
        .filter(date__in=days)
        .values("id", "user_id", "date", "period", "task_id", "action")
    )
    draft_payload = [
        {
            "id": d["id"],
            "user_id": d["user_id"],
            "date": d["date"].isoformat(),
            "period": d["period"],
            "task_id": d["task_id"],
            "action": d["action"],
        }
        for d in drafts_qs
    ]

    unpublished_count = ShiftDraft.objects.filter(date__in=days).count()

    # --- Week picker options ---
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

    days_payload = []
    for d in days:
        days_payload.append({
            "iso": d.isoformat(),
            "label": date_format(d, "l").capitalize(),
            "short": date_format(d, "D").capitalize()[:2],
            "daymonth": d.strftime("%d-%m"),
        })

    pd_data = {
        "weekStart": monday.isoformat(),
        "weekEnd": week_end.isoformat(),
        "unpublishedCount": unpublished_count,
        "days": days_payload,
        "locations": locations_payload,
        "users": users_payload,
        "publishedShifts": published_payload,
        "draftShifts": draft_payload,
        "saveConceptUrl": reverse("pd_save_concept"),
        "assignSlotUrl": reverse("pd_assign_slot"),
        "deleteShiftUrl": reverse("pd_delete_shift"),
        "publishUrl": reverse("pd_publish_shifts"),
        "copyPrevWeekUrl": reverse("pd_copy_prev_week"),
    }

    return render(request, "personeelsdashboard/index.html", {
        "monday": monday,
        "week_end": week_end,
        "week_options": week_options,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_monday": prev_monday,
        "next_monday": next_monday,
        "header_title": header_title,
        "pd_data": pd_data,
    })


@login_required
@require_POST
def assign_slot_api(request):
    """
    Assign a set of users to a (task, date, period) slot.
    Body: { "task_id": 1, "date": "YYYY-MM-DD", "period": "morning",
            "user_ids": [1,2,3], "week_start": "...", "week_end": "..." }
    Computes the diff and creates/removes drafts atomically.
    """
    if not can(request.user, "can_view_beschikbaarheidsdashboard"):
        return JsonResponse({"ok": False, "error": "Geen toegang."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Ongeldige JSON."}, status=400)

    try:
        task_id = int(payload["task_id"])
        dt = date.fromisoformat(payload["date"])
        period = str(payload["period"])
        user_ids = [int(uid) for uid in payload.get("user_ids", [])]
        week_start = date.fromisoformat(payload.get("week_start", dt.isoformat()))
        date.fromisoformat(payload.get("week_end", dt.isoformat()))  # validated but unused
    except Exception:
        return JsonResponse({"ok": False, "error": "Ongeldige parameters."}, status=400)

    if period not in ("morning", "afternoon", "evening"):
        return JsonResponse({"ok": False, "error": "Ongeldige period."}, status=400)

    target_set = set(user_ids)

    # Determine all existing drafts for this date+period (any task)
    all_drafts_for_slot = {
        d.user_id: d for d in ShiftDraft.objects.filter(date=dt, period=period)
    }

    # Published shifts for this exact task+date+period
    published_for_task = {
        s.user_id for s in Shift.objects.filter(date=dt, period=period, task_id=task_id)
    }

    # Current effective set assigned to this task
    current_set = set()
    for uid, draft in all_drafts_for_slot.items():
        if draft.action == "upsert" and draft.task_id == task_id:
            current_set.add(uid)
    # Published shifts only count if no draft overrides them
    for uid in published_for_task:
        if uid not in all_drafts_for_slot:
            current_set.add(uid)

    to_add = target_set - current_set
    to_remove = current_set - target_set

    with transaction.atomic():
        for uid in to_add:
            ShiftDraft.objects.update_or_create(
                user_id=uid, date=dt, period=period,
                defaults={"task_id": task_id, "action": "upsert"}
            )
        for uid in to_remove:
            if uid in all_drafts_for_slot:
                draft = all_drafts_for_slot[uid]
                if draft.action == "upsert":
                    draft.delete()
            elif uid in published_for_task:
                ShiftDraft.objects.update_or_create(
                    user_id=uid, date=dt, period=period,
                    defaults={"action": "delete", "task": None}
                )

    week_days = [week_start + timedelta(days=i) for i in range(6)]
    updated_drafts = list(
        ShiftDraft.objects.filter(date__in=week_days)
        .values("id", "user_id", "date", "period", "task_id", "action")
    )
    updated_published = list(
        Shift.objects.filter(date__in=week_days)
        .values("user_id", "date", "period", "task_id")
    )
    unpublished_count = ShiftDraft.objects.filter(date__in=week_days).count()

    return JsonResponse({
        "ok": True,
        "unpublishedCount": unpublished_count,
        "draftShifts": [
            {
                "id": d["id"],
                "user_id": d["user_id"],
                "date": d["date"].isoformat(),
                "period": d["period"],
                "task_id": d["task_id"],
                "action": d["action"],
            }
            for d in updated_drafts
        ],
        "publishedShifts": [
            {
                "user_id": s["user_id"],
                "date": s["date"].isoformat(),
                "period": s["period"],
                "task_id": s["task_id"],
            }
            for s in updated_published
        ],
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
    week_start_s = payload.get("week_start")
    week_end_s = payload.get("week_end")

    if not isinstance(items, list):
        return JsonResponse({"ok": False, "error": "items moet een lijst zijn."}, status=400)

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
        ShiftDraft.objects.update_or_create(
            user_id=user_id,
            date=dt,
            period=period,
            defaults={"task_id": task_id, "action": "upsert"}
        )

    # Return updated week state if week bounds provided
    if week_start_s and week_end_s:
        try:
            week_start = date.fromisoformat(week_start_s)
            week_days = [week_start + timedelta(days=i) for i in range(6)]
            updated_drafts = list(
                ShiftDraft.objects.filter(date__in=week_days)
                .values("id", "user_id", "date", "period", "task_id", "action")
            )
            updated_published = list(
                Shift.objects.filter(date__in=week_days)
                .values("user_id", "date", "period", "task_id")
            )
            unpublished_count = ShiftDraft.objects.filter(date__in=week_days).count()
            return JsonResponse({
                "ok": True,
                "unpublishedCount": unpublished_count,
                "draftShifts": [
                    {
                        "id": d["id"],
                        "user_id": d["user_id"],
                        "date": d["date"].isoformat(),
                        "period": d["period"],
                        "task_id": d["task_id"],
                        "action": d["action"],
                    }
                    for d in updated_drafts
                ],
                "publishedShifts": [
                    {
                        "user_id": s["user_id"],
                        "date": s["date"].isoformat(),
                        "period": s["period"],
                        "task_id": s["task_id"],
                    }
                    for s in updated_published
                ],
            })
        except Exception:
            pass

    return JsonResponse({"ok": True})


@login_required
@require_POST
def delete_shift_api(request):
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
        week_start_s = payload.get("week_start")
        week_end_s = payload.get("week_end")
    except Exception:
        return JsonResponse({"ok": False, "error": "user_id/date/period ongeldig."}, status=400)

    if period not in ("morning", "afternoon", "evening"):
        return JsonResponse({"ok": False, "error": "Ongeldige period."}, status=400)

    draft = ShiftDraft.objects.filter(user_id=user_id, date=d, period=period).first()
    if draft:
        draft.delete()
        mode = "undone"
    else:
        exists = Shift.objects.filter(user_id=user_id, date=d, period=period).exists()
        if not exists:
            mode = "noop"
        else:
            ShiftDraft.objects.update_or_create(
                user_id=user_id, date=d, period=period,
                defaults={"action": "delete", "task": None}
            )
            mode = "marked_delete"

    if week_start_s and week_end_s:
        try:
            week_start = date.fromisoformat(week_start_s)
            week_days = [week_start + timedelta(days=i) for i in range(6)]
            updated_drafts = list(
                ShiftDraft.objects.filter(date__in=week_days)
                .values("id", "user_id", "date", "period", "task_id", "action")
            )
            updated_published = list(
                Shift.objects.filter(date__in=week_days)
                .values("user_id", "date", "period", "task_id")
            )
            unpublished_count = ShiftDraft.objects.filter(date__in=week_days).count()
            return JsonResponse({
                "ok": True,
                "mode": mode,
                "unpublishedCount": unpublished_count,
                "draftShifts": [
                    {
                        "id": dr["id"],
                        "user_id": dr["user_id"],
                        "date": dr["date"].isoformat(),
                        "period": dr["period"],
                        "task_id": dr["task_id"],
                        "action": dr["action"],
                    }
                    for dr in updated_drafts
                ],
                "publishedShifts": [
                    {
                        "user_id": s["user_id"],
                        "date": s["date"].isoformat(),
                        "period": s["period"],
                        "task_id": s["task_id"],
                    }
                    for s in updated_published
                ],
            })
        except Exception:
            pass

    return JsonResponse({"ok": True, "mode": mode})


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

        existing_keys = set(
            Shift.objects
            .filter(user_id__in=affected_user_ids, date__gte=week_start, date__lte=week_end)
            .values_list("user_id", "date", "period")
        )

        per_user_counts = defaultdict(lambda: {"added": 0, "changed": 0, "removed": 0})

        deletes = list(drafts.filter(action="delete").values_list("user_id", "date", "period"))
        for (uid, d, p) in deletes:
            if (uid, d, p) in existing_keys:
                per_user_counts[uid]["removed"] += 1
            Shift.objects.filter(user_id=uid, date=d, period=p).delete()

        upserts = list(drafts.filter(action="upsert"))
        for dr in upserts:
            key = (dr.user_id, dr.date, dr.period)
            if key in existing_keys:
                per_user_counts[dr.user_id]["changed"] += 1
            else:
                per_user_counts[dr.user_id]["added"] += 1
            Shift.objects.update_or_create(
                user_id=dr.user_id,
                date=dr.date,
                period=dr.period,
                defaults={"task_id": dr.task_id}
            )

        changed_count = drafts.count()
        drafts.delete()

        def _on_commit_actions():
            keys = [f"diensten_ics:{uid}" for uid in affected_user_ids]
            cache.delete_many(keys)

            from core.tasks.push import send_user_shifts_changed_push_task

            iso_year = week_start.isocalendar().year
            iso_week = week_start.isocalendar().week

            for uid, c in per_user_counts.items():
                total = int(c["added"]) + int(c["changed"]) + int(c["removed"])
                if total <= 0:
                    continue
                send_user_shifts_changed_push_task.delay(
                    int(uid),
                    int(iso_year),
                    int(iso_week),
                    week_start.isoformat(),
                    int(c["added"]),
                    int(c["changed"]),
                    int(c["removed"]),
                )

        transaction.on_commit(_on_commit_actions)

    iso_week = week_start.isocalendar().week
    messages.success(
        request,
        f"{int(changed_count)} wijziging(en) gepubliceerd voor week {iso_week} "
        f"({week_start:%d-%m} t/m {week_end:%d-%m})."
    )
    return JsonResponse({"ok": True, "changed_count": int(changed_count)})


@login_required
@require_POST
def copy_prev_week_api(request):
    """
    Copy published shifts from the previous week for vast users who have availability.
    Only creates drafts for slots that are not already planned (draft or published).
    Body: { "week_start": "YYYY-MM-DD", "week_end": "YYYY-MM-DD" }
    """
    if not can(request.user, "can_view_beschikbaarheidsdashboard"):
        return JsonResponse({"ok": False, "error": "Geen toegang."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
        week_start = date.fromisoformat(payload["week_start"])
        week_end = date.fromisoformat(payload["week_end"])
    except Exception:
        return JsonResponse({"ok": False, "error": "Ongeldige parameters."}, status=400)

    prev_start = week_start - timedelta(weeks=1)
    prev_days = [prev_start + timedelta(days=i) for i in range(6)]
    curr_days = [week_start + timedelta(days=i) for i in range(6)]

    # Published shifts from prev week
    prev_shifts = list(
        Shift.objects
        .filter(date__in=prev_days, task_id__isnull=False)
        .select_related("user", "user__profile")
    )

    # Limit to vast users only
    vast_shifts = [s for s in prev_shifts if _user_dienstverband(s.user) == "vast"]
    if not vast_shifts:
        return JsonResponse({"ok": True, "copied": 0, "empty": True})

    vast_user_ids = {s.user_id for s in vast_shifts}

    # Availability for current week for these users
    av_qs = (
        Availability.objects
        .filter(date__in=curr_days, user_id__in=vast_user_ids)
        .prefetch_related("dagdelen")
    )
    avail_map = defaultdict(lambda: defaultdict(lambda: {
        "morning": False, "afternoon": False, "evening": False,
    }))
    for av in av_qs:
        codes = set(av.dagdelen.values_list("code", flat=True))
        avail_map[av.user_id][av.date]["morning"]   = Dagdeel.CODE_MORNING in codes
        avail_map[av.user_id][av.date]["afternoon"] = Dagdeel.CODE_AFTERNOON in codes
        avail_map[av.user_id][av.date]["evening"]   = Dagdeel.CODE_PRE_EVENING in codes

    # Map prev week date → current week date (same weekday offset)
    prev_to_curr = dict(zip(prev_days, curr_days))

    # Existing coverage for current week (drafts + published) — skip if already planned
    existing_drafts = set(
        ShiftDraft.objects.filter(date__in=curr_days, user_id__in=vast_user_ids)
        .values_list("user_id", "date", "period")
    )
    existing_published = set(
        Shift.objects.filter(date__in=curr_days, user_id__in=vast_user_ids)
        .values_list("user_id", "date", "period")
    )
    existing = existing_drafts | existing_published

    copied = 0
    with transaction.atomic():
        for s in vast_shifts:
            curr_date = prev_to_curr.get(s.date)
            if curr_date is None:
                continue
            if not avail_map[s.user_id][curr_date].get(s.period, False):
                continue
            if (s.user_id, curr_date, s.period) in existing:
                continue
            ShiftDraft.objects.create(
                user_id=s.user_id,
                date=curr_date,
                period=s.period,
                task_id=s.task_id,
                action="upsert",
            )
            copied += 1

    week_days = [week_start + timedelta(days=i) for i in range(6)]
    updated_drafts = list(
        ShiftDraft.objects.filter(date__in=week_days)
        .values("id", "user_id", "date", "period", "task_id", "action")
    )
    updated_published = list(
        Shift.objects.filter(date__in=week_days)
        .values("user_id", "date", "period", "task_id")
    )
    unpublished_count = ShiftDraft.objects.filter(date__in=week_days).count()

    return JsonResponse({
        "ok": True,
        "copied": copied,
        "empty": False,
        "unpublishedCount": unpublished_count,
        "draftShifts": [
            {
                "id": d["id"],
                "user_id": d["user_id"],
                "date": d["date"].isoformat(),
                "period": d["period"],
                "task_id": d["task_id"],
                "action": d["action"],
            }
            for d in updated_drafts
        ],
        "publishedShifts": [
            {
                "user_id": s["user_id"],
                "date": s["date"].isoformat(),
                "period": s["period"],
                "task_id": s["task_id"],
            }
            for s in updated_published
        ],
    })
