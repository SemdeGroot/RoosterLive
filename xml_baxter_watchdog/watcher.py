import time
import logging
import os
from logging.handlers import RotatingFileHandler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from xml_baxter_watchdog.xml_parser import verwerk_bestand
from xml_baxter_watchdog.api_client import stuur_naar_api
from xml_baxter_watchdog.config import WATCH_FOLDER

# Helpers

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

# ------------------------------------------------------------------
#  Logging — max 3MB totaal daarna overschreven
#  Bij 144 files/dag (elke 10 min) blijft dit altijd klein
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        RotatingFileHandler(
            "watcher.log",
            maxBytes=3_000_000,   # 3MB, paar dagen aan logs
            backupCount=0,        # watcher.log + watcher.log.1 + watcher.log.2
            encoding="utf-8",
        ),
        logging.StreamHandler(),  # ook naar console / NSSM output
    ]
)
log = logging.getLogger(__name__)


# ------------------------------------------------------------------
#  Event handler
# ------------------------------------------------------------------

class XMLHandler(FileSystemEventHandler):

    def on_created(self, event):
        if event.is_directory:
            return

        filepath = event.src_path

        if not filepath.lower().endswith(".xml"):
            return

        # Soms schrijft het systeem het bestand nog, even wachten
        wacht_tot_bestand_stabiel(filepath)

        try:
            payload = verwerk_bestand(filepath)
            ok = stuur_naar_api(payload)

            if ok:
                log.info(
                    f"{payload['machine_id']} | {payload['date']} {payload['time']} "
                    f"| {payload['aantal_zakjes']} zakjes | [SUCCES] verstuurd"
                )
            else:
                log.error(
                    f"{payload['machine_id']} | {payload['date']} {payload['time']} "
                    f"| {payload['aantal_zakjes']} zakjes | [ERROR] API versturen mislukt"
                )

        except ValueError as e:
            log.error(f"{filepath} | [ERROR] Parse fout: {e}")
        except Exception as e:
            log.exception(f"{filepath} | [ERROR] Onverwacht: {e}")


# ------------------------------------------------------------------
#  Main
# ------------------------------------------------------------------

if __name__ == "__main__":
    if not os.path.isdir(WATCH_FOLDER):
        log.error(f"Watch folder bestaat niet: {WATCH_FOLDER}")
        raise SystemExit(1)

    handler = XMLHandler()
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