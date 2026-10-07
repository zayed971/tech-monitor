# GAPS (tech_monitor): what the monitor cannot see, sees wrong, or does not know
Measured 2026-10-07 18:30 to 19:30 +0300 by Claude on the live database (66,695 rows seen in the last 72 h) and a 12-product web audit. Every number says how it was got. When a gap is closed, change its line here and say where the fix is.
Status marks: OPEN, FIXED (code done, live proof pending), DONE.

## 1. Coverage: what is not in the database at all
| # | Gap | Evidence | Status |
|---|---|---|---|
| 1.1 | At least 27 Egyptian shops are outside `sources.json` | Web audit of 12 random products found: puzzle-technology.com, dream2000.com, smartshop-it.com, sama-link.com, redlinesys.com, compuscience.com.eg, softlaptop.com, maximumhardware.store, zstations.com, recoverytrading.org, barakacomputer.net, king-tech-eg.com, dokkantech.com, wifigroup.shop, new-vision.tech, egdigitaldreams.com, eastasiaeg.com, geeksstoreeg.com, v2comeg.com, arctichunter-eg.com, cairovolt.com (Anker, cash on delivery), elseragtech.myeasyorders.com, gamesworldegypt.com, myxprs.com, raneen.com, etisalstore.com, mobileworld-zag.com. The monitor has about 20 Egyptian domains. | OPEN |
| 1.2 | Because of 1.1, the cheapest price is sometimes missed | Same audit: 3 of 12 products were cheaper elsewhere (D-Link R04 575 vs 649 = 11%, Aerocool 750W 2,350 vs 2,499 = 6%, Soundcore R50i NC 1,199 vs 1,499 = 20%), 6 were the same, 2 were cheaper in the monitor, 1 cheaper but out of stock. So about 1 in 4 prices the monitor calls "cheapest" is not. Small sample: treat as a rough guide. | OPEN |
| 1.3 | Sources that fail every run | `source_runs`: egprices (network/TLS error since 10-06 20:04), Noon plain (robots), Facebook public probe (robots), Microless (wall, 403), Newegg, Micro Center, Swappa (walls), Amazon.com (no USD prices from an Egypt browser). Still scheduled and still failing. | OPEN |
| 1.4 | El Badr stopped refreshing | Last good run 10-06 23:09; "invalid sitemap" at 03:30, 07:56, 12:23. Cause found: its product sitemap 2 returns a PHP notice instead of XML (`getimagesize(): Read error`) and the parser aborted the whole source. 4,189 listings, a main source for SSDs and boards. | FIXED in `adapters.py` (a broken child sitemap is skipped); needs the next egypt-shops pass to prove it |
| 1.5 | Pages known but never read (depth) | `harvest-state`: egyptlaptop 6,193 URLs, tv-it 4,516, raya 4,191, btech 3,180, 2b 2,631 found; each pass reads about 100 (B.TECH only 26 rows per run). A full cycle takes days, and nothing says how far along it is. | OPEN |
| 1.6 | UAE, KSA and US are 25x thinner than Egypt | Rows: EG 60,435, UAE 2,256, KSA 2,435, US 1,569. UAE is almost only Amazon.ae (97 SSD rows; Noon, Sharaf, Jumbo gave 2 to 4 each). No portable SSDs from the UAE at all. | OPEN |
| 1.7 | Burner shops read page 1 only | Noon and Sharaf return about 60 rows per run, a few hundred queries' worth of catalogue is unseen. | OPEN |
| 1.8 | Facebook Marketplace is narrow | 7 queries only (RTX 3060 12GB, RTX 3090, RTX 4070, gaming laptop, gaming PC, Ryzen 7, ...), 2 scrolls, one city per zone (Mansoura, Dubai, Riyadh). No SSD, RAM, monitor, peripheral queries. No Cairo or Alexandria. No US lane scheduled. | OPEN |
| 1.9 | Cross-zone comparison is almost impossible | Of 8,405 distinct models seen, only 28 are priced in 2 or more zones and 3 in 3 zones. Titles are not matched by part number, so "same item cheaper in the UAE" is rarely detectable. | OPEN |
| 1.10 | Not covered by design or by effort | Shops with no website (WhatsApp, Instagram, Facebook pages), Telegram buy and sell groups, wholesale markets (Cairo Ataba / Nasr City), official brand stores, trade-in and repair shops, eBay sold prices (only asking prices), China (AliExpress, Banggood), other Gulf countries. | OPEN |

