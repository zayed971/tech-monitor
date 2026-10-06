"""Read-only Facebook Marketplace collection through the burner Chrome (port 9222). See egypt_deals/facebook_burner.py."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from egypt_deals.facebook_burner import DEFAULT_QUERIES, collect  # noqa: E402
from egypt_deals.storage import Database  # noqa: E402
from egypt_deals.zones import usd_egp  # noqa: E402

CITIES = {'EG': 'mansoura', 'UAE': 'dubai', 'KSA': 'riyadh', 'US': 'newyork'}


def main():
    ap = argparse.ArgumentParser(description='Collect visible Marketplace cards via the burner Chrome (read only)')
    ap.add_argument('--zone', choices=sorted(CITIES), default='EG')
    ap.add_argument('--city', help='Marketplace city slug (default per zone)')
    ap.add_argument('--query', action='append', help='repeat; default is a built-in tech list')
    ap.add_argument('--scrolls', type=int, default=2)
    ap.add_argument('--delay', type=float, default=8)
    ap.add_argument('--no-save', action='store_true')
    a = ap.parse_args()
    if a.delay < 6: ap.error('delay must be at least 6 seconds')
    listings, status = collect(a.zone, a.city or CITIES[a.zone], a.query or DEFAULT_QUERIES, scrolls=a.scrolls,
                               delay=a.delay, rate_usd_egp=usd_egp(ROOT))
    if not a.no_save:
        Database(ROOT / 'data/deals.sqlite3').save(listings, status)
    print(json.dumps(status, ensure_ascii=False))


if __name__ == '__main__': main()
