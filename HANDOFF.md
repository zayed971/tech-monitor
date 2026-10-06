# Local handoff

The user is shopping in Egypt, destination Mansoura, with a 70,000 EGP device
budget. Used hardware is welcome. Interests include Blender, AI, desktops and
PC builds, laptops, all separate components, and affordable sub-27-inch IPS
screens. Current monitor examples and verification timestamps are in
`data/small-screen-top10/`; used desktop candidates are in
`data/used-pc-candidates.json`. Most cheap used OEM PCs lack storage or a GPU;
do not describe them as ready for Blender/AI without checking the full build.

Read `LOCAL-PC.md` to install and run. The included database is a consistent
snapshot, with historical observations and alert deduplication. URL queues were
copied before the backup, so interrupted batches may safely revisit pages.
The original stopping deadline is October 27, 2026 at 01:17 Cairo time
(October 26 at 22:17 UTC). Do not reset it on restart.

Read `TRANSFER-MANIFEST.json` and `data/cloud-handoff.json` for the final cloud
shutdown and database snapshot. The complete private transfer preserves all
cached pages, ignored runtime data and the existing Telegram `.env` settings.
The older reduced package remains unchanged in `existing-packages/`. A local
copy does not synchronize with the cloud. `Start-Monitor-With-Telegram.cmd`
resumes alerts after the recorded cloud shutdown.

The stock parser recognizes full schema.org Product type URLs and scopes
availability to the main product, excluding recommendation cards. EgyptLaptop
stock was repaired from cached primary evidence; false in-stock labels and
their historical eligibility were corrected. Never replace missing stock with
"in stock." Pending Telegram alerts get an uncached primary/variant check.

The local Marketplace collector is owner-operated visible Chrome. The user
signs in and configures Mansoura/Egypt pricing locally. It saves product-card
candidates separately, with availability unknown and no seller/contact data.
It pauses on login/checkpoint prompts, without bypassing access restrictions.
Parser behavior is tested; live authenticated Facebook behavior has not been tested. The anonymous
cloud probe collected zero because robots.txt disallows Marketplace paths. Do not claim a successful Facebook harvest before checking a
local run's `data/facebook-local/latest-summary.json` and exported listings.

Known coverage gaps include Dubizzle HTTP 401, Amazon access errors, Pricena
rate limits, some robots-blocked URLs, Btech adapter failures, and pending or
limited catalog inventories. Inspect `data/hardware/coverage-and-gaps.json` and
source_runs in the database for current evidence. No full-Egypt market coverage
or verified used selling-price history has been established.
