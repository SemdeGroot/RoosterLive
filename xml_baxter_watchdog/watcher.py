import os
import time
import logging
from datetime import date
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from xml_baxter_watchdog.xml_parser import verwerk_bestand
from xml_baxter_watchdog.api_client import stuur_naar_api
from xml_baxter_watchdog.env_config import WATCH_FOLDER


LOG_FILE = "watcher.log"
LOG_MAX_BYTES = 3_000_000

MAX_PARSE_ATTEMPTS = 5
RETRY_INTERVAL_S = 1.0


def truncate_log_if_needed(path: str, max_bytes: int) -> None:
    try:
        if os.path.exists(path) and os.path.getsize(path) > max_bytes:
            with open(path, "w", encoding="utf-8"):
                pass
    except OSError:
        pass


def setup_logging() -> logging.Logger:
    truncate_log_if_needed(LOG_FILE, LOG_MAX_BYTES)

    logger = logging.getLogger("xml_baxter_watchdog")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        fmt = logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)

        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(fmt)

        logger.addHandler(fh)
        logger.addHandler(sh)

    return logger


def wacht_tot_bestand_stabiel(filepath: str, timeout_s: int = 10, interval_s: float = 0.25) -> None:
    end = time.time() + timeout_s
    last_size = -1

    while time.time() < end:
        try:
            size = os.path.getsize(filepath)
        except OSError:
            time.sleep(interval_s)
            continue

        if size == last_size and size > 0:
            return

        last_size = size
        time.sleep(interval_s)

    raise TimeoutError(f"Bestand niet stabiel binnen {timeout_s}s: {filepath}")


class XMLHandler(FileSystemEventHandler):
    def __init__(self, log: logging.Logger) -> None:
        self.log = log
        self._verwerkt: set[str] = set()
        self._verwerkt_datum: date = date.today()

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.lower().endswith(".xml"):
            self._verwerk(event.dest_path)

    def on_created(self, event):
        if event.is_directory or not event.src_path.lower().endswith(".xml"):
            return
        self._verwerk(event.src_path)

    def _verwerk(self, filepath: str) -> None:
        vandaag = date.today()
        if vandaag != self._verwerkt_datum:
            self._verwerkt.clear()
            self._verwerkt_datum = vandaag

        key = os.path.basename(filepath).lower()
        if key in self._verwerkt:
            return
        self._verwerkt.add(key)

        try:
            wacht_tot_bestand_stabiel(filepath)
        except TimeoutError as e:
            self.log.error(f"{filepath} | [ERROR] {e}")
            return

        last_error: Exception | None = None

        for attempt in range(1, MAX_PARSE_ATTEMPTS + 1):
            try:
                payload = verwerk_bestand(filepath)
                break
            except ValueError as e:
                last_error = e
                if attempt < MAX_PARSE_ATTEMPTS:
                    self.log.warning(
                        f"{filepath} | Poging {attempt}/{MAX_PARSE_ATTEMPTS} mislukt: {e} — opnieuw over {RETRY_INTERVAL_S}s"
                    )
                    time.sleep(RETRY_INTERVAL_S)
        else:
            truncate_log_if_needed(LOG_FILE, LOG_MAX_BYTES)
            self.log.error(
                f"{filepath} | [ERROR] Parse fout na {MAX_PARSE_ATTEMPTS} pogingen: {last_error}"
            )
            return

        try:
            ok = stuur_naar_api(payload)
        except Exception as e:
            truncate_log_if_needed(LOG_FILE, LOG_MAX_BYTES)
            self.log.exception(f"{filepath} | [ERROR] Onverwacht bij API-aanroep: {e}")
            return

        truncate_log_if_needed(LOG_FILE, LOG_MAX_BYTES)

        if ok:
            self.log.info(
                f"{payload['machine_id']} | {payload['date']} {payload['time']} "
                f"| {payload['aantal_zakjes']} zakjes | [SUCCES] verstuurd"
            )
        else:
            self.log.error(
                f"{payload['machine_id']} | {payload['date']} {payload['time']} "
                f"| {payload['aantal_zakjes']} zakjes | [ERROR] API versturen mislukt"
            )

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true", help="Eenmalig backfill uitvoeren")
    args = parser.parse_args()

    if args.backfill:
        from xml_baxter_watchdog.backfill import run_backfill
        return run_backfill()

    log = setup_logging()

    if not os.path.isdir(WATCH_FOLDER):
        log.error(f"Watch folder bestaat niet: {WATCH_FOLDER}")
        return 1

    handler = XMLHandler(log)
    observer = Observer()
    observer.schedule(handler, path=WATCH_FOLDER, recursive=False)
    observer.start()

    log.info(f"Gestart | watching: {WATCH_FOLDER}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
    log.info("Gestopt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())