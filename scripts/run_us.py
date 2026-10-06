"""Collect US store/marketplace prices (zone US) and save them.

  python scripts/run_us.py --source all
  python scripts/run_us.py --source us_wisetek --source us_techmikeny --queries-file my_terms.txt --max-items 100

One thread per source (hosts are different), at most 4 at a time; each source has its own polite client
(delay >= 2 s per host, robots.txt honoured). Blocked sites are recorded as blocked, never worked around.
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from egypt_deals import global_us, zones  # noqa: E402
from egypt_deals.http import Client  # noqa: E402
from egypt_deals.storage import Database  # noqa: E402

DEFAULT_QUERIES = [
    'RTX 3060 12GB', 'RTX 4070 Super', 'RTX 4070 Ti Super', 'RTX 3090', 'RTX 4060 Ti 16GB', 'RTX 4080', 'RTX 3080 Ti',
    'RTX A4000', 'RTX 5070', 'laptop RTX 4060', 'laptop RTX 4070', 'laptop RTX 3070', 'RTX gaming laptop 32GB',
    'workstation laptop RTX', 'gaming PC RTX', 'desktop RTX 4070', 'DDR5 32GB kit', 'DDR4 32GB kit', '64GB DDR5',
    'NVMe 2TB', 'NVMe 1TB', 'SSD 2TB', '27 inch IPS monitor', '27 inch 4K monitor', '32 inch monitor',
]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', action='append', default=[], help='source id (repeatable) or "all"; ids: ' + ', '.join(global_us.SOURCES))
    ap.add_argument('--queries-file', help='text file, one search term per line')
    ap.add_argument('--max-items', type=int, default=200, help='listings kept per source')
    ap.add_argument('--delay', type=float, default=3.0, help='seconds between requests to one host (minimum 2)')
    ap.add_argument('--root', default=str(ROOT), help='project root (data/deals.sqlite3 lives under it)')
    ap.add_argument('--rate', type=float, help='USD to EGP; default is references.json, else 52')
    ap.add_argument('--no-save', action='store_true', help='print only, do not write the database')
    ap.add_argument('--workers', type=int, default=4)
    args = ap.parse_args(argv)

    ids = list(global_us.SOURCES) if (not args.source or 'all' in args.source) else args.source
    unknown = [i for i in ids if i not in global_us.SOURCES]
    if unknown: ap.error('unknown source: ' + ', '.join(unknown))
    queries = DEFAULT_QUERIES
    if args.queries_file:
        queries = [x.strip() for x in Path(args.queries_file).read_text(encoding='utf-8').splitlines() if x.strip() and not x.startswith('#')]
    root = Path(args.root)
    rate = args.rate or zones.usd_egp(root) or 52.0
    delay = max(2.0, args.delay)
    db = None if args.no_save else Database(root / 'data' / 'deals.sqlite3')

    def job(source_id):
        client = Client(root / 'data' / 'cache' / 'us', delay=delay)
        try:
            return source_id, global_us.collect(source_id, queries, root=root, rate_usd_egp=rate, max_items=args.max_items, client=client, delay=delay)
        finally:
            client.close()

    results = {}
    with ThreadPoolExecutor(max_workers=max(1, min(4, args.workers))) as pool:
        for future in as_completed([pool.submit(job, i) for i in ids]):
            source_id, (listings, status) = future.result()
            results[source_id] = (listings, status)
            if db: db.save(listings, status)   # saved here, in the main thread
            print(f"{source_id:24} {status['verdict']:21} parsed={status['parsed']:<5} kept={status['kept']:<4} requests={status['requests']}  {status['evidence'][:110]}", flush=True)
    total = sum(len(v[0]) for v in results.values())
    print(f'{total} listings from {len(results)} sources at {rate} EGP/USD' + ('' if db else ' (not saved)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
