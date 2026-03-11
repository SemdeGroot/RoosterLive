# Machine statistieken (Gebruiker)

De module **Machine statistieken** in de **Apotheek Jansen App** biedt real-time inzicht in de productieprestaties van de baxter-machines. Hiermee kan de voortgang van de dagelijkse productie worden gevolgd en kunnen trends in de productiecapaciteit over langere periodes worden geanalyseerd.

## Doel van de module
Het doel van deze module is het monitoren van de operationele efficiëntie van de baxter-machines. Door inzicht te geven in het aantal geproduceerde zakjes per machine, kan de planning worden geoptimaliseerd en kunnen eventuele afwijkingen of vertragingen in het productieproces sneller worden gesignaleerd.

## Wat kun je met deze module?
Met de module Machine statistieken kun je het volgende:

- De actuele productie (aantal zakjes) van vandaag per machine inzien.
- De voortgang gedurende de dag volgen via een grafiek met tijdstippen (snapshots).
- Weektotalen bekijken om de prestaties van de afgelopen dagen te vergelijken.
- Historische gegevens opvragen om de productie van specifieke periodes in het verleden te analyseren.
- Direct zien wanneer de laatste update van een machine is ontvangen.

## Werkwijze
Volg deze stappen om de statistieken te raadplegen:

- **Dashboard openen**: Navigeer naar **Statistieken** > **Machine statistieken**.
- **Vandaag bekijken**: Bovenaan de pagina zie je direct het totaal aantal zakjes van de huidige dag, onderverdeeld per machine.
- **Trendgrafiek**: De grafiek toont het verloop van de productie over de dag. Hierdoor kun je zien op welke piekmomenten de machines het meest actief zijn.
- **Historie**: Gebruik de opties voor tijdsperiodes om terug te kijken in de geschiedenis en de productiecijfers van eerdere weken of maanden in te zien.

## Bijzonderheden
- De gegevens worden automatisch en real-time bijgewerkt door een 'Watchdog'-koppeling met de baxter-machines. Je hoeft zelf geen gegevens in te voeren.
- De productiecijfers zijn gebaseerd op het aantal succesvol verwerkte zakjes in de baxterrol.
- Toegang tot deze gedetailleerde statistieken is alleen beschikbaar voor gebruikers met de permissie `can_view_machine_statistieken`.
