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
    if re.search(r'radeon|\bRX\s*\d{4}', listing.raw_title, re.I): return None
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


def not_a_real_offer(listing):
    """Price makes no sense for the item, or the ad is a buyer's 'wanted' post."""
    return any('implausible' in q or 'Wanted ad' in q or 'unknown size' in q or 'Currency label' in q for q in listing.quality_issues)


def usable(listing, max_age_hours=None):
    if listing.placeholder or listing.price_egp is None or listing.comparison_only: return False
    if not_a_real_offer(listing): return False
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
    best, more = {}, {}
    for r in sorted(out, key=order):
        key = model_key(r)
        if key in best: more[key] = more.get(key, 0) + 1
        else: best[key] = r
    for key, r in best.items(): r['more_offers'] = more.get(key, 0)
    return sorted(best.values(), key=order)[:limit]


# Spec words that carry digits and letters but name no product ("2.4ghz" gives "4ghz", "3200dpi", "ddr5", "1080p"). Without this,
# every wireless mouse shared one "model" and got compared with all the others.
SPEC_TOKEN = re.compile(r'^(?:\d+(?:ghz|mhz|hz|dpi|mah|mm|cm|mbps|gbps|rpm|ms|mp|nm|db|kg|lm|gb|tb|w|v|a|k|p|m|g|s|x|in|pin|core|bit|fps|cfm|cl)'
                        r'|ddr[2-5]|usb\d*|type\w?|wifi\d?|bt\d*|pcie\d*|gen\d+|sata\d*|hdmi\d*|rgb\d*|argb\d*|\d+(?:st|nd|rd|th)|2in1|3in1|4in1|5in1)$')


# Words that separate versions of one model code (G502 Hero vs G502 X vs G502 Lightspeed; 4070 vs 4070 Ti Super).
VARIANT_WORDS = {'hero', 'lightspeed', 'plus', 'pro', 'ti', 'super', 'xt', 'xtx', 'max', 'mini', 'lite', 'ultra', 'se'}


def model_tokens(title):
    """Identity of a product from its title: model codes (letters+digits, 4+ chars) plus capacity, pack size and screen size.

    "WD SN850X 1TB" and "WD SN850X 2TB" are different products, as are a 1-pack and a 3-pack of the same fan. None when the title has no
    model code, so unlike products are never matched by accident."""
    t = str(title).lower()
    codes = {x for x in re.findall(r'[a-z0-9]{4,}', t) if re.search(r'\d', x) and re.search(r'[a-z]', x) and not SPEC_TOKEN.match(x)}
    if not codes: return None
    caps = {re.sub(r'\s', '', m) for m in re.findall(r'\b\d+(?:\.?\d+)?\s?(?:gb|tb)\b', t)}
    packs = {'pack' + m for m in re.findall(r'\b(\d)\s*(?:in\s?1|-?pack|pcs|pc|pieces)\b', t)}
    sizes = {'in' + m for m in re.findall(r'\b(\d{2}(?:\.?\d)?)\s?(?:inch|in\b|")', t)}
    variants = {'v_' + w for w in re.findall(r'[a-z]+', t) if w in VARIANT_WORDS}
    variants |= {'v_x' for _ in re.findall(r'[a-z]{1,2}' + chr(92) + 'd{2,4}' + chr(92) + 's+x' + chr(92) + 'b', t)}
    return tuple(sorted(codes | caps | packs | sizes | variants))


def model_key(r):
    """One row per model per zone and condition: stores selling the same model are folded into the cheapest ('+N more')."""
    tokens = model_tokens(r['title'])
    if tokens: return (r['zone'], r['condition'], r['category'], tokens)
    return (r['zone'], r['store'], r['title'][:60].lower())


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
            lines.append(f"| {i} | {r['zone']} | {r['store']} | [{title}]({r['url']}) | {r['condition']} | {r['stock']}{' (aggregator, verify)' if r['src']=='aggregator' else ''}{(' +' + str(r['more_offers']) + ' more stores') if r.get('more_offers') else ''} | "
                         f"{price} | {r['price_egp']:,.0f} | {r['landed']} | {r['payments']} | {r['age_h']} |")
        lines.append('')
    return '\n'.join(lines), data
