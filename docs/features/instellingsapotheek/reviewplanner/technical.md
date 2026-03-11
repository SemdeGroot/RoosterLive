# Review planner (Technisch)

## Technisch ontwerp
De Review planner module is opgebouwd rondom het `ReviewPlanner` model. De interface maakt gebruik van een interactieve tabel met autosave-functionaliteit en een modal-venster voor invoer. Voor de export naar Excel wordt de `openpyxl` bibliotheek gebruikt.

## Datamodel
De module maakt gebruik van de volgende modellen in `core/models.py`:

- **`ReviewPlanner`**: Bevat de velden `datum`, `afdeling` (FK naar `MedicatieReviewAfdeling`), `status`, `arts`, `tijd`, `bijzonderheden`, `voorbereid_door` (FK naar `User`), `uitgevoerd_door` (FK naar `User`), `created_by`, `updated_by` en tijdstempels.
- **`MedicatieReviewAfdeling`**: Wordt gebruikt als referentie voor de afdelingen waarvoor reviews gepland worden.

## Implementatiedetails
- **Weergave en bewerking**: De `reviewplanner` view in `core/views/reviewplanner.py` handelt zowel de weergave (GET) als de verwerking van wijzigingen (POST) af.
- **Validatie**: Bij het opslaan (zowel via modal als autosave) wordt gevalideerd of de datum niet verder dan 4 weken in het verleden ligt.
- **Autosave**: De frontend verstuurt wijzigingen in bulk (`action="autosave"`) naar de server, waar de records atomair worden bijgewerkt.
- **Export**: De functie `reviewplanner_export_overview` genereert een Excel-bestand met alle opgeslagen reviews, inclusief details van afdeling en organisatie.

## Autorisatie en beveiliging
De volgende permissies zijn van toepassing:

- **`can_view_reviewplanner`**: Vereist om de module te kunnen inzien.
- **`can_edit_reviewplanner`**: Vereist om reviews toe te voegen, te wijzigen of te exporteren.
- **`can_perform_medicatiebeoordeling`**: Alleen gebruikers met deze permissie kunnen worden geselecteerd als `voorbereid_door` of `uitgevoerd_door`.

## Relevante bestanden
- `core/models.py`: Definitie van het `ReviewPlanner` model.
- `core/views/reviewplanner.py`: Logica voor weergave, opslaan en export.
- `core/forms.py`: `ReviewPlannerForm` voor validatie en modal-invoer.
- `core/templates/reviewplanner/index.html`: Frontend template voor de interactieve interface.
