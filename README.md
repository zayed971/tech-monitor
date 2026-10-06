# Egyptian laptop and PC deal scraper

This HTTP scraper collects Egyptian laptops, complete PCs, build bundles and separate hardware components. It records SQLite price observations, exports CSV/JSON, evaluates five product thresholds plus the 24-hour drop rule, and sends Telegram alerts when configured. See **data/hardware/report.md** for current hardware counts and RAM prices, **data/hardware/coverage-and-gaps.json** for source coverage and pending URLs, and **coverage.json** for deferred sources and fields. Collection has no price ceiling; buying alerts retain the 70,000 EGP ceiling. Coverage is measured against configured public sources, not every store in Egypt.

## Run

```bash
cd /workspace/egypt-deals
python -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/egypt-deals run
.venv/bin/pytest -q
```

Examples:

```bash
# A narrow collection, still subject to robots.txt and rate limits
.venv/bin/egypt-deals run --sources qarenly,compumarts,ennap,elbadr --max-pages 4
# Increase feed coverage (more requests and time)
.venv/bin/egypt-deals run --sources compumarts,kimo --max-pages 12
# Export existing data without another network collection
.venv/bin/egypt-deals export
# Refresh a sourced USD/EGP baseline
.venv/bin/egypt-deals fx
# Broad, fresh catalog collection (variants still remain explicit)
.venv/bin/egypt-deals run --scope catalog --max-pages 30 --cache-ttl 0
# Every recognized laptop in each fetched feed; Sigma language pages are deduplicated
.venv/bin/egypt-deals run --scope laptops --max-pages 100 --max-details 200
# All hardware; complete available feeds and rotate through discovered product URLs
.venv/bin/egypt-deals run --scope hardware --max-pages 150 --max-details 100 --cache-ttl 0
```

The default is four catalogue/search pages and eight detail pages per source with the narrow `tracked` scope. Shopify pages contain up to 250 products; WooCommerce pages up to 100. Use `--scope hardware` for all components and computer builds. Dedicated retailer feeds retain their full catalogues; hardware exports then exclude recognized phones and household electronics. Sitemap discovery follows product indexes and persists an inventory in `data/harvest-state/`. Each batch visits never-attempted URLs first, then the oldest attempted URLs. Interrupted detail batches checkpoint collected rows. Empty extraction, access failures and queued URLs are reported separately. Hardware URL filters on general marketplaces may miss opaque product slugs; those exclusions are counted.

`--scope catalog` retains the broader retailer catalogs, including accessories and other electronics. The October 5 expanded run fetched every counted record afresh: **22,218 unique priced retailer products**, including **10,558 marked in stock**. The counts collapse Shopify variants and exclude aggregator records, placeholders and prices below 100 EGP. See `data/catalog-counts.json`, `data/run-manifest.json`, `data/current-products.csv` and `data/in-stock-products.csv`. The broader database retains explicit variants and old observations separately. Repeated pagination cannot inflate the count. Compumarts and Alfrensia reached the chosen page cap; no full-market coverage is claimed.

## Files

