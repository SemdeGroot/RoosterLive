import sys
import os
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from xml_parser import parse_filename, parse_xml


# ------------------------------------------------------------------
#  Bestandsnaam tests
# ------------------------------------------------------------------

def test_filename_machine_02():
    result = parse_filename("M022025-12-03T102017.xml")
    assert result["machine_id"] == "M02"
    assert result["date"] == "2025-12-03"
    assert result["time"] == "10:20:17"
    print("[SUCCES] test_filename_machine_02")

def test_filename_machine_12():
    result = parse_filename("M122025-11-26T143449.xml")
    assert result["machine_id"] == "M12"
    assert result["date"] == "2025-11-26"
    assert result["time"] == "14:34:49"
    print("[SUCCES] test_filename_machine_12")

def test_filename_invalid():
    try:
        parse_filename("ongeldig_bestand.xml")
        print("[ERROR] test_filename_invalid: had ValueError moeten gooien")
    except ValueError:
        print("[SUCCES] test_filename_invalid (ValueError correct)")


# ------------------------------------------------------------------
#  zak_id tests
# ------------------------------------------------------------------

def maak_test_xml(zak_ids: list) -> str:
    root = ET.Element("root")
    for zak_id in zak_ids:
        el = ET.SubElement(root, "zak_id")
        el.text = str(zak_id)
    tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="w", encoding="utf-8")
    ET.ElementTree(root).write(tmp.name, encoding="unicode")
    return tmp.name

def test_zak_id_leading_zero():
    path = maak_test_xml(["2511261206313"])
    assert parse_xml(path) == 6313
    os.unlink(path)
    print("[SUCCES] test_zak_id_leading_zero (06313 -> 6313)")

def test_zak_id_no_leading_zero():
    path = maak_test_xml(["2511261210000"])
    assert parse_xml(path) == 10000
    os.unlink(path)
    print("[SUCCES] test_zak_id_no_leading_zero (10000 -> 10000)")

def test_zak_id_pakt_laatste():
    path = maak_test_xml(["2511261200001", "2511261206313", "2511261299999"])
    assert parse_xml(path) == 99999
    os.unlink(path)
    print("[SUCCES] test_zak_id_pakt_laatste (allerlaatste entry)")

def test_zak_id_geen_gevonden():
    path = maak_test_xml([])
    try:
        parse_xml(path)
        print("[ERROR] test_zak_id_geen_gevonden: had ValueError moeten gooien")
    except ValueError:
        print("[SUCCES] test_zak_id_geen_gevonden (ValueError correct)")
    finally:
        os.unlink(path)


if __name__ == "__main__":
    print("=== Parser tests ===\n")
    test_filename_machine_02()
    test_filename_machine_12()
    test_filename_invalid()
    print()
    test_zak_id_leading_zero()
    test_zak_id_no_leading_zero()
    test_zak_id_pakt_laatste()
    test_zak_id_geen_gevonden()
    print("\n=== Alle tests geslaagd ===")