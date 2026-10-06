# Runbook (tech_monitor): exact commands, nothing else
## Open the project
`p tech-monitor` (PowerShell) once it is in C:\PROJECTS\PROJECTS.yaml.

## Setup (once)
```
cd C:\PROJECTS\tech_monitor
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[browser,test]"
```

## Tests
```
.venv\Scripts\python.exe -m pytest -q
```

## One monitor pass, NO alerts (never add --send)
```
.venv\Scripts\python.exe -m egypt_deals.cli run --root . --scope hardware --max-pages 4 --max-details 8 --workers 4 --delay 4
```

## Check it worked
```
.venv\Scripts\python.exe -c "import sqlite3;db=sqlite3.connect('file:data/deals.sqlite3?mode=ro',uri=True);print(db.execute('select count(*) from listings').fetchone(), db.execute('select count(*) from source_runs').fetchone())"
```

## Top findings (read only; ask any time)
```
.venv\Scripts\python.exe scripts\top_findings.py --kind laptop --kind gpu --zone UAE --zone KSA --limit 10
```
Kinds: laptop gpu pc ram ssd cpu motherboard psu. Zones: EG UAE KSA US. Budget default 70000 EGP, screen excluded.

## Always-on collector (no alerts)
```
cd C:\PROJECTS\tech_monitor
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-X","utf8","scripts\watch_all.py" -WorkingDirectory $PWD -WindowStyle Hidden -RedirectStandardOutput "data\watch_all.out.log" -RedirectStandardError "data\watch_all.err.log"
```
Log: `data\watch_all.log`. Stop: create an empty file `data\STOP_WATCH`. Facebook and Reddit lanes need the burner Chrome: `powershell -ExecutionPolicy Bypass -File C:\Users\HP\ZAYED-AI\browser\launch-agent-chrome.ps1`.

## One lane by hand
```
.venv\Scripts\python.exe scripts\run_uae_ksa.py --source amazon_ae --max-items 300
.venv\Scripts\python.exe scripts\run_us.py --source us_wisetek --max-items 300
.venv\Scripts\python.exe scripts\run_facebook.py --zone UAE --city dubai --scrolls 2 --delay 8
.venv\Scripts\python.exe scripts\burner_state.py      (is the burner logged in to Facebook?)
```
