# core/utils/calendar_sync.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.core.cache import cache
from django.utils import timezone


CALENDAR_ACTIVE_TTL_SECONDS = 60 * 60 * 24 * 4  # 4 dagen


def _calendar_active_key(user_id: int) -> str:
    return f"calendar_active:{user_id}"


@dataclass(frozen=True)
class CalendarSyncStatus:
    active: bool
    last_synced: Optional[timezone.datetime]


def mark_calendar_active(user_id: int) -> None:
    """
    Zet/refresh calendar_active met TTL=4 dagen en update last_synced.
    Wordt aangeroepen bij elke webcal fetch.
    """
    payload = {
        "active": True,
        # datetime object is prima; django-redis kan dit picklen.
        "last_synced": timezone.now(),
    }
    cache.set(_calendar_active_key(user_id), payload, timeout=CALENDAR_ACTIVE_TTL_SECONDS)


def get_calendar_sync_status(user_id: int) -> CalendarSyncStatus:
    payload = cache.get(_calendar_active_key(user_id))
    if not payload:
        return CalendarSyncStatus(active=False, last_synced=None)

    last = payload.get("last_synced")
    if last and timezone.is_naive(last):
        # Voor de zekerheid (zou normaliter al aware zijn)
        last = timezone.make_aware(last, timezone=timezone.utc)

    return CalendarSyncStatus(active=bool(payload.get("active")), last_synced=last)