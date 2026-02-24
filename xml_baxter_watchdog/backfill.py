import os
import logging
from datetime import date

from xml_baxter_watchdog.xml_parser import verwerk_bestand, parse_filename
from xml_baxter_watchdog.api_client import stuur_naar_api
from xml_baxter_watchdog.env_config import WATCH_FOLDER

BACKFILL_FROM = date(2026, 1, 1)


def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("backfill")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def _select_last_file_per_machine_per_day(filenames: list[str], log: logging.Logger) -> list[str]:
    """
    For each (machine_id, date) pair keep only the file with the latest time.
    Works because the timestamp portion HHMMSS is fixed-width, so lexicographic == chronological.
    """
    best: dict[tuple[str, str], str] = {}

    for filename in filenames:
        try:
            meta = parse_filename(filename)
        except ValueError as e:
            log.warning(f"{filename} | overgeslagen (ongeldige bestandsnaam): {e}")
            continue

        key = (meta["machine_id"], meta["date"])
        if key not in best or filename > best[key]:
            best[key] = filename

    return sorted(best.values())


def run_backfill() -> int:
    log = _setup_logging()

    if not os.path.isdir(WATCH_FOLDER):
        log.error(f"Watch folder bestaat niet: {WATCH_FOLDER}")
        return 1

    all_xml = sorted(f for f in os.listdir(WATCH_FOLDER) if f.lower().endswith(".xml"))

    if not all_xml:
        log.info("Geen XML bestanden gevonden.")
        return 0

    candidates = _select_last_file_per_machine_per_day(all_xml, log)

    selected = []
    skipped_date = 0
    for filename in candidates:
        meta = parse_filename(filename)
        if date.fromisoformat(meta["date"]) < BACKFILL_FROM:
            skipped_date += 1
        else:
            selected.append(filename)

    log.info(
        f"Totaal: {len(all_xml)} bestanden | "
        f"Na deduplicatie: {len(candidates)} | "
        f"Te verwerken: {len(selected)} | "
        f"Voor {BACKFILL_FROM} overgeslagen: {skipped_date}"
    )

    ok_count = 0
    error_count = 0

    for filename in selected:
        filepath = os.path.join(WATCH_FOLDER, filename)

        try:
            payload = verwerk_bestand(filepath)
        except ValueError as e:
            log.error(f"{filename} | [ERROR] Parse fout: {e}")
            error_count += 1
            continue

        ok = stuur_naar_api(payload)
        if ok:
            log.info(
                f"{payload['machine_id']} | {payload['date']} {payload['time']} "
                f"| {payload['aantal_zakjes']} zakjes | [SUCCES]"
            )
            ok_count += 1
        else:
            log.error(
                f"{payload['machine_id']} | {payload['date']} {payload['time']} "
                f"| {payload['aantal_zakjes']} zakjes | [ERROR] API versturen mislukt"
            )
            error_count += 1

    log.info(f"Klaar. Verstuurd: {ok_count} | Fouten: {error_count}")
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_backfill())