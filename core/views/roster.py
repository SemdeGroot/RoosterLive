from datetime import date, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone, translation

from core.tasks import send_roster_updated_push_task
from ._helpers import (
    can,
    ROSTER_DIR,            # bijv. MEDIA_ROOT / "rooster"
    CACHE_ROSTER_DIR,      # bijv. MEDIA_ROOT / "cache" / "rooster"
    clear_dir,
    render_pdf_to_cache,   # (pdf_bytes, dpi, cache_root) -> (hash_id, n_pages)
    save_pdf_upload_with_hash,
)

# Belangrijk: helpers importeren uit je bestaande beschikbaarheid-view
from .mijnbeschikbaarheid import _monday_of_iso_week, _clamp_week


# -----------------------------
# Slug helpers: 'weekNN' (alleen weeknummer)
# -----------------------------
def _week_slug_from_monday(monday: date) -> str:
    _, iso_week, _ = monday.isocalendar()
    return f"week{iso_week:02d}"

def _week_pdf_dir(monday: date) -> Path:
    return (ROSTER_DIR / _week_slug_from_monday(monday)).resolve()

def _week_pdf_path(monday: date) -> Path:
    """
    Zoek de PDF voor deze week:

    - eerst: rooster.<hash>.pdf in de weekmap
    - anders: fallback naar legacy rooster.pdf
    """
    d = _week_pdf_dir(monday)
    if d.exists():
        candidates = sorted(d.glob("rooster.*.pdf"))
        if candidates:
            return candidates[-1]

    # legacy fallback
    return d / "rooster.pdf"

def _week_cache_dir(monday: date) -> Path:
    return (CACHE_ROSTER_DIR / _week_slug_from_monday(monday)).resolve()


def _allowed_week_slugs(min_monday: date, weeks_ahead: int) -> set:
    """Set met 'weekNN' slugs voor [min_monday .. min_monday + weeks_ahead]."""
    allowed = set()
    cur = min_monday
    for _ in range(weeks_ahead + 1):
        allowed.add(_week_slug_from_monday(cur))
        cur += timedelta(weeks=1)
    return allowed


def _roster_housekeeping(min_monday: date, weeks_ahead: int) -> None:
    """
    Verwijder alle weekmappen (PDF + cache) die NIET in het venster
    [huidige week .. +weeks_ahead] vallen.
    Daardoor verdwijnt week x automatisch zodra week x+1 start.
    """
    ROSTER_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_ROSTER_DIR.mkdir(parents=True, exist_ok=True)

    allowed = _allowed_week_slugs(min_monday, weeks_ahead)

    # Rooster-weekmappen
    for week_dir in ROSTER_DIR.glob("week*"):
        if not week_dir.is_dir():
            continue
        if week_dir.name not in allowed:
            try:
                clear_dir(week_dir)
                week_dir.rmdir()
            except Exception:
                pass

    # Cache-weekmappen
    for cache_week_dir in CACHE_ROSTER_DIR.glob("week*"):
        if not cache_week_dir.is_dir():
            continue
        if cache_week_dir.name not in allowed:
            try:
                clear_dir(cache_week_dir)
                cache_week_dir.rmdir()
            except Exception:
                pass


