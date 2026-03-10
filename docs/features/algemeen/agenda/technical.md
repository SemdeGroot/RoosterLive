# Agenda (Technisch)

## Technisch ontwerp
De Agenda module in de **Apo Jansen App** is een Django-gebaseerde module die gebruikmaakt van het `AgendaItem` model voor het opslaan van agendapunten. De module biedt zowel een interne weergave in de webapp als een externe WebCal/ICS-feed voor agenda-synchronisatie.

## Datamodel
De belangrijkste velden van het `AgendaItem` model zijn:

- `title`: De naam van het agendapunt.
- `description`: Een korte omschrijving.
- `date`: De specifieke datum van het evenement.
- `start_time` / `end_time`: Optionele tijden voor het evenement.
- `category`: Categorie-indeling (bijv. "general", "outing").
- `created_by`: Koppeling met de gebruiker die het item heeft aangemaakt.

## Implementatiedetails
De module is opgebouwd uit de volgende onderdelen:

- **WebCal Feed**: Via `core/views/diensten_webcal.py` wordt een ICS-feed gegenereerd die alle actieve agendapunten ontsluit voor externe agenda-applicaties.
- **Push Notificaties**: Bij het toevoegen van een nieuw agendapunt kan de Celery-task `send_agenda_uploaded_push_task` worden aangeroepen om gebruikers te informeren.
- **Caching**: Voor een snelle weergave worden agendapunten vaak gecachet in de frontend componenten (bijv. in dashboard-tegels).

## Autorisatie en beveiliging
De volgende Django permissies zijn van toepassing op deze module:

- `can_view_agenda`: Geeft toegang tot het bekijken van de agenda in de applicatie.
- `can_upload_agenda`: Staat de gebruiker toe nieuwe items aan te maken, te wijzigen of te verwijderen via de admin-interface of speciale views.
- **WebCal Token**: Gebruikers kunnen alleen hun eigen gesynchroniseerde data inzien via een uniek, geheim token in de URL van de WebCal-feed.

## Relevante bestanden
De belangrijkste bestanden voor deze module zijn:

- `core/models.py`: Bevat de definitie van `AgendaItem`.
- `core/views/agenda.py`: Bevat de views voor het tonen en beheren van de agenda.
- `core/views/diensten_webcal.py`: Implementeert de ICS-export functionaliteit.
- `core/forms.py`: Bevat het `AgendaItemForm`.
- `core/tasks/`: Bevat de push-notificatie taken.
