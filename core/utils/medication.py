import json
from pathlib import Path
from django.conf import settings


def _load_jansen_groups_json():
    path = Path(settings.BASE_DIR) / "core" / "data" / "jansen_groups.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data


def get_jansen_group_choices():
    data = _load_jansen_groups_json()
    data_sorted = sorted(data, key=lambda item: (item.get("name") or "").strip().casefold())
    return [(int(item["id"]), item["name"]) for item in data_sorted]


def get_jansen_group_map():
    data = _load_jansen_groups_json()
    return {int(item["id"]): item["name"] for item in data}


def group_meds_by_jansen(geneesmiddelen_lijst, overrides_lookup=None):
    """
    Groepeert meds op Jansen ID, met ondersteuning voor overrides per patient.

    overrides_lookup keys are (med_clean, med_gebruik) tuples.
    gebruik is the unique disambiguator for duplicate med names.

    Verplichte lege groepen:
      0  = Labwaarden
      1  = Vallen?
      2  = Malen?
      50 = Buiten formularium?
    """
    overrides_lookup = overrides_lookup or {}
    jansen_map = get_jansen_group_map()

    groepen = {
        0:  {"naam": jansen_map.get(0,  "Labwaarden"),          "meds": []},
        1:  {"naam": jansen_map.get(1,  "Vallen?"),             "meds": []},
        2:  {"naam": jansen_map.get(2,  "Malen?"),              "meds": []},
        50: {"naam": jansen_map.get(50, "Buiten formularium?"), "meds": []},
    }

    for gm in geneesmiddelen_lijst:
        if not isinstance(gm, dict):
            continue

        med_clean = (gm.get("clean") or "").strip()
        if not med_clean:
            continue

        gebruik = (gm.get("gebruik") or "").strip()

        try:
            natural_gid = int(gm.get("ATC3_jansen_id")) if gm.get("ATC3_jansen_id") is not None else 43
        except (TypeError, ValueError):
            natural_gid = 43

        # (med_clean, gebruik) uniquely identifies a medication row.
        override_gid = overrides_lookup.get((med_clean, gebruik))

        gid = override_gid if override_gid is not None else natural_gid

        # 0, 1, 2 are non-medication groups; never place meds there.
        if gid in (0, 1, 2):
            continue

        if override_gid is not None:
            gnaam = jansen_map.get(gid, "Overig")
        else:
            gnaam = (gm.get("ATC3_jansen_naam") or jansen_map.get(gid) or "Overig")

        if gid not in groepen:
            groepen[gid] = {"naam": gnaam, "meds": []}
        else:
            if (groepen[gid].get("naam") in (None, "", "Overig")) and gnaam:
                groepen[gid]["naam"] = gnaam

        groepen[gid]["meds"].append(gm)

    return sorted(groepen.items(), key=lambda item: item[0])