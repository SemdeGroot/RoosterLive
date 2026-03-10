# Houdbaarheidscheck (Technisch)

## Technisch ontwerp
De module Houdbaarheidscheck is ontworpen om snel informatie op te vragen uit een SQLite-database (`lookup.db`) die geëxtraheerde gegevens uit de G-Standaard bevat. De focus ligt op het efficiënt opzoeken van houdbaarheidstermijnen na eerste opening of bereiding.

## Datamodel
De belangrijkste componenten zijn:

- **`lookup.db`**: Een SQLite-database in de project root met G-Standaard tabellen.
- **`g_bst004_articles`**: Bevat de artikelen en hun RVG-nummers (`rvg_norm`).
- **`g_bst020_names`**: Bevat de namen van de artikelen.
- **`g_bst371_bbetnr_category`**: Bevat de koppeling tussen de HPK-code en de houdbaarheidscategorieën (categorie 118).
- **`g_bst362_bbetnr_text`**: Bevat de daadwerkelijke houdbaarheidsteksten.

## Implementatiedetails
- **RVG Normalisatie**: De functie `_norm_rvg` verwijdert alle niet-cijferige karakters en stript de voorloopnullen uit de invoer van de gebruiker om een match te kunnen maken met de database.
- **SQL Query**: De module voert een complexe JOIN-query uit op de G-Standaard tabellen (`g_bst004`, `g_bst020`, `g_bst351`, `g_bst371`, `g_bst362`) op basis van het genormaliseerde RVG-nummer en categorie 118.
- **Read-only**: De databaseverbinding wordt geconfigureerd met `PRAGMA query_only = ON` voor extra veiligheid.
- **Form**: Gebruikt `HoudbaarheidCheckForm` voor de invoer van het RVG-nummer.

## Autorisatie en beveiliging
- **Permissies**: Toegang tot deze module is beperkt tot gebruikers met de permissie `can_edit_houdbaarheidcheck`.

## Relevante bestanden
- `core/views/houdbaarheidcheck.py`: Bevat de view-logica en de database-queries.
- `lookup.db`: De SQLite-database met G-Standaard data.
- `core/forms.py`: Bevat het `HoudbaarheidCheckForm`.
- `core/templates/houdbaarheidcheck/index.html`: Het sjabloon voor de zoekinterface.
