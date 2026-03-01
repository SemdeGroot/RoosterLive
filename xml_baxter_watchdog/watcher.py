import os
import time
import logging
from datetime import date

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from xml_baxter_watchdog.xml_parser import verwerk_bestand, parse_filename
from xml_baxter_watchdog.api_client import stuur_naar_api
from xml_baxter_watchdog.env_config import WATCH_FOLDER


LOG_FILE      = "watcher.log"
LOG_MAX_BYTES = 3_000_000
POLL_INTERVAL = 60  # seconden


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
        fh.setFormatter(fmt)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(sh)

    return logger


def _nieuwste_dag_in_folder(log: logging.Logger) -> date | None:
    """Geeft de nieuwste datum terug die voorkomt in de bestandsnamen, of None als er niets geldig is."""
    try:
        bestanden = [f for f in os.listdir(WATCH_FOLDER) if f.lower().endswith(".xml")]
    except OSError:
        return None

    nieuwste: date | None = None
    for filename in bestanden:
        try:
            meta = parse_filename(filename)
        except ValueError:
            continue
        d = date.fromisoformat(meta["date"])
        if nieuwste is None or d > nieuwste:
            nieuwste = d
    return nieuwste


class XMLHandler(FileSystemEventHandler):
    def __init__(self, log: logging.Logger) -> None:
        self.log = log
        # Initialiseer op de nieuwste dag die al in de folder zit, zodat
        # bestanden van die dag bij herstart niet opnieuw verstuurd worden.
        gevonden = _nieuwste_dag_in_folder(log)
        self._huidige_dag: date = gevonden if gevonden is not None else date.today()
        self._verstuurd: set[tuple[str, str, str]] = set()
        self.log.info(f"Handler gestart | actieve dag: {self._huidige_dag}")

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".xml"):
            self._verwerk(event.src_path)

    def on_moved(self, event):
        # Sommige systemen schrijven eerst naar een temp-bestand en hernoemen daarna.
        if not event.is_directory and event.dest_path.lower().endswith(".xml"):
            self._verwerk(event.dest_path)

    def _verwerk(self, filepath: str) -> None:
        filename = os.path.basename(filepath)

        try:
            meta = parse_filename(filename)
        except ValueError:
            return

        bestand_dag = date.fromisoformat(meta["date"])

        # Reset bij nieuwe dag op basis van bestandsnaam, niet op systeemtijd.
        if bestand_dag > self._huidige_dag:
            self.log.info(f"Nieuwe dag gedetecteerd ({bestand_dag}), verstuurd-set gereset.")
            self._verstuurd.clear()
            self._huidige_dag = bestand_dag

        # Bestanden van een oudere dag dan de actieve dag negeren.
        if bestand_dag < self._huidige_dag:
            return

        key = (meta["machine_id"], meta["date"], meta["time"])
        if key in self._verstuurd:
            return

        try:
            payload = verwerk_bestand(filepath)
        except ValueError as e:
            self.log.warning(f"{filename} | Parse fout: {e}")
            return

        truncate_log_if_needed(LOG_FILE, LOG_MAX_BYTES)
        ok = stuur_naar_api(payload)

        if ok:
            self._verstuurd.add(key)
            self.log.info(
                f"{payload['machine_id']} | {payload['date']} {payload['time']} "
                f"| {payload['aantal_zakjes']} zakjes | [SUCCES]"
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

    while not os.path.isdir(WATCH_FOLDER):
        log.warning("Netwerkmap niet bereikbaar, wacht 10s...")
        time.sleep(10)

    handler = XMLHandler(log)
    observer = PollingObserver(timeout=POLL_INTERVAL)
    observer.schedule(handler, path=WATCH_FOLDER, recursive=False)
    observer.start()
    log.info(f"Gestart | PollingObserver elke {POLL_INTERVAL}s | watching: {WATCH_FOLDER}")

    try:
        while True:
            time.sleep(5)
            if not observer.is_alive():
                log.warning("Observer gestopt, herstarten...")
                while not os.path.isdir(WATCH_FOLDER):
                    log.warning("Netwerkmap niet bereikbaar, wacht 10s...")
                    time.sleep(10)
                observer = PollingObserver(timeout=POLL_INTERVAL)
                observer.schedule(handler, path=WATCH_FOLDER, recursive=False)
                observer.start()
                log.info("Observer herstart.")
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
    log.info("Gestopt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())