"""Top findings for Zayed's Blender + local-AI machine. Reads the database only; nothing is fetched or sent.

The GPU tier numbers are a ROUGH relative scale (100 = RTX 4090 desktop class) for ranking only. They are not a
benchmark; real Blender or AI speed needs a matched test, and laptop chips run slower than desktop cards of the same name.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .model import date_value, now

GPU_TIER = {
    'RTX 5090': 120, 'RTX 5080': 95, 'RTX 5070 TI': 80, 'RTX 5070': 62, 'RTX 5060 TI': 52, 'RTX 5060': 45, 'RTX 5050': 38,
    'RTX 4090': 100, 'RTX 4080': 82, 'RTX 4070 TI SUPER': 72, 'RTX 4070 TI': 66, 'RTX 4070 SUPER': 64, 'RTX 4070': 56,
    'RTX 4060 TI': 46, 'RTX 4060': 38, 'RTX 4050': 30,
    'RTX 3090 TI': 78, 'RTX 3090': 72, 'RTX 3080 TI': 66, 'RTX 3080': 60, 'RTX 3070 TI': 50, 'RTX 3070': 46,
    'RTX 3060 TI': 42, 'RTX 3060': 33, 'RTX 3050': 20,
}


def gpu_tier(model):
    if not model: return None
    key = re.sub(r'\s+', ' ', str(model).upper().replace('GEFORCE', '').replace('NVIDIA', '')).strip()
    if key in GPU_TIER: return GPU_TIER[key]
    for name in sorted(GPU_TIER, key=len, reverse=True):
        if key.startswith(name): return GPU_TIER[name]
    return None


def title_confirms(model, title):
    """The GPU model number from the spec reader must appear in the item's own title; otherwise it is a guess."""
    digits = re.findall(r'\d{4}', str(model or ''))
    return bool(digits) and all(d in (title or '') for d in digits)


def gpu_of(listing):
    """GPU model for ranking, only when the title agrees with the spec reader and the card is NVIDIA RTX."""
    model = (listing.specs or {}).get('gpu_model')
    if not model or not str(model).upper().startswith('RTX'): return None
    if re.search(r'radeon|RX\s*\d{4}', listing.raw_title, re.I): return None
    return model if title_confirms(model, listing.raw_title) else None


AD_SOURCES = ('haraj', 'opensooq', 'facebook', 'dubizzle', 'us_reddit', 'swappa', 'olx')


def stock_label(listing):
    """Classified ads and Marketplace adverts never prove stock; their own 'in stock' flag is not shown as fact."""
    if listing.source_kind == 'used' or str(listing.source).startswith(AD_SOURCES):
        return 'ad listed (unconfirmed)'
    return listing.stock


def age_hours(listing):
    t = date_value(listing.observed_at)
    return None if t is None else round((datetime.now(timezone.utc) - t).total_seconds() / 3600, 1)


def row(listing):
    s = listing.specs or {}
    return {
        'zone': listing.zone, 'store': listing.store, 'title': listing.raw_title[:110], 'category': listing.category,
        'condition': listing.condition, 'stock': stock_label(listing),
        'price_local': listing.price_local if listing.zone != 'EG' else listing.price_egp,
        'currency': listing.currency, 'price_egp': listing.price_egp, 'landed': listing.landed_status,
        'payments': ','.join(listing.payments) or 'unknown', 'route': listing.route or '',
        'gpu': gpu_of(listing), 'vram_gb': s.get('gpu_vram_gb'), 'ram_gb': s.get('ram_gb'),
        'storage_gb': s.get('storage_gb'), 'cpu': s.get('cpu_model'),
        'src': listing.source_kind, 'issues': '; '.join(listing.quality_issues)[:90], 'age_h': age_hours(listing), 'url': listing.url,
    }


def usable(listing, max_age_hours=None):
    if listing.placeholder or listing.price_egp is None or listing.comparison_only: return False
    if listing.stock == 'out_of_stock': return False
    if max_age_hours is not None:
        age = age_hours(listing)
        if age is None or age > max_age_hours: return False
    return True


