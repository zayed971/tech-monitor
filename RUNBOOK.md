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
Zone counts live inside each row's JSON (`zone` field; rows with no zone are older Egyptian rows, read as EG). The `listings` table has only `id, payload`.

## Top findings (read only; ask any time)
```
.venv\Scripts\python.exe scripts\top_findings.py --kind laptop --kind gpu --zone UAE --zone KSA --limit 10
```
Kinds: laptop gpu pc ram ssd cpu motherboard psu. Zones: EG UAE KSA US. Budget default 70000 EGP, screen excluded.
More examples: `--kind pc --kind ram --kind ssd --zone EG --condition used --limit 10` ; `--max-age-hours 24` ; `--out data\my_list.md` also saves the list.
CAUTION: the spec reader still mislabels some GPUs (QUEUE NOW), so check a GPU title yourself before saying "buy this". Landed cost shows "unconfirmed" for UAE, KSA and US items until real quotes exist; it is never zero. Give Zayed the source, time and stock status of every price.

## Search any model, or check a listing you found (read only)
```
.venv\Scripts\python.exe scripts\find.py --q "K552|G403" --zone EG --condition new --limit 0
.venv\Scripts\python.exe scripts\check_listing.py --title "Zotac RTX 3060 12GB" --price 12000 --currency EGP --condition used
```
`find.py` shows every match, not a top 10; a `*` after the condition means "assumed new, the shop only sells new". `check_listing.py` reads the specs from the title you paste and compares the price with stored prices; it never fetches or posts anything. Both take about 30 s because they read every stored row.

## Always-on collector (no alerts)
Start (hidden, no window). Only ONE at a time: check first with the next block.
```
cd C:\PROJECTS\tech_monitor
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-X","utf8","scripts\watch_all.py" -WorkingDirectory $PWD -WindowStyle Hidden -RedirectStandardOutput "data\watch_all.out.log" -RedirectStandardError "data\watch_all.err.log"
```
Is it running? Each collector shows as two python.exe lines (a launcher and its child); that is one collector.
```
Get-CimInstance Win32_Process | ?{$_.CommandLine -match 'watch_all'} | select ProcessId,ParentProcessId,CreationDate
Get-Content data\watch_all.log -Tail 10
```
Stop cleanly: create an empty file `data\STOP_WATCH`, wait until the log says `watch_all stopped` (the running job finishes first; the Egyptian shops job takes about 30 minutes), then delete the file. To load code or job changes: stop cleanly, then start.
Jobs and their hours: the JOBS list in `scripts\watch_all.py`; last-run times in `data\watch_all_state.json`. A job runs only when free RAM is at least 2.5 GB. A reboot stops the collector; nothing restarts it yet (QUEUE LATER).
Burner Chrome (needed by the burner shop jobs and Facebook jobs; they skip when it is down). Is it up: `Invoke-WebRequest http://127.0.0.1:9222/json/version -UseBasicParsing`. Launch: `powershell -ExecutionPolicy Bypass -File C:\Users\HP\ZAYED-AI\browser\launch-agent-chrome.ps1`. Never log into anything there; if a site shows logged out, stop and tell Zayed.

Burner shop ids (for --source): br_noon_ae br_noon_sa br_noon_eg br_sharaf_ae br_jumbo br_extra_sa br_jarir_sa br_dubizzle_ae br_dubizzle_eg br_microless (Gulf); br_us_ebay br_us_bh br_us_bestbuy br_us_backmarket br_us_newegg br_us_microcenter br_us_swappa br_us_amazon (US).

## One lane by hand
```
.venv\Scripts\python.exe scripts\run_uae_ksa.py --source amazon_ae --max-items 300
.venv\Scripts\python.exe scripts\run_us.py --source us_wisetek --max-items 300
.venv\Scripts\python.exe scripts\run_burner_gulf.py --source br_noon_ae --query "RTX 3060 12GB" --max-items 30
.venv\Scripts\python.exe scripts\run_burner_us.py --source br_us_ebay --query "RTX 3090" --max-items 60
.venv\Scripts\python.exe scripts\run_facebook.py --zone UAE --city dubai --scrolls 2 --delay 8
.venv\Scripts\python.exe scripts\burner_state.py      (is the burner logged in to Facebook?)
```
