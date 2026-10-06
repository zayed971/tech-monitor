# THE ULTIMATE TECH MONITOR: plan (2026-10-06, written 19:4x)

One monitor for tech buying: **Egypt + UAE + outside**, **new + used**, **every payment way**, with the **burner Chrome** covering what plain scraping cannot reach (Facebook Marketplace and similar). It merges three things: Codex's Egypt Deals, the laptop market scan, and cheap_tech.

---

## 1. What I already did (checked, not assumed)

- Found all **49 parts** (`EgyptDeals-Full.zip.part001` to `part049`) in `Downloads\Telegram Desktop`. Joined them: **2,163,406,755 bytes, SHA-256 matches** what Codex's script expects.
- Extracted to **`Desktop\EgyptDeals\egypt-deals`** (16,820 files, about 3.5 GB). The 2 GB zip sits in `Desktop\EgyptDeals-Transfer`.
- A full check of every file against the manifest is still running. I'll report the result.
- **Not started:** the monitor, Telegram sending, Chrome. I did **not** open `.env` (it holds your Telegram settings).
- Codex's manifest says the **cloud monitor is stopped** and its **watch deadline is 2026-10-27 01:17 Cairo time**. The handoff says not to reset it.

## 2. What Egypt Deals already is (the core we keep)

| Part | State |
|---|---|
| Database | `deals.sqlite3`, 336 MB: **58,242 listings, 122,252 price observations, 1,233 source runs, 8 alerts** |
| Sources | **23**: 6 Shopify, 7 sitemap, 2 Woo, 3 HTML, price sites (Qarenly, EGPrices, Pricena), Dubizzle, Jumia, Noon, Amazon.eg, B.TECH, Facebook-public |
| Biggest stores in the data | Compumarts 9,987, Alfrensia 8,642, Ennap 8,065, Kimo 8,004, EgyptLaptop 5,937, El Badr 4,189, Raya 3,559 |
| Condition split | new 52,748 / used 1,045 / unknown 4,385 / refurbished 35 / open box 29 |
| Categories | laptop 4,707, GPU 2,281, monitor 2,799, SSD 2,069, RAM 1,439, CPU 1,546, PSU 1,499, motherboard 2,674, case 2,256, and more |
| Alerts | price thresholds (rules.json: LOQ 5060 laptop, used RTX 3060, DDR5 sticks, used 5600X PC) + "fell 8% in 24 h" + Telegram with dedupe |
| Safe habits | never turns "unknown stock" into "in stock"; shipping/tax never becomes zero; Facebook collector is owner-operated and pauses at a login prompt |
| Known holes (Codex's own list) | Dubizzle HTTP 401, Amazon access errors, Pricena rate limits (429), robots-blocked pages, B.TECH adapter failures, **no Facebook run ever tested live** |

## 3. What the two old scrapers add

| Old scraper | Brings | Merge action |
|---|---|---|
| **laptop market scan** (`ebay_laptop_scrape`) | eBay, Amazon.ae and .eg, Dubizzle EG, OpenSooq UAE/SA, Reddit r/hardwareswap (over the burner), GPU/RAM text parsers, scam-pattern filter, Blender value score, TOP20 verified picks | Port eBay, Amazon.ae, OpenSooq and Reddit as new adapters. Reuse its parsers and scam filter. Its Shopify scraper is **dropped** (Codex already does Shopify better). |
| **cheap_tech** | **30 stores** (Egypt, US, China) that ship to Egypt and take PayPal, the store lists with proof, Egypt import rules, Reddit advice, the UAE shopping scrapers (Amazon.ae, Noon, Microless, Sharaf, Jumbo), the BUY_PLAN part lists | Load `stores_checked.csv` as the **WORLD source list** with a PayPal flag. Port the UAE scrapers. Keep BUY_PLAN as the seed watchlist. |

Result: the old two stop being separate scrapers (families 11 and 12). Their data and their lessons live inside one monitor.

## 4. What the ultimate monitor must do (your list, made exact)

1. **Zones.** Every listing is tagged `EG`, `UAE` or `WORLD`.
2. **Payments.** Every listing records which ways it accepts: **PayPal, COD, card (Visa/Mastercard), installments** (valU, Contact, Souhoola and similar), bank transfer, InstaPay/Fawry/Meeza. You can filter "PayPal only" or "COD only". Unknown is "unknown", never a guess.
3. **Condition.** New, used, refurbished, open-box. Used prices are asking prices, not proven sale prices.
4. **All tech.** Priority 1 is the Blender and AI machine: laptops, PCs, GPUs (12 GB or more for AI), 32 GB RAM, SSDs, monitors under 27". Priority 2 is everything in cheap_tech D-005 (keyboards, maker, 3D printing, homelab, Raspberry Pi, and so on).
5. **Landed cost to Mansoura.** Foreign and UAE items get item + shipping + customs/VAT + card or PayPal fee at today's rate. If any piece is unknown, the result says "unconfirmed", never a total with zero in the gap. Quotes come from real checkouts (Codex already has `import-quote.example.json`).
6. **Platforms.** All shops, price sites, marketplaces and classifieds in section 5, plus the burner for logged-in ones.
7. **Burner coverage.** Facebook Marketplace for Mansoura and Egypt, read only, slow, stops at a login or checkpoint.
8. **Alerts.** One Telegram sender, no duplicates, price thresholds from your buy plan, an 8% drop in 24 h rule, and a weekly "best buys" report as a PDF.

## 5. Platform map (what exists, what is missing)

| Zone | Have in Codex's monitor | Add from old scrapers / new |
|---|---|---|
| **Egypt shops** | Compumarts, Kimo, AHW, Ennap, Elyamama, Alarabiya, Alfrensia, Softlink, El Badr, Sigma, EgyptLaptop, TV-IT, 2B, Raya, B.TECH, Jumia, Noon, Amazon.eg | fix B.TECH and Amazon.eg; the other Egyptian stores from cheap_tech's list |
| **Egypt price sites** | Qarenly, EGPrices, Pricena (rate-limited) | slow Pricena down |
| **Egypt used** | Dubizzle (blocked 401), a Facebook public probe (collected zero) | Dubizzle via the burner browser, OpenSooq, Facebook Marketplace and Egyptian Facebook buy-and-sell groups (burner), Reddit |
| **UAE** | nothing | Amazon.ae, Noon UAE, Sharaf DG, Microless, Jumbo, Dubizzle UAE, OpenSooq UAE |
| **WORLD** | nothing | eBay, Amazon US, Newegg and B&H, AliExpress and Banggood, plus the cheap_tech China and US store lists; Reddit r/hardwareswap for used |

## 6. Things you didn't mention (reminders)

1. **Installments** are a big Egyptian payment way; I'm adding it as its own flag. Also InstaPay, Fawry and Meeza.
2. **Your own card and PayPal limits and fees** (an earlier note says fees may eat 6–7%). They feed the landed cost.
3. **How does a UAE or foreign order reach Mansoura?** Courier, forwarder, or someone traveling? The landed cost needs this.
4. **Customs and phones.** Egypt has electronics customs and a phone registration fee. cheap_tech has `EGYPT_IMPORT_RULES.md`; the monitor uses it.
5. **Warranty and authenticity:** local agent versus grey import versus used with no warranty (Codex already tracks warranty fields).
6. **Used checks:** mining history and serial for GPUs, battery health for laptops. The old scam filter helps; a checklist attaches to every used alert.
7. **Build checker:** a PC is parts from several shops. A "can these parts work together, and what is the total" check (socket, DDR generation, power supply watts, the 70,000 EGP budget).
8. **Price history per exact model** with the exchange rate stored, so "cheaper than last month" is real.
9. **Power and plugs:** items from outside need 220 V and a plug that fits. Laptops bring an Arabic or English keyboard question.
10. **Scope control:** "all techs" can explode. Priority 1 first, then widen.
11. **Facebook and Dubizzle terms and robots rules.** Owner-operated, read only, slow. Risk: the burner account can get restricted. Never post, message, or bypass a login or checkpoint.
12. **One owner at a time for the code.** If Codex and I both edit the same folder we will overwrite each other.
13. **Secrets:** `.env` has the Telegram token; the Facebook Chrome profile keeps a login. Both stay out of git and out of any report.
14. **The laptop is RAM-starved and must stay awake.** The monitor needs a scheduled task and a free-RAM check; Marketplace browsing is the heavy part.
15. **The deadline:** the watch ends 2026-10-27 unless you extend it. Do you want it to run for life instead?
16. **Backups:** the database is 336 MB of history. It goes into the backup plan (all on one SSD today).
17. **Laptop or PC is still undecided.** The monitor must watch both: laptops under 70k and PC parts for a build.

## 7. The build order (each step has a "done means")

| # | Step | Done means |
|---|---|---|
| 0 | Verify the package | all 16,820 files match the manifest, database integrity ok (running) |
| 1 | One home + git | one folder, git started from day one, secrets ignored, no remote until you say |
| 2 | Baseline run on the laptop | tests pass; one retailer run completes with **no Telegram send**; the database is unchanged except new rows |
| 3 | Add zone, payments, landed cost to the data | the three new fields appear on every listing; unknown stays unknown |
| 4 | Port the old scrapers | eBay, Amazon.ae, OpenSooq, Reddit, UAE stores and the WORLD store list produce rows in the same database |
| 5 | Landed cost to Mansoura | a foreign item shows a real landed price or "unconfirmed", never a fake total |
| 6 | Burner lane | Dubizzle and Facebook Marketplace candidates saved as "availability unknown", with a live check, or a plain report that it was logged out |
| 7 | Alerts and report | one sender, dedupe tested, first "best buys" PDF |
| 8 | Run it for real | scheduled task, health check, gap report, backup |

Steps 0–2 are safe and need only your go on the home folder. Steps 3–5 are code only. Step 6 needs you at the screen if Facebook asks for a login.

## 8. What I need from you

1. **Home folder.** Recommended: **`C:\PROJECTS\tech_monitor`** (a copy of Codex's code and data; the Desktop copy stays as a backup). Codex and I take turns, never at once. Or keep working in `Desktop\EgyptDeals`. Which?
2. **Resume Telegram alerts from this laptop?** The cloud sender is stopped, so there is no duplicate risk. Yes or no.
3. **Burner Chrome and Facebook.** Is the burner logged in to Facebook? I will not log in or create an account. If it is logged out, I stop and tell you. Or do you prefer Codex's own Chrome profile where you sign in yourself?
4. **How an order gets to Mansoura** (courier, forwarder, someone traveling) and which cards or PayPal you would use.
5. **Budget and priority:** keep 70,000 EGP for the device? Priority 1 first, then widen?
6. **Spend:** none needed. The scraping is free. Say so if you want Hermes or Haiku to do the bulk reading.

## 9. Rules this follows (yours, not mine)

Read only. No posting, messaging or buying. No password typing, no CAPTCHA solving, no new accounts. Stop and tell you if logged out. Keys are never printed. Delete nothing without your yes. No push to any remote without your yes. Every price carries its source, time and stock status.
