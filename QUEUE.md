# Queue (tech_monitor)
## NOW (max 3)
- Always-on collector `scripts/watch_all.py` is RUNNING (started 2026-10-07 01:10, no alerts). Log: data/watch_all.log. Done when it has completed one full cycle of every lane without errors.
- Egyptian blocked sources: a worker is fixing adapters.py and sources.json; verify with one Egyptian pass, then commit.
- Payments: Hermes read 37 of 58 stores but only 9 gave a payment quote (data/stores_verified.csv); second pass with more pages per store.

## NEXT
- Burner browser lane for JS-drawn sites that robots allow (Sharaf DG, Jarir) and for Dubizzle UAE/KSA, OpenSooq detail pages.
- Zayed's call: read robots-disallowed retail search (Noon, Jumbo, eXtra, eBay, B&H) through the burner anyway? (D-007)
- Real landed-cost quotes: US store to a UAE address (shipping, duty), UAE and Saudi carry (customs/baggage at Cairo).
- Spec precision: Codex's spec reader mislabels some GPUs (AMD card read as RTX 5090); findings now require the model in the title; fix the reader itself.
- A PC-parts build checker (socket, DDR, PSU watts, total under 70,000 EGP).

## LATER
- Windows scheduled task to start watch_all at logon; backup of data/deals.sqlite3 (336 MB+).
- Telegram stays OFF (D-002).

## WAITING ON ZAYED
- Which items to look at first: ask for top findings any time (RUNBOOK).
- Decision D-007 (robots-disallowed retail pages through the burner).
