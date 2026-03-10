# Diensten (Technisch)

De module **Diensten** binnen de **Apotheek Jansen App** beheert het weergeven en ontsluiten van persoonlijke werkroosters voor medewerkers.

## Technisch ontwerp
De architectuur is opgebouwd rondom de toewijzing van specifieke taken (`Task`) op specifieke tijdstippen (`Shift`) aan gebruikers. De module integreert een webkalender-systeem (WebCal/iCal) en een notificatiesysteem (Celery tasks voor e-mail en push-notificaties).

## Datamodel
De module wordt ondersteund door de volgende modellen in `core/models.py`:

- **Shift**:
    - `user`: De medewerker.
    - `task`: De specifieke taak die uitgevoerd moet worden.
    - `date`: De datum van de dienst.
    - `period`: Het dagdeel (`morning`, `afternoon`, `evening`).
- **Task**:
    - Gekoppeld aan een `Location`.
- **Location**:
    - Bevat naam, adres en kleurcode voor weergave.
- **UserProfile**:
    - Bevat het `calendar_token` (UUID) voor unieke iCal-synchronisatie.

## Implementatiedetails
- **Roosterweergave**: De `mijndiensten_view` in `core/views/diensten.py` berekent de ISO-week en haalt de bijbehorende shifts op. Het rooster is beperkt tot 12 weken in de toekomst.
- **iCal Synchronisatie**: Gerealiseerd via `core/views/diensten_webcal.py`. Er wordt een `.ics` bestand gegenereerd op basis van de unieke `calendar_token` van de gebruiker. De cache wordt automatisch ongeldig gemaakt (`signals.py`) zodra een relevante dienst of taak wordt gewijzigd.
- **Wekelijkse Mail**: Een Celery beat task (`core/tasks/beat/dienstenoverzicht.py`) verstuurt elke vrijdagavond een gepersonaliseerd overzicht van de diensten voor de volgende week naar alle actieve gebruikers.
- **Push Notificaties**: Bij het publiceren van roosterwijzigingen in het **Teamdashboard** wordt via `core/utils/push/push.py` een signaal verzonden naar de relevante apparaten.

## Autorisatie en beveiliging
- Gebruikers hebben de permissie `can_view_diensten` nodig om hun rooster in te zien.
- Toegang tot de iCal-feed is beveiligd via een uniek UUID-token in de URL. Bij misbruik kan dit token worden vernieuwd door een beheerder (door de `calendar_token` in `UserProfile` te resetten).

## Relevante bestanden
- `core/models.py`: Definities van `Shift`, `Task`, `Location`.
- `core/views/diensten.py`: Logica voor de weergave van het rooster.
- `core/views/diensten_webcal.py`: Engine voor iCal export.
- `core/tasks/beat/dienstenoverzicht.py`: Achtergrondtaak voor wekelijkse mail.
- `core/templates/diensten/index.html`: Frontend template.
- `core/static/js/diensten/diensten.js`: Interactieve elementen (zoals agenda-modal).
