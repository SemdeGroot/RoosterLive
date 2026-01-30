from celery import shared_task
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.core.cache import cache
import tempfile
import time, random
import os
from datetime import timedelta

from core.models import ScrapedPage
from core.utils.kompasscraper.scraper import KompasScraper

LOCK_KEY = "lock:kompas_scraper"
LOCK_TTL = 12 * 60 * 60  # 12 uur

RECIPIENT = "semdegroot2003@gmail.com"

@shared_task(
    name="tasks.run_kompas_scraper",
    time_limit=6 * 60 * 60,
    soft_time_limit=5 * 60 * 60,
)
def run_kompas_scraper(test_mode=False, categories=None):
    if not cache.add(LOCK_KEY, "1", timeout=LOCK_TTL):
        return "Kompas scraper draait al; nieuwe run overgeslagen."

    start_ts = timezone.localtime()
    ts = start_ts.strftime("%Y%m%d_%H%M%S")

    # tmp folder consistent met scraper
    tmp_dump_dir = (os.getenv("FK_TMP_DUMP_DIR", "").strip() or "tmp/kompasgpt").strip("/")
    log_storage_path = f"{tmp_dump_dir}/{ts}_kompas_run.log"

    # Counters / summary
    analyzed = 0
    uploaded = 0
    unchanged = 0
    errors = 0
    consecutive_errors = 0
    MAX_CONSEC_ERRORS = 25
    MAX_ERROR_LOG_LINES = 50

    # Random “sample picks”: 1 url per categorie (niet “de eerste 3”)
    sample_url_by_cat = {"preparaat": None, "groep": None, "indicatie": None}

    # we willen uiteindelijk precies 3 md files opslaan (1 per cat)
    dumped_paths = []

    # log naar lokale temp file (later uploaden naar storage)
    tmp_log = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8")
    tmp_log_path = tmp_log.name

    def log(line: str, flush: bool = False) -> None:
        now = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
        tmp_log.write(f"[{now}] {line}\n")
        if flush:
            tmp_log.flush()

    try:
        limit = 3 if test_mode else None
        scraper = KompasScraper(debug_limit=limit)
        
        log(f"START run (test_mode={test_mode})", flush=True)
        all_discovered = scraper.discovery_phase(categories=categories)
        # SELECTIE LOGICA
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        # Haal alle bekende URLs op uit de DB
        existing_urls_map = {
            p.url: p.last_scraped 
            for p in ScrapedPage.objects.filter(url__in=[item['url'] for item in all_discovered])
        }
        
        new_items = []
        outdated_items = []

        for item in all_discovered:
            url = item['url']
            if url not in existing_urls_map:
                new_items.append(item)
            elif existing_urls_map[url] < seven_days_ago:
                outdated_items.append(item)

        # Prioriteit: Nieuw eerst, dan de rest, totaal max 300 (of 3 bij test_mode)
        batch_limit = 3 if test_mode else 300
        urls = (new_items + outdated_items)[:batch_limit]
        
        total_to_analyze = len(urls)
        log(f"DISCOVERY: {len(all_discovered)} gevonden. BATCH: {total_to_analyze} (Nieuw: {len(new_items)}, Oud: {len(outdated_items)})", flush=True)

        # Reservoir sampling voor samples (moet nu op de gefilterde 'urls' lijst)
        seen_cat = {"preparaat": 0, "groep": 0, "indicatie": 0}
        for it in urls:
            cat = it.get("category")
            if cat not in seen_cat:
                continue
            seen_cat[cat] += 1
            if random.randint(1, seen_cat[cat]) == 1:
                sample_url_by_cat[cat] = it.get("url")
        log(f"SAMPLES {sample_url_by_cat}", flush=True)

        for item in urls:
            if test_mode and analyzed >= 50:
                log("TESTMODE stop after 50 analyses")
                break

            analyzed += 1
            cat = item.get("category")
            url = item.get("url")
            want_dump = (url is not None and url == sample_url_by_cat.get(cat))

            try:
                status, dumped_path = scraper.process_url(item, dump_md=want_dump)

                if analyzed % 20 == 0:
                    import gc
                    gc.collect()
                    # Voeg deze log-regel toe:
                    progress_pct = (analyzed / total_to_analyze) * 100
                    log(f"PROGRESS: {analyzed}/{total_to_analyze} ({progress_pct:.1f}%) | "
                        f"Uploaded: {uploaded}, Unchanged: {unchanged}, Errors: {errors}", flush=True)
                if status == "uploaded":
                    uploaded += 1
                    consecutive_errors = 0
                elif status == "unchanged":
                    ScrapedPage.objects.filter(url=url).update(last_scraped=timezone.now())
                    unchanged += 1
                    consecutive_errors = 0
                else:
                    errors += 1
                    consecutive_errors += 1
                    if errors <= MAX_ERROR_LOG_LINES or errors % 100 == 0:
                        log(f"ERROR(status=failed) cat={cat} url={url}", flush=True)
                    if consecutive_errors >= MAX_CONSEC_ERRORS:
                        log(f"ABORT: {consecutive_errors} consecutive errors (>= {MAX_CONSEC_ERRORS})", flush=True)
                        break

                if dumped_path:
                    dumped_paths.append(dumped_path)

            except Exception as e:
                errors += 1
                consecutive_errors += 1

                # log alleen de eerste 50 errors, daarna elke 100e
                if errors <= MAX_ERROR_LOG_LINES or errors % 100 == 0:
                    log(f"ERROR cat={cat} url={url} err={type(e).__name__}: {e}", flush=True)

                if consecutive_errors >= MAX_CONSEC_ERRORS:
                    log(f"ABORT: {consecutive_errors} consecutive errors (>= {MAX_CONSEC_ERRORS})", flush=True)
                    break


            time.sleep(random.uniform(1, 3))

        end_ts = timezone.localtime()
        duration = end_ts - start_ts

        summary = (
            f"SUMMARY analyzed={analyzed} uploaded={uploaded} unchanged={unchanged} "
            f"errors={errors} dumped={len(dumped_paths)} duration={duration}"
        )
        log(summary, flush=True)

        # upload log naar storage
        tmp_log.close()
        with open(tmp_log_path, "rb") as f:
            default_storage.save(log_storage_path, ContentFile(f.read()))

        # Mail met attachments: log + dumped md files (max 3)
        subject = f"Kompas scrape run {ts} (uploaded={uploaded}, errors={errors})"
        body = (
            "Kompas scrape run is klaar.\n\n"
            f"{summary}\n\n"
            f"Sample picks:\n{sample_url_by_cat}\n\n"
            "Attachments: log + sample markdown files (1 per categorie als beschikbaar)."
        )

        email = EmailMessage(
            subject=subject,
            body=body,
            to=[RECIPIENT],
        )

        # attach log
        with default_storage.open(log_storage_path, "rb") as f:
            email.attach(filename=os.path.basename(log_storage_path), content=f.read(), mimetype="text/plain")

        # attach md dumps (1 per categorie, dus max 3)
        for p in dumped_paths[:3]:
            try:
                with default_storage.open(p, "rb") as f:
                    email.attach(filename=os.path.basename(p), content=f.read(), mimetype="text/markdown")
            except Exception as e:
                # als attachment faalt, schrijf in log maar laat mail doorlopen
                # (we kunnen log niet meer append-en in storage, dus schrijf in body)
                body += f"\n\nKon attachment niet openen: {p} ({e})"

        email.body = body
        email.send(fail_silently=False)

        # Verwijder tmp files uit storage (S3) nadat mail is verstuurd
        for p in [log_storage_path] + dumped_paths:
            try:
                default_storage.delete(p)
            except Exception:
                pass

        return summary

    finally:
        # cleanup local temp log
        try:
            if os.path.exists(tmp_log_path):
                os.remove(tmp_log_path)
        except Exception:
            pass
        cache.delete(LOCK_KEY)
        import gc
        gc.collect()