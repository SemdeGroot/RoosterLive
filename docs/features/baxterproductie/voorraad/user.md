# Voorraad (Gebruiker)

De **Apotheek Jansen App** biedt een module voor het inzien en beheren van de actuele baxtervoorraad. Deze module stelt medewerkers in staat om snel te controleren welke geneesmiddelen aanwezig zijn in de baxterproductie en biedt beheerders de mogelijkheid om deze lijst actueel te houden.

## Doel van de module
Het doel van de module is het centraal beschikbaar stellen van de actuele voorraadstatus van geneesmiddelen die gebruikt worden in het baxterproces. Dit versnelt het productieproces door direct inzicht te geven in de aanwezige middelen en bijbehorende specificaties.

## Wat kun je met deze module?
Met de module Voorraad kun je het volgende:

- De volledige lijst met geneesmiddelen in de baxtervoorraad doorzoeken op naam of ZI-nummer.
- Gedetailleerde informatie per geneesmiddel bekijken (zoals sterkte, vorm of specifieke voorraadkenmerken).
- De actuele voorraadlijst exporteren naar een HTML-bestand voor lokaal gebruik.
- Het voorraadoverzicht direct per e-mail versturen naar aangesloten apotheken.
- Als beheerder de voorraadlijst actualiseren door middel van een CSV- of Excel-upload (.xlsx).

## Werkwijze
Volg deze stappen om de voorraad te raadplegen of bij te werken:

- **Voorraad bekijken**: Navigeer naar de tegel **Baxterproductie** en kies voor **Voorraad**. Gebruik de zoekbalk om specifiek op naam of ZI-nummer te filteren.
- **Lijst exporteren**: Klik op de exportknop om de huidige lijst als HTML-bestand te downloaden of direct via e-mail te verzenden naar de geselecteerde ontvangers.
- **Voorraad bijwerken (Beheerder)**: 
    - Zorg voor een bestand in CSV- of Excel-formaat (.xlsx).
    - Het bestand moet minimaal twee kolommen bevatten: het **ZI-nummer** (8 cijfers) en de **Naam** van het geneesmiddel.
    - Eventuele extra kolommen in het bestand worden automatisch als extra informatie bij het medicijn getoond.
    - Upload het bestand via de upload-functie in de module. De software valideert het bestand op correcte ZI-nummers en dubbele regels voordat de database wordt bijgewerkt.

## Bijzonderheden
- Het ZI-nummer is de unieke sleutel; als een ZI-nummer al bestaat, wordt de informatie van dit middel bijgewerkt met de gegevens uit het nieuwe bestand.
- De geneesmiddelen in deze voorraadlijst vormen de basis voor andere modules binnen de baxterproductie, zoals de **Omzettingslijst**, **Geen levering**, **Laatste potten** en **Nazendingen**.
- Bij het uploaden voert het systeem een controle uit op veelvoorkomende middelen (zoals Paracetamol) om te verifiëren of de kolommen in het bestand waarschijnlijk op de juiste plek staan.
- Alleen gebruikers met de juiste permissies (`can_view_av_medications` voor inzien en `can_upload_voorraad` voor wijzigen) hebben toegang tot deze functies.
