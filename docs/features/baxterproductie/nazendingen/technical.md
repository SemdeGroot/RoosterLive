# Nazendingen (Technisch)

De module Nazendingen beheert de registratie en de communicatie van geneesmiddelen die tijdelijk niet leverbaar zijn.

## Technisch ontwerp
De module combineert een database-overzicht van nazendingen met functionaliteiten voor PDF-generatie en asynchrone e-maildistributie. De architectuur maakt gebruik van een API-endpoint voor snelle voorraadselectie en Celery-tasks voor achtergrondprocessen.

## Datamodel
- `Nazending`:
    - `voorraad_item`: ForeignKey naar `VoorraadItem` (bevat ZI-nummer en naam).
    - `datum`: De registratiedatum van de nazending.
    - `nazending_tot`: Vrij tekstveld voor de verwachte leverdatum of periode.
    - `alternatief`: Optioneel vrij tekstveld voor vervangende medicatie.

## Implementatiedetails
- **API Zoeken**: `medications_search_api` doorzoekt `VoorraadItem` op ZI-nummer of naam via `icontains`.
- **CRUD**: De view `nazendingen_view` beheert de lijst en wijzigingen via `NazendingForm`.
- **PDF Export**: Maakt gebruik van de helper `_render_pdf` (WeasyPrint) om de HTML-template `nazendingen/pdf/nazendingen_lijst.html` te converteren.
- **Email Distributie**: `send_nazendingen_pdf_task` (Celery) genereert PDF-bestanden en verzendt deze naar geselecteerde organisaties vanuit `baxterezorg@apotheekjansen.com`.

## Autorisatie en beveiliging
- Toegang tot overzichten wordt gecontroleerd via `can_view_av_nazendingen`.
- Wijzigingen en distributie vereisen de permissie `can_upload_nazendingen`.
- De module maakt gebruik van Django's standaard CSRF-beveiliging en SQL-injectie preventie via ORM-queries.

## Relevante bestanden
- `core/models.py`: Het `Nazending` model.
- `core/views/nazendingen.py`: De hoofdview en PDF/Email logica.
- `core/tasks.py`: De Celery-task voor e-mailverzending.
- `core/forms.py`: Het `NazendingForm`.
- `core/templates/nazendingen/`: Interface en PDF-layouts.
