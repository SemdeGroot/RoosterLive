# Organisatiesbeheer (Technisch)

## Technisch ontwerp
Het organisatiemodel dient als de hoogste laag voor data-isolatie en categorisering binnen de applicatie. Gebruikersprofielen en afdelingen zijn altijd gekoppeld aan een specifieke organisatie.

## Datamodel
- `core.models.Organization`:
    - `name`: Unieke naam van de organisatie (CharField, uniek, geïndexeerd).
    - `org_type`: Keuzeveld met opties `apotheek` of `zorginstelling`.
    - `email`: Primair e-mailadres (EmailField).
    - `email2`: Secundair e-mailadres voor extra notificaties.
    - `phone`: Telefoonnummer van de locatie.

## Implementatiedetails

- **Views**: De logica bevindt zich in `core.views.admin.admin_orgs`, `org_update` en `org_delete`.
- **Forms**: `core.forms.OrganizationEditForm` wordt gebruikt voor updates.
- **Integriteitscheck**: In de `org_delete` view wordt gecontroleerd of er nog `UserProfile` records gekoppeld zijn aan de organisatie via `UserProfile.objects.filter(organization=org).count()`. Als dit aantal groter is dan 0, wordt verwijdering geblokkeerd met een foutmelding.

## Autorisatie en beveiliging

- Toegang tot het beheerdashboard vereist `can_access_admin`.
- Voor alle mutaties is de permissie `can_manage_orgs` vereist.
- Alle post-requests zijn beveiligd met `@require_POST` en CSRF-tokens.

## Relevante bestanden

- `core/views/admin.py`: Bevat de view-logica.
- `core/models.py`: Definieert `Organization`.
- `core/forms.py`: Bevat `OrganizationEditForm`.
