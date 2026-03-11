# Machine statistieken (Technisch)

De module **Machine statistieken** binnen de **Apotheek Jansen App** verzamelt en visualiseert productiedata van baxter-machines via een externe 'Watchdog'-component.

## Technisch ontwerp
De module bestaat uit een centrale API (Ingest) die data ontvangt van een externe watchdog-service. De architectuur scheidt de data-acquisitie (watchdog) van de opslag (snapshots en dagtotalen) en de visualisatie (dashboard met grafieken). De snapshots bieden real-time inzicht, terwijl de dagtotalen worden gebruikt voor historische analyse.

## Datamodel
De module wordt ondersteund door twee modellen in `core/models.py`:

- **BaxterProductie**: Slaat geaggregeerde dagtotalen per machine op.
- **BaxterProductieSnapshotPunt**: Slaat individuele meetpunten gedurende de dag op voor trendanalyse.

Beide modellen gebruiken `machine_id` en een tijdsaanduiding als unieke combinaties voor data-integriteit.

## Implementatiedetails
- **Ingest API**: De endpoint `machine_statistieken_ingest` in `core/views/machine_statistieken.py` verwerkt de inkomende XML-parsed data.
- **Visualisatie**: Maakt gebruik van grafiek-bibliotheken in de front-end om trends over de dag en historische periodes weer te geven via de API-endpoints `api/vandaag/` en `api/geschiedenis/`.

## XML Baxter Watchdog
De **XML Baxter Watchdog** is een standalone component die verantwoordelijk is voor de data-acquisitie vanaf de baxter-machines.

### Werking
De watchdog monitort een specifieke folder op nieuwe of hernoemde XML-bestanden met behulp van een `PollingObserver` elke 60 seconden.

- **Parsing**: De metadata (machine_id, datum en tijd) wordt uit de bestandsnaam geëxtraheerd via een regex-patroon. Het aantal geproduceerde zakjes wordt uit het XML-bestand gehaald door de laatste 5 cijfers van de laatste `<zak_id>` tag te parsen.
- **Data-overdracht**: De verzamelde gegevens worden als JSON-payload via een HTTPS POST-request naar de Ingest API verstuurd.
- **Duplicatie-preventie**: De watchdog houdt een set bij van unieke combinaties (machine, datum, tijd) die reeds succesvol zijn verstuurd. Deze set wordt automatisch geleegd zodra een bestand met een nieuwere datum wordt gedetecteerd.

### Robuustheid en Beheer
- **Logging**: Activiteiten en fouten worden lokaal gelogd in `watcher.log`. Dit bestand wordt automatisch geleegd (truncate) zodra het de limiet van 3MB overschrijdt om schijfruimte te besparen.
- **Connectiviteit**: Bij verlies van de netwerkverbinding met de monitoringsmap probeert de watchdog elke 60 seconden opnieuw verbinding te maken.
- **Backfill**: Via `backfill.py` kunnen historische XML-bestanden in bulk worden verwerkt en naar de API worden gestuurd.
- **Deployment**: De component wordt gecompileerd naar een standalone Windows executable (`.exe`) met PyInstaller en draait als een Windows Service via Taakplanner.

## Autorisatie en beveiliging
- **Dashboard Toegang**: Vereist de permissie `can_view_machine_statistieken`.
- **API Beveiliging**: De Ingest API wordt beveiligd door de `BAXTER_WATCHDOG_API_KEY`. Zonder deze sleutel worden meldingen geweigerd.
- **Timezone Management**: Meldingen worden gecorrigeerd naar de lokale Amsterdamse tijdzone voor consistente rapportage.

## Relevante bestanden
- `core/models.py`: Modeldefinities `BaxterProductie` en `BaxterProductieSnapshotPunt`.
- `core/views/machine_statistieken.py`: Bevat de Ingest API en de dashboard-logica.
- `xml_baxter_watchdog/`: Broncode van de externe watchdog-component.
- `core/templates/machine-statistieken/`: Templates voor de front-end visualisatie.
