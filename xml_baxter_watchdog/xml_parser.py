import re
import xml.etree.ElementTree as ET


FILENAME_PATTERN = re.compile(
    r'^(M\d{2})'
    r'(\d{4})'
    r'-(\d{2})'
    r'-(\d{2})'
    r'T(\d{2})'
    r'(\d{2})'
    r'(\d{2})'
    r'\.xml$',
    re.IGNORECASE
)


def parse_filename(filename: str) -> dict:
    basename = filename.split("\\")[-1].split("/")[-1]

    match = FILENAME_PATTERN.match(basename)
    if not match:
        raise ValueError(f"Bestandsnaam matcht niet het verwachte formaat: {basename}")

    machine_id, jaar, maand, dag, uur, minuut, seconde = match.groups()

    return {
        "machine_id": machine_id.upper(),
        "date": f"{jaar}-{maand}-{dag}",
        "time": f"{uur}:{minuut}:{seconde}",
    }


def parse_xml(filepath: str) -> int:
    tree = ET.parse(filepath)
    root = tree.getroot()

    alle_zak_ids = root.findall(".//zak_id")
    if not alle_zak_ids:
        raise ValueError(f"Geen <zak_id> gevonden in {filepath}")

    txt = alle_zak_ids[-1].text
    if not txt:
        raise ValueError(f"Laatste <zak_id> is leeg in {filepath}")

    laatste_zak_id = txt.strip()
    if len(laatste_zak_id) < 5:
        raise ValueError(f"Onverwachte <zak_id> waarde in {filepath}: {laatste_zak_id!r}")

    return int(laatste_zak_id[-5:])


def verwerk_bestand(filepath: str) -> dict:
    metadata = parse_filename(filepath)
    aantal_zakjes = parse_xml(filepath)

    return {
        **metadata,
        "aantal_zakjes": aantal_zakjes,
    }