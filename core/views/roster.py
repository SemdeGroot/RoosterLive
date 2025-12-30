# core/views/roster.py
from datetime import date, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone, translation
from django.core.files.storage import default_storage

from core.models import RosterWeek
from core.tasks import send_roster_updated_push_task

from ._helpers import (
    can,
    ROSTER_DIR,            # MEDIA_ROOT / "rooster"
    CACHE_ROSTER_DIR,      # CACHE_DIR / "rooster"
    clear_dir,
)

from ._upload_helpers import (
    save_upload_with_hash,
    ensure_pdf_previews_exist,
    list_pdf_preview_urls,
    read_storage_bytes,
    _media_relpath,
)

# Helpers delen met beschikbaarheid
from .mijnbeschikbaarheid import _monday_of_iso_week, _clamp_week


# -----------------------------
# Slug helpers: 'weekNN' (alleen weeknummer)
# -----------------------------
def _week_slug_from_monday(monday: date) -> str:
    _, iso_week, _ = monday.isocalendar()
    return f"week{iso_week:02d}"


def _week_pdf_dir(monday: date) -> Path:
    # /media/.../rooster/weekNN
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
    # /media/.../cache/rooster/weekNN
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

    - In DEV: opruimen op filesystem.
    - In PROD: opruimen in S3 onder:
        media/rooster/weekNN/...
        media/cache/rooster/weekNN/...
    """
    ROSTER_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_ROSTER_DIR.mkdir(parents=True, exist_ok=True)

    allowed = _allowed_week_slugs(min_monday, weeks_ahead)

    # === DEV: lokaal filesystem ===
    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        for week_dir in ROSTER_DIR.glob("week*"):
            if not week_dir.is_dir():
                continue
            if week_dir.name not in allowed:
                try:
                    clear_dir(week_dir)
                    week_dir.rmdir()
                except Exception:
                    pass

        for cache_week_dir in CACHE_ROSTER_DIR.glob("week*"):
            if not cache_week_dir.is_dir():
                continue
            if cache_week_dir.name not in allowed:
                try:
                    clear_dir(cache_week_dir)
                    cache_week_dir.rmdir()
                except Exception:
                    pass

        return

    # === PROD: S3 ===
    roster_root = _media_relpath(ROSTER_DIR)  # "rooster"
    try:
        week_dirs, _files = default_storage.listdir(roster_root)
    except FileNotFoundError:
        week_dirs = []

    for slug in list(week_dirs):
        if slug not in allowed:
            week_prefix = f"{roster_root}/{slug}"
            try:
                _subdirs, files = default_storage.listdir(week_prefix)
            except FileNotFoundError:
                files = []
            for name in files:
                if name.lower().endswith(".pdf"):
                    default_storage.delete(f"{week_prefix}/{name}")

    # Cache: cache/rooster/weekNN/<hash>/page_XXX.(webp/png)
    cache_root = "cache/rooster"
    try:
        cache_week_dirs, _ = default_storage.listdir(cache_root)
    except FileNotFoundError:
        cache_week_dirs = []

    for slug in list(cache_week_dirs):
        if slug not in allowed:
            week_cache_prefix = f"{cache_root}/{slug}"
            try:
                hash_dirs, _files = default_storage.listdir(week_cache_prefix)
            except FileNotFoundError:
                hash_dirs = []
            for h in hash_dirs:
                hash_prefix = f"{week_cache_prefix}/{h}"
                try:
                    _d2, files = default_storage.listdir(hash_prefix)
                except FileNotFoundError:
                    files = []
                for name in files:
                    # verwijder zowel webp als png
                    if name.startswith("page_") and (name.endswith(".webp") or name.endswith(".png")):
                        default_storage.delete(f"{hash_prefix}/{name}")


@login_required
def rooster(request):
    if not can(request.user, "can_view_roster"):
        return HttpResponseForbidden("Geen toegang tot rooster.")

    translation.activate("nl")

    today = timezone.localdate()
    base_date = today + timedelta(weeks=1) if today.weekday() >= 4 else today

    WEEKS_AHEAD = 12
    min_monday = _monday_of_iso_week(today)
    max_monday = _monday_of_iso_week(today + timedelta(weeks=WEEKS_AHEAD))

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

    # --- upload ---
    if request.method == "POST":
        if not can(request.user, "can_upload_roster"):
            return HttpResponseForbidden("Geen uploadrechten.")

        form_monday = request.POST.get("monday") or monday.isoformat()
        try:
            y, m, d = map(int, form_monday.split("-"))
            post_monday = _clamp_week(date(y, m, d), min_monday, max_monday)
        except Exception:
            post_monday = monday

        post_week_pdf_dir = _week_pdf_dir(post_monday)
        post_week_cache_dir = _week_cache_dir(post_monday)

        f = request.FILES.get("file")
        if not f or not f.name.lower().endswith(".pdf"):
            messages.error(request, "Upload een PDF-bestand (.pdf).")
            return redirect(f"{reverse('rooster')}?monday={post_monday.isoformat()}")

        post_week_pdf_dir.mkdir(parents=True, exist_ok=True)
        CACHE_ROSTER_DIR.mkdir(parents=True, exist_ok=True)

        # Lees bytes voor directe render
        pdf_bytes = f.read()
        try:
            f.seek(0)
        except Exception:
            pass

        # Cache voor deze week leegmaken
        clear_dir(post_week_cache_dir)

        # PDF opslaan als rooster.<hash>.pdf (max 1 per week)
        rel_path, h = save_upload_with_hash(
            uploaded_file=f,
            target_dir=post_week_pdf_dir,
            base_name="rooster",
            clear_existing=True,
            convert_images_to_webp=False,
        )

        # Render previews (webp voorkeur)
        hash_id, n_pages, ext_used = ensure_pdf_previews_exist(
            pdf_bytes=pdf_bytes,
            cache_root=post_week_cache_dir,
            file_hash=h,
        )

        # Model updaten
        RosterWeek.objects.update_or_create(
            monday=post_monday,
            defaults={
                "week_slug": _week_slug_from_monday(post_monday),
                "file_path": rel_path,
                "file_hash": hash_id,
                "n_pages": n_pages,
                "preview_ext": ext_used,
            },
        )

        # Weekinfo voor notificatie
        iso_year_post, iso_week_post, _ = post_monday.isocalendar()
        week_end_post = post_monday + timedelta(days=4)

        messages.success(request, f"Rooster voor week {iso_week_post} geüpload.")

        send_roster_updated_push_task.delay(
            iso_year_post,
            iso_week_post,
            post_monday.isoformat(),
            week_end_post.isoformat(),
        )

        # ==== Direct nieuwe roster tonen voor post_monday ====
        monday_view = post_monday
        week_end = week_end_post
        iso_year, iso_week, _ = monday_view.isocalendar()

        prev_raw = monday_view - timedelta(weeks=1)
        next_raw = monday_view + timedelta(weeks=1)
        has_prev = prev_raw >= min_monday
        has_next = next_raw <= max_monday
        prev_monday = prev_raw if has_prev else min_monday
        next_monday = next_raw if has_next else max_monday

        week_slug = _week_slug_from_monday(monday_view)
        week_cache_dir = _week_cache_dir(monday_view)

        page_urls, _ext_used2 = list_pdf_preview_urls(
            cache_root=week_cache_dir,
            file_hash=hash_id,
        )

        context = {
            "year": datetime.now().year,
            "monday": monday_view,
            "week_end": week_end,
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_monday": prev_monday,
            "next_monday": next_monday,
            "week_slug": week_slug,
            "no_roster": False,
            "page_urls": page_urls,
            "header_title": f"Week {iso_week} – {iso_year}",
            "min_monday": min_monday,
            "max_monday": max_monday,
            "week_options": [],
            "can_upload": can(request.user, "can_upload_roster"),
        }

        cur = min_monday
        while cur <= max_monday:
            context["week_options"].append({
                "value": cur.isoformat(),
                "start": cur,
                "end": cur + timedelta(days=4),
                "iso_week": cur.isocalendar()[1],
                "iso_year": cur.isocalendar()[0],
            })
            cur += timedelta(weeks=1)

        return render(request, "rooster/index.html", context)

    # ==== GET / normale weergave ====
    week_end = monday + timedelta(days=4)
    iso_year, iso_week, _ = monday.isocalendar()

    prev_raw = monday - timedelta(weeks=1)
    next_raw = monday + timedelta(weeks=1)
    has_prev = prev_raw >= min_monday
    has_next = next_raw <= max_monday
    prev_monday = prev_raw if has_prev else min_monday
    next_monday = next_raw if has_next else max_monday

    week_slug = _week_slug_from_monday(monday)
    week_pdf_dir = _week_pdf_dir(monday)
    week_pdf_path = _week_pdf_path(monday)
    week_cache_dir = _week_cache_dir(monday)

    context = {
        "year": datetime.now().year,
        "monday": monday,
        "week_end": week_end,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_monday": prev_monday,
        "next_monday": next_monday,
        "week_slug": week_slug,
        "no_roster": False,
        "page_urls": [],
        "header_title": f"Week {iso_week} – {iso_year}",
        "min_monday": min_monday,
        "max_monday": max_monday,
        "week_options": [],
        "can_upload": can(request.user, "can_upload_roster"),
    }

    cur = min_monday
    while cur <= max_monday:
        context["week_options"].append({
            "value": cur.isoformat(),
            "start": cur,
            "end": cur + timedelta(days=4),
            "iso_week": cur.isocalendar()[1],
            "iso_year": cur.isocalendar()[0],
        })
        cur += timedelta(weeks=1)

    # 1) Probeer eerst uit model + cache (zodat je geen PDF hoeft te lezen)
    rw = RosterWeek.objects.filter(monday=monday).first()
    if rw and rw.file_hash:
        urls, _ext_used = list_pdf_preview_urls(
            cache_root=week_cache_dir,
            file_hash=rw.file_hash,
        )
        if urls:
            context["page_urls"] = urls
            context["no_roster"] = False
            return render(request, "rooster/index.html", context)

    # 2) Fallback: PDF ophalen (DEV vs PROD) en previews maken
    storage_path = None

    if getattr(settings, "SERVE_MEDIA_LOCALLY", False) or settings.DEBUG:
        if not week_pdf_path.exists():
            context["no_roster"] = True
            return render(request, "rooster/index.html", context)
        pdf_bytes = week_pdf_path.read_bytes()
        # rel_path in dev (voor model)
        rel_dir = _media_relpath(week_pdf_dir)
        storage_path = f"{rel_dir}/{week_pdf_path.name}" if rel_dir else week_pdf_path.name
    else:
        week_rel_dir = _media_relpath(week_pdf_dir)  # bijv. "rooster/week48"
        try:
            _dirs, files = default_storage.listdir(week_rel_dir)
        except FileNotFoundError:
            files = []

        pdf_name = None
        hashed = sorted(
            name for name in files
            if name.startswith("rooster.") and name.endswith(".pdf")
        )
        if hashed:
            pdf_name = hashed[-1]
        elif "rooster.pdf" in files:
            pdf_name = "rooster.pdf"

        if not pdf_name:
            context["no_roster"] = True
            return render(request, "rooster/index.html", context)

        storage_path = f"{week_rel_dir}/{pdf_name}"
        with default_storage.open(storage_path, "rb") as f:
            pdf_bytes = f.read()

    # Previews maken/zekerstellen
    hash_id, n_pages, ext_used = ensure_pdf_previews_exist(
        pdf_bytes=pdf_bytes,
        cache_root=week_cache_dir,
        file_hash=(rw.file_hash if rw and rw.file_hash else None),
    )

    # Model bijwerken/aanmaken
    RosterWeek.objects.update_or_create(
        monday=monday,
        defaults={
            "week_slug": week_slug,
            "file_path": storage_path or "",
            "file_hash": hash_id,
            "n_pages": n_pages,
            "preview_ext": ext_used,
        },
    )

    urls, _ext_used2 = list_pdf_preview_urls(cache_root=week_cache_dir, file_hash=hash_id)
    context["page_urls"] = urls

    return render(request, "rooster/index.html", context)