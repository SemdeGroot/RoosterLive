# Formulieren (Technisch)

De module Formulieren biedt een centrale opslagplaats voor externe links naar onboardingformulieren.

## Technisch ontwerp
De module faciliteert een CRUD-interface voor het beheren van links. De backend is opgebouwd als een Django-view die formulieren toont in een lijst, waarbij elke rij bewerkt of verwijderd kan worden met behulp van Django Forms en form-prefixes.

## Datamodel
Het belangrijkste model is:
- `OnboardingFormulier`:
    - `title`: De naam van het formulier.
    - `url`: De volledige link (bijv. Google Forms).
    - `created_by`: Foreign key naar de `User` die het formulier heeft aangemaakt.

## Implementatiedetails
De view `onboarding_formulieren` handelt de CRUD-acties af:
- **Lijst**: Toont alle formulieren gesorteerd op titel.
- **Toevoegen**: Maakt een nieuw formulier aan met `prefix="new"`.
- **Bewerken**: Gebruikt een form-instance per item met een prefix (`edit-{item_id}`) om specifieke rijen te kunnen bewerken in de lijstweergave.
- **Verwijderen**: Verwijdert het geselecteerde formulier op basis van de ID.

## Autorisatie en beveiliging
- Toegang wordt gereguleerd via `can_view_forms`.
- Modificaties (toevoegen, bewerken, verwijderen) vereisen de permissie `can_edit_forms`.
- Invoervalidatie op de URL wordt afgedwongen via `URLField`.

## Relevante bestanden
- `core/models.py`: Het `OnboardingFormulier` model.
- `core/views/onboarding_forms.py`: De view-logica.
- `core/forms.py`: De `OnboardingFormulierForm`.
- `core/templates/onboarding_formulieren/index.html`: De gebruikersinterface.
