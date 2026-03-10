# Urendoorgeven (Technisch)

De module **Urendoorgeven** binnen de **Apotheek Jansen App** verzorgt de registratie en verwerking van gewerkte uren en reiskosten.

## Technisch ontwerp
De module maakt gebruik van een gelaagd datamodel waarbij ruwe invoer (`UrenDag`) wordt vertaald naar geatomiseerde regels (`UrenRegel`) om berekeningen en rapportages te vergemakkelijken. De module integreert met het roostersysteem om gewerkte diensten weer te geven.

## Datamodel
De module wordt ondersteund door de volgende modellen in `core/models.py`:

- **UrenMaand**:
    - Bevat metadata per gebruiker per kalendermaand (bijv. `kilometers`).
- **UrenDag**:
    - Bevat de ruwe dagelijkse invoer (`start_time`, `end_time`, `break_hours`).
- **UrenRegel**:
    - Een afgeleide tabel waarin gewerkte uren per `Dagdeel` worden opgeslagen. Dit model wordt gebruikt voor de daadwerkelijke berekening van toeslagen en rapportages.
- **Dagdeel**:
    - Definieert de tijdsvensters en de bijbehorende `allowance_pct` (bijv. 120% voor avonddiensten).

## Implementatiedetails
- **Uren Invoeren**: De `urendoorgeven` view in `core/views/urendoorgeven.py` verwerkt zowel handmatige invoer als bulk-acties (voorinvullen vanuit shifts).
- **Berekeningslogica**: Bij het opslaan van een `UrenDag` wordt op de achtergrond de bijbehorende `UrenRegel` records bijgewerkt. Hierbij wordt gecontroleerd in welke dagdelen de gewerkte tijd valt.
- **Kilometerregistratie**: Kilometergegevens worden opgeslagen in `UrenMaand` gekoppeld aan de eerste dag van de betreffende maand.
- **Email herinneringen**: Een Celery beat task (`core/tasks/beat/uren.py`) controleert periodiek of gebruikers met een actieve planning hun uren al hebben ingediend voor de voorgaande maand. Indien niet, wordt er een automatische e-mail verstuurd.

## Autorisatie en beveiliging
- Gebruikers hebben de permissie `can_view_urendoorgeven` nodig om hun eigen uren in te zien en in te voeren.
- De permissie `can_edit_urendoorgeven` is gereserveerd voor beheerders die uren van andere medewerkers moeten kunnen inzien of corrigeren.
- Wijzigingen in het verleden (voorgaande maanden) kunnen worden geblokkeerd op basis van administratieve deadlines (implementatie afhankelijk van configuratie).

## Relevante bestanden
- `core/models.py`: Definities van `UrenMaand`, `UrenDag`, `UrenRegel`.
- `core/views/urendoorgeven.py`: Logica voor registratie en beheer.
- `core/tasks/beat/uren.py`: Achtergrondtaak voor herinneringen.
- `core/templates/urendoorgeven/index.html`: Frontend template.
- `core/static/js/urendoorgeven/urendoorgeven.js`: Interactieve invoer-logica.
