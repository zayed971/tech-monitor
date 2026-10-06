"""Read Gulf and Egypt shops through the burner Chrome (port 9222) into data/deals.sqlite3. Read only, slow, own tab.

  python scripts/run_burner_gulf.py                       (all 10 sites, default queries)
  python scripts/run_burner_gulf.py --source br_noon_ae --source br_jumbo --query "RTX 3060 12GB" --max-items 30

Launch the burner Chrome first (the launch-agent-chrome.ps1 script in ZAYED-AI browser). Sites run one after another. At least
6 seconds pass between page loads on one site (--delay below 6 is raised to 6). A CAPTCHA, challenge or block page
ends that site (recorded as state 'wall') and the run moves on. No logins, no CAPTCHA solving.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from egypt_deals import burner_retail_gulf as B  # noqa: E402
from egypt_deals.storage import Database  # noqa: E402
from egypt_deals.zones import usd_egp  # noqa: E402

DEFAULT_QUERIES = [
    'RTX 3060 12GB', 'RTX 3070', 'RTX 3090', 'RTX 4070', 'RTX 4070 Super', 'RTX 4060 Ti 16GB', 'gaming laptop RTX',
    'DDR5 32GB', 'DDR4 32GB', 'NVMe 2TB SSD', 'Ryzen 7 7700', 'used gaming PC',
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', action='append', help='source id (repeatable) or all; ids: ' + ', '.join(B.SOURCES))
    ap.add_argument('--query', action='append', help='search term (repeatable); default ~12 tech queries')
    ap.add_argument('--max-items', type=int, default=60, help='cap on listings per site')
    ap.add_argument('--delay', type=float, default=7.0, help='seconds between page loads on one site (minimum 6)')
    ap.add_argument('--cdp', default='http://127.0.0.1:9222')
    ap.add_argument('--no-save', action='store_true', help='print only, do not write the database')
    args = ap.parse_args()
    wanted = list(B.SOURCES) if not args.source or 'all' in args.source else args.source
    unknown = [s for s in wanted if s not in B.SOURCES]
    if unknown: ap.error('unknown source(s): ' + ', '.join(unknown))
    queries = args.query or DEFAULT_QUERIES
    rate = usd_egp(ROOT)
    if rate is None: print('warning: no dollar rate in references.json; EGP prices will be empty', file=sys.stderr)
    db = None if args.no_save else Database(ROOT / 'data' / 'deals.sqlite3')
    for source_id in wanted:
        listings, status = B.collect(source_id, queries, root=ROOT, rate_usd_egp=rate, max_items=args.max_items,
                                     cdp=args.cdp, delay=args.delay)
        if db: db.save(listings, status)
        print(f"{source_id:15} {status['state']:14} listings={status['listings']:3} pages={status['pages_fetched']} "
              f"{(status['evidence'] or '')[:100]} {status['errors'][:1] or ''}", flush=True)


if __name__ == '__main__':
    main()
