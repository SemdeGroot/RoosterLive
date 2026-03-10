# Profiel (Gebruiker)

## Doel van de module
Het doel van de Profiel module is om medewerkers van de **Apotheek Jansen App** in staat te stellen hun persoonlijke gegevens, voorkeuren en beveiligingsinstellingen te beheren.

## Wat kun je met deze module?
Met deze module kun je:

- Een profielfoto instellen en wijzigen.
- Persoonlijke gegevens inzien, zoals je naam, organisatie en functie.
- Persoonlijke gegevens aanpassen (in ontwikkeling).
- Je privacyvoorkeuren instellen (in ontwikkeling).
- Je authenticatiemethoden opnieuw instellen (in ontwikkeling).
- Je notificatievoorkeuren instellen voor pushberichten en e-mails.

## Werkwijze
Je kunt je profiel openen via de profiel-tegel op het dashboard of via het menu.

1. Open de Profiel module vanuit het menu of het dashboard.
2. Klik op "Bewerken" om je gegevens (zoals je telefoonnummer) aan te passen (in ontwikkeling).
3. Gebruik de sectie "Notificaties" om aan te geven van welke gebeurtenissen je op de hoogte gehouden wilt worden.
4. Ga naar "Beveiliging" om passkeys te beheren voor een veiligere inlogervaring (in ontwikkeling).

## Bijzonderheden
- Je profielfoto wordt automatisch gehasht om caching-problemen te voorkomen en veilig opgeslagen in AWS S3.
- Notificatievoorkeuren zijn onderverdeeld in categorieën, zoals "Rooster", "Agenda" en "Nieuws".
- Voor medewerkers met een vast contract zijn hier ook hun vaste werkdagen zichtbaar, die de basis vormen voor de automatische beschikbaarheidsplanning.
- Je kunt hier haptische feedback in- of uitschakelen voor een verbeterde interactie met de mobiele app.
