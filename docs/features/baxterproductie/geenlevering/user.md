# Geen levering (Gebruiker)

De module **Geen levering** in de **Apotheek Jansen App** wordt gebruikt voor het registreren van geneesmiddelen die niet geleverd zijn in de baxterrol voor een patiënt. Dit is essentieel voor de communicatie tussen de baxterproductie en de ontvangende apotheek.

## Doel van de module
Het doel van deze module is het informeren van de apotheek over ontbrekende medicatie in de baxter. Door deze informatie digitaal vast te leggen, kan de apotheek direct actie ondernemen en wordt voorkomen dat patiënten onbedoeld hun medicatie overslaan.

## Wat kun je met deze module?
Met de module Geen levering kun je het volgende:

- Lijsten met niet-geleverde middelen aanmaken per apotheek, jaar, week en dag.
- Per patiënt registreren welk geneesmiddel ontbreekt in de baxterrol.
- De afdeling en de ingangsdatum van de ontbrekende medicatie vastleggen.
- Parafen toevoegen voor de STS-controle en de Roller-controle om de melding te accorderen.
- De lijst met niet-geleverde middelen exporteren naar een PDF-document.
- De lijst direct per e-mail versturen naar de betreffende apotheek.

## Werkwijze
Volg deze stappen om een lijst met niet-geleverde middelen te beheren:

- **Lijst aanmaken of selecteren**: Kies de apotheek, het jaar, de week en de dag. Indien er nog geen lijst is voor dit moment, kun je deze aanmaken.
- **Entry toevoegen**: Klik op de knop om een nieuwe regel toe te voegen. Voer de afdeling en patiëntgegevens in en selecteer het geneesmiddel dat niet geleverd is uit de baxtervoorraad.
- **Autorisatie**: Nadat de controle is uitgevoerd, worden de parafen van de STS-medewerker en de Roller-medewerker ingevoerd om de registratie te bevestigen.
- **Rapportage**: Klik op de exportknop om een PDF te genereren of gebruik de e-mailfunctie om de apotheek direct op de hoogte te stellen van de ontbrekende middelen.

## Bijzonderheden
- Patiëntgegevens (naam en geboortedatum) worden versleuteld opgeslagen ter bescherming van de privacy.
- De koppeling met de baxtervoorraad zorgt voor eenduidige benaming van de geneesmiddelen op de lijst.
- Toegang tot deze module is voorbehouden aan geautoriseerde gebruikers met de permissies `can_view_baxter_no_delivery`, `can_edit_baxter_no_delivery` en `can_send_baxter_no_delivery`.
