# Laatste potten (Technisch)

De module **Laatste potten** binnen de **Apotheek Jansen App** beheert meldingen over kritieke voorraadstanden in de baxterproductie en automatiseert het proces van notificeren aan de inkoopafdeling.

## Technisch ontwerp
De module is ontworpen rond een event-driven notificatiesysteem. Bij het aanmaken van een nieuwe record (`LaatstePot`) worden direct acties getriggerd om relevante medewerkers te informeren via pushberichten en e-mail. De module bevat tevens een automatische opschoningsfunctie die het overzicht actueel houdt.

## Datamodel
De module maakt gebruik van het `LaatstePot` model in `core/models.py`.

- **LaatstePot**:
    - `voorraad_item` (ForeignKey): Koppeling naar de centrale baxtervoorraad (`VoorraadItem`).
    - `datum` (DateField): Ingangsdatum van de melding.
    - `afhandeling` (TextField): Tekstveld voor de status van de opvolging.
    - `created_at` (DateTimeField): Gebruikt voor de retentieperiode (30 dagen).

## Implementatiedetails
- **Automatische Retentie**: Bij elke aanroep van de `laatstepotten` view worden records die ouder zijn dan 30 dagen (op basis van `created_at`) automatisch verwijderd.
- **Notificatie-engine**: Bij het opslaan van een nieuwe melding worden de Celery-taken `send_laatste_pot_push_task` en `send_laatste_pot_email_task` aangeroepen.
- **Asynchroniteit**: De taken worden op de achtergrond verwerkt via Celery en Redis om een snelle reactietijd van de webinterface te garanderen.

## Autorisatie en beveiliging
Toegang wordt beheerd via de volgende permissies:
- `can_view_baxter_laatste_potten`: Inzien van de lijst.
- `can_edit_baxter_laatste_potten`: Toevoegen, bewerken en handmatig verwijderen.
- `can_perform_bestellingen`: Verplicht om pushmeldingen en e-mails te ontvangen bij nieuwe invoer.

## Relevante bestanden
- `core/models.py`: Modeldefinitie `LaatstePot`.
- `core/views/laatstepotten.py`: Interface-logica en automatische retentie-logica.
- `core/tasks/`: Celery-taken voor pushmeldingen en e-mails.
- `core/forms.py`: Validatie van het invoerformulier.
