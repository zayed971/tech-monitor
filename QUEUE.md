# Queue (tech_monitor)
## NOW (max 3)
- Burner jobs finished (02:22, 02:40) and egypt-shops ended exit=0 at 06:36 (KeyError fix proven live). Still to do: read which burner sites gave rows vs "wall" (source_runs state). The collector keeps running; its next job loads the D-011 code, so read that job's END line.
- "What to buy": Zayed may buy a local PC soon. When he asks, run top_findings (RUNBOOK) for pc, gpu, ram, ssd, cpu, motherboard, psu in EG, then laptops; answer in plain words with the source, time and stock of every price.
- Spec precision: the reader still mislabels some GPUs and can take the CPU from marketing text ("Ryzen 9 8945HS (Beat i9-13900H)" read as i9). Fix egypt_deals/model.py and add a test. Storage, condition, PSU/UPS and category fixes are done (D-011).

## NEXT
- UAE coverage gap found 2026-10-07: only Amazon.ae gives SSD rows (97); Noon, Sharaf DG and Jumbo gave 2 to 4 each and there are no external/portable SSD rows from the UAE at all (the UAE external prices in the answer came from web search, not the database). Add SSD, portable SSD and flash-storage queries to the burner Gulf shops module.
- Deal hunt follow-ups: (1) the peer-gap rule needs finer model identity for motherboards and coolers; (2) check the ASUS ProArt PA278CGRV at B&H (13,010 EGP, US$249 vs US$299 elsewhere) in the burner Chrome if Zayed wants a monitor after all; (3) SSDs and RAM in Egypt look cheaper than the US or UK right now (e.g. Lexar NM620 2TB 10,000 EGP at Compumarts vs about US$250 for a 2TB NVMe in US shops): watch whether Egyptian shops reprice, and tell Zayed to buy storage and RAM locally if he is buying soon.
- After the next egypt-shops pass (about 10:12) re-measure unknown condition and the "other" category (14 k old rows) under the D-011 rules; add classifier rules from a sample of what is left in "other".
- Coverage: Technology Valley (4,501 pages unvisited), 2B, Raya, B.TECH need more detail passes (max-details per run is the limit). Pricena 429 now backs off (D-011); watch its next run.
- A per-decision report limited to the categories one purchase needs (instead of the 120-category dump), with a budget limit and resale credit; check_listing.py is the first piece.
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
