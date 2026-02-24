# XML Watchdog

Monitort een folder op nieuwe XML bestanden, parsed machine data en stuurt dit naar de Django API.

## Structuur

```
watchdog/
├── watcher.py          # Main script (entry point)
├── xml_parser.py       # Bestandsnaam + XML parsing
├── api_client.py       # Verstuurt JSON naar Django
├── config.py           # ← HIER je instellingen aanpassen
├── requirements.txt
└── test_parser.py      # Parser tests
```

---

## Stap 1: config.py aanpassen

```python
WATCH_FOLDER = r"C:\machines\output"
API_URL      = "http://jouw-server/api/machine-data/"
API_TOKEN    = "jouw-token"
```

---

## Stap 2: EXE bouwen (op je eigen machine)

```cmd
pip install pyinstaller watchdog requests
pyinstaller --onefile --name WatchdogService watcher.py
```

EXE staat in `dist\WatchdogService.exe`.
Kopieer naar doelmachine: `C:\watchdog\WatchdogService.exe` + `config.py`

---

## Stap 3: Windows Service via NSSM

Download NSSM van https://nssm.cc/download

Open **Command Prompt als Administrator**:

```cmd
C:\nssm\win64\nssm.exe install WatchdogService
```

Vul in:
- **Path:**        `C:\watchdog\WatchdogService.exe`
- **Startup dir:** `C:\watchdog`

Tabje **I/O**:
- **Output:** `C:\watchdog\watcher.log`
- **Error:**  `C:\watchdog\watcher.log`

```cmd
C:\nssm\win64\nssm.exe start WatchdogService
```

---

## Logging

Max 3MB totaal (3 x 1MB rotating). Bij 144 files/dag blijft dit altijd klein.
Logformat: `2025-12-03 10:20:17  INFO  M02 | 2025-12-03 10:20:17 | 6313 zakjes | [SUCCES] verstuurd`

---

## Handige commando's

```cmd
sc query WatchdogService                          # status
nssm stop / start / restart WatchdogService       # beheer
nssm remove WatchdogService confirm               # verwijderen
Get-Content C:\watchdog\watcher.log -Wait         # live logs (PowerShell)
```

---

## Lokaal testen

```cmd
pip install -r requirements.txt
python test_parser.py     # parser testen
python watcher.py         # watchdog starten
```