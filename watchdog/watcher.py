import time
import logging
import os
from logging.handlers import RotatingFileHandler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from xml_parser import verwerk_bestand
from api_client import stuur_naar_api
from config import WATCH_FOLDER


# ------------------------------------------------------------------
#  Logging — max 3MB totaal (3 x 1MB), daarna overschreven
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
        time.sleep(1)

        try:
            payload = verwerk_bestand(filepath)
            stuur_naar_api(payload)
            log.info(
                f"{payload['machine_id']} | {payload['date']} {payload['time']} "
                f"| {payload['aantal_zakjes']} zakjes | [SUCCES] verstuurd"
            )

        except ValueError as e:
            log.error(f"{filepath} | [ERROR] Parse fout: {e}")
        except (ConnectionError, TimeoutError, RuntimeError) as e:
            log.error(f"{filepath} | [ERROR] API fout: {e}")
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