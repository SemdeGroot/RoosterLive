# Laatste potten (Gebruiker)

De module **Laatste potten** in de **Apotheek Jansen App** is een hulpmiddel voor het voorraadbeheer binnen de baxterproductie. Het stelt medewerkers in staat om direct te melden wanneer een geneesmiddel de status "laatste pot" heeft bereikt, zodat er tijdig actie kan worden ondernomen door de afdeling bestellingen.

## Doel van de module
Het doel van deze module is het voorkomen van productieproblemen bij de baxterafdeling door tijdig inzicht te geven in geneesmiddelen die bijna uit de voorraad zijn. Door de automatische notificaties worden de verantwoordelijke bestellers direct op de hoogte gebracht, wat de kans op het volledig uitlopen van de voorraad minimaliseert.

## Wat kun je met deze module?
Met de module Laatste potten kun je het volgende:

- Een melding maken van een "laatste pot" door een geneesmiddel te selecteren uit de voorraad.
- Een omschrijving toevoegen over de afhandeling (bijvoorbeeld: "reeds besteld" of "vervangend middel in gebruik").
- Een overzicht bekijken van alle actuele laatste-pot-meldingen.
- Automatisch meldingen laten opschonen die ouder zijn dan 30 dagen.
- Notificaties ontvangen (als besteller) via pushberichten en e-mail zodra er een nieuwe melding wordt gemaakt.

## Werkwijze
Volg deze stappen om een laatste pot te melden of af te handelen:

- **Melding maken**: Navigeer naar **Baxterproductie** > **Laatste potten**. Klik op de knop om een nieuwe melding toe te voegen. Selecteer het geneesmiddel uit de lijst en geef eventueel aan hoe de afhandeling verloopt.
- **Overzicht raadplegen**: De lijst toont alle actieve meldingen van de afgelopen 30 dagen. Je ziet direct welk middel het betreft, wanneer het gemeld is en of er al bijzonderheden zijn genoteerd.
- **Notificatie (Bestellers)**: Medewerkers met de rol 'Besteller' ontvangen direct een pushbericht op hun mobiele apparaat en een e-mail met de details van de nieuwe melding.
- **Afhandeling bijwerken**: Je kunt een bestaande melding bewerken om de tekst bij 'Afhandeling' aan te vullen, zodat collega's weten wat de status van de bestelling is.

## Bijzonderheden
- De module is zelfreinigend; meldingen die ouder zijn dan 30 dagen worden automatisch uit de lijst verwijderd om het overzicht actueel te houden.
- Alleen gebruikers met de permissie `can_view_baxter_laatste_potten` kunnen de lijst inzien. Gebruikers met `can_edit_baxter_laatste_potten` kunnen meldingen toevoegen of wijzigen.
- De pushberichten worden alleen verzonden naar gebruikers die de app hebben geïnstalleerd en de juiste notificatie-instellingen hebben.
