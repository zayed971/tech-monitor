# Decisions (newest at the bottom; never delete, mark SUPERSEDED)
## D-001 Home = C:\PROJECTS\tech_monitor; Desktop\EgyptDeals is the backup  [ACTIVE]
- Date: 2026-10-06. Decided by: Zayed. Source: "let it be in proejct and as the main scrpeer for this and the desktop is just a backup or a piece of it"

## D-002 No alerts. It monitors; Zayed asks for top findings  [ACTIVE]
- Date: 2026-10-06. Decided by: Zayed. Source: "nah fuck the alerts just montir that shit and each time iw ill ask u for top fiidnings"
- Decision: Telegram off, `.env` not copied here, never use --send.

## D-003 Zones and budget  [ACTIVE]
- Date: 2026-10-06. Decided by: Zayed. Zones: Egypt, UAE, Saudi, America; online and local stores and marketplaces; used and new.
- Device budget 70,000 EGP without the extra monitor (screen). Someone traveling brings the screen (and maybe more): landed cost for hand-carried items is an estimate until Zayed names the route.

## D-004 Hermes does the bulk reading  [ACTIVE]
- Date: 2026-10-06. Decided by: Zayed ("the bulk reading is hermes"). Cap set by HELM: US$2 total for the first build (about 105 EGP). The DeepSeek hard stop at balance US$1.80 still holds. Zayed can change the cap.

## D-005 Facebook: Zayed signs up himself  [ACTIVE]
- Date: 2026-10-06. Zayed offered "create one ... or open it for me to do it". HELM opens the sign-up page in the burner Chrome and Zayed completes it. House rule: agents do not create accounts, type passwords or solve CAPTCHAs.

## D-006 Routes to Mansoura: two travelers  [ACTIVE]
- Date: 2026-10-07. Decided by: Zayed. Source: "he will come from either sauid or uae , i have two . for us , i will delver it to uae then the uae traveler will get it to me"
- Decision: UAE items are bought in the UAE and carried by the UAE traveler; Saudi items are bought in Saudi Arabia and carried by the Saudi traveler; US items are ordered to a UAE address, then carried by the UAE traveler. Landed cost stays "unconfirmed" until real quotes exist (US-to-UAE shipping, UAE duty, Egypt customs/baggage are unknown). Item prices are converted at the stored USD rate (AED 3.6725 and SAR 3.75 per USD are pegs).

## D-007 Sites that block plain HTTP or disallow robots are not worked around  [ACTIVE]
- Date: 2026-10-07. Decided by: HELM (house rule 7). Noon, Jumbo, eXtra, eBay, B&H, Back Market and others disallow search in robots.txt; Microless, Newegg, Micro Center, Swappa return 403; Dubizzle sits behind Imperva. They are recorded as blocked with evidence. Facebook Marketplace and Reddit are read only through the burner Chrome, slowly, because Zayed asked for that lane (D-005). Zayed can decide to read robots-disallowed retail pages through the burner too; that is his call, not made yet.

## D-008 Facebook burner account is signed in; pacing  [ACTIVE]
- Date: 2026-10-07. Zayed signed up himself. Marketplace is read at most once per 8 hours per zone (2 scrolls, 8 s pauses, about 11 page loads), stopping at any login or checkpoint.

## D-009 Robots-disallowed and JavaScript shops are read through the burner Chrome  [ACTIVE, supersedes the "not decided" part of D-007]
- Date: 2026-10-07. Decided by: Zayed. Source: "yes all of them into the bruner chrome idc. fiunish the job and let the monitor keep going"
- Decision: Noon, Jumbo, eXtra, Jarir, Sharaf DG, Microless, Dubizzle, eBay, B&H, Back Market, Newegg, Micro Center, Swappa, Amazon.com may be read by driving the burner Chrome like a person: slow (6 s or more between page loads per site), read only, own tab, never logging in, never solving a CAPTCHA or bypassing a challenge. A challenge, CAPTCHA, "unusual traffic" or block page ends that site's run and is recorded.

## D-010 Close-up fixes: report tolerates rows without a status; the Telegram file-permission test is skipped on Windows  [ACTIVE]
- Date: 2026-10-07. Decided by: HELM (small, safe, reversible; no rule of Zayed's touched).
- Why: the `egypt-shops` job exited 1 at 02:10 with `KeyError: 'status'`. The UAE, Saudi and US collectors save source_runs rows without a `status` key, and the report step in `egypt_deals/cli.py` read it directly. Collected rows were safe, but the report files (data/report.md, listings.json) would not refresh. Fix: read the fields with defaults. Checked with `cli export` on a copy of the database (exit 0, report lists amazon_ae and us_wisetek).
- The old "known failing" test `test_start_message_connects_and_enters_bounded_monitor` failed only on its last line, a Unix file-mode check (0600) that Windows cannot satisfy. It now runs that line only when not on Windows. Telegram stays off (D-002); nothing was sent.
- Also: the collector was restarted at 02:12 so it loads the two burner jobs (burner-gulf-shops every 6 h, burner-us-shops every 8 h). Burner readers are the ones D-009 allows.

## D-011 Scraper upgrade: honest condition, sanity filters, full search, manual check  [ACTIVE]
- Date: 2026-10-07. Decided by: Claude on Zayed's ask ("Upgrade our scraper there is a lot info we are not gathering"). Small and reversible; no rule of Zayed's touched; nothing public.
- Condition: a shop that sells only new (list NEW_ONLY_SOURCES in egypt_deals/model.py) gets condition "new" when the title has no used/refurbished/renewed/open-box marker, and the row says condition_basis source_default. Marketplaces, classifieds and aggregators keep "unknown". Title words always win.
- Sanity: PSU under 1.5 EGP/W (300 W or more) and UPS under 1.5 EGP/VA (400 VA or more) are flagged "implausible" and never shown; "wanted/buying" ads (مطلوب, WTB, Buying) are flagged and never shown; storage under 64 GB on a PC or laptop is dropped and flagged; GPU memory and "PCIe 4.0" are no longer read as storage; camera/CCTV supplies and 12 V mini UPS units are not PC power gear.
- Old rows get these rules when read (Listing.refresh_on_read, called by Database.listings()); the database file is not rewritten.
- New tools: scripts/find.py (any model or keyword, full results) and scripts/check_listing.py (paste a listing found anywhere; it compares the price with stored data). Findings fold the same model sold by several stores into the cheapest row ("+N more stores").
- HTTP: a 429 now slows that host (2x, up to 8x), waits Retry-After (max 90 s) and retries twice before pausing it. Not a way around a block: 401/403 still pause the host.
- Not done, on purpose: the "40k bundle" comparison and the 292-page PDF come from an older Codex report, not from this code. Coverage gaps (Technology Valley, 2B, Raya pages never visited) need more detail passes, not code changes.
