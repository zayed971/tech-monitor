# Move Egypt Deals to your PC

The complete transfer includes the scraper, tests, documentation, a consistent
SQLite database snapshot, all runtime data, collection queues, price/alert history,
rules and the original stop deadline (October 27 at 01:17 Cairo time). Read
`TRANSFER-README.md` and `TRANSFER-MANIFEST.json` for the complete private package
and cloud handover status. The older reduced bundle is preserved unchanged in
`existing-packages/`. Databases do not synchronize after transfer.

## Windows

1. Extract the ZIP into an ordinary folder, such as `Documents\EgyptDeals`.
2. Install Python 3.11 or newer from python.org if needed, and Google Chrome.
3. Double-click `Setup-Windows.cmd` to install the scraper and browser support.
4. Double-click `Start-Monitor.cmd` for the retailer monitor. Keep its console
   open and the PC awake; it resumes the included inventory and history.
5. Double-click `Start-Marketplace.cmd` for a separate visible Chrome session.

The scripts do not install a background service or expose a browser-control
port. Closing the monitor or sleeping the PC interrupts collection. The local
launcher prevents a second collector from writing the same local database.

## macOS / Linux

In the extracted folder, run:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[browser]'
.venv/bin/python scripts/run-local.py
```

For Marketplace, run `.venv/bin/python scripts/local-marketplace.py`.
Google Chrome must be installed.

## Facebook Marketplace in local Chrome

The collector opens visible Chrome with its own profile in
`data/local-chrome-profile`. This can serve as the dedicated profile you wanted;
it does not attach to an already-open Chrome or copy another profile's cookies.
Sign in yourself in that window, set Marketplace to Mansoura/Egypt and confirm
prices are EGP. Press Enter in the console when the search page is ready.

It browses four used-PC/GPU/monitor searches by default and scrolls each search three
times, waiting five seconds between scrolls. You can specify other searches:

```text
Start-Marketplace.cmd --query "RTX 3060 12GB" --query "كيسة كمبيوتر"
Start-Marketplace.cmd --query "كيسة فاضية" --query "PC case"
```

On macOS/Linux, replace `Start-Marketplace.cmd` with
`.venv/bin/python scripts/local-marketplace.py`.

Results appear in `data/facebook-local/` as CSV/JSON: product title, displayed
price, URL, observed time and condition. Seller names/profiles, contacts,
messages, raw page HTML and cookies are not exported. Browser login data stays
in the local Chrome profile; do not share that folder.

Visible adverts are **availability-unconfirmed candidates**. They do not enter
the verified deal-alert database or silently become in-stock offers. A listed
price is an asking price, and a missing advert does not establish a sale.
Login/checkpoint prompts stop collection for owner attention. There is no
CAPTCHA bypass, stealth browser, account rotation or background GraphQL/API
harvest. Changing profiles does not remove Facebook's access restrictions.

Facebook extraction has parser tests, but live account/browser behavior must be
checked on your PC. Facebook may change its markup; a zero-result run is reported
as a gap rather than successful harvesting.

## Telegram handover

The complete private transfer includes the existing `.env` Telegram settings.
After the cloud handover recorded in the manifest, use
`Start-Monitor-With-Telegram.cmd` to resume sending. The older reduced bundle
excluded credentials. To change configuration, run `Set-Up-Telegram.cmd` on
Windows and enter your token locally at the hidden prompt. On macOS/Linux, use
`.venv/bin/python -m egypt_deals.cli telegram-setup`.

For a manifest that confirms cloud shutdown, enable local Telegram with
`Start-Monitor.cmd --send` (or add `--send` to the macOS/Linux launch command).
If using the older reduced package, stop the cloud sender before enabling local
Telegram. Running two independent senders can produce
duplicate alerts. The database snapshot preserves alert deduplication up to its
backup time; later cloud alerts are not part of that snapshot.

Running these scripts on your PC does not give this cloud conversation control
of your computer. For interactive local development, open the extracted folder
in a locally installed Codex client or editor; the cloud and local sessions are
separate.
