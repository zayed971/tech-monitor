"""Collect UAE and Saudi prices into data/deals.sqlite3.

  python scripts/run_uae_ksa.py --source all
  python scripts/run_uae_ksa.py --source amazon_ae --source haraj_sa --max-items 40 --delay 3
  python scripts/run_uae_ksa.py --source all --queries-file my_queries.txt   (one search term per line)

Different hosts run in parallel (max 4 workers); sources on the same host run one after another.
Every host waits at least 2 seconds between requests and obeys robots.txt (egypt_deals.http.Client).
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from egypt_deals import global_uae_ksa as G  # noqa: E402
from egypt_deals.http import Client  # noqa: E402
from egypt_deals.storage import Database  # noqa: E402
from egypt_deals.zones import usd_egp  # noqa: E402

DEFAULT_QUERIES = [
    'RTX 3060 12GB', 'RTX 3070', 'RTX 3080', 'RTX 3090', 'RTX 4060 Ti 16GB', 'RTX 4070', 'RTX 4070 Super',
    'RTX 4080', 'RTX 4090', 'RTX 5070', 'RX 7900 XT', 'laptop RTX 4060', 'laptop RTX 4070', 'laptop RTX 4050',
    'gaming laptop 32GB RAM', 'DDR5 32GB', 'DDR4 32GB kit', 'NVMe 2TB', 'NVMe 1TB SSD', 'Ryzen 7 7700',
    'Ryzen 9 7900X', '27 inch IPS monitor', '27 inch 4K monitor', 'used gaming PC', 'used RTX GPU', 'MacBook Pro M3',
]


def run_host(host_sources, queries, args, rate):
    client = Client(ROOT / 'data' / 'cache_uae_ksa', delay=max(2.0, args.delay), ttl=1800)
    db = Database(ROOT / 'data' / 'deals.sqlite3')
    out = []
    try:
        for source_id in host_sources:
            listings, status = G.collect(source_id, queries, root=ROOT, rate_usd_egp=rate,
                                         max_items=args.max_items, client=client)
            db.save(listings, status)
            out.append(status)
            print(f"{source_id:12} {status['state']:15} listings={status['listings']:3} pages={status['pages_fetched']} "
                  f"{(status['evidence'] or '')[:90]}", flush=True)
    finally:
        client.close()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', action='append', help='source id (repeatable) or all; ids: ' + ', '.join(G.SOURCES))
    ap.add_argument('--queries-file', help='text file, one search term per line')
    ap.add_argument('--max-items', type=int, default=60, help='cap on listings per source')
    ap.add_argument('--delay', type=float, default=2.5, help='seconds between requests to one host (minimum 2)')
    args = ap.parse_args()
    wanted = list(G.SOURCES) if not args.source or 'all' in args.source else args.source
    unknown = [s for s in wanted if s not in G.SOURCES]
    if unknown: ap.error('unknown source(s): ' + ', '.join(unknown))
    queries = DEFAULT_QUERIES
    if args.queries_file:
        queries = [x.strip() for x in Path(args.queries_file).read_text(encoding='utf-8').splitlines() if x.strip()]
    rate = usd_egp(ROOT)
    if rate is None: print('warning: no dollar rate in references.json; EGP prices will be empty', file=sys.stderr)
    groups = {}
    for source_id in wanted: groups.setdefault(G.SOURCES[source_id]['base'], []).append(source_id)
    with ThreadPoolExecutor(max_workers=min(4, len(groups))) as pool:
        for future in [pool.submit(run_host, g, queries, args, rate) for g in groups.values()]: future.result()


if __name__ == '__main__':
    main()
