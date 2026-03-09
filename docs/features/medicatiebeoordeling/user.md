# Medicatiebeoordeling (Gebruiker)

De medicatiebeoordeling-module controleert medicatielijsten uit Apotheek Informatie Systemen op basis van ingestelde standaardvragen, landelijke richtlijnen en toont relevante aandachtspunten.

> __Privacy & Beveiliging__
> Namen en geboortedatums van patiënten worden versleuteld opgeslagen. Het overzicht is IP-afgeschermd: resultaten zijn uitsluitend in te zien via het interne netwerk van de apotheek.

---

## 1. Een analyse starten

Volg deze stappen om een lijst te controleren:

1. __Selecteer de instellingen__: 
   - Kies het bronsysteem. Momenteel wordt Medimo ondersteund. (De Pharmacom-export functionaliteit is in ontwikkeling).
   - Kies de scope: een afdelingslijst (meerdere patiënten) of een individuele patiënt.
2. __Kopieer de tekst uit het AIS__:
   - Volg hierbij de aanwijzingen die in de app getoond worden.
3. __Plakken en Analyseren__: 
   - Plak de tekst in het invoerveld.
   - _Tip bij individuele patiënten:_ Vul de geboortedatum handmatig in. De leeftijd is vereist voor sommige standaardvragen.
   - Klik op 'Analyseer'.

---

## 2. Resultaten en Controles

De resultaten verschijnen per patiënt op het scherm. De applicatie voert vier controles uit:

