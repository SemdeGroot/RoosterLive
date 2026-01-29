# core/utils/medication.py
import json
from pathlib import Path
from django.conf import settings


def _load_jansen_groups_json():
    """
    Leest je JSON met Jansen groepen.
    Verwacht: [{"id": 1, "name": "Vallen?"}, ...]
    """
    path = Path(settings.BASE_DIR) / "core" / "data" / "jansen_groups.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data

def get_jansen_group_choices():
    """
    Choices voor forms/model fields.
    -> alfabetisch op naam i.p.v. op id
    """
    data = _load_jansen_groups_json()

    # Sorteren op naam (case-insensitive)
    data_sorted = sorted(data, key=lambda item: (item.get("name") or "").strip().casefold())

    return [(int(item["id"]), item["name"]) for item in data_sorted]

def get_jansen_group_map():
    """
    Handig voor lookups: {id: name}
    """
    data = _load_jansen_groups_json()
    return {int(item["id"]): item["name"] for item in data}


def group_meds_by_jansen(geneesmiddelen_lijst, overrides_lookup=None):
    """
    Groepeert meds op Jansen ID, met ondersteuning voor overrides per patient.

    - Default grouping: gm["ATC3_jansen_id"] (fallback 43)
    - Override: overrides_lookup = { "<gm.clean>": <target_jansen_group_id> }

    Verplichte lege groepen:
      1 = Vallen?
      2 = Malen?
      50 = Buiten formularium?
    """
    overrides_lookup = overrides_lookup or {}
    # keys veilig maken (strip)
    overrides_lookup = { (k or "").strip(): v for k, v in overrides_lookup.items() if k is not None }

    jansen_map = get_jansen_group_map()

    # verplichte groepen (mogen leeg zijn)
    groepen = {
        1:  {"naam": jansen_map.get(1, "Vallen?"), "meds": []},
        2:  {"naam": jansen_map.get(2, "Malen?"), "meds": []},
        50: {"naam": jansen_map.get(50, "Buiten formularium?"), "meds": []},
    }

    for gm in geneesmiddelen_lijst:
        if not isinstance(gm, dict):
            continue

        med_clean = (gm.get("clean") or "").strip()
        if not med_clean:
            continue

        # override?
        override_gid = None
        if med_clean in overrides_lookup:
            override_gid = overrides_lookup.get(med_clean)

        raw_gid = override_gid if override_gid is not None else gm.get("ATC3_jansen_id")

        try:
            gid = int(raw_gid) if raw_gid is not None else 43
        except (TypeError, ValueError):
            gid = 43

        # Vallen/Malen zijn geen medicatie-groepen
        if gid in (1, 2):
            continue

        # ✅ BELANGRIJK:
        # Als override actief is -> groepsnaam uit JSON gebruiken, nooit uit gm (oude naam)
        if override_gid is not None:
            gnaam = jansen_map.get(gid, "Overig")
        else:
            gnaam = (gm.get("ATC3_jansen_naam") or jansen_map.get(gid) or "Overig")

        if gid not in groepen:
            groepen[gid] = {"naam": gnaam, "meds": []}
        else:
            # als groep al bestond, maar naam is per ongeluk leeg/Overig, verbeter hem
            if (groepen[gid].get("naam") in (None, "", "Overig")) and gnaam:
                groepen[gid]["naam"] = gnaam

        groepen[gid]["meds"].append(gm)

    return sorted(groepen.items(), key=lambda item: item[0])