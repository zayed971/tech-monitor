# TECH_MONITOR: START HERE
Updated: 2026-10-07 02:15 +0300 by HELM (Claude, close-up)

## What this is (3 lines)
Zayed's one tech price monitor: Egypt, UAE, Saudi and the US; new and used; shops, marketplaces and (via the burner Chrome) Facebook Marketplace. It only collects; Zayed asks "top findings" and gets a ranked list.
Zayed already bought his PC and will not change GPU or CPU, and will not buy a laptop (D-013, 2026-10-09). Focus: RAM, SSD, monitors, peripherals, network, power, accessories, gadgets, used finds. The collector still collects everything.
Done = a database of sourced, timed prices with payments and landed cost per item, and one command that prints top findings.

## Where we are (5 lines max)
- It is RUNNING: `scripts/watch_all.py` collects Egypt, UAE, Saudi and the US in a loop, no alerts. Numbers: STATE.yaml. Check and restart: RUNBOOK.md.
- Burner Chrome shop readers (D-009) and Facebook Marketplace are wired in. Open problems and next steps: QUEUE.md.
- Cold start for a new session: `HANDOFF_2026-10-07.md` (paste prompt inside). Long history and gap list: `COFOUNDER_REPORT_2026-10-07.md`.
- Merge design (history): `PLAN.md`.
- Desktop backups, not deleted, one holds the Telegram `.env`: `C:\Users\HP\Desktop\EgyptDeals` and `C:\Users\HP\Desktop\EgyptDeals-Transfer`.

## Reading order
1. This file. 2. A brand-new session: `HANDOFF_2026-10-07.md` (verification step first). 3. `QUEUE.md`. 4. Only what the task needs: `STATE.yaml` (numbers), `RUNBOOK.md` (commands), `DECISIONS.md` (why), `HANDOFF_2026-10-07.md` (cold-start handoff), `HANDOFF.md` (Codex's old notes).

## Where things live (one home per fact)
| Fact | Home |
|---|---|
| Status, counts, which sites work or are walled | STATE.yaml |
| What to do next, open problems | QUEUE.md |
| Everything the monitor cannot see, sees wrong, or does not know (with evidence) | GAPS.md |
| Why we chose X | DECISIONS.md |
| How to run X, how to ask "top findings", how to restart the collector | RUNBOOK.md |
| The merge design | PLAN.md |
| Code | egypt_deals/ (package), scripts/ |
| Source list | sources.json |
| Threshold rules (alerts are OFF) | rules.json |
| Data (not in git) | data/ (deals.sqlite3, cache) |

## Zayed's standing words (verbatim, with date)
- "i wanna spend max 70 [k] egp . wihtout the extra monitor ... i will bring either way extra moninotr. someone traveling . check ameria , uae , and saudi and egypt .. all online and local stors and marketplaces. used new all . nah fuck the alerts just montir that shit and each time iw ill ask u for top fiidnings ... let it be in proejct and as the main scrpeer for this and the desktop is just a backup" (2026-10-06)
- "the bulk reading is hermes" (2026-10-06)
- "he will come from either sauid or uae , i have two . for us , i will delver it to uae then the uae traveler will get it to me" (2026-10-07)
- "yes all of them into the bruner chrome idc. fiunish the job and let the monitor keep going" (2026-10-07)