def pick(listings, kind, budget, zones=None, conditions=None, limit=15, max_age_hours=None):
    """Ranked rows for one kind: laptop | gpu | pc | ram | ssd | cpu | motherboard | psu."""
    zones = {z.upper() for z in zones} if zones else None
    out = []
    for l in listings:
        if not usable(l, max_age_hours) or l.price_egp > budget: continue
        if zones and l.zone not in zones: continue
        if conditions and l.condition not in conditions: continue
        s = l.specs or {}
        score = None
        if kind == 'laptop':
            if l.category != 'laptop': continue
            tier = gpu_tier(gpu_of(l))
            if tier is None or tier < 30 or (s.get('ram_gb') or 0) < 16: continue
            score = tier
        elif kind == 'gpu':
            if l.category != 'gpu': continue
            tier = gpu_tier(gpu_of(l))
            vram = s.get('gpu_vram_gb') or 0
            if tier is None or vram < 12: continue
            score = tier + vram
        elif kind == 'pc':
            if l.category != 'pc' or l.build_complete is False: continue
            tier = gpu_tier(gpu_of(l))
            if tier is None: continue
            score = tier
        elif kind == 'ram':
            if l.category != 'ram' or (s.get('ram_gb') or 0) < 32 or s.get('ram_type') not in ('DDR4', 'DDR5'): continue
            score = s.get('ram_gb')
        elif kind == 'ssd':
            if l.category != 'ssd' or (s.get('storage_gb') or 0) < 1000: continue
            score = s.get('storage_gb')
        elif kind in ('cpu', 'motherboard', 'psu'):
            if l.category != kind: continue
            score = 0
        else:
            raise ValueError('unknown kind ' + kind)
        r = row(l)
        r['score'] = score
        r['value'] = round(score / l.price_egp * 10000, 2) if score and kind in ('laptop', 'gpu', 'pc') else None
        out.append(r)
    # In-stock before unknown, then best value (or cheapest per capacity), then price.
    def order(r):
        value = r['value'] if r['value'] is not None else (-(r['price_egp'] / (r['score'] or 1)))
        return (r['stock'] not in ('in_stock', 'ad listed (unconfirmed)'), r['stock'] != 'in_stock', -value, r['price_egp'])
    best = {}
    for r in sorted(out, key=order):
        key = (r['zone'], r['store'], r['title'][:60].lower())
        best.setdefault(key, r)
    return sorted(best.values(), key=order)[:limit]


def load(root):
    from .storage import Database
    db = Database(Path(root) / 'data' / 'deals.sqlite3')
    try: return db.listings()
    finally: db.close()


def report(root, budget=70000, kinds=('laptop', 'gpu', 'pc', 'ram', 'ssd'), zones=None, conditions=None, limit=10,
           max_age_hours=None):
    listings = load(root)
    lines = [f'# Top findings, budget {budget:,} EGP per device (monitor screen excluded)',
             f'Made {now()} from {len(listings):,} stored listings. Prices are asking prices as last seen; '
             'a listing is only "in_stock" when its own page said so.', '']
    data = {}
    for kind in kinds:
        rows = pick(listings, kind, budget, zones, conditions, limit, max_age_hours)
        data[kind] = rows
        lines += [f'## {kind.upper()} ({len(rows)} shown)', '']
        if not rows:
            lines += ['Nothing matched. Not the same as "none exist": see source coverage.', '']
            continue
        lines += ['| # | zone | store | item | cond | stock | price | EGP | landed | payments | age h |', '|---|---|---|---|---|---|---|---:|---|---|---:|']
        for i, r in enumerate(rows, 1):
            price = f"{r['price_local']:,.0f} {r['currency']}" if r['price_local'] else ''
            title = r['title'].replace('|', '/').replace('[', '(').replace(']', ')')
            lines.append(f"| {i} | {r['zone']} | {r['store']} | [{title}]({r['url']}) | {r['condition']} | {r['stock']}{' (aggregator, verify)' if r['src']=='aggregator' else ''} | "
                         f"{price} | {r['price_egp']:,.0f} | {r['landed']} | {r['payments']} | {r['age_h']} |")
        lines.append('')
    return '\n'.join(lines), data
