r"""Exact-model / keyword search over every stored listing, full results (no top-10 cut). Read only.

    .venv\Scripts\python.exe scripts\find.py --q "G403"
    .venv\Scripts\python.exe scripts\find.py --q "K552|BlackShark" --zone EG --condition new --max-age-hours 72
    .venv\Scripts\python.exe scripts\find.py --q "MP225" --category monitor --limit 0 --all-offers

--q is a case-insensitive regex over the title, brand, model and SKU/MPN. Default: one row per store and title, cheapest first,
in-stock before unknown. --limit 0 prints everything. Prices are asking prices as last seen.
"""
import argparse
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from egypt_deals import findings  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--q', required=True, help='regex, e.g. "G403|G502"')
    p.add_argument('--category')
    p.add_argument('--zone', action='append', choices=['EG', 'UAE', 'KSA', 'US'])
    p.add_argument('--condition', action='append', choices=['new', 'used', 'refurbished', 'open_box', 'unknown'])
    p.add_argument('--max-price', type=float, help='EGP')
    p.add_argument('--max-age-hours', type=float)
    p.add_argument('--limit', type=int, default=40, help='0 = everything')
    p.add_argument('--all-offers', action='store_true', help='keep every variant row instead of one per store+title')
    p.add_argument('--include-out-of-stock', action='store_true')
    a = p.parse_args()
    pattern = re.compile(a.q, re.I)
    rows = []
    for l in findings.load(root):
        hay = ' '.join(str(x) for x in (l.raw_title, l.brand, l.model, l.sku, l.mpn) if x)
        if not pattern.search(hay): continue
        if a.category and l.category != a.category: continue
        if a.zone and l.zone not in a.zone: continue
        if a.condition and l.condition not in a.condition: continue
        if l.price_egp is None or l.placeholder: continue
        if findings.not_a_real_offer(l): continue
        if l.stock == 'out_of_stock' and not a.include_out_of_stock: continue
        if a.max_price and l.price_egp > a.max_price: continue
        age = findings.age_hours(l)
        if a.max_age_hours is not None and (age is None or age > a.max_age_hours): continue
        rows.append((l, age))
    rows.sort(key=lambda x: (x[0].stock not in ('in_stock',), x[0].price_egp))
    if not a.all_offers:
        seen, keep = set(), []
        for l, age in rows:
            k = (l.zone, l.store, re.sub(r'\W+', ' ', l.raw_title.lower())[:60])
            if k not in seen: seen.add(k); keep.append((l, age))
        rows = keep
    total = len(rows)
    if a.limit: rows = rows[:a.limit]
    sys.stdout.reconfigure(encoding='utf-8')
    print(f'{total} match(es) for /{a.q}/ (showing {len(rows)}). Prices are asking prices as last seen; condition_basis "src" = shop sells new only, not stated on the page.')
    print('| zone | store | item | cond | stock | price | EGP | landed | age h | url |')
    print('|---|---|---|---|---|---|---:|---|---:|---|')
    for l, age in rows:
        r = findings.row(l)
        basis = '*' if l.condition_basis == 'source_default' else ''
        price = f"{r['price_local']:,.0f} {r['currency']}" if r['price_local'] else ''
        print(f"| {l.zone} | {l.store} | {l.raw_title[:90].replace('|', '/')} | {l.condition}{basis} | {r['stock']} | {price} | "
              f"{l.price_egp:,.0f} | {l.landed_status} | {age} | {l.url} |")
    if any(l.condition_basis == 'source_default' for l, _ in rows): print('\n* condition assumed new because the shop only sells new stock.')


if __name__ == '__main__':
    main()