## 2. Accuracy: what the monitor sees but gets wrong
| # | Gap | Evidence | Status |
|---|---|---|---|
| 2.1 | "In stock" is old | 68% of 24,826 in-stock rows were last verified more than 24 h ago. Raya 91%, 2B 93%, El Badr 99%, Kimo 79%, Alfrensia 83%, Qarenly and Pricena 100% (more than 48 h). The Egypt pass reads about 100 detail pages per shop, so stock rotates over days. | OPEN |
| 2.2 | In stock when the page says no | Audit: Alfrensia Lian Li HydroShift row says in_stock (verified 41 h ago), the page says Out Of Stock; Compumarts H610M H V2 row says in_stock (verified 41 h ago), page says backordered. Shop pages also show a price on out-of-stock and backorder items. | OPEN |
| 2.3 | Price of an unknown size | 1,082 SSD, RAM and HDD rows list several capacities ("500GB / 1TB / 2TB") and carry the cheapest variant's price. | FIXED (flagged "unknown size", hidden from findings) |
| 2.4 | Wrong currency | 476 Pricena rows labelled AED inside Egypt with prices like 130,800 for a laptop. | FIXED (flagged, hidden) |
| 2.5 | Fake "was" prices | 466 rows with a "was" price 60% or more above the current one (Compumarts Ryzen 5800X3D "was 33,333", sold everywhere at 18,500). Not used as a deal signal any more without a second source. | OPEN (needs a rule in `findings`) |
| 2.6 | Installment, bundle, VAT, shipping prices | Audit saw installment tables next to cash prices (Amazon.eg, gamesworldegypt), prices "incl. VAT" (sama-link), delivery 65 to 115 EGP on top (arctichunter), shipping "by phone". Shipping known on 3.8% of rows. | OPEN |
| 2.7 | Near-identical products merged | Aerocool 750W ATX 3.1 vs ATX12V 2.52 under one name; Soundcore R50i (A3949) vs R50i NC (A3959); two Hiksemi "Elite" models at different speeds; i7-14700 tray vs box. Model identity is title tokens plus capacity, pack and screen size, still too coarse for boards and coolers. | OPEN |
| 2.8 | Spec fields mostly empty | Rows with the key spec: GPU VRAM 36%, laptop GPU model 49%, CPU model 68%, monitor size 0% (no screen size, resolution, refresh or panel parsed at all). CPU can be read from marketing text (Ryzen 9 8945HS "Beat i9-13900H" read as i9). | OPEN |
| 2.9 | Category "other" and misfiles | 21.4% of rows are "other" (a fraction is phones and appliances on purpose). | PARTLY FIXED (D-011 rules) |
| 2.10 | Condition unknown | 12% unknown (down from about 30%); new-only shops now default to new (marked). Marketplaces stay unknown. | PARTLY FIXED (D-011) |
| 2.11 | Placeholders and empty prices | 6,039 rows (9%) are placeholders; 101 rows have no price. | OPEN (hidden from findings) |
| 2.12 | Rows are not products | 66,695 rows are about 8,400 distinct models; variants, colours and duplicates inflate the count. "66 k listings" overstates coverage. | OPEN |
| 2.13 | Used ads | Wanted ads, deposits and bait prices (a 5800X at 4,876 next to another at 11,146) look like offers. Wanted ads are now hidden; bait is not detected. | PARTLY FIXED |

