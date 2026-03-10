# Werkafspraken (Technisch)

De module **Werkafspraken** binnen de **Apotheek Jansen App** beheert het opslaan, weergeven en categoriseren van PDF-werkinstructies en protocollen.

## Technisch ontwerp
De module maakt gebruik van een categoriseringssysteem waarbij documenten worden gekoppeld aan specifieke werkgebieden (baxter, openbare, instelling). De technische architectuur integreert PDF-verwerking met een hashes-gebaseerd opslagsysteem om dubbele bestanden te voorkomen en previews te automatiseren.

## Datamodel
De module wordt ondersteund door het `Werkafspraak` model in `core/models.py`.

- **Werkafspraak**:
    - `file`: Het geüploade PDF-bestand.
    - `category`: Gebruikt voor autorisatie en weergavefiltering.
    - `file_hash`: SHA-256 hash voor deduplicatie en cache-sleutel voor previews.

## Implementatiedetails
- **Opslag en Hashing**: Bij upload wordt een SHA-256 hash van het bestand gegenereerd via `core/views/_upload_helpers.py`. Dit vormt de bestandsnaam en voorkomt redundante opslag.
- **Preview Systeem**: De eerste pagina van elke PDF wordt automatisch gerenderd naar een WebP-afbeelding (`pymupdf`) voor snelle weergave in de interface. De previews worden gecached in een aparte directory op basis van de hash.
- **Cleanup**: Bij het verwijderen van een record wordt gecontroleerd of de fysieke 'blob' nog in gebruik is door andere records; zo niet, dan wordt de opslagruimte opgeruimd.

## Autorisatie en beveiliging
De toegang wordt geregeld via een mapping van categorie naar permissie:
- `baxter` -> `can_view_baxter`
- `instelling` -> `can_view_instellings_apo`
- `openbare` -> `can_view_openbare_apo`
- Beheer (upload/delete) vereist `can_upload_werkafspraken`.

Door de categorisering zien gebruikers alleen de documenten die relevant zijn voor hun specifieke werkomgeving.

## Relevante bestanden
- `core/models.py`: Modeldefinitie `Werkafspraak`.
- `core/views/policies.py`: Bevat de categoriseringslogica en weergave.
- `core/views/_upload_helpers.py`: Bevat de engine voor hashing en PDF-rendering.
- `media/werkafspraken/`: Opslag van de bron-PDF's.
- `cache/werkafspraken/`: Opslag van de gegenereerde previews.
