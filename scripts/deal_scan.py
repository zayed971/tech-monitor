r"""Stage 1 of the deal hunt (no money, no network): pick the rows worth a second look from the whole collection.

    .venv\Scripts\python.exe scripts\deal_scan.py [--max-age-hours 96] [--limit 1500] [--out data\deal_scan\shortlist.jsonl]

Signals (a row can have several; every number is from the stored data):
  markdown  the page's own old price is at least 30% above the current price (EG shops)
  cheap_vs_peers  same model, 3+ offers in the zone, this one is at least 20% under the median of the others
  cheap_vs_abroad  new abroad is at least 40% under the Egyptian median for the same model (landed cost unconfirmed)
  dropped   price fell at least 12% from its highest stored price in the last 14 days
  used_vs_new  used/refurbished ad at least 35% under the new Egyptian median of the same model
Model identity = model codes plus capacity, pack size and screen size from the title (SN850X+1tb is not SN850X+2tb), see findings.model_tokens.
"""
import argparse
import collections
import json
import re
import sqlite3
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from egypt_deals import findings  # noqa: E402

CATS = {'ssd', 'hdd', 'monitor', 'peripheral', 'accessory', 'audio', 'gaming', 'creator', 'maker', 'smart_home', 'network',
        'psu', 'ups', 'cpu', 'motherboard', 'cooler', 'case', 'tablet', 'wearable', 'ereader'}
USED_SRC = ('haraj', 'opensooq', 'facebook', 'dubizzle', 'br_dubizzle', 'us_reddit', 'br_us_ebay', 'br_us_backmarket')


def model_tokens(l):
    return findings.model_tokens(l.raw_title)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-age-hours', type=float, default=96)
    ap.add_argument('--limit', type=int, default=1500)
    ap.add_argument('--cats', help='comma list; default = SSD, monitors, peripherals, accessories, gadgets, network, power, parts')
    ap.add_argument('--out', default=str(root / 'data' / 'deal_scan' / 'shortlist.jsonl'))
    a = ap.parse_args()
    cats = set(a.cats.split(',')) if a.cats else CATS
    rows = [l for l in findings.load(root) if l.category in cats and findings.usable(l, a.max_age_hours) and l.price_egp >= 400]
    print(len(rows), 'fresh usable rows in scope')
    by_model = collections.defaultdict(list)
    for l in rows:
        k = model_tokens(l)
        if k: by_model[(l.category, k)].append(l)
    # price history: highest price in the last 14 days per listing
    db = sqlite3.connect(f'file:{root / "data" / "deals.sqlite3"}?mode=ro', uri=True)
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    hist = collections.defaultdict(list)
    for lid, price in db.execute('SELECT listing_id, price FROM observations WHERE observed_at>=? AND price>0', (since,)):
        hist[lid].append(price)
    found = {}

    def add(l, signal, ref, note):
        d = found.setdefault(l.identity, dict(id=l.identity, zone=l.zone, store=l.store, source=l.source, category=l.category,
                                              title=l.raw_title[:140], condition=l.condition, basis=l.condition_basis, stock=findings.stock_label(l),
                                              price_egp=round(l.price_egp), price_local=l.price_local, currency=l.currency,
                                              age_h=findings.age_hours(l), url=l.url, signals=[], score=0.0))
        d['signals'].append(f'{signal}: {note}')
        d['score'] = max(d['score'], round(1 - l.price_egp / ref, 3))

    for l in rows:
        if l.zone == 'EG' and l.old_price_egp and l.price_egp <= 0.7 * l.old_price_egp and l.source_kind != 'used':
            add(l, 'markdown', l.old_price_egp, f'was {l.old_price_egp:,.0f}')
        h = hist.get(l.identity, [])
        if len(h) >= 2 and l.price_egp <= 0.88 * max(h): add(l, 'dropped', max(h), f'high {max(h):,.0f} in 14 days')
    for (cat, k), group in by_model.items():
        eg_new = [x for x in group if x.zone == 'EG' and x.condition in ('new',) and x.source_kind != 'aggregator']
        eg_med = statistics.median(x.price_egp for x in eg_new) if len(eg_new) >= 2 else None
        zone_new = collections.defaultdict(list)
        for x in group:
            if x.condition == 'new': zone_new[x.zone].append(x)
        for z, g in zone_new.items():
            if len(g) >= 3:
                for x in g:
                    others = [y.price_egp for y in g if y is not x]
                    m = statistics.median(others)
                    if x.price_egp <= 0.8 * m: add(x, 'cheap_vs_peers', m, f'median of {len(others)} other offers {m:,.0f}')
        if eg_med:
            for x in group:
                if x.zone != 'EG' and x.condition == 'new' and x.price_egp <= 0.6 * eg_med:
                    add(x, 'cheap_vs_abroad', eg_med, f'Egypt median {eg_med:,.0f} ({len(eg_new)} shops); landed unconfirmed')
                if x.condition in ('used', 'refurbished', 'open_box') and x.price_egp <= 0.65 * eg_med:
                    add(x, 'used_vs_new', eg_med, f'new in Egypt median {eg_med:,.0f} ({len(eg_new)} shops)')
    out = sorted(found.values(), key=lambda d: (-len(d['signals']), -d['score']))[:a.limit]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        for d in out: f.write(json.dumps(d, ensure_ascii=False) + '\n')
    sig = collections.Counter(s.split(':')[0] for d in out for s in d['signals'])
    print(len(found), 'rows flagged;', len(out), 'written to', a.out, '| by signal:', dict(sig))
    print('by category:', dict(collections.Counter(d['category'] for d in out).most_common(8)))


if __name__ == '__main__':
    main()
