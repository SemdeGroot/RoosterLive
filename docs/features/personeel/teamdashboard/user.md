# Teamdashboard (Gebruiker)

Het **Teamdashboard** in de **Apotheek Jansen App** is het centrale punt voor de planning en het beheer van de personeelsbezetting. Het biedt planners en beheerders een actueel overzicht van de beschikbaarheid van het team en de mogelijkheid om diensten toe te wijzen.

## Doel van de module
Het doel van deze module is om het planningsproces te vereenvoudigen en te centraliseren. Door de beschikbaarheid van medewerkers direct naast de minimale bezetting te tonen, kunnen planners snel en nauwkeurig een rooster maken.

## Wat kun je met deze module?
Met het Teamdashboard kun je het volgende:

- **Planning per taak**: Een overzicht van alle taken en locaties op de verticale as en de tijd op de horizontale as. Hier zie je direct wie waar is ingepland.
- **Planning per medewerker**: Een overzicht met alle medewerkers op de verticale as. Dit helpt om de individuele werkdruk en contracturen te bewaken.
- **Visuele status (Donuts)**: Direct inzicht in de voortgang van de planning per dag en voor de gehele week via interactieve cirkeldiagrammen.
- **Beschikbaarheid inzien**: Real-time weergave van de door medewerkers opgegeven beschikbaarheid (ochtend, middag, vooravond).
- **Concept-modus**: Wijzigingen worden eerst als concept opgeslagen (gemarkeerd in blauw). Medewerkers zien deze pas na publicatie.
- **Publiceren**: Het definitief maken van het weekrooster, waarbij medewerkers direct een push-notificatie ontvangen.
- **Shifts kopiëren**: Snel de planning van de vorige week overnemen voor vaste medewerkers die beschikbaar zijn.
- **Zoeken en Filteren**: Snel taken of medewerkers vinden via de zoekbalken boven de roosters.
- **Sorteren**: De medewerkerslijst sorteren op naam, functie of het aantal ingeplande diensten.

## Werkwijze

### Navigatie en Status
- **Week selecteren**: Gebruik de pijlen of de weekkiezer bovenin om naar de gewenste week te navigeren.
- **Statusoverzicht**: De "donuts" boven het rooster tonen per dag de verhouding tussen de geplande bezetting en de minimale eisen. Beweeg je muis over een donut voor een gedetailleerde uitsplitsing per taak.

### Roosteren per Taak
In dit tabblad plan je medewerkers in op specifieke taken:

1. Klik op een cel (combinatie van taak, dag en dagdeel).
2. Er opent een venster waarin je één of meerdere medewerkers kunt selecteren. Beschikbare medewerkers worden getoond; vaste medewerkers zijn **dikgedrukt**.
3. Gebruik de sorteeroptie in het selectievenster om te wisselen tussen "Vast eerst" of "Oproep eerst".
4. Wijzigingen worden direct als concept opgeslagen.

### Roosteren per Medewerker
In dit tabblad wijs je taken toe aan specifieke medewerkers:

1. Klik op een cel bij een medewerker op een specifiek dagdeel.
2. Selecteer de gewenste taak uit de lijst. Je ziet direct de huidige bezetting van die taak (bijv. 1/2 betekent één van de twee benodigde medewerkers is gepland).
3. Cellen zonder planning tonen de beschikbaarheid van de medewerker (groen voor beschikbaar, rood voor niet beschikbaar).

### Afronden en Publiceren
- **Concepten herkennen**: Nieuw toegevoegde conceptdiensten zijn groen gemarkeerd.
- **Vorige week kopiëren**: Klik op "Vul shifts" om de planning van de voorgaande week over te nemen. Dit werkt alleen voor vaste medewerkers op momenten dat zij als beschikbaar staan geregistreerd.
- **Publiceren**: Klik op "Publiceer weekrooster" om alle concepten definitief te maken. Het systeem verstuurt automatisch push-notificaties naar de medewerkers met wijzigingen in hun rooster.

## Bijzonderheden
- **Bezettingseisen**: De getallen in de tabelkoppen en cellen (bijv. 2/3) geven aan hoeveel medewerkers er zijn ingepland ten opzichte van de minimale eis. Een rode kleur duidt op onderbezetting, groen op een volledige bezetting.
- **Vaste medewerkers**: Medewerkers met een vast dienstverband worden in de lijsten dikgedrukt weergegeven om ze makkelijker te onderscheiden van oproepkrachten.
- **Zichtbaarheid**: Medewerkers zien hun nieuwe diensten pas in hun eigen overzicht ("Mijn diensten") nadat de planner op "Publiceer weekrooster" heeft geklikt.
- **Permissies**: Toegang tot het Teamdashboard is beperkt tot gebruikers met de permissie `can_view_beschikbaarheidsdashboard`. Het maken van wijzigingen vereist de permissie `can_edit_beschikbaarheidsdashboard`.
