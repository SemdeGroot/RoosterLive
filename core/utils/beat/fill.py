# core/utils/beat/fill.py

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from core.models import Availability, UserProfile


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _compute_window(*, today: date, weeks_ahead: int) -> Tuple[date, date]:
    start_monday = _monday_of_week(today)
    max_monday = _monday_of_week(today + timedelta(weeks=weeks_ahead))
    end_date = max_monday + timedelta(days=6)
    return start_monday, end_date


def _date_range(start: date, end_inclusive: date) -> Iterable[date]:
    cur = start
    while cur <= end_inclusive:
        yield cur
        cur += timedelta(days=1)


def _profile_dayparts(profile: UserProfile, weekday: int) -> Tuple[bool, bool]:
    if weekday == 0:
        return profile.work_mon_am, profile.work_mon_pm
    if weekday == 1:
        return profile.work_tue_am, profile.work_tue_pm
    if weekday == 2:
        return profile.work_wed_am, profile.work_wed_pm
    if weekday == 3:
        return profile.work_thu_am, profile.work_thu_pm
    if weekday == 4:
        return profile.work_fri_am, profile.work_fri_pm
    return False, False


def fill_availability_for_profile(
    profile: UserProfile,
    *,
    weeks_ahead: int = 12,
    today: Optional[date] = None,
) -> int:
    """
    Wekelijks aanvullen (veilig):
    - Create ontbrekende rows met source="auto" voor vaste dagdelen.
    - Update bestaande rows ALLEEN als source="auto": zet morning/afternoon aan indien nodig.
    - source="manual" wordt NOOIT aangepast.
    - evening wordt NOOIT aangepast.
    """
    if profile.dienstverband != UserProfile.Dienstverband.VAST:
        return 0

    if today is None:
        today = timezone.localdate()

    start_date, end_date = _compute_window(today=today, weeks_ahead=weeks_ahead)

    existing_qs = Availability.objects.filter(
        user_id=profile.user_id,
        date__gte=start_date,
        date__lte=end_date,
    )
    existing_by_date: Dict[date, Availability] = {a.date: a for a in existing_qs}

    to_create: List[Availability] = []
    to_update: List[Availability] = []

    for d in _date_range(start_date, end_date):
        wd = d.weekday()
        need_m, need_a = _profile_dayparts(profile, wd)

        if not (need_m or need_a):
            continue

        av = existing_by_date.get(d)
        if av is None:
            to_create.append(
                Availability(
                    user_id=profile.user_id,
                    date=d,
                    morning=need_m,
                    afternoon=need_a,
                    evening=False,
                    source="auto",
                )
            )
            continue

        # manual nooit aanpassen
        if av.source != "auto":
            continue

        changed = False
        # alleen aanzetten (nooit uitzetten) in weekly fill
        if need_m and not av.morning:
            av.morning = True
            changed = True
        if need_a and not av.afternoon:
            av.afternoon = True
            changed = True

        if changed:
            to_update.append(av)

    if not to_create and not to_update:
        return 0

    with transaction.atomic():
        if to_create:
            Availability.objects.bulk_create(to_create, ignore_conflicts=True)
        if to_update:
            Availability.objects.bulk_update(to_update, ["morning", "afternoon"])

    return len(to_create) + len(to_update)


def rebuild_auto_availability_for_profile(
    profile: UserProfile,
    *,
    weeks_ahead: int = 12,
    today: Optional[date] = None,
) -> int:
    """
    Rebuild (admin actie):
    - Alleen rows met source="auto" in het window worden OVERSCHREVEN naar het vaste schema.
    - manual blijft 100% onaangeraakt.
    - evening blijft onaangeraakt.
    - Als er nog geen row bestaat maar wel vaste dagdelen: maak aan met source="auto".
    """
    if profile.dienstverband != UserProfile.Dienstverband.VAST:
        return 0

    if today is None:
        today = timezone.localdate()

    start_date, end_date = _compute_window(today=today, weeks_ahead=weeks_ahead)

    existing_qs = Availability.objects.filter(
        user_id=profile.user_id,
        date__gte=start_date,
        date__lte=end_date,
    )
    existing_by_date: Dict[date, Availability] = {a.date: a for a in existing_qs}

    to_create: List[Availability] = []
    to_update: List[Availability] = []

    for d in _date_range(start_date, end_date):
        wd = d.weekday()
        want_m, want_a = _profile_dayparts(profile, wd)

        # Alleen iets doen op dagen waar vaste dagdelen bestaan
        if not (want_m or want_a):
            continue

        av = existing_by_date.get(d)
        if av is None:
            to_create.append(
                Availability(
                    user_id=profile.user_id,
                    date=d,
                    morning=want_m,
                    afternoon=want_a,
                    evening=False,
                    source="auto",
                )
            )
            continue

        if av.source != "auto":
            continue  # manual = hands off

        # Rebuild = exact zetten op schema voor auto (dus ook uitzetten)
        if av.morning != want_m or av.afternoon != want_a:
            av.morning = want_m
            av.afternoon = want_a
            to_update.append(av)

    if not to_create and not to_update:
        return 0

    with transaction.atomic():
        if to_create:
            Availability.objects.bulk_create(to_create, ignore_conflicts=True)
        if to_update:
            Availability.objects.bulk_update(to_update, ["morning", "afternoon"])

    return len(to_create) + len(to_update)


def fill_availability_for_all_vast_users(
    *,
    weeks_ahead: int = 12,
    today: Optional[date] = None,
) -> int:
    if today is None:
        today = timezone.localdate()

    profiles = UserProfile.objects.filter(
        dienstverband=UserProfile.Dienstverband.VAST
    ).only(
        "user_id", "dienstverband",
        "work_mon_am", "work_mon_pm",
        "work_tue_am", "work_tue_pm",
        "work_wed_am", "work_wed_pm",
        "work_thu_am", "work_thu_pm",
        "work_fri_am", "work_fri_pm",
    )

    total = 0
    for p in profiles.iterator():
        total += fill_availability_for_profile(p, weeks_ahead=weeks_ahead, today=today)

    return total