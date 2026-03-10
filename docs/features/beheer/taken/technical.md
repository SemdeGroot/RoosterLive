# Taken en Locaties (Technisch)

## Technisch ontwerp
De structuur van de roosterplanning is gebaseerd op een hiërarchie van Locaties en Taken. Dagdelen vormen de tijdssloten waarin deze taken worden gepland.

## Datamodel
- `core.models.Location`:
    - `name`, `address`, `color`.
    - `is_active`: Gebruikt voor soft-delete functionaliteit.
- `core.models.Task`:
    - `name`, `location` (ForeignKey naar Location), `description`.
    - `min_mon_morning` t/m `min_sat_evening`: Integer-velden voor de bezettingseis.
    - `is_active`: Gebruikt voor soft-delete functionaliteit.
- `core.models.Dagdeel`:
    - `code`: Unieke code (bijv. 'morning', 'afternoon').
    - `name`: Display naam.
    - `start_time`, `end_time`: `TimeField` objecten voor de shift-tijden.
    - `sort_order`: Bepaalt de weergavevolgorde.

## Implementatiedetails

- **Views**: De logica bevindt zich in `core.views.admin.admin_taken`. Updates verlopen via `location_update`, `task_update` en `dagdeel_update`.
- **Soft Delete**: De `delete_location` en `delete_task` views gebruiken `obj.delete()`, waarbij in de `Location` en `Task` modellen een custom delete-methode is geïmplementeerd (of een manager wordt gebruikt) die `is_active` op `False` zet in plaats van het record fysiek te verwijderen.
- **Validatie**: Bij het updaten van dagdelen wordt in het model gecontroleerd (`clean` methode) of de starttijd vóór de eindtijd ligt.

## Autorisatie en beveiliging

- Toegang tot het beheerdashboard vereist `can_access_admin`.
- Voor alle mutaties is de permissie `can_manage_tasks` vereist.
- Toegang tot dagdeel-updates is ook beveiligd met deze permissie.

## Relevante bestanden

- `core/views/admin.py`: Bevat de view-logica.
- `core/models.py`: Definieert `Location`, `Task` en `Dagdeel`.
- `core/forms.py`: Bevat `LocationForm`, `TaskForm` en `DagdeelForm`.
