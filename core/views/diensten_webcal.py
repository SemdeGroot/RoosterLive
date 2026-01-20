from datetime import datetime, timedelta, time, timezone as dt_timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from zoneinfo import ZoneInfo
import gzip

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.utils import timezone

from core.models import Shift, UserProfile, AgendaItem
from core.utils.calendar_active import mark_calendar_active
from core.utils.dagdelen import get_period_meta

def _ics_escape(s: str) -> str:
    s = (s or "").replace("\\", "\\\\")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", "\\n")
    s = s.replace(";", r"\;").replace(",", r"\,")
    return s


def _fmt_dt_utc(dt: datetime) -> str:
    dt_utc = dt.astimezone(dt_timezone.utc)
    return dt_utc.strftime("%Y%m%dT%H%M%SZ")


def _httpdate(dt: datetime) -> str:
    from django.utils.http import http_date
    return http_date(int(dt.timestamp()))


def _etag_for_bytes(payload: bytes) -> str:
    return '"' + sha256(payload).hexdigest() + '"'


def _fold_ics_line(line: str, limit_octets: int = 75) -> list[str]:
    """
    RFC5545 line folding: >75 octets => CRLF + SP continuation.
    """
    b = line.encode("utf-8")
    if len(b) <= limit_octets:
        return [line]

    out = []
    start = 0
    while start < len(b):
        end = min(start + limit_octets, len(b))
        # Don't split inside UTF-8 continuation bytes
        while end < len(b) and (b[end] & 0xC0) == 0x80:
            end -= 1
        chunk = b[start:end].decode("utf-8", errors="strict")
        if start == 0:
            out.append(chunk)
        else:
            out.append(" " + chunk)
        start = end
    return out


def _fold_ics_lines(lines: list[str]) -> list[str]:
    folded = []
    for line in lines:
        folded.extend(_fold_ics_line(line))
    return folded


def _parse_accept_encoding(header_value: str) -> dict[str, float]:
    """
    Return mapping {coding: q}. Missing q => 1.0. Invalid => 0.0.
    """
    result: dict[str, float] = {}
    if not header_value:
        return result

    parts = [p.strip() for p in header_value.split(",") if p.strip()]
    for p in parts:
        coding, *params = [x.strip() for x in p.split(";")]
        coding = coding.lower()
        q = 1.0
        for param in params:
            if param.startswith("q="):
                try:
                    q = float(param[2:])
                except ValueError:
                    q = 0.0
        result[coding] = q
    return result


def _client_accepts_gzip(request) -> bool:
    enc = _parse_accept_encoding(request.headers.get("Accept-Encoding", ""))

    if "gzip" in enc:
        return enc["gzip"] > 0.0
    if "*" in enc:
        return enc["*"] > 0.0
    return False


def _etag_matches(if_none_match_value: str, etag: str) -> bool:
    """
    Handle lists and weak tags (W/"...") and wildcard (*).
    """
    if not if_none_match_value:
        return False
    v = if_none_match_value.strip()
    if v == "*":
        return True

    candidates = [c.strip() for c in v.split(",") if c.strip()]
    for c in candidates:
        if c.startswith("W/"):
            c = c[2:].strip()
        if c == etag:
            return True
    return False


def _maybe_304(request, etag: str, last_modified_utc: datetime):
    inm = request.headers.get("If-None-Match")
    if inm and _etag_matches(inm, etag):
        resp = HttpResponseNotModified()
        resp["ETag"] = etag
        resp["Last-Modified"] = _httpdate(last_modified_utc)
        resp["Cache-Control"] = "private, max-age=0, must-revalidate"
        resp["Vary"] = "Accept-Encoding"
        return resp

    ims = request.headers.get("If-Modified-Since")
    if ims:
        try:
            ims_dt = parsedate_to_datetime(ims)
            if ims_dt.tzinfo is None:
                ims_dt = ims_dt.replace(tzinfo=dt_timezone.utc)
            if ims_dt >= last_modified_utc:
                resp = HttpResponseNotModified()
                resp["ETag"] = etag
                resp["Last-Modified"] = _httpdate(last_modified_utc)
                resp["Cache-Control"] = "private, max-age=0, must-revalidate"
                resp["Vary"] = "Accept-Encoding"
                return resp
        except Exception:
            pass

    return None


