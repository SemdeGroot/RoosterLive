from collections import defaultdict

def group_meds_by_jansen(geneesmiddelen_lijst):
    """
    Groepeert een lijst geneesmiddelen (dicts) op basis van 'ATC3_jansen_id'.
    
    Returns:
        Een lijst van tuples, gesorteerd op groepsnaam:
        [
            (1, {'naam': 'Mond', 'meds': [gm1, gm2]}), 
            (2, {'naam': 'Maag/darm', 'meds': [gm3]}),
            ...
        ]
    """
    groepen = {} # Key = ID

    for gm in geneesmiddelen_lijst:
        gm = gm if isinstance(gm, dict) else {}
        
        # Haal ID en Naam uit de API data (ingevuld door jouw nieuwe parser)
        # Fallback naar 999/Overig als het mist
        gid = gm.get("ATC3_jansen_id") or 999
        gnaam = gm.get("ATC3_jansen_naam") or "Overig"
        
        if gid not in groepen:
            groepen[gid] = {'naam': gnaam, 'meds': []}
        
        groepen[gid]['meds'].append(gm)

    # Sorteer de output alfabetisch op NAAM (prettig voor de gebruiker)
    # We gebruiken een lambda functie om te sorteren op de naam in de value dict
    sorted_groups = sorted(groepen.items(), key=lambda item: item[1]['naam'])
    
    return sorted_groups