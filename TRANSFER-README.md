# Complete Windows transfer

This private transfer preserves the full project, all tests and documentation,
the SQLite database and observation/alert/source-run history, generated reports,
all cached public pages, crawl inventories/checkpoints, logs and other ignored
runtime data. The existing Telegram configuration is included as `.env` so the
owner can resume alerts without re-entering credentials. Keep this package private.

The earlier Windows package is preserved unchanged at
`existing-packages/egypt-deals-local.zip`. The older cloud package is also retained
in that directory. Linux Python runtime files are archived at
`cloud-only/linux-python-runtime.tar.gz`; Windows setup creates a fresh `.venv`.

The cloud process is stopped only after a complete verified safety package
exists. The final transfer is refreshed again after shutdown to include the last
committed changes. `TRANSFER-MANIFEST.json` identifies that final state;
`data/cloud-handoff.json` records the shutdown. The original monitoring stop
deadline remains October 27, 2026 at 01:17 Cairo time (October 26 at 22:17 UTC).

## Start on Windows

1. Install Python 3.11 or newer. Extract the ZIP into a writable folder with
   enough free space for approximately 12 GB of project data.
2. Optionally run `Verify-Transfer.cmd` before making changes. It checks every
   file hash and SQLite integrity and can take several minutes for the cache.
3. Run `Setup-Windows.cmd`. It needs internet to install Windows dependencies.
4. Run `Start-Monitor-With-Telegram.cmd` to resume retailer monitoring and
   Telegram alerts. Use `Start-Monitor.cmd` to monitor without sending alerts.
5. Keep the console open and the PC awake. These scripts do not install a
   background Windows service. The copied databases do not synchronize.

Run `.venv\Scripts\python.exe -m pytest -q` in the extracted project to run tests.
The project was checked in Linux; Windows launchers still need a local run.

## Current Facebook result

The public cloud Marketplace probe collected zero listings because Facebook's
robots rules disallow the requested paths. It is recorded in the source coverage
report and will recheck at most daily. No Facebook login/profile is supplied.
`Start-Marketplace.cmd` is a separate optional visible local Chrome collector;
read `LOCAL-PC.md` before using it. It is not part of the automatic retailer
loop and has not been tested with a live Facebook account. Product cards remain
availability-unconfirmed candidates, never automatic stock-confirmed alerts.

## What resumes

The local loop retains the 70,000 EGP buying budget, collection without a price
ceiling, configured source intervals, inventory rotation, database history and
alert deduplication. Running crawl batches at cloud shutdown are marked as
interrupted; their uncommitted tail may be fetched again. Existing shortlist
files remain dated evidence, not a new live stock guarantee.