def _ics_cache_key(user_id: int) -> str:
    return f"diensten_ics:{user_id}"


def _build_cached_payload_for_user(user) -> dict:
    """
    Build ICS once and return cache payload:
      - store_bytes: either plain or gzip (whichever is smaller)
      - store_encoding: "gzip" or "identity"
      - etag_plain, etag_gzip
      - last_modified_utc
      - gzip_better: bool (len(gz) < len(plain))
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

    agenda_items = (
        AgendaItem.objects
        .filter(date__gte=start_date)
        .order_by("date", "category", "title")
    )

    now = timezone.now()
    last_modified_utc = now.astimezone(dt_timezone.utc)


    lines: list[str] = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//Apotheek Jansen//Diensten//NL")
    lines.append("CALSCALE:GREGORIAN")
    lines.append("METHOD:PUBLISH")
    lines.append(f"X-WR-CALNAME:{_ics_escape('Apotheek Jansen Agenda')}")
    lines.append(f"X-WR-TIMEZONE:{_ics_escape(str(tz))}")

    for s in shifts:
        meta = get_period_meta(s.period)
        start_t, end_t = meta["start"], meta["end"]
        dt_start_local = datetime.combine(s.date, start_t, tzinfo=tz)
        dt_end_local = datetime.combine(s.date, end_t, tzinfo=tz)

        task_name = getattr(s.task, "name", "") or ""
        loc = getattr(s.task, "location", None)
        loc_name = getattr(loc, "name", "") if loc else ""
        loc_addr = getattr(loc, "address", "") if loc else ""
        task_desc = (getattr(s.task, "description", "") or "").strip()

        summary = f"Werken bij Apotheek Jansen – {task_name}".strip()
        location_line = " – ".join([x for x in [loc_name, loc_addr] if x]).strip()

        desc_parts = [f"Dagdeel: {meta['label']}"]
        if loc_name:
            desc_parts.append(f"Locatie: {loc_name}")
        if loc_addr:
            desc_parts.append(f"Adres: {loc_addr}")
        if task_desc:
            desc_parts.append("")  # lege regel in de ICS description
            desc_parts.append("Taakomschrijving:")
            desc_parts.append(task_desc)

        description = "\n".join(desc_parts)

        uid = f"shift-{s.id}@apotheekjansen"
        dt_event_mod = now.astimezone(dt_timezone.utc)

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{_ics_escape(uid)}")
        lines.append(f"DTSTAMP:{_fmt_dt_utc(dt_event_mod)}")
        lines.append(f"LAST-MODIFIED:{_fmt_dt_utc(dt_event_mod)}")
        lines.append(f"DTSTART:{_fmt_dt_utc(dt_start_local)}")
        lines.append(f"DTEND:{_fmt_dt_utc(dt_end_local)}")
        lines.append(f"SUMMARY:{_ics_escape(summary)}")
        if location_line:
            lines.append(f"LOCATION:{_ics_escape(location_line)}")
        lines.append(f"DESCRIPTION:{_ics_escape(description)}")
        lines.append("END:VEVENT")
        
    for item in agenda_items:
        if item.category == "outing":
            summary = f"Apotheek Jansen Uitje: {item.title}".strip()
        else:
            summary = f"Apotheek Jansen Algemeen: {item.title}".strip()

        description = (item.description or "").strip()
        uid = f"agenda-{item.id}@apotheekjansen"
        dt_event_mod = now.astimezone(dt_timezone.utc)

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{_ics_escape(uid)}")
        lines.append(f"DTSTAMP:{_fmt_dt_utc(dt_event_mod)}")
        lines.append(f"LAST-MODIFIED:{_fmt_dt_utc(dt_event_mod)}")
        lines.append(f"SUMMARY:{_ics_escape(summary)}")
        lines.append(f"DESCRIPTION:{_ics_escape(description)}")

        if item.start_time and item.end_time:
            # timed event
            dt_start_local = datetime.combine(item.date, item.start_time, tzinfo=tz)
            dt_end_local = datetime.combine(item.date, item.end_time, tzinfo=tz)

            # safety: als er toch iets misgaat (zou door form-validatie niet mogen)
            if dt_end_local <= dt_start_local:
                dt_end_local = dt_end_local + timedelta(days=1)

            lines.append(f"DTSTART:{_fmt_dt_utc(dt_start_local)}")
            lines.append(f"DTEND:{_fmt_dt_utc(dt_end_local)}")
        else:
            # all-day event
            dtstart_date = item.date.strftime("%Y%m%d")
            dtend_date = (item.date + timedelta(days=1)).strftime("%Y%m%d")  # DTEND exclusief
            lines.append(f"DTSTART;VALUE=DATE:{dtstart_date}")
            lines.append(f"DTEND;VALUE=DATE:{dtend_date}")

        lines.append("END:VEVENT")


    lines.append("END:VCALENDAR")

    lines = _fold_ics_lines(lines)
    ics_text = "\r\n".join(lines) + "\r\n"
    plain_bytes = ics_text.encode("utf-8")
    etag_plain = _etag_for_bytes(plain_bytes)

    gz_bytes = gzip.compress(plain_bytes, compresslevel=6)
    etag_gzip = _etag_for_bytes(gz_bytes)

    gzip_better = len(gz_bytes) < len(plain_bytes)

    if gzip_better:
        store_bytes = gz_bytes
        store_encoding = "gzip"
    else:
        store_bytes = plain_bytes
        store_encoding = "identity"

    return {
        "store_bytes": store_bytes,
        "store_encoding": store_encoding,
        "etag_plain": etag_plain,
        "etag_gzip": etag_gzip,
        "gzip_better": gzip_better,
        "last_modified_utc": last_modified_utc,
    }


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
    mark_calendar_active(user.id)
    key = _ics_cache_key(user.id)

    wants_gzip = _client_accepts_gzip(request)

    cached = cache.get(key)
    if not cached:
        cached = _build_cached_payload_for_user(user)
        cache.set(key, cached, timeout=60 * 60 * 24 * 7)

    # Decide response representation:
    # - Only serve gzip if client accepts gzip AND gzip is actually smaller.
    serve_gzip = bool(wants_gzip and cached["gzip_better"])

    chosen_etag = cached["etag_gzip"] if serve_gzip else cached["etag_plain"]
    last_modified_utc = cached["last_modified_utc"]

    maybe = _maybe_304(request, chosen_etag, last_modified_utc)
    if maybe:
        return maybe

    store_bytes: bytes = cached["store_bytes"]
    store_encoding: str = cached["store_encoding"]

    if serve_gzip:
        # Need gzip body
        if store_encoding == "gzip":
            body = store_bytes
        else:
            # stored plain, but gzip is better => compress on the fly (should be rare)
            body = gzip.compress(store_bytes, compresslevel=6)

        resp = HttpResponse(body, content_type="text/calendar; charset=utf-8")
        resp["Content-Encoding"] = "gzip"
        resp["ETag"] = chosen_etag

    else:
        # Need plain body
        if store_encoding == "identity":
            body = store_bytes
        else:
            body = gzip.decompress(store_bytes)

        resp = HttpResponse(body, content_type="text/calendar; charset=utf-8")
        resp["ETag"] = chosen_etag

    resp["Content-Disposition"] = 'inline; filename="diensten.ics"'
    resp["Last-Modified"] = _httpdate(last_modified_utc)
    resp["Cache-Control"] = "private, max-age=0, must-revalidate"
    resp["Vary"] = "Accept-Encoding"
    return resp