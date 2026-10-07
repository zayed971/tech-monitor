r"""Manual mode: you found a listing (Facebook, Dubizzle, a friend, a shop) and want to know if the price is good.

Nothing is fetched or posted. You paste the title and the price; this reads the specs out of the title, then compares the
price with what the monitor has stored for the same kind of item.

    .venv\Scripts\python.exe scripts\check_listing.py --title "RTX 3060 12GB Zotac used" --price 12000
    .venv\Scripts\python.exe scripts\check_listing.py --title "Ryzen 5 5600 + B550 + 16GB" --price 9500 --currency EGP --condition used
    .venv\Scripts\python.exe scripts\check_listing.py --title "ASUS TUF A15 RTX 3050 16GB 512GB" --price 3000 --currency AED --condition used

--currency EGP (default), AED, SAR or USD (converted at the stored rate). The verdict compares against stored asking prices,
which are not sale prices; used prices are asking prices too.
"""
import argparse
import re
import statistics
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from egypt_deals import findings, zones  # noqa: E402
from egypt_deals.model import Listing  # noqa: E402


def key_specs(l):
    s = l.specs or {}
    if l.category == 'gpu': return ('gpu_model', 'gpu_vram_gb')
    if l.category == 'ram': return ('ram_type', 'ram_gb', 'ram_form_factor')
    if l.category == 'cpu': return ('cpu_model',)
    if l.category in ('ssd', 'hdd'): return ('storage_gb', 'storage_type')
    if l.category == 'psu': return ('psu_w',)
    if l.category == 'ups': return ('ups_va',)
    if l.category in ('laptop', 'pc'): return ('gpu_model', 'ram_gb', 'storage_gb')
    return ()


def comparable(mine, other):
    if other.category != mine.category or other.price_egp is None or other.placeholder: return False
    if other.stock == 'out_of_stock' or findings.not_a_real_offer(other): return False
    ks = key_specs(mine)
    if ks:
        wanted = {k: mine.specs.get(k) for k in ks if mine.specs.get(k) is not None}
        if not wanted: return False
        return all(other.specs.get(k) == v for k, v in wanted.items())
    # No spec keys for this category: need the same brand and 2+ shared model words.
    words = {w for w in re.findall(r'[a-z0-9]{3,}', mine.raw_title.lower())} - {'with', 'and', 'for', 'the', 'new', 'used'}
    theirs = set(re.findall(r'[a-z0-9]{3,}', other.raw_title.lower()))
    return len(words & theirs) >= max(3, len(words) // 2)


def stat(rows):
    p = sorted(r.price_egp for r in rows)
    return f'{len(p)} offers, low {p[0]:,.0f}, median {statistics.median(p):,.0f}, high {p[-1]:,.0f} EGP' if p else 'none stored'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--title', required=True)
    ap.add_argument('--price', type=float, required=True)
    ap.add_argument('--currency', default='EGP', choices=['EGP', 'AED', 'SAR', 'USD'])
    ap.add_argument('--condition', default='used', choices=['new', 'used', 'refurbished', 'open_box', 'unknown'])
    ap.add_argument('--zone', default='EG', choices=['EG', 'UAE', 'KSA', 'US'], help='where the item is')
    a = ap.parse_args()
    rate = zones.usd_egp(root)
    egp = zones.to_egp(a.price, a.currency, rate)
    if egp is None:
        sys.exit('No stored USD/EGP rate; cannot convert. Give the price in EGP.')
    mine = Listing(store='manual', url='manual', raw_title=a.title, price_egp=egp, source='manual', condition=a.condition,
                   zone=a.zone, currency=a.currency, price_local=a.price).finish()
    mine.condition = a.condition
    sys.stdout.reconfigure(encoding='utf-8')
    s = {k: v for k, v in (mine.specs or {}).items() if v is not None}
    print(f'Read from your title: category={mine.category}, specs={s or "nothing recognised"}')
    print(f'Your price: {a.price:,.0f} {a.currency} = {egp:,.0f} EGP' + ('' if a.currency == 'EGP' else f' (rate {rate} EGP/USD, item price only; landed cost unconfirmed)'))
    for q in mine.quality_issues: print('WARNING:', q)
    others = [l for l in findings.load(root) if comparable(mine, l)]
    if not others:
        print('No comparable listings stored (the title gave too few specs, or the category has no spec keys). Not the same as "no deal".')
        return
    fresh = [l for l in others if (findings.age_hours(l) or 9e9) <= 24 * 7]
    print(f'\nSame kind in the database (last 7 days: {len(fresh)} of {len(others)}):')
    medians = {}
    for label, f in (('New, Egypt', lambda l: l.condition == 'new' and l.zone == 'EG'),
                     ('Used/refurbished, Egypt', lambda l: l.condition in ('used', 'refurbished', 'open_box') and l.zone == 'EG'),
                     ('Used/refurbished, UAE+KSA+US', lambda l: l.condition in ('used', 'refurbished', 'open_box') and l.zone != 'EG'),
                     ('New, UAE+KSA+US', lambda l: l.condition == 'new' and l.zone != 'EG')):
        rows = [l for l in fresh if f(l)]
        print(f'  {label}: {stat(rows)}')
        if rows: medians[label] = statistics.median(r.price_egp for r in rows)
    ref = medians.get('New, Egypt') if mine.condition == 'new' else medians.get('Used/refurbished, Egypt') or medians.get('New, Egypt')
    if ref:
        diff = (egp - ref) / ref * 100
        word = 'below' if diff < 0 else 'above'
        print(f'\nVerdict: your price is {abs(diff):.0f}% {word} the stored median for that group ({ref:,.0f} EGP).')
        if diff < -35: print('  Very cheap for the group: check for a scam, a mining card, a missing part or a wrong spec before getting excited.')
        elif diff < -10: print('  Good price if it is as described. Ask for proof it works.')
        elif diff <= 10: print('  Normal market price.')
        else: print('  Above market. Negotiate or look elsewhere.')
    cheapest = sorted(fresh, key=lambda l: l.price_egp)[:3]
    if cheapest:
        print('\nCheapest comparable offers right now:')
        for l in cheapest: print(f'  {l.price_egp:>8,.0f} EGP  {l.zone} {l.store} [{l.condition}] {l.raw_title[:70]}  {l.url}')


if __name__ == '__main__':
    main()
