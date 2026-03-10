# Inschrijven (Technisch)

De module **Inschrijven** binnen de **Apotheek Jansen App** functioneert als portaal voor externe inschrijfformulieren en activiteiten.

## Technisch ontwerp
De module is ontworpen als een eenvoudige lijstbeheerder waarbij externe links (`URLField`) worden gekoppeld aan titels en verloopdata. De module bevat logica voor automatische filtering op basis van de huidige datum.

## Datamodel
De module wordt ondersteund door het `InschrijvingItem` model in `core/models.py`.

- **InschrijvingItem**:
    - `title`: De naam van de activiteit of het formulier.
    - `url`: De volledige URL naar de externe omgeving.
    - `verloopdatum`: Datum waarna het item automatisch wordt verborgen (optioneel).
    - `created_by`: Verwijzing naar de gebruiker die het item heeft aangemaakt.

## Implementatiedetails
- **Lijstweergave**: De `inschrijvingen` view in `core/views/inschrijven.py` filtert de items in de database. Alleen items waarbij de `verloopdatum` in de toekomst ligt of `NULL` is, worden getoond aan reguliere gebruikers.
- **Sorteervolgorde**: Items worden primair gesorteerd op `verloopdatum` (oplopend) en vervolgens op `title`. Hierdoor verschijnen items die bijna verlopen bovenaan de lijst.
- **CRUD Operaties**: Beheerders met de juiste rechten kunnen direct vanuit de interface nieuwe items toevoegen of bestaande items bewerken via modals.

## Autorisatie en beveiliging
- Gebruikers hebben de permissie `can_view_inschrijven` nodig om de lijst te bekijken.
- Beheerfuncties (toevoegen, bewerken, verwijderen) zijn beperkt tot gebruikers met de permissie `can_edit_inschrijven`.
- Bij het openen van externe links wordt `target="_blank"` gebruikt om de veiligheid en UX van de app te waarborgen.

## Relevante bestanden
- `core/models.py`: Definitie van `InschrijvingItem`.
- `core/views/inschrijven.py`: Logica voor weergave en beheer.
- `core/templates/inschrijven/index.html`: Frontend template.
