# Authenticatie, Autorisatie & Beveiliging

De Apotheek Jansen App bevat medische en bedrijfsgevoelige informatie en maakt daarom gebruik van een strikt beveiligingsmodel. Dit document beschrijft hoe we de toegang tot de app en de zichtbaarheid van gegevens binnen de app beheren.

## Toegangsbeheer op basis van rollen (RBAC)

De applicatie maakt gebruik van **Role-Based Access Control (RBAC)**. De toegang tot gegevens is direct gekoppeld aan de specifieke functie van een medewerker (zoals apotheker, assistent of bezorger). 

- Een medewerker krijgt uitsluitend toegang tot modules en overzichten die noodzakelijk zijn voor de uitvoering van zijn of haar werkzaamheden (**Least Privilege**).
- Autorisatierechten worden op serverniveau gevalideerd bij elke aanvraag.

## Beveiliging van patiëntgegevens

Wanneer er binnen modules gewerkt wordt met herleidbare patiëntgegevens, gelden aanvullende beveiligingsmaatregelen:

- **Versleutelde Opslag**: Gevoelige gegevens, zoals patiëntnamen en geboortedatums, worden versleuteld in de database bewaard. Zonder de juiste cryptografische sleutels zijn deze gegevens niet leesbaar op databaseniveau.
- **IP-Restricties**: Pagina's die medische informatie bevatten, zijn uitsluitend toegankelijk vanaf het geautoriseerde interne netwerk van de apotheek. Toegang vanaf een externe locatie wordt voor deze onderdelen geblokkeerd.

## Interne API-beveiliging

De beveiliging van de interne communicatie is gelaagd en afhankelijk van het type verbinding:

- **Django naar Analyse-engine (AWS Lambda)**: Verzoeken tussen de webserver en de analyse-engine worden gevalideerd via een statische `X-API-Key`. Dit zorgt ervoor dat uitsluitend geautoriseerde verzoeken vanuit de applicatie door de engine worden verwerkt.
- **AWS Infrastructuur**: De communicatie binnen de AWS-cloudomgeving (bijvoorbeeld tussen servers en databases) is beveiligd met **IAM-rollen**. Hierdoor heeft uitsluitend de geautoriseerde server toegang tot de specifieke data en bronnen, zonder dat er statische wachtwoorden of keys in de code nodig zijn.
