# Omzettingslijst (Gebruiker)

De module **Omzettingslijst** in de **Apotheek Jansen App** wordt gebruikt voor het registreren en communiceren van medicatie-omzettingen binnen het baxterproces. Hiermee wordt vastgelegd wanneer een gevraagd geneesmiddel is vervangen door een alternatief (bijvoorbeeld een ander merk of een andere vorm) voor een specifieke patiënt.

## Doel van de module
Het doel van deze module is het waarborgen van de medicatieveiligheid en transparantie bij omzettingen door omzettingen digitaal vast te leggen en te communiceren met andere organisaties (apotheken en zorginstellingen)

## Wat kun je met deze module?
Met de module Omzettingslijst kun je het volgende:

- Omzettingslijsten aanmaken per apotheek, jaar, week en dag.
- Specifieke omzettingen toevoegen per patiënt en afdeling.
- Vastleggen welk geneesmiddel gevraagd is en welk alternatief geleverd wordt.
- De begindatum van de omzetting en de visuele omschrijving van het middel registreren.
- Parafen toevoegen voor de STS-controle en de Roller-controle.
- De volledige lijst exporteren naar een PDF-document.
- De lijst direct per e-mail versturen naar de betreffende apotheek.

## Werkwijze
Volg deze stappen om een omzettingslijst te beheren:

- **Lijst aanmaken of selecteren**: Kies de gewenste apotheek, het jaar, de week en de dag. Indien de lijst nog niet bestaat, kun je deze aanmaken.
- **Omzetting toevoegen**: Klik op de knop om een nieuwe regel toe te voegen. Vul de afdeling, patiëntgegevens en de betreffende geneesmiddelen in. Je kunt geneesmiddelen direct selecteren uit de baxtervoorraad.
- **Controleren en paraferen**: Na het fysiek uitvoeren van de controle kunnen de parafen van de STS-medewerker en de Roller-medewerker in het systeem worden ingevoerd.
- **Verzenden**: Gebruik de e-mailfunctie om de afgeronde lijst als PDF naar de apotheek te sturen. De software zorgt ervoor dat de lijst professioneel geformatteerd wordt.

## Bijzonderheden
- Patiëntgegevens (naam en geboortedatum) worden versleuteld in de database opgeslagen om de privacy te waarborgen.
- De module is direct gekoppeld aan de actuele baxtervoorraad, waardoor fouten bij het invoeren van geneesmiddelnamen worden geminimaliseerd.
- Alleen geautoriseerde gebruikers met de juiste permissies (`can_view_baxter_omzettingslijst`, `can_edit_baxter_omzettingslijst`, `can_send_baxter_omzettingslijst`) hebben toegang tot deze module.
