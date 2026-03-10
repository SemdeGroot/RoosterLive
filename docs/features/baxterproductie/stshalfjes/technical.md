# STS Halfjes (Onnodig Gehalveerde Geneesmiddelen) (Technisch)

De STS Halfjes module is ontworpen om registraties te maken van geneesmiddelen die onnodig gehalveerd worden in het baxterproces en deze informatie te communiceren naar de verantwoordelijke apotheken.

## Architectuur en Gegevensmodel

### Model: `STSHalfje`
Het kernmodel voor deze module bevindt zich in `core/models.py`.

Belangrijke velden:

- `afdeling`: CharField voor de afdeling van de patiënt.
- `item_gehalveerd`: ForeignKey naar `VoorraadItem` (het gehalveerde middel).
- `item_alternatief`: ForeignKey naar `VoorraadItem` (de alternatieve sterkte).
- `apotheek`: ForeignKey naar `Organization` (de eigenaar van de patiënt/melding).
- `patient_naam_enc` en `patient_geboortedatum_enc`: Versleutelde velden voor patiëntgegevens (gebruikmakend van Django's `EncryptedCharField` en `EncryptedDateField`).

### Views
De logica voor het weergeven, toevoegen en wijzigen van meldingen bevindt zich in `core/views/stshalfjes.py`.

- `stshalfjes(request)`: De hoofdpagina die de lijst met meldingen toont en het `STSHalfjeForm` afhandelt.
- `export_stshalfjes_pdf(request)`: Genereert een PDF-export van alle of gefilterde meldingen.
- `email_stshalfjes_pdf(request)`: Verwerkt de POST-aanvraag voor het versturen van meldingen naar geselecteerde organisaties via een Celery-task.

## Verzending en PDF Generatie

Het verzendproces is ontworpen om privacy en efficiëntie te waarborgen.

### Celery Task: `send_stshalfjes_pdf_task`
De verzending wordt afgehandeld door een achtergrondtaak in `core/tasks/emails.py`. De workflow binnen deze taak is als volgt:

1.  **Iteratie**: Voor elke geselecteerde `Organization ID` wordt een aparte PDF gegenereerd.
2.  **Filtering**: De query wordt gefilterd op `apotheek=org`. Dit zorgt ervoor dat de PDF alleen meldingen bevat die eigendom zijn van de betreffende apotheek.
3.  **PDF Creatie**: De PDF wordt opgebouwd met het sjabloon `stshalfjes/pdf/onnodig_gehalveerde_geneesmiddelen.html` via de `_render_pdf` helper.
4.  **E-mail Dispatcher**: Er wordt een signaal gestuurd naar de `email_dispatcher_task` met het type `stshalfjes_single`.
5.  **Verwijdering**: Zodra de e-mail succesvol is verzonden, roept de dispatcher `delete_stshalfjes_by_ids(item_ids)` aan om de verzonden meldingen uit de database te verwijderen.

### Verwijderingslogica
De logica voor het verwijderen bevindt zich in `core/utils/emails/stshalfjes_email.py` in de functie `delete_stshalfjes_by_ids`. Dit gebeurt alleen *nadat* de e-mail succesvol is verwerkt.

## Beveiliging en Autorisatie

- **Toegang**: De module is beveiligd met `@ip_restricted` en `@login_required`.
- **Permissies**: Er zijn drie specifieke permissies gedefinieerd:
    - `can_view_baxter_sts_halfjes`: Voor het inzien van de lijst.
    - `can_edit_baxter_sts_halfjes`: Voor het toevoegen, bewerken en verwijderen van meldingen.
    - `can_send_baxter_sts_halfjes`: Voor het exporteren en versturen van de rapportages via e-mail.
- **Encryptie**: Patiëntgegevens worden versleuteld in de database opgeslagen om te voldoen aan privacywetgeving.

## Gerelateerde bestanden

- **Backend**: `core/models.py`, `core/views/stshalfjes.py`, `core/forms.py`
- **Achtergrondtaken**: `core/tasks/emails.py`, `core/tasks/email_dispatcher.py`
- **Utility**: `core/utils/emails/stshalfjes_email.py`
- **Templates**: `core/templates/stshalfjes/index.html`, `core/templates/stshalfjes/pdf/onnodig_gehalveerde_geneesmiddelen.html`
- **Assets**: `core/static/css/stshalfjes/stshalfjes.css`, `core/static/js/stshalfjes/stshalfjes.js`
