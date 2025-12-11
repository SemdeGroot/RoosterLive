def group_meds_by_jansen(geneesmiddelen_lijst):
    """
    Groepeert meds op Jansen ID.
    Zorgt dat ID 1 (Vallen?) en ID 2 (Malen?) ALTIJD aanwezig zijn,
    ook als er geen medicatie in zit.
    """
    
    # 1. We initialiseren de 'verplichte' groepen vooraf.
    #    Zo zijn ze altijd aanwezig, ook als de lijst meds leeg is.
    groepen = {
        1: {'naam': 'Vallen?', 'meds': []},
        2: {'naam': 'Malen?',  'meds': []}
    }

    # 2. Loop door de daadwerkelijke medicatie
    for gm in geneesmiddelen_lijst:
        gm = gm if isinstance(gm, dict) else {}
        
        # ID ophalen en veilig naar int converteren
        raw_id = gm.get("ATC3_jansen_id")
        try:
            gid = int(raw_id) if raw_id is not None else 9999
        except ValueError:
            gid = 9999
            
        gnaam = gm.get("ATC3_jansen_naam") or "Overig"
        
        # Als deze groep nog niet bestaat (bijv ID 3, 4, etc), maak hem aan.
        # ID 1 en 2 bestaan al, dus die slaan we hier over (en behouden de naam).
        if gid not in groepen:
            groepen[gid] = {'naam': gnaam, 'meds': []}
        else:
            # Optioneel: Update de naam als de parser een specifiekere naam heeft,
            # maar voor 1 en 2 wil je waarschijnlijk je eigen hardcoded naam houden.
            # Als je de parser naam leidend wilt laten zijn voor ID 1 en 2, uncomment dan:
            # groepen[gid]['naam'] = gnaam
            pass
        
        # Voeg medicijn toe aan de lijst
        groepen[gid]['meds'].append(gm)

    # 3. Sorteer numeriek op ID (1, 2, 3 ... 9999)
    sorted_groups = sorted(groepen.items(), key=lambda item: item[0])
    
    return sorted_groups