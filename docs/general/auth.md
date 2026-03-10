# Authenticatie, Autorisatie & Beveiliging

De Apotheek Jansen App bevat medische en bedrijfsgevoelige informatie en maakt daarom gebruik van een strikt beveiligingsmodel. Dit document beschrijft hoe we de toegang tot de app en de zichtbaarheid van gegevens binnen de app beheren.

## Toegangsbeheer op basis van rollen (RBAC)

De applicatie maakt gebruik van **Role-Based Access Control (RBAC)**. De toegang tot gegevens is direct gekoppeld aan de specifieke functie van een medewerker (zoals apotheker, assistent of bezorger). 

- Een medewerker krijgt uitsluitend toegang tot modules en overzichten die noodzakelijk zijn voor de uitvoering van zijn of haar werkzaamheden (**Least Privilege**).
- Autorisatierechten worden op serverniveau gevalideerd bij elke aanvraag.

## Beveiliging van patiëntgegevens

Wanneer er binnen modules gewerkt wordt met herleidbare patiëntgegevens, gelden aanvullende beveiligingsmaatregelen:

- **Versleutelde Opslag**: Gevoelige gegevens, zoals patiëntnamen en geboortedata, worden versleuteld in de database bewaard. Zonder de juiste cryptografische sleutels zijn deze gegevens niet leesbaar op databaseniveau.
- **IP-Restricties**: Pagina's die medische informatie bevatten, zijn uitsluitend toegankelijk vanaf het geautoriseerde interne netwerk van de apotheek. Toegang vanaf een externe locatie wordt voor deze onderdelen geblokkeerd.

## Multi-Factor Authenticatie (MFA)

Om een hoog beveiligingsniveau te waarborgen, ondersteunt de **Apotheek Jansen App** verschillende vormen van Multi-Factor Authenticatie. Gebruikers kunnen hun account beveiligen met de volgende methoden:

- **Wachtwoord**: De primaire authenticatiemethode. Wachtwoorden worden veilig gehasht opgeslagen in de database.
- **TOTP (Time-based One-Time Password)**: Een extra beveiligingslaag waarbij de gebruiker een 6-cijferige code genereert via een authenticatie-app (zoals Google Authenticator of Authy). Deze code is slechts kort geldig en wordt bij elke inlogpoging vereist na het invoeren van het wachtwoord.
- **Passkey (WebAuthn)**: De modernste en veiligste methode waarbij gebruik wordt gemaakt van de biometrische beveiliging van het apparaat (zoals FaceID, TouchID of een pincode). Dit is gebaseerd op de **WebAuthn** standaard en maakt inloggen mogelijk zonder wachtwoord of extra code na de initiële configuratie.

## Interne API-beveiliging

De beveiliging van de interne communicatie is gelaagd en afhankelijk van het type verbinding:

- **AWS Infrastructuur**: De communicatie binnen de AWS-cloudomgeving (bijvoorbeeld tussen servers en databases) is beveiligd met **IAM-rollen**. Hierdoor heeft uitsluitend de geautoriseerde server toegang tot de specifieke data en bronnen.
- **EC2 naar AWS Lambda**: Verzoeken tussen de webserver (EC2) en de medicatiebeoordeling microservice (AWS Lambda) worden gevalideerd via een statische `X-API-Key`. Dit zorgt ervoor dat uitsluitend geautoriseerde verzoeken vanuit de applicatie door de engine worden verwerkt.