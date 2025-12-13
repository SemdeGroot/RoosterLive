def group_meds_by_jansen(geneesmiddelen_lijst):
    """
    Groepeert meds op Jansen ID.
    Zorgt dat ID 1 (Vallen?) en ID 2 (Malen?) ALTIJD aanwezig zijn,
    maar hier worden NOOIT geneesmiddelen aan gekoppeld.
    """

    # 1. Verplichte (lege) groepen vooraf initialiseren
    groepen = {
        1: {'naam': 'Vallen?', 'meds': []},
        2: {'naam': 'Malen?',  'meds': []},
        50: {'naam': 'Formularium B3.0', 'meds': []}
    }

    for gm in geneesmiddelen_lijst:
        if not isinstance(gm, dict):
            continue

        raw_id = gm.get("ATC3_jansen_id")

        # ID veilig naar int
        try:
            gid = int(raw_id) if raw_id is not None else 43
        except ValueError:
            gid = 43

        # ✅ Alles met Jansen ID 1 of 2 nooit als medicijn opnemen
        if gid in (1, 2, 50):
            continue

        gnaam = gm.get("ATC3_jansen_naam") or "Overig"

        # Nieuwe groep aanmaken (behalve 1 en 2, die bestaan al)
        if gid not in groepen:
            groepen[gid] = {'naam': gnaam, 'meds': []}

        # Medicijn toevoegen aan de juiste groep
        groepen[gid]['meds'].append(gm)

    # Gesorteerde lijst van (jansen_id, groep_dict)
    sorted_groups = sorted(groepen.items(), key=lambda item: item[0])
    return sorted_groups