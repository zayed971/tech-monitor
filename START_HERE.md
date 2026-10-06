# TECH_MONITOR: START HERE
Updated: 2026-10-06 23:00 +0300 by HELM (Claude)

## What this is (3 lines)
Zayed's one tech price monitor: Egypt, UAE, Saudi and the US; new and used; shops, marketplaces and (via the burner Chrome) Facebook Marketplace. It only collects; Zayed asks "top findings" and gets a ranked list.
Goal machine: Blender + local AI box (laptop or PC parts). Device budget 70,000 EGP; the extra monitor (screen) is excluded because someone traveling brings it.
Done = a database of sourced, timed prices with payments and landed cost per item, and one command that prints top findings.

## Where we are (5 lines max)
- Moved from Codex's cloud "Egypt Deals" on 2026-10-06: 49 Telegram parts, SHA-256 ok, 16,819 files verified, 58,242 listings, 23 Egyptian sources.
- Merge design: `PLAN.md`. Old scrapers to fold in (read-only sources): `C:\PROJECTS\ebay_laptop_scrape`, `C:\PROJECTS\cheap_tech`.
- Desktop backup (untouched; it has the Telegram `.env`): `C:\Users\HP\Desktop\EgyptDeals`.
- Full list: QUEUE.md

## Reading order
1. This file. 2. `QUEUE.md`. 3. Only what the task needs: `STATE.yaml` (numbers), `RUNBOOK.md` (commands), `DECISIONS.md` (why), `HANDOFF.md` (Codex's own notes).

## Where things live (one home per fact)
| Fact | Home |
|---|---|
| Status, counts | STATE.yaml |
| What to do next | QUEUE.md |
| Why we chose X | DECISIONS.md |
| How to run X | RUNBOOK.md |
| The merge design | PLAN.md |
| Code | egypt_deals/ (package), scripts/ |
| Source list | sources.json |
| Threshold rules (alerts are OFF) | rules.json |
| Data (not in git) | data/ (deals.sqlite3, cache) |

## Zayed's standing words (verbatim, with date)
- "i wanna spend max 70 [k] egp . wihtout the extra monitor ... i will bring either way extra moninotr. someone traveling . check ameria , uae , and saudi and egypt .. all online and local stors and marketplaces. used new all . nah fuck the alerts just montir that shit and each time iw ill ask u for top fiidnings ... let it be in proejct and as the main scrpeer for this and the desktop is just a backup" (2026-10-06)
- "the bulk reading is hermes" (2026-10-06)
