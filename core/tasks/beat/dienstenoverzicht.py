# core/tasks/beat/dienstenoverzicht.py
from __future__ import annotations

from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone, translation

from core.models import Shift, UserProfile
from core.views._helpers import can, wants_email
from core.utils.dagdelen import get_period_meta
from core.tasks.email_dispatcher import email_dispatcher_task

def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


# Mail-safe, lichte tinten (zelfde als util)
ROW_BG = {
    "green": "#EAF7F0",
    "red":   "#FDEDED",
    "blue":  "#EEF4FF",
}

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_weekly_diensten_overzicht(self):
    """
    Elke vrijdag: stuur per user een overzicht van diens diensten voor de week erna.
    Alleen als:
    - user email heeft
    - permissie can_view_diensten
    - preference email_diensten_overzicht aan staat
    - user minstens 1 shift heeft in de week erna
    """
    translation.activate("nl")

    today = timezone.localdate()
    next_monday = _monday_of_week(today) + timedelta(weeks=1)
    week_end = next_monday + timedelta(days=5)  # ma..za
    days = [next_monday + timedelta(days=i) for i in range(6)]
    saturday = next_monday + timedelta(days=5)

    iso_year, iso_week, _ = next_monday.isocalendar()
    header_title = f"Week {iso_week} – {iso_year}"

    profiles = (
        UserProfile.objects
        .select_related("user", "notif_prefs")
        .filter(user__is_active=True)
    )

    for profile in profiles:
        user = profile.user
        if not user or not user.email:
            continue

        # consistent met je app: alleen als user dit onderdeel mag zien
        if not can(user, "can_view_diensten"):
            continue

        prefs = getattr(profile, "notif_prefs", None)
        if not wants_email(user, "email_diensten_overzicht", prefs=prefs):
            continue

        shifts_qs = (
            Shift.objects
            .filter(user=user, date__in=days)
            .select_related("task", "task__location")
            .order_by("date", "period")
        )

        # Geen diensten? niks sturen.
        if not shifts_qs.exists():
            continue

        shifts = list(shifts_qs)
        shift_map = {(s.date, s.period): s for s in shifts}
        show_saturday = any(s.date == saturday for s in shifts)

        def has_evening(d: date) -> bool:
            return (d, "evening") in shift_map

        def row_bg_for_shift(s: Shift | None) -> str:
            loc = getattr(getattr(s, "task", None), "location", None)
            c = (getattr(loc, "color", "") or "").strip()
            return ROW_BG.get(c, "")

        rows: list[dict] = []

        # ma..vr: morning + afternoon alleen als shift bestaat, evening alleen als bestaat
        for d in days[:5]:
            day_rows: list[dict] = []

            for p in ("morning", "afternoon"):
                s = shift_map.get((d, p))
                if not s:
                    continue

                meta = get_period_meta(p)
                day_rows.append({
                    "date": d.isoformat(),  # <-- JSON-safe
                    "period": p,
                    "period_label": meta["label"],
                    "period_time": meta["time_str"],
                    "location": s.task.location.name if s.task and s.task.location else "",
                    "task": s.task.name if s.task else "",
                    "show_day": False,          # vullen we hieronder
                    "is_assigned": True,
                    "row_bg": row_bg_for_shift(s),
                })

            if has_evening(d):
                s = shift_map.get((d, "evening"))
                if s:
                    meta = get_period_meta("evening")
                    day_rows.append({
                        "date": d.isoformat(),  # <-- JSON-safe
                        "period": "evening",
                        "period_label": meta["label"],
                        "period_time": meta["time_str"],
                        "location": s.task.location.name if s.task and s.task.location else "",
                        "task": s.task.name if s.task else "",
                        "show_day": False,
                        "is_assigned": True,
                        "row_bg": row_bg_for_shift(s),
                    })

            # show_day alleen op de eerste row van die dag (geen dubbele dag-namen)
            for idx, r in enumerate(day_rows):
                r["show_day"] = (idx == 0)
                rows.append(r)

        # zaterdag: alleen als er shifts zijn, net als je view
        if show_saturday:
            d = saturday
            sat_periods = [p for p in ("morning", "afternoon", "evening") if (d, p) in shift_map]
            for idx, p in enumerate(sat_periods):
                s = shift_map[(d, p)]
                meta = get_period_meta(p)
                rows.append({
                    "date": d.isoformat(),  # <-- JSON-safe
                    "period": p,
                    "period_label": meta["label"],
                    "period_time": meta["time_str"],
                    "location": s.task.location.name if s.task and s.task.location else "",
                    "task": s.task.name if s.task else "",
                    "show_day": (idx == 0),
                    "is_assigned": True,
                    "row_bg": row_bg_for_shift(s),
                })

        # Unieke locaties die in deze shifts voorkomen (met adres + tint)
        loc_seen: dict[int, object] = {}
        for s in shifts:
            loc = getattr(getattr(s, "task", None), "location", None)
            if not loc:
                continue
            loc_seen[loc.id] = loc

        location_rows: list[dict] = []
        for loc in sorted(loc_seen.values(), key=lambda x: (x.name or "").lower()):
            c = (getattr(loc, "color", "") or "").strip()
            location_rows.append({
                "name": (loc.name or "").strip(),
                "address": (loc.address or "").strip(),
                "row_bg": ROW_BG.get(c, ""),
            })

        job = {
            "type": "diensten_overzicht",
            "payload": {
                "to_email": user.email,
                "first_name": user.first_name,
                "header_title": header_title,
                "monday": next_monday.isoformat(),
                "week_end": week_end.isoformat(),
                "rows": rows,
                "location_rows": location_rows,
            },
        }

        email_dispatcher_task.apply_async(args=[job], queue="mail")