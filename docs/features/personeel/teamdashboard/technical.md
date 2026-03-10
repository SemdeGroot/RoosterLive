# Teamdashboard (Technisch)

De module **Teamdashboard** binnen de **Apotheek Jansen App** vormt de kern van de planningslogica en beheert de toewijzing van diensten aan medewerkers via een interactieve interface.

## Technisch ontwerp
Het dashboard is ontworpen als een Single Page Application (SPA)-achtig onderdeel binnen Django. Het combineert server-side rendering van de initiële status met client-side interactie voor een snelle gebruikerservaring.

Een cruciaal concept is het **Draft-systeem**:

- Alle wijzigingen die een planner maakt, worden eerst opgeslagen als `ShiftDraft`.
- Pas bij een expliciete publicatie-actie worden deze omgezet naar definitieve `Shift` records.
- Dit voorkomt dat medewerkers meldingen krijgen van tussentijdse wijzigingen terwijl de planner nog aan het puzzelen is.

## Datamodel
De module maakt gebruik van de volgende modellen in `core/models.py`:

- **Availability**: Koppelt een medewerker aan een datum en één of meerdere `Dagdeel` records om beschikbaarheid aan te geven.
- **ShiftDraft**: Slaat concept-wijzigingen op (`upsert` voor nieuwe/gewijzigde diensten, `delete` voor te verwijderen diensten).
- **Shift**: De gepubliceerde en definitieve diensten.
- **Location & Task**: Definiëren de werkplek en de aard van de werkzaamheden. `Task` bevat per dagdeel minimale bezettingseisen (bijv. `min_mon_morning`).
- **Dagdeel**: De periodes waarin een dag is opgedeeld (ochtend, middag, vooravond).

## Implementatiedetails

### Frontend (JavaScript & CSS)
- **Grid Rendering**: De roosters worden dynamisch opgebouwd in `personeelsdashboard.js` op basis van een JSON-payload (`pd-data`) die door de server wordt aangeleverd.
- **Status Donut Charts**: Er wordt gebruik gemaakt van **Chart.js** om visuele indicatoren te tonen van de planningsstatus per dag. De kleuren (rood/oranje/groen) worden berekend op basis van de verhouding tussen geplande shifts en de `min_`-eisen in het `Task` model.
- **Select2**: Wordt gebruikt in de modals voor het zoeken en selecteren van medewerkers of taken.
- **AJAX Interactie**: Elke wijziging (bijv. het toewijzen van een medewerker aan een slot) triggert een POST-verzoek naar de API, die de state update en de nieuwe `draftShifts` teruggeeft om het grid te verversen zonder pagina-reload.

### Backend (Python/Django)
- **`personeelsdashboard_view`**: Verzamelt alle relevante data (gebruikers, taken, beschikbaarheid, shifts, drafts) voor de geselecteerde week en bereidt de JSON-payload voor.
- **Atomic Publishing**: De `publish_shifts_api` voert de conversie van drafts naar shifts uit binnen een `transaction.atomic()`.
- **Signalen & Tasks**: Na een succesvolle publicatie wordt een Celery-task (`send_user_shifts_changed_push_task`) aangeroepen om push-notificaties te versturen naar de betrokken medewerkers. Ook worden de iCal-caches voor de betreffende gebruikers geïnvalideerd.
- **Copy Logic**: De `pd_copy_prev_week` API zoekt naar gepubliceerde shifts van de vorige week, filtert op medewerkers met een vast dienstverband en controleert hun beschikbaarheid voor de nieuwe week voordat er drafts worden aangemaakt.

## Autorisatie en beveiliging
- **Inzage**: Vereist de permissie `can_view_beschikbaarheidsdashboard`.
- **Wijzigen**: Vereist de permissie `can_edit_beschikbaarheidsdashboard`.
- **API Security**: Alle API endpoints controleren expliciet op de `can_edit`-permissie en maken gebruik van CSRF-bescherming.

## Relevante bestanden
- **Logica**: `core/views/personeelsdashboard.py`
- **Modellen**: `core/models.py` (zoek naar `Shift`, `ShiftDraft`, `Availability`)
- **Template**: `core/templates/personeelsdashboard/index.html`
- **JavaScript**: `core/static/js/personeelsdashboard/personeelsdashboard.js`
- **Styling**: `core/static/css/personeelsdashboard/personeelsdashboard.css`
- **Push Notificaties**: `core/tasks/push.py`
