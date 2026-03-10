# Omzettingslijst (Technisch)

De module **Omzettingslijst** binnen de **Apotheek Jansen App** faciliteert de administratie van medicatie-omzettingen in het baxterproces. De module maakt gebruik van versleutelde patiëntgegevens en is direct gekoppeld aan de centrale baxtervoorraad.

## Technisch ontwerp
De module volgt een container-entry architectuur waarbij individuele omzettingen (`OmzettingslijstEntry`) worden gegroepeerd binnen een `Omzettingslijst`. De architectuur zorgt voor een strikte scheiding tussen de beheerinterface en het asynchrone proces voor het genereren en verzenden van PDF-rapportages.

## Datamodel
De module gebruikt twee modellen in `core/models.py`:

- **Omzettingslijst**: De container voor een specifieke combinatie van apotheek, jaar, week en dag.
- **OmzettingslijstEntry**: De details van een individuele omzetting.
    - Bevat ForeignKeys naar `VoorraadItem` (`gevraagd_geneesmiddel` en `geleverd_geneesmiddel`).
    - Bevat versleutelde patiëntgegevens via `EncryptedCharField` en `EncryptedDateField`.

## Implementatiedetails
- **Versleuteling**: Alle patiëntgegevens worden versleuteld in de database opgeslagen (`django-fernet-fields`).
- **PDF-generatie**: Gebeurt via de interne `_render_pdf` helperfunctie, die HTML-templates omzet naar PDF.
- **Asynchrone verwerking**: De e-mailverzending van de PDF-rapportage wordt afgehandeld door de Celery-taak `send_omzettingslijst_pdf_task` om de webervaring niet te blokkeren.

## Autorisatie en beveiliging
De toegang is geregeld via drie specifieke permissies:
- `can_view_baxter_omzettingslijst`: Inzien van de lijsten.
- `can_edit_baxter_omzettingslijst`: Aanmaken en wijzigen van lijsten en entries.
- `can_send_baxter_omzettingslijst`: Verzenden van de PDF-rapportage.

Beveiliging op dataniveau wordt gewaarborgd door Fernet-encryptie, waardoor patiëntgegevens niet leesbaar zijn in de ruwe database-exports.

## Relevante bestanden
- `core/models.py`: Definities van `Omzettingslijst` en `OmzettingslijstEntry`.
- `core/views/omzettingslijst.py`: Interface-logica en afhandeling van acties.
- `core/forms.py`: Validatieregels voor de invoerformulieren.
- `core/tasks/`: Celery-taak voor de e-mailverzending.