| File | Purpose |
| --- | --- |
| `sources.json` | Source URL, adapter and polling interval |
| `rules.json` | Five thresholds and the 8% drop rule |
| `references.json` | Exact-MPN specs/benchmarks and exchange-rate evidence |
| `coverage.json` | Explicit source and feature limits |
| `data/deals.sqlite3` | Listings, observations, source runs and alert outbox |
| `data/listings.csv`, `data/listings.json` | Collected data and computed metrics |
| `data/comparisons.json` | Exact-MPN comparisons with known configurations separated |
| `data/alerts.json` | Current rule matches; `new` indicates a newly queued alert |
| `data/report.md` | Readable results and source health |
| `data/run-manifest.json` | Fresh collection start/end, scope, and counts excluding old/cache-only observations |
| `data/current-products.csv` | Lightweight unique store/product export for the expanded run |
| `data/in-stock-products.csv` | The unique products whose fresh feed reports an in-stock priced variant |
| `data/import-comparison.md` | Import feasibility, sources and all-in break-even thresholds |
| `data/laptop-review/all-under-70000.csv` | Every collected retailer laptop under the active 70,000 EGP ceiling, with stock and verification fields |
| `data/laptop-review/summary.json` | Laptop counts with variants and translated Sigma URLs separated |
| `data/hardware/all-hardware.csv` | Hardware variants across all stock states, with price and verification fields |
| `data/hardware/pc-builds-and-bundles.csv` | Complete PCs and bundles; a bundle is not assumed to contain every component |
| `data/hardware/separate-components.csv` | CPUs, GPUs, motherboards, RAM, SSDs/HDDs, PSUs, cases, coolers, UPSs and peripherals |
| `data/hardware/ram-prices-by-brand.csv` | RAM grouped by brand, DDR generation, capacity, form, module count, speed, CAS and ECC |
| `data/hardware/ram-capacity-overview.csv` | Lowest observed new in-stock 8/16/32/64GB prices, with unknown configurations kept separate |
| `data/hardware/unpriced-or-unverified.csv` | Listings excluded from verified price floors and buying alerts |
| `data/hardware/coverage-and-gaps.json` | Per-source results, missing prices/stock, pending inventory and explicit collection gaps |
| `data/hardware/accessories-and-tech.csv` | PC/laptop accessories, peripherals, audio, gaming/VR, creator gear, maker tools, smart-home devices, wearables, tablets and e-readers |
| `data/hardware/accessories-by-type-and-brand.csv` | Accessory types and brands with counts and lowest observed eligible prices; different models remain distinct in the offer export |
| `data/harvest-state/` | Persistent URL queues and per-product extraction failures |

## Telegram

Create a bot with Telegram's BotFather and start a conversation with it. Obtain your own chat ID, then place credentials in `.env` using the template `.env.example`; keep `.env` private. The CLI reads environment variables, while `scripts/run-once.sh` loads `.env`. Never commit credentials or put them into tracked configuration.

The guided command can now discover the chat ID and send a connection test:

```bash
cd /workspace/egypt-deals
.venv/bin/egypt-deals telegram-setup
```

