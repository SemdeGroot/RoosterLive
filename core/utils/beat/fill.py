# core/utils/beat/fill.py

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from core.models import Availability, UserProfile, Dagdeel


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


def _profile_dayparts(profile: UserProfile, weekday: int) -> tuple[bool, bool, bool]:
    if weekday == 0:
        return profile.work_mon_am, profile.work_mon_pm, profile.work_mon_ev
    if weekday == 1:
        return profile.work_tue_am, profile.work_tue_pm, profile.work_tue_ev
    if weekday == 2:
        return profile.work_wed_am, profile.work_wed_pm, profile.work_wed_ev
    if weekday == 3:
        return profile.work_thu_am, profile.work_thu_pm, profile.work_thu_ev
    if weekday == 4:
        return profile.work_fri_am, profile.work_fri_pm, profile.work_fri_ev
    if weekday == 5:
        return profile.work_sat_am, profile.work_sat_pm, profile.work_sat_ev
    return False, False, False


def _wanted_codes_for_day(profile: UserProfile, d: date) -> set[str]:
    need_m, need_a, need_pe = _profile_dayparts(profile, d.weekday())
    codes: set[str] = set()
    if need_m:
        codes.add(Dagdeel.CODE_MORNING)
    if need_a:
        codes.add(Dagdeel.CODE_AFTERNOON)
    if need_pe:
        codes.add(Dagdeel.CODE_PRE_EVENING)
    return codes


def fill_availability_for_profile(
    profile: UserProfile,
    *,
    weeks_ahead: int = 12,
    today: Optional[date] = None,
) -> int:
    """
    Wekelijks aanvullen (veilig):
    - Create ontbrekende Availability rows met source="auto" waar vaste dagdelen bestaan.
    - Update bestaande rows ALLEEN als source="auto": zet gewenste PLANNING_CODES aan indien nodig.
    - source="manual" wordt NOOIT aangepast.
    - Niet-PLANNING_CODES (zoals evening/night) worden NOOIT aangepast.
    """
    if profile.dienstverband != UserProfile.Dienstverband.VAST:
        return 0

    if today is None:
        today = timezone.localdate()

    start_date, end_date = _compute_window(today=today, weeks_ahead=weeks_ahead)

    # Dagdeel objects 1x ophalen (en alleen planning codes)
    dagdeel_by_code: Dict[str, Dagdeel] = {
        d.code: d
        for d in Dagdeel.objects.filter(code__in=Dagdeel.PLANNING_CODES)
    }

    existing_qs = (
        Availability.objects.filter(
            user_id=profile.user_id,
            date__gte=start_date,
            date__lte=end_date,
        )
        .prefetch_related("dagdelen")
    )
    existing_by_date: Dict[date, Availability] = {a.date: a for a in existing_qs}

    to_create: List[Availability] = []
    # we gaan M2M zetten, dus update-lijst is eigenlijk "te wijzigen availabilities"
    to_m2m_add: List[tuple[Availability, set[str]]] = []

    # 1) bepaal wat we willen
    for d in _date_range(start_date, end_date):
        wanted_codes = _wanted_codes_for_day(profile, d)
        if not wanted_codes:
            continue

        av = existing_by_date.get(d)
        if av is None:
            # aanmaken; dagdelen koppelen doen we na bulk_create
            to_create.append(
                Availability(
                    user_id=profile.user_id,
                    date=d,
                    source="auto",
                )
            )
            continue

        # manual nooit aanpassen
        if av.source != "auto":
            continue

        current_codes = set(av.dagdelen.values_list("code", flat=True))
        missing = wanted_codes - current_codes
        if missing:
            to_m2m_add.append((av, missing))

    if not to_create and not to_m2m_add:
        return 0

    with transaction.atomic():
        created_by_date: Dict[date, Availability] = {}

        if to_create:
            Availability.objects.bulk_create(to_create, ignore_conflicts=True)

            # bulk_create + ignore_conflicts geeft je niet gegarandeerd pks terug,
            # dus we lezen ze terug.
            created_qs = Availability.objects.filter(
                user_id=profile.user_id,
                date__gte=start_date,
                date__lte=end_date,
                source="auto",
            )
            created_by_date = {a.date: a for a in created_qs}

        # 2) koppel dagdelen voor nieuw aangemaakte records
        if to_create:
            for d in [a.date for a in to_create]:
                av = created_by_date.get(d) or existing_by_date.get(d)
                if not av:
                    continue
                wanted_codes = _wanted_codes_for_day(profile, d)
                # alleen planning codes koppelen (safety)
                dd_objs = [dagdeel_by_code[c] for c in wanted_codes if c in dagdeel_by_code]
                if dd_objs:
                    av.dagdelen.add(*dd_objs)

        # 3) voeg ontbrekende dagdelen toe voor bestaande auto records
        for av, missing_codes in to_m2m_add:
            dd_objs = [dagdeel_by_code[c] for c in missing_codes if c in dagdeel_by_code]
            if dd_objs:
                av.dagdelen.add(*dd_objs)

    return len(to_create) + len(to_m2m_add)


