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
