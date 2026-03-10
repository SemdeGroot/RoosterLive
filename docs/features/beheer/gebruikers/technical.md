# Gebruikersbeheer (Technisch)

## Technisch ontwerp
Gebruikersbeheer is gebouwd op het standaard Django `User` model, uitgebreid met een `UserProfile` model via een één-op-één relatie. Dit stelt ons in staat om apotheek-specifieke metadata op te slaan zonder het kernmodel van Django te wijzigen.

## Datamodel
De belangrijkste componenten zijn:

- `django.contrib.auth.models.User`: Beheert authenticatie, e-mail en basisnaam.
- `core.models.UserProfile`: Bevat uitgebreide velden zoals:
    - `organization`: Koppeling naar de `Organization` van de gebruiker.
    - `function`: Koppeling naar de `Function` (rol) van de medewerker.
    - `dienstverband`: Keuze tussen 'VAST' of 'OPROEP'.
    - `work_mon_am` t/m `work_sat_ev`: Boolean velden voor vaste werkdagen.
    - `calendar_token`: Een unieke UUID voor het synchroniseren van persoonlijke roosters met externe agenda's.

## Implementatiedetails

- **Views**: De logica bevindt zich in `core.views.admin.admin_users` (lijst en creatie), `user_update` (wijzigen) en `user_delete` (verwijderen).
- **Forms**: `core.forms.SimpleUserEditForm` wordt gebruikt voor zowel creatie als updates, waarbij zowel `User` als `UserProfile` velden worden afgehandeld.
- **Automatisering**:
    - Bij het aanmaken van een gebruiker wordt `core.tasks.send_invite_email_task` aangeroepen via Celery om asynchroon een uitnodigingsmail te versturen.
    - Bij het wijzigen naar een 'Vast' dienstverband of het aanpassen van werkdagen wordt `fill_availability_for_profile` of `rebuild_auto_availability_for_profile` (in `core.utils.beat.fill`) uitgevoerd om de `Availability` records in de database te synchroniseren voor de komende 12 weken.
- **Filter**: De "Kiosk login" (Algemene apotheek account) wordt standaard uitgefilterd in de beheerderslijst via de `StandaardInlog` configuratie.

## Autorisatie en beveiliging

- De view is beveiligd met de `@login_required` decorator.
- Toegang tot de beheerpagina vereist de permissie `can_access_admin`.
- Acties zoals aanmaken, wijzigen en verwijderen vereisen de permissie `can_manage_users`.
- Uitnodigingen verlopen via beveiligde Django password reset tokens.

## Relevante bestanden

- `core/views/admin.py`: Bevat de view-logica.
- `core/models.py`: Definieert het `UserProfile`.
- `core/forms.py`: Bevat `SimpleUserEditForm`.
- `core/utils/beat/fill.py`: Bevat de logica voor het vullen van automatische beschikbaarheid.
