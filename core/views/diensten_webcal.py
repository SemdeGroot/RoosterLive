from datetime import datetime, timedelta, time
from email.utils import parsedate_to_datetime
from hashlib import sha256
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.utils import timezone

from core.models import Shift, UserProfile


PERIOD_TIMES = {
    "morning": (time(9, 0), time(13, 0)),
    "afternoon": (time(13, 0), time(17, 30)),
    "evening": (time(18, 0), time(20, 0)),
}

PERIOD_LABELS = {
    "morning": "Ochtend",
    "afternoon": "Middag",
    "evening": "Avond",
}


def _ics_escape(s: str) -> str:
    s = (s or "").replace("\\", "\\\\")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", "\\n")
    s = s.replace(";", r"\;").replace(",", r"\,")
    return s


def _fmt_dt_utc(dt: datetime) -> str:
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y%m%dT%H%M%SZ")


def _httpdate(dt: datetime) -> str:
    # RFC7231 compliant-ish via Django format
    from django.utils.http import http_date
    return http_date(int(dt.timestamp()))


def _build_ics_for_user(user) -> tuple[str, datetime]:
    """
    Returns: (ics_text, last_modified_utc)
    last_modified_utc = max(updated_at) of included shifts (or now if none).
    """
    tz = ZoneInfo(getattr(settings, "TIME_ZONE", "Europe/Amsterdam"))

    today = timezone.localdate()
    start_date = today - timedelta(weeks=8)

    shifts = (
        Shift.objects
        .filter(user=user, date__gte=start_date)
        .select_related("task", "task__location")
        .order_by("date", "period")
    )

    now = timezone.now()

    last_mod = None
    for s in shifts:
        if last_mod is None or s.updated_at > last_mod:
            last_mod = s.updated_at
    if last_mod is None:
        last_mod = now
    last_mod_utc = last_mod.astimezone(timezone.utc)

    lines = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//Apotheek Jansen//Diensten//NL")
    lines.append("CALSCALE:GREGORIAN")
    lines.append("METHOD:PUBLISH")
    lines.append(f"X-WR-CALNAME:{_ics_escape('Werken bij Apotheek Jansen')}")
    lines.append(f"X-WR-TIMEZONE:{_ics_escape(str(tz))}")

    for s in shifts:
        start_t, end_t = PERIOD_TIMES.get(s.period, (time(9, 0), time(13, 0)))
        dt_start_local = datetime.combine(s.date, start_t, tzinfo=tz)
        dt_end_local = datetime.combine(s.date, end_t, tzinfo=tz)

        task_name = getattr(s.task, "name", "") or ""
        loc = getattr(s.task, "location", None)
        loc_name = getattr(loc, "name", "") if loc else ""
        loc_addr = getattr(loc, "address", "") if loc else ""

        summary = f"Werken bij Apotheek Jansen – {task_name}".strip()
        location_line = " – ".join([x for x in [loc_name, loc_addr] if x]).strip()

        desc_parts = [
            f"Dagdeel: {PERIOD_LABELS.get(s.period, s.period)}",
        ]
        if loc_name:
            desc_parts.append(f"Locatie: {loc_name}")
        if loc_addr:
            desc_parts.append(f"Adres: {loc_addr}")
        desc_parts.append("Deze agenda synchroniseert automatisch. Het kan even duren voordat wijzigingen zichtbaar zijn (afhankelijk van je agenda-app).")
        description = "\n".join(desc_parts)

        uid = f"shift-{s.id}@apotheekjansen"

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{_ics_escape(uid)}")
        lines.append(f"DTSTAMP:{_fmt_dt_utc(now)}")
        lines.append(f"DTSTART:{_fmt_dt_utc(dt_start_local)}")
        lines.append(f"DTEND:{_fmt_dt_utc(dt_end_local)}")
        lines.append(f"SUMMARY:{_ics_escape(summary)}")
        if location_line:
            lines.append(f"LOCATION:{_ics_escape(location_line)}")
        lines.append(f"DESCRIPTION:{_ics_escape(description)}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    ics = "\r\n".join(lines) + "\r\n"
    return ics, last_mod_utc


def _ics_cache_key(user_id: int) -> str:
    return f"diensten_ics:{user_id}"


def _maybe_304(request, etag: str, last_modified_utc: datetime):
    inm = request.headers.get("If-None-Match")
    if inm and inm.strip() == etag:
        resp = HttpResponseNotModified()
        resp["ETag"] = etag
        resp["Last-Modified"] = _httpdate(last_modified_utc)
        resp["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp

    ims = request.headers.get("If-Modified-Since")
    if ims:
        try:
            ims_dt = parsedate_to_datetime(ims)
            if ims_dt.tzinfo is None:
                ims_dt = ims_dt.replace(tzinfo=timezone.utc)
            # 304 als client al iets heeft dat >= last_modified
            if ims_dt >= last_modified_utc:
                resp = HttpResponseNotModified()
                resp["ETag"] = etag
                resp["Last-Modified"] = _httpdate(last_modified_utc)
                resp["Cache-Control"] = "private, max-age=0, must-revalidate"
                return resp
        except Exception:
            pass

    return None


def diensten_webcal_view(request, token):
    profile = (
        UserProfile.objects
        .select_related("user")
        .filter(calendar_token=token)
        .first()
    )
    if not profile or not profile.user or not profile.user.is_active:
        raise Http404("Onbekende gebruiker.")

    user = profile.user
    key = _ics_cache_key(user.id)

    cached = cache.get(key)
    if cached:
        ics = cached["ics"]
        etag = cached["etag"]
        last_modified_utc = cached["last_modified_utc"]

        maybe = _maybe_304(request, etag, last_modified_utc)
        if maybe:
            return maybe

        resp = HttpResponse(ics, content_type="text/calendar; charset=utf-8")
        resp["Content-Disposition"] = 'inline; filename="diensten.ics"'
        resp["ETag"] = etag
        resp["Last-Modified"] = _httpdate(last_modified_utc)
        resp["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp

    ics, last_modified_utc = _build_ics_for_user(user)
    etag = '"' + sha256(ics.encode("utf-8")).hexdigest() + '"'

    cache.set(
        key,
        {"ics": ics, "etag": etag, "last_modified_utc": last_modified_utc},
        timeout=60 * 60 * 24 * 7,  # 7 dagen
    )

    maybe = _maybe_304(request, etag, last_modified_utc)
    if maybe:
        return maybe

    resp = HttpResponse(ics, content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = 'inline; filename="diensten.ics"'
    resp["ETag"] = etag
    resp["Last-Modified"] = _httpdate(last_modified_utc)
    resp["Cache-Control"] = "private, max-age=0, must-revalidate"
    return resp