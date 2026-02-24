# XML Baxter Watchdog

Monitort een folder op nieuwe XML bestanden, parsed machine data en stuurt dit naar de Django API.

## Structuur

```

xml_baxter_watchdog/
├── watcher.py          # Entry point
├── xml_parser.py       # Bestandsnaam + XML parsing
├── api_client.py       # Verstuurt JSON naar Django
├── env_config.py       # Instellingen (ingebakken in EXE)
├── requirements.txt
└── test_parser.py      # Parser tests

````

## Lokaal testen

```cmd
pip install -r requirements.txt
python -m xml_baxter_watchdog.test_parser
python -m xml_baxter_watchdog.watcher
````

## EXE bouwen

Vanuit de project root:

```cmd
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --name XMLBaxterWatchdog xml_baxter_watchdog/watcher.py
```

De EXE staat in `dist\XMLBaxterWatchdog.exe`.

## Windows Service via NSSM

```cmd
C:\nssm\win64\nssm.exe install XMLBaxterWatchdog
```

* **Path:**        `C:\watchdog\XMLBaxterWatchdog.exe`
* **Startup dir:** `C:\watchdog`

Tab **I/O**:

* **Output:** `C:\watchdog\watcher.log`
* **Error:**  `C:\watchdog\watcher.log`

Start:

```cmd
C:\nssm\win64\nssm.exe start XMLBaxterWatchdog
```

## Logging

Er is één logbestand: `watcher.log`. Als die groter wordt dan 3MB, wordt hij leeggemaakt en opnieuw gevuld.

```

---

### Wat is er nu gefixt / waarom werkt dit
- Overal import je nu **env_config** (geen `config.py` meer).
- `api_client.py` is stil en robuust: geen prints, geen crash door `response`-scope.
- Logging is **1 file** (geen backups) met een eenvoudige truncate bij >3MB.
- `test_parser.py` gebruikt correcte package-imports.

Als je wil dat die “truncate” in plaats van leegmaken alleen de laatste X regels behoudt, kan ook, maar dit is het simpelst en het meest betrouwbaar voor “1 file”.