It reads `TELEGRAM_BOT_TOKEN` from the environment (cloud secret settings) or `.env`. If neither exists, it prompts with hidden input. Press **Start** in your own bot first. If several private chats appear, it asks which ID is yours; names and message bodies are not logged. It saves the chat ID in a mode-600 `.env` file and sends a test to that chat. Later CLI commands load only the two Telegram settings from `.env` as data; shell expressions in that file are not executed. The bot does not provide access to your general Telegram account or personal chat history. [Telegram's official setup tutorial](https://core.telegram.org/bots/tutorial).

```bash
cp .env.example .env
chmod 600 .env
# Edit .env locally, then:
bash scripts/run-once.sh
```

`--send` enables delivery. `egypt-deals notify` also sends pending alerts if environment variables are already exported. Every queued alert gets an uncached primary-product stock check before delivery; Shopify checks the exact variant. Sold-out, preorder, unknown or failed checks suppress the alert, and a changed price expires the old message. Product-page availability is scoped to the main product; recommended items cannot supply stock for it. Requests avoid printing the bot token on errors. Missing credentials leave valid alerts queued. Duplicate rule/listing/price alerts are sent once; stale or no-longer-eligible queued entries expire. A changed price can alert again at the new price, and an expired alert may be queued again if it becomes valid. This is persistent price-level deduplication, not a daily reminder. Shipping is shown when available but thresholds use the advertised item price.

The laptop budget is now 70,000 EGP. The LOQ i7-14700HX/RTX 5060 threshold uses that ceiling, and `laptop_watch` extends the 8%/24h drop rule to all eligible collected laptops under the ceiling. Each export refreshes the full under-budget CSV and summary when `data/laptop-search.json` exists. The ceiling covers advertised laptop prices; RAM upgrades, delivery and Windows licensing must be checked separately. The expanded review reached the ends of the eight configured feeds and discovered 137 distinct Sigma laptop products. Recognized laptop names are separated from replacement parts and accessories; unknown specs remain unknown.

The initial catalog run had no Telegram credentials. The current connection and delivery state is recorded in `data/telegram-status.json`; it never includes the token or private message bodies.

`hardware_watch` extends the 8%/24h drop rule to eligible desktops and separate components under 70,000 EGP. RAM price tables exclude prices explicitly available only inside a build, unknown stock, placeholders and contradictory listings. A listed 32GB price can represent one stick or a kit: the module count stays unknown unless stated. No PSU quality tier, warranty or missing compatibility fact is guessed.

The accessory harvest also includes hubs/docks/KVMs, cables, chargers, power banks, stands, bags, monitor arms, mouse pads, keycaps, maintenance tools, storage enclosures, audio, gaming/VR, drawing tablets, streaming equipment and maker hardware. Where available, smart-home gadgets, wearables, tablets and e-readers are retained. Ordinary phones and household appliances remain outside this scope. `accessory_type` gives a more detailed classification. These categories use the same verified 8%/24h drop alerts and 70,000 EGP buying budget, with no collection price ceiling. General marketplace discovery still filters public titles/URLs; opaque URLs, unavailable sources and missing compatibility remain coverage gaps.

## Scheduling and the three-week limit

The repository has a runnable scheduler, but creating the project does not make a remote session an always-on server. No scheduler is installed or running by default. Use a continuously running VM/container for unattended monitoring.

```bash
# Foreground scheduler; stop with Ctrl-C. With exported Telegram variables:
.venv/bin/egypt-deals watch --scope hardware --max-pages 150 --max-details 100 --cache-ttl 0 --send --days 21 --bootstrap --poll-seconds 60
```

The first watch invocation writes a durable start/deadline in `data/watch.json`; restarting does not reset the 21-day horizon. Sources are interval-gated: full feeds and aggregators every 24 hours, Kimo every four hours, Dubizzle every three hours. Unattempted sitemap URLs get another batch at the next cycle; after initial coverage, URL batches rotate to spread rechecks across the source interval. Access-blocked sources keep their longer retry interval. The scheduler checks every 60 seconds between collection cycles; a cycle can take longer while requests finish. `--bootstrap` forces all configured sources on the first cycle only; omit it when resuming an existing monitor. The process stops at the deadline and does not buy anything.

For a bot whose token is configured but whose owner has not pressed Start yet:

```bash
flock -n -F data/monitor.lock .venv/bin/python scripts/connect-and-watch.py
```

This checks for the owner's first private message every 15 seconds, sends a connection test and valid queued alerts, and starts hardware monitoring with 150-page limits, rotating detail batches and a four-second request delay. Multiple private chats require manual identification. The 21-day deadline begins when this launcher starts and does not reset on restarts. `data/watch-status.json` records the latest monitor check. The cloud workspace must stay running; this is not a separately deployed always-on service. Idle checks preserve the last collection's data and manifest.

Alternatively, run `bash /workspace/egypt-deals/scripts/run-once.sh` hourly from your server's cron. `--due` enforces per-source intervals, but cron does **not** implement the watch command's 21-day deadline. Use `flock` around cron jobs to prevent overlapping writers. Do not run two collectors against the same database concurrently.

## Evidence and safeguards

- Robots rules include wildcard paths, end anchors and repeated agent groups. Robots retrieval fails closed on access failures. Redirect destinations are checked too.
- Requests wait at least four seconds per host by default, honor longer crawl delays, and use a 30-minute cache. Rate-limit/access failures pause that host for the client. No CAPTCHA bypass or stealth browser is used.
- Cached pages retain their original observation time, so rereading the cache cannot refresh an old price.
- Only explicit in-stock, EGP, non-placeholder listings with a retailer observation no older than seven days can alert. Aggregator-only entries cannot alert without retailer verification and a recent update date. Direct observations verify what a retailer currently advertises; a page modification date does not guarantee the price itself changed.
- Product thresholds require the requested model/CPU/GPU or RAM configuration. A Legion 15IRX10 is not a LOQ 15IRX10. An RTX 3060 8GB is not a 12GB card. Unknown kit sizes and form factors cannot match strict RAM rules.
- Recognized Kingston kit part-number/title contradictions are flagged and excluded. This is a targeted check, not a full product-consistency engine.
- Cross-store comparisons use exact MPNs and matching known configuration/condition, never fuzzy titles or store SKUs. Missing storage facts can still conceal upgrades: confirm the retailer's complete configuration before buying.
- Qarenly verification follows the primary "Go to site" link for a bounded set of tracked candidates. It fetches only already configured retailer hosts and extracts the retailer's own title/price/specs. Similar-product links and grouped aggregate-offer prices are not transferred onto the primary product's hardware specs.
- Personal sellers are not collected. Used HTML is not cached, seller identity fields are dropped, and obvious contact details are removed from descriptions. The Dubizzle adapter currently requires structured product data and its live request returned 401; no used-market coverage is claimed.
- No historical low predating the first run is fabricated. Every low includes observation count and coverage dates. Disappearance of an advert cannot tell us what the buyer paid, or even establish a sale.
- LHR/import/mining strings are review signals, not proof of a bad item. Region suffixes alone do not establish official local warranty. RAM-slot count alone does not establish maximum supported memory capacity.
- Detailed laptop/desktop spec fields are available and exported as null until known. Shipping, quantity, warranty and installment fields are not universally supported by feed adapters.

## Exact-part-number reference data

Populate `references.json` with verified facts, not estimates. References are applied only when a listing has that exact MPN, with a source URL and a `checked_at` date within 35 days. Example format (replace the example key/date and null values with verified evidence):

```json
{
  "products": {
    "EXACT_MPN": {
      "source_url": "https://psref.lenovo.com/verified-model-page",
      "checked_at": "2026-10-05T00:00:00+00:00",
      "specs": {
        "gpu_tgp_w": null,
        "ram_slots": null,
        "ram_modules": null,
        "ram_soldered": null,
        "ram_max_gb": null
      },
      "blender_score": null,
      "cpu_multi_score": null,
      "cpu_single_score": null,
      "us_price_usd": null
    }
  },
  "fx": {"usd_egp": null, "source_url": null, "checked_at": null}
}
```

Recollect after updating references. Benchmark metrics are EGP per point (lower is better), with the benchmark source and version requiring your reference evidence. RAM cost to 32GB requires known replaceable slot layout, a supported maximum, and a fresh compatible 16GB DDR5 SODIMM price. It is a parts-cost estimate excluding installation and resale of removed RAM; speed/vendor compatibility still needs confirmation. Import premium is a currency comparison, excluding shipping, tax, customs and warranty differences. Store risk scoring, review APIs, automatic benchmark/spec ingestion and used-listing survival analysis remain deferred.

The optional `fx` command uses [ExchangeRate-API's open access feed](https://www.exchangerate-api.com/), stores the provider's quote timestamp and rejects quotes older than seven days. Its daily rate is a baseline, not a guaranteed bank execution rate.

For a real import comparison, copy `import-quote.example.json`, fill in the final checkout item/shipping/import-charge figures and your payment conversion costs, and run:

```bash
.venv/bin/egypt-deals import-check --quote-file my-quote.json
```

Unknown shipping or import charges yield `incomplete_quote`, not a free-shipping assumption. The formula avoids adding VAT again when it is already covered by the checkout import line. Do not put payment-card, account or full-address data in the quote file.

## Adding a source

Adapters exist for Shopify, WooCommerce Store API, JSON-LD product pages, Qarenly, EGPrices embedded data, HTML product discovery and indexed product sitemaps. There are 23 configured sources, including a bounded public Facebook Marketplace probe. An adapter being configured does not guarantee a site's markup is supported; check source status and compare a sample with the actual page. Supply Smart Technology's precise URL before adding it. Amazon/Noon get only a small daily public sample, with robots and access failures recorded; aggregator coverage is not treated as verified marketplace inventory.

For reference sites, use their published interfaces and terms. For review sources requiring an API, use the official API with your credentials. The cloud HTTP monitor excludes scraped Google Maps reviews. At the owner's request, it now checks public Egypt Facebook Marketplace searches at most daily, stops on the first access/robots failure, and records the gap. The 2026-10-06 cloud test collected zero listings because robots.txt disallows Marketplace paths; it did not request those disallowed pages. The adapter only accepts explicit EGP hardware cards if public access becomes available, and leaves their stock unconfirmed. It does not use an authenticated Facebook session. An optional owner-operated local Chrome collector reads visible Marketplace product cards into separate, availability-unconfirmed candidate files; see `LOCAL-PC.md`. It exports no contacts, seller profiles, messages or browser credentials.