- __STOPP-NL v2__: Signaleert medicatie die volgens de richtlijn mogelijk gestopt of gewijzigd dient te worden (zie: [NHG STOP-NL V2](https://www.nhg.org/thema/farmacotherapie/stop-nl-v2/)).
- __Anticholinerge Belasting (ACB)__: Berekent de ACB-score op basis van de [Ephor lijst](https://ephor.nl/wp-content/uploads/2018/12/anticholinergic-drugs.pdf). Bij een score van 3 of hoger wordt een waarschuwing getoond.
- __Dubbelmedicatie__: Controleert op meerdere voorschriften binnen dezelfde werkzame stof-groep.
- __Standaardvragen__: Toont apotheek-specifieke vragen als aandachtspunt of agendapunt.

---

## 3. Medicatie Aanpassen & Bevindingen Noteren

### Handmatige Overrides
Indien een medicijnnaam niet correct wordt herkend of in een verkeerde categorie (Jansen Groep) is geplaatst, kan dit worden aangepast:
1. Klik bij een medicijn op het bewerk-icoon.
2. Wijzig de categorie via de dropdown.
3. Klik op opslaan. De wijziging is direct zichtbaar en wordt meegenomen in exports.

### Bevindingen en Historie Vastleggen
Er zijn tekstvakken beschikbaar voor opmerkingen.
Deze notities worden opgeslagen. Bij een latere beoordeling van dezelfde patiënt worden eerdere opmerkingen getoond onder het veld __Historie__. Het is daarom wenselijk dat eventuele opmerkingen direct gedocumenteerd worden, zodat een volgende reviewer hier niet opnieuw naar hoeft te zoeken.

---

## 4. Resultaten Exporteren

Het overzicht kan worden geëxporteerd voor het patiëntendossier of overleg met de arts:
- __Word-document (.docx)__: Om het document voor het delen nog aan te kunnen passen.
- __PDF-document__: Voor een onwijzigbaar eindrapport.

Overrides en opmerkingen worden meegenomen in de export.

---

## 5. Zelf de Standaardvragen Aanpassen

De 'Standaardvragen' zijn te beheren via het menu (__Medicatiebeoordeling -> Instellingen__).

Voor de configuratie worden altijd ATC-codes gebruikt (nooit diagnoses of indicaties). Tip: Je hoeft deze codes niet uit je hoofd te weten. Je kunt in de app gewoon de Nederlandse naam van een geneesmiddel of groep typen, waarna het systeem zelf de juiste ATC-code erbij zoekt.

Hieronder volgt een uitleg over de logica van de regels ("Triggers", "AND" en "AND_NOT").

### A. De Trigger (Wanneer wordt de vraag overwogen?)
Elke vraag heeft een "Primary Trigger" nodig. Dit is altijd de basis ATC-code.

**Eén code invullen**
Voorbeeld: Je wilt een vraag stellen over NSAID's. Je vult als trigger de ATC-code `M01A` (NSAID's) in.
Werking: Als de patiënt een NSAID gebruikt, wordt de vraag in de basis getoond.

**Meerdere codes invullen (OF-voorwaarde)**
Voorbeeld: Je wilt waarschuwen bij valgevaar. Je vult de codes `N05A` (Antipsychotica) en `N05B` (Anxiolytica) in.
Werking: De vraag wordt getoond als de patiënt een Antipsychoticum **OF** een Anxiolyticum gebruikt (minimaal één van de codes moet aanwezig zijn).

### B. Extra Voorwaarde / "AND" (Wat moet er nog meer aanwezig zijn?)
Voor een combinatie van middelen wordt de "AND" regel gebruikt. 

Let op: Je kunt hier dezelfde ATC-code gebruiken als bij de trigger. Het systeem toont de vraag in dat geval alleen als de patiënt twee **verschillende** medicijnen met diezelfde code tegelijk gebruikt.

**Meerdere middelen binnen één AND-regel (OF-voorwaarde)**
Voorbeeld: Vraag over hartfalen met als trigger `C03C` (Lisdiureticum). Je voegt één "AND" regel toe met daarin `C07` (Bètablokker) en `C09` (RAS-remmer).
Werking: Naast het lisdiureticum moet de patiënt een bètablokker **OF** een RAS-remmer gebruiken. Heeft de patiënt minstens één van deze twee? Dan slaagt de regel en zie je de vraag.

**Meerdere aparte AND-regels (EN-voorwaarde)**
Voorbeeld: Dezelfde vraag over hartfalen. Je maakt nu twee losse "AND" regels. Regel 1 bevat `C07` (Bètablokker) en Regel 2 bevat `C09` (RAS-remmer).
Werking: Naast het lisdiureticum moet de patiënt nu **zowel** een bètablokker **als** een RAS-remmer gebruiken. Ontbreekt er een van de twee? Dan faalt de regel en wordt de vraag geannuleerd.

### C. Uitsluiting / "AND_NOT" (Wanneer moet de vraag geblokkeerd worden?)
Met de "AND_NOT" regel stel je in wanneer een vraag juist verborgen moet worden, bijvoorbeeld omdat het probleem al medisch is afgedekt.

**Meerdere middelen binnen één AND_NOT-regel (OF-voorwaarde)**
Voorbeeld: Vraag over het missen van maagbescherming bij een NSAID (Trigger = `M01A`). Bij de "AND_NOT" regel voeg je `A02BC` (Protonpompremmer) en `A02BA` (H2-antagonist) toe.
Werking: Zodra de patiënt een Protonpompremmer **OF** een H2-antagonist gebruikt, is de maag al beschermd en wordt de vraag direct geblokkeerd.

**Meerdere aparte AND_NOT-regels**
Voorbeeld: Vraag over een mogelijk kaliumtekort bij een lisdiureticum (`C03C`). Je wilt de vraag uitsluiten als de patiënt al kalium krijgt, óf als de patiënt een kaliumsparend diureticum gebruikt. Je maakt voor de overzichtelijkheid twee losse regels: Regel 1 bevat Kaliumsupplementen (`A12BA`) en Regel 2 bevat Kaliumsparende diuretica (`C03D`).
Werking: Elke uitsluitingsregel werkt als een onafhankelijke 'veto'. Heeft de patiënt kalium? Dan grijpt regel 1 in en wordt de vraag geblokkeerd. Heeft de patiënt een kaliumsparend diureticum? Dan grijpt regel 2 in en wordt de vraag geblokkeerd. 
_Praktisch gezien werkt het toevoegen van losse AND_NOT regels dus exact hetzelfde als het toevoegen van meerdere middelen binnen één regel (het is een grote OF-voorwaarde voor uitsluiting), maar het kan helpen om je instellingen overzichtelijk te houden._
