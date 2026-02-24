import re
import xml.etree.ElementTree as ET


# ------------------------------------------------------------------
#  Bestandsnaam parsen
#  Formaat: M022025-12-03T102017.xml
#
#  M02        → machine_id  "M02"
#  2025-12-03 → date        "2025-12-03"
#  102017     → time        "10:20:17"
# ------------------------------------------------------------------

FILENAME_PATTERN = re.compile(
    r'^(M\d{2})'       # Machine: M02, M12
    r'(\d{4})'         # Jaar: 2025
    r'-(\d{2})'        # Maand: 12
    r'-(\d{2})'        # Dag: 03
    r'T(\d{2})'        # Uur: 10
    r'(\d{2})'         # Minuut: 20
    r'(\d{2})'         # Seconde: 17
    r'\.xml$',
    re.IGNORECASE
)


def parse_filename(filename: str) -> dict:
    """
    Geeft dict met machine_id, date, time.
    Gooit ValueError als de bestandsnaam niet matcht.
    """
    # Alleen de bestandsnaam, niet het volledige pad
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


# ------------------------------------------------------------------
#  XML parsen — pakt de allerlaatste <zak_id> uit het bestand
#  Laatste 5 cijfers = aantal zakjes, leading zeros strippen
#
#  Voorbeeld: <zak_id>2511261206313</zak_id>
#             laatste 5 = "06313" → int = 6313
# ------------------------------------------------------------------

def parse_xml(filepath: str) -> int:
    """
    Geeft het aantal zakjes als integer.
    Gooit ValueError als er geen <zak_id> gevonden wordt.
    """
    tree = ET.parse(filepath)
    root = tree.getroot()

    # Alle zak_id elementen ophalen, we willen de laatste
    alle_zak_ids = root.findall(".//zak_id")

    if not alle_zak_ids:
        raise ValueError(f"Geen <zak_id> gevonden in {filepath}")

    laatste_zak_id = alle_zak_ids[-1].text.strip()

    # Laatste 5 cijfers pakken, dan als int (strips leading zeros automatisch)
    aantal_zakjes = int(laatste_zak_id[-5:])

    return aantal_zakjes


# ------------------------------------------------------------------
#  Combineer alles: geeft de volledige payload voor de API
# ------------------------------------------------------------------

def verwerk_bestand(filepath: str) -> dict:
    """
    Parsed bestandsnaam + XML en geeft de volledige API payload.
    """
    metadata = parse_filename(filepath)
    aantal_zakjes = parse_xml(filepath)

    payload = {
        **metadata,
        "aantal_zakjes": aantal_zakjes,
    }

    return payload