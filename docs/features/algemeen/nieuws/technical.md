# Nieuws (Technisch)

## Technisch ontwerp
De Nieuws module in de **Apo Jansen App** is gebaseerd op het `NewsItem` model en wordt aangestuurd via de views in `core/views/news.py`. De module ondersteunt zowel tekstuele berichten als bestandsuploads (PDF en afbeeldingen) en integreert met Celery voor achtergrondtaken.

## Datamodel
De belangrijkste velden van het `NewsItem` model zijn:

- `title`: De hoofdtitel van het nieuwsbericht.
- `short_description`: Een compacte omschrijving voor de lijstweergave.
- `description`: Een uitgebreide tekstuele toelichting.
- `file_path`: Relatief pad naar het geüploade bestand in `MEDIA_ROOT/news/`.
- `file_hash`: Een unieke hash van het bestand voor deduplicatie en caching.
- `uploaded_at`: Datum en tijd van upload.

## Implementatiedetails
De module is opgebouwd uit de volgende componenten:

- **Bestandsbeheer**: Bestanden worden opgeslagen in een specifieke directory binnen de `MEDIA_ROOT`. Voor PDF-bestanden wordt vaak een preview gegenereerd en gecachet in de `CACHE_DIR`.
- **Opschoning**: In `core/views/news.py` bevindt zich de functie `_cleanup_expired_news`, die periodiek wordt aangeroepen om berichten ouder dan 3 maanden te verwijderen (inclusief bijbehorende bestanden).
- **Push Notificaties**: Bij het opslaan van een nieuw `NewsItem` wordt de taak `send_news_uploaded_push_task` gestart om push-notificaties te versturen naar alle geregistreerde apparaten.

## Autorisatie en beveiliging
De volgende permissies bepalen de toegang tot de nieuwsmodule:

- `can_view_news`: Geeft toegang tot de nieuwslijst en individuele berichten.
- `can_upload_news`: Staat de gebruiker toe nieuwe berichten aan te maken, te uploaden en te beheren.
- **Bestandstoegang**: Toegang tot nieuwsbestanden wordt afgehandeld via de `news_media` view, die controleert of de gebruiker de juiste rechten heeft voordat het bestand wordt geserveerd.

## Relevante bestanden
De belangrijkste bestanden voor deze module zijn:

- `core/models.py`: Bevat de definitie van `NewsItem`.
- `core/views/news.py`: Bevat alle logica voor het tonen, uploaden en beheren van nieuws.
- `core/forms.py`: Bevat het `NewsItemForm`.
- `core/tasks/`: Bevat de push-notificatie taken voor nieuws.
