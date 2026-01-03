from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone, translation

from core.models import Shift
from ._helpers import can


def _monday_of_iso_week(some_date: date) -> date:
    return some_date - timedelta(days=some_date.weekday())


def _clamp_week(target_monday: date, min_monday: date, max_monday: date) -> date:
    if target_monday < min_monday:
        return min_monday
    if target_monday > max_monday:
        return max_monday
    return target_monday


@login_required
def mijndiensten_view(request):
    if not can(request.user, "can_view_diensten"):
        return HttpResponseForbidden("Geen toegang.")

    translation.activate("nl")

    today = timezone.localdate()
    WEEKS_AHEAD = 12

    min_monday = _monday_of_iso_week(today)
    max_monday = _monday_of_iso_week(today + timedelta(weeks=WEEKS_AHEAD))

    # ---- weekselectie (zelfde pattern als jouw beschikbaarheid-view) ----
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
            year_str, wstr = qs_week.split("-W")
            monday = date.fromisocalendar(int(year_str), int(wstr), 1)
        except Exception:
            monday = min_monday
    else:
        monday = min_monday

    monday = _clamp_week(monday, min_monday, max_monday)
    week_end = monday + timedelta(days=5)  # ma..za

    # Navigatie (alleen tussen huidige week en +WEEKS_AHEAD)
    prev_raw = monday - timedelta(weeks=1)
    next_raw = monday + timedelta(weeks=1)
    has_prev = prev_raw >= min_monday
    has_next = next_raw <= max_monday
    prev_monday = prev_raw if has_prev else min_monday
    next_monday = next_raw if has_next else max_monday

    # ma..za dates
    days = [monday + timedelta(days=i) for i in range(6)]
    saturday = monday + timedelta(days=5)

    # Shifts voor user in deze week
    shifts = (
        Shift.objects
        .filter(user=request.user, date__in=days)
        .select_related("task", "task__location")
        .order_by("date", "period")
    )

    # map: (date, period) -> Shift
    shift_map = {(s.date, s.period): s for s in shifts}

    # Alleen zaterdag tonen als er zaterdag-shifts bestaan
    show_saturday = any(s.date == saturday for s in shifts)

    PERIOD_META = {
        "morning": {"label": "Ochtend", "time": "09:00 - 13:00"},
        "afternoon": {"label": "Middag", "time": "13:00 - 17:30"},
        "evening": {"label": "Avond", "time": "18:00 - 20:00"},
    }

    def has_evening(d: date) -> bool:
        return (d, "evening") in shift_map

    def row_payload(d: date, p: str, s: Shift | None, show_day: bool):
        """
        Enrich row with location color classes (for subtle background tint).
        """
        color = ""
        if s and s.task and s.task.location:
            color = (s.task.location.color or "").strip()

        return {
            "date": d,
            "period": p,
            "period_label": PERIOD_META[p]["label"],
            "period_time": PERIOD_META[p]["time"],
            "location": s.task.location.name if s else "",
            "task": s.task.name if s else "",
            "is_assigned": bool(s),
            "show_day": show_day,
            "loc_color": color,
            "row_class": f"loc-tint loc-tint--{color}" if color else "",
        }

    rows = []

    # Ma–Vr: ochtend + middag altijd, avond alleen als ingepland
    for d in days[:5]:
        # Ochtend (dag tonen)
        p = "morning"
        s = shift_map.get((d, p))
        rows.append(row_payload(d, p, s, show_day=True))

        # Middag (dag leeg)
        p = "afternoon"
        s = shift_map.get((d, p))
        rows.append(row_payload(d, p, s, show_day=False))

        # Avond alleen als ingepland (dag nooit tonen)
        if has_evening(d):
            p = "evening"
            s = shift_map.get((d, p))
            rows.append(row_payload(d, p, s, show_day=False))

    # Zaterdag alleen als ingepland (dag alleen bij ochtend; fallback bij eerste rij)
    if show_saturday:
        d = saturday
        sat_periods = [p for p in ("morning", "afternoon", "evening") if (d, p) in shift_map]

        for idx, p in enumerate(sat_periods):
            s = shift_map[(d, p)]
            show_day = (p == "morning") or ("morning" not in sat_periods and idx == 0)
            rows.append(row_payload(d, p, s, show_day=show_day))

    # Dropdown weeks
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

    return render(request, "diensten/index.html", {
        "monday": monday,
        "week_end": week_end,
        "rows": rows,
        "week_options": week_options,
        "min_monday": min_monday,
        "max_monday": max_monday,
        "header_title": header_title,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_monday": prev_monday,
        "next_monday": next_monday,
        "show_saturday": show_saturday,
    })