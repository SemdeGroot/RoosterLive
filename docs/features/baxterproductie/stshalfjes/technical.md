# STS Halfjes (Technisch)

De STS Halfjes module registreert geneesmiddelen die onnodig gehalveerd worden in het baxterproces. De module faciliteert rapportage en communicatie hierover naar de betreffende apotheken.

## Architectuur en Gegevensmodel

### Model: `STSHalfje`
Het model bevindt zich in `core/models.py`.


- `afdeling`: CharField voor de afdeling van de patiënt.
- `item_gehalveerd`: ForeignKey naar `VoorraadItem` (gehalveerd middel).
- `item_alternatief`: ForeignKey naar `VoorraadItem` (alternatieve sterkte).
- `apotheek`: ForeignKey naar `Organization` (eigenaar van de melding).
- `patient_naam_enc` en `patient_geboortedatum_enc`: Versleutelde velden voor patiëntgegevens via `EncryptedCharField` en `EncryptedDateField`.

### Views
De logica is ondergebracht in `core/views/stshalfjes.py`.


- `stshalfjes(request)`: Hoofdpagina voor weergave en beheer via `STSHalfjeForm`.
- `export_stshalfjes_pdf(request)`: Genereert PDF-export van (gefilterde) meldingen.
- `email_stshalfjes_pdf(request)`: Start de Celery-task voor e-mailverzending.

## Verzending en PDF-generatie

### Celery Task: `send_stshalfjes_pdf_task`
De verzending verloopt via `core/tasks/emails.py`. De workflow is:


1.  **Iteratie**: Per `Organization ID` wordt een PDF gegenereerd.
2.  **Filtering**: Meldingen worden gefilterd op `apotheek_id`.
3.  **PDF Creatie**: De PDF wordt opgebouwd met template `stshalfjes/pdf/onnodig_gehalveerde_geneesmiddelen.html` via de `_render_pdf` helper.
4.  **E-mail Dispatcher**: Signaal naar `email_dispatcher_task` met type `stshalfjes_single`.
5.  **Verwijdering**: Na succesvolle verzending roept de dispatcher `delete_stshalfjes_by_ids(item_ids)` aan.

### Verwijderingslogica
De functie `delete_stshalfjes_by_ids` in `core/utils/emails/stshalfjes_email.py` verwijdert records uitsluitend na bevestiging van succesvolle e-mailverwerking.

## Beveiliging en Autorisatie

- **Toegang**: Beveiligd met `@ip_restricted` en `@login_required`.
- **Permissies**:
    - `can_view_baxter_sts_halfjes`: Inzien van de lijst.
    - `can_edit_baxter_sts_halfjes`: Toevoegen, bewerken en handmatig verwijderen.
    - `can_send_baxter_sts_halfjes`: Exporteren en e-mailen van rapportages.
- **Encryptie**: Patiëntgegevens zijn versleuteld opgeslagen op database-niveau.

## Bestanden

- **Backend**: `core/models.py`, `core/views/stshalfjes.py`, `core/forms.py`
- **Taken**: `core/tasks/emails.py`, `core/tasks/email_dispatcher.py`
- **Utility**: `core/utils/emails/stshalfjes_email.py`
- **Templates**: `core/templates/stshalfjes/index.html`, `core/templates/stshalfjes/pdf/onnodig_gehalveerde_geneesmiddelen.html`
- **Static**: `core/static/css/stshalfjes/stshalfjes.css`, `core/static/js/stshalfjes/stshalfjes.js`
