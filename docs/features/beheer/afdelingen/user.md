# Afdelingenbeheer (Gebruiker)

## Doel van de module
Het beheren van afdelingen binnen zorginstellingen waarvoor medicatiebeoordelingen worden uitgevoerd. Deze module zorgt voor een correcte indeling van patiënten per afdeling binnen de applicatie.

## Wat kun je met deze module?

- Nieuwe afdelingen aanmaken en koppelen aan een specifieke zorginstelling.
- Bestaande afdelingsnamen en koppelingen wijzigen.
- Afdelingen verwijderen die niet meer relevant zijn.
- Inzicht krijgen in welke afdelingen actief zijn per organisatie.

## Werkwijze

1.  Ga in het hoofdmenu naar **Beheer** en klik op de tegel **Afdelingen**.
2.  **Afdeling toevoegen**: Gebruik het formulier 'Afdeling toevoegen'. Selecteer de zorginstelling in het dropdown-menu en typ de naam van de afdeling in. Klik op 'Opslaan'.
3.  **Afdeling wijzigen**: Klik in de lijst op de afdeling die je wilt aanpassen. Wijzig de naam of de organisatie en sla de wijzigingen op.
4.  **Afdeling verwijderen**: Gebruik de prullenbak-icoon bij de afdeling in de lijst. Let op: dit kan invloed hebben op bestaande medicatiebeoordelingen die aan deze afdeling zijn gekoppeld.

## Bijzonderheden

- Om afdelingen te kunnen beheren, moet je beschikken over de permissie `can_manage_afdelingen`.
- Afdelingen kunnen alleen worden gekoppeld aan organisaties die in het systeem zijn geregistreerd als 'Zorginstelling'.
- De afdelingsindeling wordt direct gebruikt bij het inlezen van patiëntgegevens voor medicatiebeoordelingen.
