# Rooster (Technisch)

## Technisch ontwerp
De Rooster module in de **Apo Jansen App** is gebouwd rondom het `RosterWeek` model en het `Roster` model (legacy/huidige). De module automatiseert de verwerking van geüploade PDF-roosters naar geoptimaliseerde afbeeldingen voor de web- en mobiele applicatie.

## Datamodel
De belangrijkste modellen zijn:

### RosterWeek
- `monday`: De maandag van de week waarvoor het rooster geldt (unique index).
- `week_slug`: Een identifier in de vorm "week01".
- `file_path`: Pad naar het opgeslagen PDF-bestand.
- `file_hash`: Unieke hash voor bestandscaching en deduplicatie.
- `n_pages`: Aantal pagina's in het rooster-bestand.
- `preview_ext`: Het gebruikte bestandsformaat voor previews (bijv. "webp").

### Roster (Huidige)
- `file`: Het actuele rooster-bestand (`rooster/current.pdf`).
- `pages`: Een JSONField met de relatieve paden naar gerenderde afbeeldingspagina's.
- `uploaded_at`: Tijdstip van laatste upload.

## Implementatiedetails
De module bevat logica voor de volgende processen:

- **PDF Verwerking**: Bij het uploaden van een rooster wordt de PDF door een script (of task) verwerkt. Hierbij wordt elke pagina omgezet naar een geoptimaliseerd afbeeldingsformaat (meestal WebP of PNG) en opgeslagen in de `MEDIA_ROOT`.
- **Weeknavigatie**: Roosters worden gesorteerd op de startdatum van de week (maandag). De applicatie bepaalt op basis van de huidige datum welk `RosterWeek` object als standaard moet worden getoond.
- **Deduplicatie**: Door gebruik te maken van bestandshashes wordt voorkomen dat dezelfde bestanden onnodig dubbel worden opgeslagen.

## Autorisatie en beveiliging
De toegang wordt beheerd via de volgende Django permissies:

- `can_view_roster`: Mag het rooster bekijken in de applicatie.
- `can_upload_roster`: Mag nieuwe roosters uploaden via het beheerderspaneel.

## Relevante bestanden
De belangrijkste bestanden voor deze module zijn:

- `core/models.py`: Definities van `Roster` en `RosterWeek`.
- `core/views/admin.py`: Bevat logica voor het uploaden van roosters.
- `core/forms.py`: Bevat het `RosterUploadForm`.
- `core/tasks/`: Bevat achtergrondtaken voor push-notificaties bij nieuwe roosters.
