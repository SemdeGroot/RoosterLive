# Team (Technisch)

De module Team biedt een overzicht van de medewerkers die werkzaam zijn bij Apotheek Jansen. De focus ligt op het ontsluiten van actieve profielen vanuit de database.

## Technisch ontwerp
De module is onderdeel van de `core` app en ontsluit gegevens uit de profielen- en functietabellen. De architectuur is gebaseerd op een standaard Django view die een gefilterde queryset naar een template stuurt, waarbij de filtering op de client-side wordt afgehandeld voor een snelle gebruikerservaring.

## Datamodel
De module maakt gebruik van de volgende modellen:
- `UserProfile`: Bevat de persoonsgegevens, contactinformatie en werkdagen.
- `Function`: Bevat de functietitels en de ranking voor de sorteervolgorde.
- `Organization`: Gebruikt om te filteren op de specifieke apotheek (ID 1).

## Implementatiedetails
De view `whoiswho` haalt de profielen op met een geoptimaliseerde query:
```python
UserProfile.objects.filter(
    user__is_active=True,
    organization_id=1
).select_related('user', 'function').order_by(
    'function__ranking',
    'function__title',
    'user__first_name',
    'user__last_name'
)
```
De `select_related` zorgt ervoor dat de gekoppelde gebruikers- en functiegegevens in één database-query worden opgehaald. De zoekfunctionaliteit in het template wordt uitgevoerd door `whoiswho.js`, die de rijen in de HTML-tabel filtert op basis van de gebruikersinvoer.

## Autorisatie en beveiliging
- Toegang is beperkt tot ingelogde gebruikers (`@login_required`).
- De permissie `can_view_whoiswho` is vereist om de pagina te laden.
- De optie om gegevens aan te passen (indien geïmplementeerd in de toekomst) wordt gecontroleerd via `can_edit_whoiswho`.

## Relevante bestanden
- `core/views/whoiswho.py`
- `core/templates/whoiswho/index.html`
- `core/static/js/whoiswho/whoiswho.js`
- `core/static/css/whoiswho/whoiswho.css`
