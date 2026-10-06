"""Read US shops through the already-running burner Chrome (port 9222), slowly, read only (decision D-009).

  python scripts/run_burner_us.py                              # every site, the default queries
  python scripts/run_burner_us.py --source br_us_ebay --source br_us_bh --query "RTX 3090" --max-items 60

One site after another (one browser, our own tab, closed after each site), at least 6 s between page loads of a site
(default 7). A CAPTCHA, challenge or block page ends that site's run and is recorded as a wall; nothing is retried or worked
around. Start the burner Chrome first (ZAYED-AI\\browser\\launch-agent-chrome.ps1).
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from egypt_deals import burner_retail_us as br, zones  # noqa: E402
from egypt_deals.storage import Database  # noqa: E402

DEFAULT_QUERIES = [
    'RTX 3060 12GB', 'RTX 4070 Super', 'RTX 3090', 'RTX 4060 Ti 16GB', 'RTX 4080', 'laptop RTX 4060', 'laptop RTX 4070',
    'DDR5 32GB kit', 'DDR4 32GB kit', 'NVMe 2TB', 'NVMe 1TB', '27 inch IPS monitor', '27 inch 4K monitor',
]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', action='append', default=[], help='source id (repeatable) or "all"; ids: ' + ', '.join(br.SOURCES))
    ap.add_argument('--query', action='append', default=[], help='search term (repeatable); default is ~13 tech terms')
    ap.add_argument('--max-items', type=int, default=200, help='listings kept per site')
    ap.add_argument('--delay', type=float, default=7.0, help='seconds between page loads of one site (minimum 6)')
    ap.add_argument('--root', default=str(ROOT), help='project root (data/deals.sqlite3 lives under it)')
    ap.add_argument('--rate', type=float, help='USD to EGP; default is references.json, else 52')
    ap.add_argument('--cdp', default=br.CDP_URL)
    ap.add_argument('--no-save', action='store_true', help='print only, do not write the database')
    args = ap.parse_args(argv)

    ids = list(br.SOURCES) if (not args.source or 'all' in args.source) else args.source
    unknown = [i for i in ids if i not in br.SOURCES]
    if unknown: ap.error('unknown source: ' + ', '.join(unknown))
    queries = args.query or DEFAULT_QUERIES
    root = Path(args.root)
    rate = args.rate or zones.usd_egp(root) or 52.0
    delay = max(6.0, args.delay)
    db = None if args.no_save else Database(root / 'data' / 'deals.sqlite3')

    total = 0
    for n, source_id in enumerate(ids):
        if n: time.sleep(delay)
        listings, status = br.collect(source_id, queries, root=root, rate_usd_egp=rate, max_items=args.max_items, cdp=args.cdp, delay=delay)
        if db: db.save(listings, status)
        total += len(listings)
        wall = f"  WALL: {status['walls'][0]['reason']}" if status.get('walls') else ''
        print(f"{source_id:18} {status['verdict']:21} parsed={status['parsed']:<4} kept={status['kept']:<4} loads={status['requests']}{wall}", flush=True)
        if status['verdict'] == 'needs_burner_browser':
            print('  ' + status['evidence']); break
    print(f'{total} listings from {len(ids)} sites at {rate} EGP/USD' + ('' if db else ' (not saved)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