def rebuild_auto_availability_for_profile(
    profile: UserProfile,
    *,
    weeks_ahead: int = 12,
    today: Optional[date] = None,
) -> int:
    """
    Rebuild (admin actie):
    - Alleen rows met source="auto" in het window worden OVERSCHREVEN naar het vaste schema (voor PLANNING_CODES).
    - manual blijft 100% onaangeraakt.
    - Niet-PLANNING_CODES (zoals evening/night) blijven onaangeraakt.
    - Als er nog geen row bestaat maar wel vaste dagdelen: maak aan met source="auto".
    """
    if profile.dienstverband != UserProfile.Dienstverband.VAST:
        return 0

    if today is None:
        today = timezone.localdate()

    start_date, end_date = _compute_window(today=today, weeks_ahead=weeks_ahead)

    dagdeel_by_code: Dict[str, Dagdeel] = {
        d.code: d
        for d in Dagdeel.objects.filter(code__in=Dagdeel.PLANNING_CODES)
    }
    planning_codes_set = set(Dagdeel.PLANNING_CODES)

    existing_qs = (
        Availability.objects.filter(
            user_id=profile.user_id,
            date__gte=start_date,
            date__lte=end_date,
        )
        .prefetch_related("dagdelen")
    )
    existing_by_date: Dict[date, Availability] = {a.date: a for a in existing_qs}

    to_create: List[Availability] = []
    to_rebuild: List[tuple[Availability, set[str]]] = []

    for d in _date_range(start_date, end_date):
        wanted_codes = _wanted_codes_for_day(profile, d)
        if not wanted_codes:
            continue

        av = existing_by_date.get(d)
        if av is None:
            to_create.append(
                Availability(
                    user_id=profile.user_id,
                    date=d,
                    source="auto",
                )
            )
            continue

        if av.source != "auto":
            continue

        current_codes = set(av.dagdelen.values_list("code", flat=True))

        # Alleen planning codes vergelijken/overschrijven
        current_planning = current_codes & planning_codes_set
        if current_planning != wanted_codes:
            to_rebuild.append((av, wanted_codes))

    if not to_create and not to_rebuild:
        return 0

    with transaction.atomic():
        if to_create:
            Availability.objects.bulk_create(to_create, ignore_conflicts=True)

        # herlees alles voor window (ook nieuw aangemaakt)
        all_qs = (
            Availability.objects.filter(
                user_id=profile.user_id,
                date__gte=start_date,
                date__lte=end_date,
            )
            .prefetch_related("dagdelen")
        )
        all_by_date = {a.date: a for a in all_qs}

        # 1) zet dagdelen voor nieuw aangemaakte rows exact
        if to_create:
            for a in to_create:
                av = all_by_date.get(a.date)
                if not av or av.source != "auto":
                    continue
                wanted_codes = _wanted_codes_for_day(profile, a.date)
                # preserve non-planning codes:
                current_codes = set(av.dagdelen.values_list("code", flat=True))
                keep_non_planning = current_codes - planning_codes_set
                final_codes = keep_non_planning | wanted_codes
                dd_objs = [dagdeel_by_code[c] for c in final_codes if c in dagdeel_by_code]
                # NB: keep_non_planning kan codes bevatten die niet in dagdeel_by_code zitten.
                # Daarom set() in 2 stappen:
                av.dagdelen.set(Dagdeel.objects.filter(code__in=final_codes))

        # 2) rebuild bestaande auto rows exact voor planning codes
        for av, wanted_codes in to_rebuild:
            current_codes = set(av.dagdelen.values_list("code", flat=True))
            keep_non_planning = current_codes - planning_codes_set
            final_codes = keep_non_planning | wanted_codes
            av.dagdelen.set(Dagdeel.objects.filter(code__in=final_codes))

    return len(to_create) + len(to_rebuild)


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
        "work_mon_am", "work_mon_pm", "work_mon_ev",
        "work_tue_am", "work_tue_pm", "work_tue_ev",
        "work_wed_am", "work_wed_pm", "work_wed_ev",
        "work_thu_am", "work_thu_pm", "work_thu_ev",
        "work_fri_am", "work_fri_pm", "work_fri_ev",
        "work_sat_am", "work_sat_pm", "work_sat_ev",
    )

    total = 0
    for p in profiles.iterator():
        total += fill_availability_for_profile(p, weeks_ahead=weeks_ahead, today=today)

    return total