@login_required
def rooster(request):
    if not can(request.user, "can_view_roster"):
        return HttpResponseForbidden("Geen toegang tot rooster.")

    translation.activate("nl")

    today = timezone.localdate()
    # Vanaf vrijdag standaard volgende week tonen
    base_date = today + timedelta(weeks=1) if today.weekday() >= 4 else today

    WEEKS_AHEAD = 12
    min_monday = _monday_of_iso_week(today)
    max_monday = _monday_of_iso_week(today + timedelta(weeks=WEEKS_AHEAD))

    # Housekeeping t.o.v. de huidige week
    _roster_housekeeping(min_monday=min_monday, weeks_ahead=WEEKS_AHEAD)

    # --- weekselectie ---
    qs_monday = request.GET.get("monday")
    qs_week = request.GET.get("week")

    if qs_monday:
        try:
            y, m, d = map(int, qs_monday.split("-"))
            monday = date(y, m, d)
        except Exception:
            monday = _monday_of_iso_week(base_date)
    elif qs_week:
        try:
            if "-W" in qs_week:
                year_str, wstr = qs_week.split("-W")
            else:
                year_str, wstr = qs_week.split("-")
            monday = date.fromisocalendar(int(year_str), int(wstr), 1)
        except Exception:
            monday = _monday_of_iso_week(base_date)
    else:
        monday = _monday_of_iso_week(base_date)

    monday = _clamp_week(monday, min_monday, max_monday)
    week_end = monday + timedelta(days=4)
    iso_year, iso_week, _ = monday.isocalendar()

    # Navigatie
    prev_raw = monday - timedelta(weeks=1)
    next_raw = monday + timedelta(weeks=1)
    has_prev = prev_raw >= min_monday
    has_next = next_raw <= max_monday
    prev_monday = prev_raw if has_prev else min_monday
    next_monday = next_raw if has_next else max_monday

    # Paden
    week_slug = _week_slug_from_monday(monday)   # 'weekNN'
    week_pdf_dir = _week_pdf_dir(monday)         # /media/rooster/weekNN/
    week_pdf_path = _week_pdf_path(monday)       # zoekt rooster.<hash>.pdf of legacy rooster.pdf
    week_cache_dir = _week_cache_dir(monday)     # /media/cache/rooster/weekNN/

    # --- upload ---
    if request.method == "POST":
        if not can(request.user, "can_upload_roster"):
            return HttpResponseForbidden("Geen uploadrechten.")

        # Hidden field bepaalt doelweek voor upload (beheerder kan vooruit werken)
        form_monday = request.POST.get("monday") or monday.isoformat()
        try:
            y, m, d = map(int, form_monday.split("-"))
            post_monday = _clamp_week(date(y, m, d), min_monday, max_monday)
        except Exception:
            post_monday = monday

        post_week_pdf_dir = _week_pdf_dir(post_monday)
        post_week_pdf_path = _week_pdf_path(post_monday)
        post_week_cache_dir = _week_cache_dir(post_monday)

        f = request.FILES.get("file")
        if not f or not f.name.lower().endswith(".pdf"):
            messages.error(request, "Upload een PDF-bestand (.pdf).")
            return redirect(f"{reverse('rooster')}?monday={post_monday.isoformat()}")

        post_week_pdf_dir.mkdir(parents=True, exist_ok=True)
        CACHE_ROSTER_DIR.mkdir(parents=True, exist_ok=True)

        # Cache-week map leegmaken zodat oude hash-subfolders weg zijn
        clear_dir(post_week_cache_dir)

        # PDF schrijven als rooster.<hash>.pdf in de weekmap (max 1 per week)
        save_pdf_upload_with_hash(
            uploaded_file=f,
            target_dir=post_week_pdf_dir,
            base_name="rooster",
            clear_existing=True,
        )

        # Weekinfo voor notificatie
        iso_year_post, iso_week_post, _ = post_monday.isocalendar()
        week_end_post = post_monday + timedelta(days=4)

        messages.success(request, f"Rooster voor week {iso_week_post} geüpload.")

        # Celery-push met weeknummer + datums
        send_roster_updated_push_task.delay(
            iso_year_post,
            iso_week_post,
            post_monday.isoformat(),   # maandag
            week_end_post.isoformat(), # vrijdag
        )

        return HttpResponseRedirect(f"{reverse('rooster')}?monday={post_monday.isoformat()}")

    # --- weergave ---
    context = {
        "year": datetime.now().year,
        "monday": monday,
        "week_end": week_end,                             # voor daterange
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_monday": prev_monday,
        "next_monday": next_monday,
        "week_slug": week_slug,
        "no_roster": False,
        "page_urls": [],
        "header_title": f"Week {iso_week} – {iso_year}",  # identiek aan beschikbaarheid
        "min_monday": min_monday,
        "max_monday": max_monday,
        "week_options": [],
        "can_upload": can(request.user, "can_upload_roster"),
    }

    # Dropdown: huidige week → +12 weken (toon ook iso_year)
    cur = min_monday
    while cur <= max_monday:
        context["week_options"].append({
            "value": cur.isoformat(),
            "start": cur,
            "end": cur + timedelta(days=4),
            "iso_week": cur.isocalendar()[1],
            "iso_year": cur.isocalendar()[0],   # <--- hier was de typo, nu goed
        })
        cur += timedelta(weeks=1)

    if not week_pdf_path.exists():
        context["no_roster"] = True
        return render(request, "rooster/index.html", context)

    # PDF -> cache renderen; let op hash-subfolder
    pdf_bytes = week_pdf_path.read_bytes()
    hash_id, n = render_pdf_to_cache(pdf_bytes, dpi=300, cache_root=week_cache_dir)

    context["page_urls"] = [
        f"{settings.MEDIA_URL}cache/rooster/{week_slug}/{hash_id}/page_{i:03d}.png"
        for i in range(1, n + 1)
    ]

    return render(request, "rooster/index.html", context)

