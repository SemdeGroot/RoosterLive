# Geen levering (Technisch)

De module **Geen levering** binnen de **Apotheek Jansen App** beheert de registratie van niet-geleverde geneesmiddelen per apotheek, week en dag. De module is gebaseerd op een vergelijkbaar technisch fundament als de omzettingslijst-module.

## Technisch ontwerp
De module maakt gebruik van een hiërarchische structuur bestaande uit lijsten (`NoDeliveryList`) en bijbehorende regels (`NoDeliveryEntry`). De koppeling met de centrale baxtervoorraad garandeert de consistentie van de gebruikte geneesmiddelnamen. De rapportage-engine genereert asynchroon PDF-documenten voor externe communicatie.

## Datamodel
De module wordt ondersteund door twee modellen in `core/models.py`:

- **NoDeliveryList**: Container voor meldingen per apotheek en tijdsperiode.
- **NoDeliveryEntry**: Details van een specifiek niet-geleverd geneesmiddel.
    - Bevat een ForeignKey naar `VoorraadItem` voor het gevraagde middel.
    - Slaat patiëntnaam en geboortedatum versleuteld op via Fernet-velden.

## Implementatiedetails
- **Datanormalisatie**: Maakt gebruik van de centrale `VoorraadItem`-database voor alle medicatiegegevens.
- **Asynchrone rapportage**: PDF-generatie en verzending worden asynchroon uitgevoerd via de Celery-taak `send_no_delivery_pdf_task`.
- **Visuele previews**: Previews van rapportages worden gegenereerd met de interne PDF-helperfuncties.

## Autorisatie en beveiliging
Toegang wordt verleend op basis van de volgende permissies:

- `can_view_baxter_no_delivery`: Inzien van meldingen.
- `can_edit_baxter_no_delivery`: Toevoegen en wijzigen van meldingen.
- `can_send_baxter_no_delivery`: Verzenden van PDF-exports naar apotheken.

Privacy-beveiliging is gewaarborgd door het gebruik van de `django-fernet-fields` voor alle persoonsgegevens in de database.

## Relevante bestanden
- `core/models.py`: Modeldefinities voor `NoDeliveryList` en `NoDeliveryEntry`.
- `core/views/no_delivery.py`: Interface-logica en afhandeling van acties.
- `core/forms.py`: Validatieregels voor de formulieren.
- `core/tasks/`: Bevat de Celery-taak voor het verzenden van de rapportage.
