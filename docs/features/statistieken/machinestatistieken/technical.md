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
- **Externe Watchdog**: Een separate component in de `xml_baxter_watchdog/` directory monitort XML-bestanden en stuurt de gegevens naar de Ingest API.
- **Visualisatie**: Maakt gebruik van grafiek-bibliotheken in de front-end om trends over de dag en historische periodes weer te geven via de API-endpoints `api/vandaag/` en `api/geschiedenis/`.

## Autorisatie en beveiliging
- **Dashboard Toegang**: Vereist de permissie `can_view_machine_statistieken`.
- **API Beveiliging**: De Ingest API wordt beveiligd door de `BAXTER_WATCHDOG_API_KEY`. Zonder deze sleutel worden meldingen geweigerd.
- **Timezone Management**: Meldingen worden gecorrigeerd naar de lokale Amsterdamse tijdzone voor consistente rapportage.

## Relevante bestanden
- `core/models.py`: Modeldefinities `BaxterProductie` en `BaxterProductieSnapshotPunt`.
- `core/views/machine_statistieken.py`: Bevat de Ingest API en de dashboard-logica.
- `xml_baxter_watchdog/`: Broncode van de externe watchdog-component.
- `core/templates/machine-statistieken/`: Templates voor de front-end visualisatie.
