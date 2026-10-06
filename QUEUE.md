# Queue (tech_monitor)
## NOW (max 3)
- Verify the collector is still running and the two new burner jobs finished at least once (RUNBOOK, Always-on collector). Done when data\watch_all.log shows END for burner-gulf-shops and burner-us-shops, then re-count listings and read which burner sites gave rows vs "wall".
- "What to buy": Zayed may buy a local PC soon. When he asks, run top_findings (RUNBOOK) for pc, gpu, ram, ssd, cpu, motherboard, psu in EG, then laptops; answer in plain words with the source, time and stock of every price.
- Spec precision: Codex's spec reader mislabels some GPUs (an AMD card read as an RTX 5090). Fix the reader (egypt_deals/model.py) and add a test; findings already require the model in the title.

## NEXT
- Payments: Hermes read 37 of 58 stores but only 9 gave a payment quote (data/stores_verified.csv); payment methods are mostly unknown. Second pass with more pages per store (cap in D-004).
- Real landed-cost quotes: US store to a UAE address (shipping, duty), UAE and Saudi carry (customs/baggage at Cairo). Needs Zayed or the travelers; until then landed stays "unconfirmed".
- Weak Egyptian sources: jumia (63 rows), tv-it (77), facebook-public (0). Noon plain adapter (1 row) is now covered by the burner module.
- Walled sites: Microless (Gulf burner), Newegg, Micro Center, Swappa (US burner). Watch whether walls change; never work around a challenge (D-009).
- A PC-parts build checker (socket, DDR, PSU watts, total under 70,000 EGP).

## LATER
- Windows scheduled task to start watch_all at logon (today it only runs while this laptop session lives; a reboot stops it); backup of data/deals.sqlite3 (385 MB).
- Telegram stays OFF (D-002).
- Tidy the untracked Telegram files and the Desktop backups only with Zayed's yes (nothing is deleted without it).

## WAITING ON ZAYED
- Whether a local PC gets bought tomorrow (then top findings for it).
- Payment methods he can use (cards, PayPal, installments), and the real route cost from the travelers.