## 3. Decision gaps: facts a buyer needs and the monitor does not have
| # | Gap | Evidence |
|---|---|---|
| 3.1 | Payment methods | known on 0.2% of rows (9 of 58 stores had a quote from Hermes) |
| 3.2 | Landed cost | 0% quoted. Every UAE, KSA and US price is an item price only. US to UAE shipping, UAE VAT and duty, traveler limits and Egyptian customs are unknown. Amazon.ae global-store listings add import charges (AED 141 on a 2TB drive) that are not stored. |
| 3.3 | Warranty | known on 6.7% of rows. Whether a UAE or US manufacturer warranty is valid in Egypt is unknown (SanDisk's AE listing says 1 year). |
| 3.4 | Seller and shop trust | seller known on 11.8%. No shop reputation, no scam list, no fake-capacity SSD warning for no-name drives, no check for counterfeit risk. |
| 3.5 | Price history | observations exist for 3 days only (10-05 to 10-07); 36% of listings have one observation. "Cheap compared with its usual price" cannot be proven; Prime Big Deal Days (10-06 and 10-07) and White Friday are not modelled. |
| 3.6 | Compatibility and build fit | no check of socket, DDR generation, M.2 slot, PSU connectors, case clearance, or the 70,000 EGP total. |
| 3.7 | Resale value and total cost of ownership | not modelled (old card resale, RAM kits, upgrade paths). |
| 3.8 | Exchange rate | one rate (52.2475 EGP per USD, checked 10-05, the free open-access feed). Card fees (plan notes 6 to 7%), bank rate and parallel rate are not in any price. |
| 3.9 | Used checks | no mining-history, battery-health or serial check; used-condition claims on ads are unverified. |

## 4. System and process gaps
| # | Gap | Evidence | Status |
|---|---|---|---|
| 4.1 | Nothing restarts the collector | no scheduled task (Task Scheduler list has none for the monitor); a reboot or Windows update stops it; PC booted 10-01. | OPEN, needs Zayed's yes |
| 4.2 | No backup | `deals.sqlite3` 391 MB, `data` 13.1 GB in about 20,000 files, one disk (46.8 GB free), no remote, code exists only on this laptop. | OPEN, needs Zayed's yes |
| 4.3 | Failures are silent | El Badr failed three runs (about 16 h) before anyone looked; egprices and Noon have failed since 10-06. There is no alert by Zayed's choice, but also no health page. | OPEN |
| 4.4 | Health data has three formats | `status` (shops), `state` (Gulf burner), `verdict` (US burner), none at all for `us_*` runs. No single view says which sources are healthy. | OPEN |
| 4.5 | One job at a time | the Egypt pass takes 25 to 30 minutes and blocks every other job; RAM 15.8 GB total, 4.1 GB free. | OPEN |
| 4.6 | Silent selector breakage | tests use saved pages; no test or probe notices when a live shop changes its HTML. | OPEN |
| 4.7 | Single points of failure | the burner Chrome (port 9222 has no password, Facebook account can be restricted, a logout stops all burner jobs); one internet connection; one machine. | OPEN |
| 4.8 | Hermes and web checks are manual | deal hunt (D-012) runs when asked, not on a schedule. | OPEN |
| 4.9 | Regex escape traps | code written through the tool layer turned `\b` into a backspace character in two files; found and fixed 10-07. Nothing scans for it. | FIXED, add a check |
| 4.10 | The house files can drift | STATE.yaml numbers go stale within hours. | OPEN |

## 5. Rules and risk gaps
- Reading robots-disallowed shops and Facebook through the burner is Zayed's call (D-009); the risk of bans, terms-of-service complaints and a blocked account is his and is not measured.
- The Telegram token sits in the Desktop backup `.env` (not in this folder); old Telegram parts (560 items) are still in Downloads.
- Seller details are redacted for used ads, but screenshots and cached pages in `data/` may still hold names or numbers (not audited).
- Hermes is capped at US$2 (D-004); web search use has no cap.

## 6. Unknown unknowns: how to keep finding them
These are the ways a purchase could still go wrong that no field in the database covers. Each is a prompt for a test, not a known gap yet.
1. The price shown is not what you pay (coupon needed, installment price, VAT, shipping, bundle-only, deposit, cash-only discount).
2. The item is not the one you think (region version, ATX version, NAND type QLC vs TLC, DRAM-less, fake capacity, refurbished sold as new, grey import).
3. The item is gone or never existed (stale stock, bait ads, scams on Marketplace).
4. A cheaper deal exists where we do not look (1.1, 1.10).
5. Timing: sales (Prime Day, White Friday, Ramadan), shortage swings (SSD and RAM prices are moving now), restocks.
6. Cost beyond the price: customs and baggage limits for travelers, warranty void abroad, return impossible, card fees.
7. The monitor is wrong about itself: a source that looks "ok" but reads the wrong thing (Pricena currency, Alfrensia stock) and a source that is dead but still counted.
Ways to find more, cheaply:
- **Golden basket**: 30 fixed products, checked against the live web every week with this same 12-product audit method; the percentage of "cheaper elsewhere" and "stock wrong" is the recall and accuracy score. First reading: 25% cheaper elsewhere, 2 of 12 stock claims wrong.
- **Source discovery loop**: every shop domain that shows up in a web audit but not in `sources.json` goes on a list; add the cheapest ones first.
- **Shadow shopping**: before any real purchase, walk the checkout of the winner to the final total (read only until Zayed buys).
- **Surprise log**: whenever a price looks too good, write down what turned out to be wrong (a bait ad, a variant, a typo) and add a test.

## 7. What to fix first (my order, effort in brackets)
1. (small, done) El Badr sitemap, Pricena currency, unknown-size storage titles, wanted ads, regex bug. Proof pending: next egypt-shops END line and El Badr source_runs row.
2. (small) A health report script: one line per source (last success, rows, age, state), red when older than its interval; run it each morning.
3. (small) Show stock age in findings and treat stock verified more than 24 h ago as "unverified".
4. (medium) Add the shops from 1.1 that were cheapest in the audit (cairovolt, sama-link, smartshop-it, puzzle-technology, dream2000), after checking each platform (Shopify, Woo or custom).
5. (medium) Raise depth: more detail pages per pass for egyptlaptop, raya, tv-it, btech, 2b; show "x of y pages read" per source.
6. (medium) Part-number matching (brand + model code, EAN/GTIN where the page has it) to unlock Egypt vs UAE vs US comparison.
7. (medium) Facebook queries for SSD, RAM, monitor, peripherals; Cairo and Alexandria; UAE portable SSDs on Amazon.ae and Noon.
8. (needs Zayed) Scheduled task for restart, database backup, a private git remote.
9. (larger) Monitor spec parser, payments and shipping from shop pages, price history views, build checker.
