# Authenticatie, Autorisatie & Beveiliging

Omdat de Apotheek Jansen App medische en bedrijfsgevoelige informatie bevat, maken we gebruik van een strikt beveiligingsmodel. We bepalen niet alleen *wie* mag inloggen, maar ook *wat* iemand mag zien en *waar* iemand zich bevindt.

## Role-Based Access Control (RBAC) & Least Privilege

De applicatie maakt gebruik van een **Role-Based Access Control (RBAC)** systeem. Dit betekent dat toegangsrechten worden gekoppeld aan de specifieke rol of functie van een medewerker (zoals apotheker of assistent). 

Wij hanteren hierbij strikt het principe van **Least Privilege** (minimale rechten):
*   Een medewerker heeft standaard **geen toegang** tot gegevens, tenzij dit absoluut noodzakelijk is voor het uitvoeren van zijn of haar werk.
*   De app toont alleen menu-items, modules en overzichten die voor de ingelogde gebruiker relevant zijn.

## Patiëntgegevens: Versleuteling & IP-Restrictie

Wanneer we in specifieke modules (zoals de medicatiebeoordeling) werken met herleidbare patiëntgegevens, gelden er extra zware beveiligingsmaatregelen:

1.  **Versleutelde Opslag (Encryption at Rest)**: Gevoelige patiëntdata zoals namen en geboortedatums worden nooit als leesbare tekst in onze database bewaard. We slaan deze altijd **versleuteld** op. Mocht een onbevoegde ooit toegang krijgen tot de database, dan ziet hij of zij enkel onleesbare reeksen karakters.
2.  **IP-Restrictie**: Pagina's waarop patiëntgegevens worden getoond, zijn uitsluitend toegankelijk vanaf geautoriseerde IP-adressen. Dit betekent in de praktijk dat je deze overzichten alleen kunt openen wanneer je fysiek bent verbonden met het beveiligde (bedrijfs)netwerk van Apotheek Jansen. Probeer je het thuis of onderweg? Dan blokkeert de app de toegang tot die specifieke pagina's.

## Interne API-beveiliging

Naast de gebruikerslogin is de communicatie tussen onze hoofdapplicatie (de Django webserver op EC2) en de analyse-servers (AWS Lambda) beveiligd. Dit gebeurt via een gecodeerde `X-API-Key`. Hierdoor kunnen de servers veilig onderling data uitwisselen zonder risico op ongeautoriseerde toegang van buitenaf.
