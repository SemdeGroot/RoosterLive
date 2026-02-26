import gc
import hashlib
import os
import random
import tempfile
import time
from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from django.utils import timezone

from core.models import ScrapedPage
from core.utils.nhgscraper.scraper import NHGScraper
from core.utils.kompasscraper.scraper import KompasScraper

LOCK_KEY = "lock:nhg_scraper"
LOCK_TTL = 6 * 60 * 60  # 6 uur

RECIPIENT = "semdegroot2003@gmail.com"

# Interne NHG categorienamen -> opslag in ScrapedPage.category
CATEGORY_MAP = {
    "standaard": "nhg_standaard",
    "behandelrichtlijn": "nhg_behandelrichtlijn",
}


def _send_error_mail(subject: str, body: str, log_storage_path: str) -> None:
    email = EmailMessage(subject=subject, body=body, to=[RECIPIENT])
    try:
        with default_storage.open(log_storage_path, "rb") as f:
            email.attach(
                filename=os.path.basename(log_storage_path),
                content=f.read(),
                mimetype="text/plain",
            )
    except Exception:
        pass
    email.send(fail_silently=True)


@shared_task(
    name="tasks.run_nhg_scraper",
    time_limit=4 * 60 * 60,
    soft_time_limit=3 * 60 * 60,
)
def run_nhg_scraper(test_mode=False):
    if not cache.add(LOCK_KEY, "1", timeout=LOCK_TTL):
        return "NHG scraper draait al; nieuwe run overgeslagen."

    start_ts = timezone.localtime()
    ts = start_ts.strftime("%Y%m%d_%H%M%S")

    tmp_dump_dir = (os.getenv("FK_TMP_DUMP_DIR", "").strip() or "tmp/kompasgpt").strip("/")
    # Log blijft staan in storage - niet verwijderd na afloop
    log_storage_path = f"{tmp_dump_dir}/logs/{ts}_nhg_run.log"

    analyzed = 0
    uploaded = 0
    unchanged = 0
    errors = 0
    consecutive_errors = 0
    MAX_CONSEC_ERRORS = 25
    MAX_ERROR_LOG_LINES = 50

    sample_url_by_cat = {cat: None for cat in CATEGORY_MAP}
    dumped_paths = []
    aborted = False

    tmp_log = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8")
    tmp_log_path = tmp_log.name

    def log(line: str, flush: bool = False) -> None:
        now = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
        tmp_log.write(f"[{now}] {line}\n")
        if flush:
            tmp_log.flush()

    try:
        nhg_scraper = NHGScraper()
        kompas = KompasScraper()

        log(f"START run (test_mode={test_mode})", flush=True)

        all_discovered = nhg_scraper.discovery_phase()
        log(f"DISCOVERY: {len(all_discovered)} items gevonden", flush=True)

        seven_days_ago = timezone.now() - timedelta(days=7)

        existing_urls_map = {
            p.url: p.last_scraped
            for p in ScrapedPage.objects.filter(
                url__in=[item["url"] for item in all_discovered]
            )
        }

        new_items = []
        outdated_items = []
        for item in all_discovered:
            url = item["url"]
            if url not in existing_urls_map:
                new_items.append(item)
            elif existing_urls_map[url] < seven_days_ago:
                outdated_items.append(item)

        # 1/7 van totaal per dag zodat alles wekelijks langskomt
        batch_limit = 3 if test_mode else max(1, len(all_discovered) // 7)
        urls = (new_items + outdated_items)[:batch_limit]
        total_to_analyze = len(urls)

        log(
            f"BATCH: {total_to_analyze} (limit=1/7={batch_limit}, "
            f"nieuw={len(new_items)}, oud={len(outdated_items)})",
            flush=True,
        )

        # Reservoir sampling: 1 sample per categorie voor md dump
        seen_cat = {cat: 0 for cat in CATEGORY_MAP}
        for it in urls:
            cat = it.get("category")
            if cat not in seen_cat:
                continue
            seen_cat[cat] += 1
            if random.randint(1, seen_cat[cat]) == 1:
                sample_url_by_cat[cat] = it.get("url")
        log(f"SAMPLES {sample_url_by_cat}", flush=True)

        for item in urls:
            if test_mode and analyzed >= 10:
                log("TESTMODE stop after 10")
                break

            analyzed += 1
            nhg_cat = item.get("category")
            url = item.get("url")
            storage_cat = CATEGORY_MAP.get(nhg_cat, nhg_cat)
            want_dump = url is not None and url == sample_url_by_cat.get(nhg_cat)

            try:
                title, md_content = nhg_scraper.scrape_to_markdown(url)

                if not md_content or not title:
                    errors += 1
                    consecutive_errors += 1
                    if errors <= MAX_ERROR_LOG_LINES:
                        log(f"ERROR(empty) cat={nhg_cat} url={url}", flush=True)
                else:
                    new_hash = hashlib.sha256(md_content.encode("utf-8")).hexdigest()
                    page_obj, created = ScrapedPage.objects.get_or_create(url=url)
                    unchanged_page = not created and page_obj.content_hash == new_hash

                    if want_dump:
                        dumped_path = kompas._maybe_dump_md_to_tmp(
                            title=title,
                            md_content=md_content,
                            category=storage_cat,
                        )
                        if dumped_path:
                            dumped_paths.append(dumped_path)

                    if unchanged_page:
                        ScrapedPage.objects.filter(url=url).update(last_scraped=timezone.now())
                        unchanged += 1
                        consecutive_errors = 0
                    elif kompas.upload_to_gemini(
                        title,
                        md_content,
                        source_url=url,
                        category=storage_cat,
                    ):
                        page_obj.title = title
                        page_obj.category = storage_cat
                        page_obj.content_hash = new_hash
                        page_obj.save()
                        uploaded += 1
                        consecutive_errors = 0
                    else:
                        errors += 1
                        consecutive_errors += 1
                        if errors <= MAX_ERROR_LOG_LINES:
                            log(f"ERROR(upload) cat={nhg_cat} url={url}", flush=True)

                if analyzed % 20 == 0:
                    gc.collect()
                    pct = (analyzed / total_to_analyze) * 100
                    log(
                        f"PROGRESS: {analyzed}/{total_to_analyze} ({pct:.1f}%) | "
                        f"uploaded={uploaded} unchanged={unchanged} errors={errors}",
                        flush=True,
                    )

                if consecutive_errors >= MAX_CONSEC_ERRORS:
                    log(f"ABORT: {consecutive_errors} consecutive errors", flush=True)
                    aborted = True
                    break

            except Exception as e:
                errors += 1
                consecutive_errors += 1
                if errors <= MAX_ERROR_LOG_LINES or errors % 100 == 0:
                    log(f"ERROR cat={nhg_cat} url={url} err={type(e).__name__}: {e}", flush=True)
                if consecutive_errors >= MAX_CONSEC_ERRORS:
                    log(f"ABORT: {consecutive_errors} consecutive errors", flush=True)
                    aborted = True
                    break

            time.sleep(random.uniform(1, 3))

        end_ts = timezone.localtime()
        duration = end_ts - start_ts
        summary = (
            f"SUMMARY analyzed={analyzed} uploaded={uploaded} unchanged={unchanged} "
            f"errors={errors} dumped={len(dumped_paths)} duration={duration}"
        )
        log(summary, flush=True)

        # Schrijf log naar storage (blijft staan)
        tmp_log.close()
        with open(tmp_log_path, "rb") as f:
            default_storage.save(log_storage_path, ContentFile(f.read()))

        # Mail alleen bij errors of abort
        if errors > 0 or aborted:
            subject = f"[FOUT] NHG scrape {ts} — errors={errors}{' ABORTED' if aborted else ''}"
            body = (
                f"NHG scrape run heeft fouten gehad.\n\n"
                f"{summary}\n\n"
                f"Log opgeslagen op: {log_storage_path}\n"
            )
            _send_error_mail(subject, body, log_storage_path)

        # Verwijder tijdelijke md dumps (log blijft staan)
        for p in dumped_paths:
            try:
                default_storage.delete(p)
            except Exception:
                pass

        return summary

    finally:
        try:
            if os.path.exists(tmp_log_path):
                os.remove(tmp_log_path)
        except Exception:
            pass
        cache.delete(LOCK_KEY)
        gc.collect()