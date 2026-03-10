# Voorraad (Technisch)

De Voorraad module binnen de **Apotheek Jansen App** beheert de geneesmiddelen die beschikbaar zijn voor de baxterproductie. Deze module dient als centrale database voor alle geneesmiddelgegevens die in andere baxter-gerelateerde modules worden gebruikt.

## Technisch ontwerp
De module is ontworpen als een centrale opslagplek voor geneesmiddelinformatie. De interface biedt functionaliteit voor het importeren van externe data (CSV/XLSX), het doorzoeken van de huidige voorraad en het exporteren van rapportages. De architectuur scheidt de import-engine van de weergave- en e-mailfunctionaliteit.

## Datamodel
Het centrale model is `VoorraadItem` in `core/models.py`.

- `zi_nummer` (CharField, Primary Key): Een uniek 8-cijferig identificatienummer (ZI-nummer).
- `naam` (CharField): De volledige naam van het geneesmiddel.
- `metadata` (JSONField): Slaat additionele kolommen uit bronbestanden op als key-value paren.
- `uploaded_at` (DateTimeField): Registreert de laatste importdatum.

Relaties: Veel andere modellen (zoals `OmzettingslijstEntry`, `NoDeliveryEntry`, `LaatstePot`) hebben een ForeignKey naar dit model.

## Implementatiedetails
- **Import Engine**: De logica in `core/views/voorraad.py` verwerkt uploads. Het ondersteunt automatische detectie van scheidingstekens via `csv.Sniffer` en XLSX-verwerking via `openpyxl`.
- **Synchronisatie**: Tijdens import worden bestaande items bijgewerkt als de naam of metadata is veranderd. Er vindt geen destructieve verwijdering plaats; items blijven in de database staan totdat ze handmatig worden verwijderd.
- **Rapportage**: De exportfunctie genereert een standalone HTML-bestand. De e-mailfunctionaliteit (`core/utils/emails/voorraad_mail.py`) verzendt dit bestand als bijlage.

## Autorisatie en beveiliging
De toegang tot de module is strikt gescheiden op basis van permissies:
- `can_view_av_medications`: Toegang tot de weergave en zoekfunctionaliteit.
- `can_upload_voorraad`: Toegang tot de importfunctionaliteit.
- **Validatie**: Bij import wordt het ZI-nummer gevalideerd via een regex (`\d{8}`) en vindt er een heuristische controle plaats op de kolomvolgorde (zoeken naar "paracetamol").

## Relevante bestanden
- `core/models.py`: Modeldefinitie `VoorraadItem`.
- `core/views/voorraad.py`: Import-logica en weergave.
- `core/utils/emails/voorraad_mail.py`: E-mailfunctionaliteit.
- `core/templates/voorraad/`: Interface templates.
