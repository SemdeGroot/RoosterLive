# Beschikbaarheid (Technisch)

## Technisch ontwerp
De Beschikbaarheid module in de **Apo Jansen App** is gebaseerd op het `Availability` en het `Dagdeel` model. Het systeem ondersteunt zowel handmatige invoer door gebruikers als automatische generatie op basis van contractuele instellingen in het `UserProfile`.

## Datamodel
De belangrijkste modellen zijn:

### Availability
- `user`: De gebruiker voor wie de beschikbaarheid geldt.
- `date`: De specifieke datum van de beschikbaarheid (unique per gebruiker).
- `dagdelen`: Een ManyToMany relatie met het model `Dagdeel`.
- `source`: De bron van de beschikbaarheid ("auto" voor contractueel, "manual" voor handmatig).

### Dagdeel
- `code`: Unieke identifier (bijv. "morning", "afternoon", "pre_evening").
- `start_time` / `end_time`: Tijden die het dagdeel definiëren.
- `allowance_pct`: Het percentage toeslag dat geldt voor dit dagdeel (bijv. 120 voor 20% toeslag).
- `PLANNING_CODES`: Geeft aan welke codes ("morning", "afternoon", "pre_evening") gebruikt mogen worden voor de reguliere planning.

## Implementatiedetails
De module bevat logica voor de volgende processen:

- **Automatische Invulling**: In `core/utils/beat/fill.py` bevinden zich de functies `fill_availability_for_profile` en `rebuild_auto_availability_for_profile`. Deze functies genereren automatisch `Availability` records op basis van de `work_mon_am` etc. velden in het `UserProfile`.
- **Dienstverband**: De automatische invulling vindt alleen plaats voor medewerkers met een vast dienstverband (`Dienstverband.VAST`).
- **Dagdeel Toeslagen**: Het `Dagdeel` model bevat logica om te bepalen of er overlappingen zijn tussen verschillende dagdelen (`clean` methode) en berekent de toeslag-multiplier.

## Autorisatie en beveiliging
De toegang wordt beheerd via de volgende Django permissies:

- `can_access_availability`: Mag de beschikbaarheidspagina openen en bekijken.
- `can_send_beschikbaarheid`: Mag handmatig beschikbaarheid doorgeven voor zichzelf.
- `can_view_beschikbaarheidsdashboard`: Mag het overzicht van alle beschikbare medewerkers bekijken.
- `can_edit_beschikbaarheidsdashboard`: Mag wijzigingen aanbrengen in de beschikbaarheid van andere medewerkers of diensten toewijzen.

## Relevante bestanden
De belangrijkste bestanden voor deze module zijn:

- `core/models.py`: Definities van `Availability` en `Dagdeel`.
- `core/views/mijnbeschikbaarheid.py`: Bevat de logica voor het tonen en aanpassen van de eigen beschikbaarheid.
- `core/utils/beat/fill.py`: Bevat de logica voor de automatische generatie van beschikbaarheid.
- `core/forms.py`: Bevat het `AvailabilityUploadForm`.
