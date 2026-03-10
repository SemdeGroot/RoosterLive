# Functiebeheer (Technisch)

## Technisch ontwerp
Functiebeheer biedt een eenvoudige manier om medewerkers te categoriseren en te sorteren. Functies zijn losgekoppeld van permissies; een functie is puur een label, terwijl een groep de rechten bepaalt.

## Datamodel
- `core.models.Function`:
    - `title`: `CharField` voor de weergavenaam van de functie.
    - `ranking`: `IntegerField` voor de sorteervolgorde (standaard `0`).

## Implementatiedetails

- **Views**: De logica bevindt zich in `core.views.admin.admin_functies`, `functie_update` en `delete_functie`.
- **Sortering**: In diverse views (zoals `admin_users`) worden gebruikers gesorteerd op basis van `profile__function__ranking` (ASC, nulls last).
- **Forms**: `core.forms.FunctionForm` wordt gebruikt voor het verwerken van input.

## Autorisatie en beveiliging

- Toegang tot het beheerdashboard vereist `can_access_admin`.
- Voor alle mutaties is de specifieke permissie `can_manage_functies` vereist.
- Verwijdering van een functie is een fysieke delete (`f.delete()`), aangezien dit model geen soft-delete gebruikt.

## Relevante bestanden

- `core/views/admin.py`: Bevat de view-logica.
- `core/models.py`: Definieert `Function`.
- `core/forms.py`: Bevat `FunctionForm`.
