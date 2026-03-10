# Teamdashboard (Technisch)

De module **Teamdashboard** binnen de **Apotheek Jansen App** vormt de kern van de planningslogica en beheert de toewijzing van diensten aan medewerkers.

## Technisch ontwerp
De module integreert realtime beschikbaarheidsgegevens van medewerkers met een flexibel rooster-systeem. Een essentieel onderdeel van het ontwerp is de scheiding tussen **concepten** (ShiftDraft) en **gepubliceerde diensten** (Shift), waardoor planners wijzigingen kunnen voorbereiden zonder de live-omgeving direct te beïnvloeden.

## Datamodel
De module wordt ondersteund door de volgende modellen in `core/models.py`:

- **Availability**:
    - Bevat de beschikbaarheid van een gebruiker per datum en dagdeel (`Dagdeel`).
- **ShiftDraft**:
    - Bevat de voorlopige toewijzingen (`upsert` of `delete` acties).
    - Wordt gebruikt om wijzigingen in het dashboard bij te houden vóór publicatie.
- **Shift**:
    - De definitieve, gepubliceerde toewijzingen.
- **Task & Location**:
    - Definiëren waar en welke werkzaamheden worden uitgevoerd.
- **Dagdeel**:
    - Definieert de tijdsvensters en eventuele toeslag-percentages.

## Implementatiedetails
- **Dashboard View**: De `personeelsdashboard_view` in `core/views/personeelsdashboard.py` berekent de beschikbaarheid en bezetting voor een geselecteerde week.
- **Draft Systeem**: Bij elke interactie in het dashboard (toevoegen of verwijderen van een dienst) wordt een AJAX-verzoek gestuurd naar de API (`pd_save_concept`, `pd_delete_shift`). Dit resulteert in een record in `ShiftDraft`.
- **Publiceren**: De `publish_shifts_api` voert de volgende acties uit in een database-transactie:
    1. Synchroniseren van alle `ShiftDraft` records naar het `Shift` model.
    2. Verwijderen van de verwerkte `ShiftDraft` records.
    3. Triggeren van push-notificaties en e-mails naar medewerkers.
    4. Invalideren van de iCal-caches voor alle betrokken medewerkers.
- **Kopiëren**: De `pd_copy_prev_week` API kopieert uitsluitend de *gepubliceerde* diensten van de voorgaande week naar de huidige week als nieuwe concepten (`ShiftDraft`).

## Autorisatie en beveiliging
- Toegang tot de module vereist de permissie `can_view_beschikbaarheidsdashboard`.
- Actieve bewerkingen (opslaan, publiceren) zijn beperkt tot gebruikers met `can_edit_beschikbaarheidsdashboard`.
- De module respecteert organisatie-grenzen; planners zien alleen medewerkers binnen hun eigen autorisatie-bereik.

## Relevante bestanden
- `core/models.py`: Definities van `Shift`, `ShiftDraft`, `Availability`.
- `core/views/personeelsdashboard.py`: Hoofdlogica en API endpoints voor planning.
- `core/templates/personeelsdashboard/index.html`: Dashboard interface.
- `core/static/js/personeelsdashboard.js`: Frontend logica voor drag-and-drop en API interactie.
