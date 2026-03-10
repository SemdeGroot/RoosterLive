# Groepenbeheer (Gebruiker)

## Doel van de module
Het beheren van permissiegroepen binnen de Apo Jansen App. Hiermee kan worden bepaald welke gebruikersgroepen toegang hebben tot specifieke onderdelen van de applicatie.

## Wat kun je met deze module?

- Nieuwe permissiegroepen aanmaken (bijv. 'Beheerders', 'Apothekers', 'Bezorgers').
- Specifieke rechten (permissies) toewijzen aan groepen.
- Bestaande groepen en hun rechten wijzigen.
- Groepen verwijderen die niet meer in gebruik zijn.
- De standaardrol configureren voor de algemene 'Kiosk' login van de apotheek.

## Werkwijze

1.  Ga in het hoofdmenu naar **Beheer** en klik op de tegel **Groepen**.
2.  **Groep aanmaken/wijzigen**: Klik op een groep in de lijst of gebruik het formulier 'Groep toevoegen'. Geef de groep een naam en vink de gewenste permissies aan in de lijst.
3.  **Permissies toewijzen**: De permissies zijn onderverdeeld in categorieën (zoals 'Algemeen', 'Rooster', 'Medicatiebeoordeling'). Vink aan wat van toepassing is voor de betreffende groep.
4.  **Standaard inlog instellen**: Onderaan de pagina staat de sectie 'Standaard inlog'. Hier kun je de rol selecteren die automatisch wordt toegekend aan de algemene Kiosk-gebruiker van de apotheek.
5.  **Groep verwijderen**: Gebruik de prullenbak-icoon bij een groep. Let op: een groep kan alleen worden verwijderd als er geen gebruikers meer lid zijn van deze groep.

## Bijzonderheden

- Rechten worden 'gestapeld': als een gebruiker lid is van meerdere groepen, krijgt deze alle rechten van al die groepen bij elkaar.
- Alleen gebruikers met de permissie `can_manage_users` kunnen groepen en de standaard inlog beheren.
- Het verwijderen van een groep vereist de specifieke permissie `can_manage_groups`.
