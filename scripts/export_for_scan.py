"""Export usable listings of chosen categories as compact TSV chunks for a model to read. Read only.

    .venv\\Scripts\\python.exe -X utf8 scripts\\export_for_scan.py OUTDIR ssd ram gpu [--chunk 250] [--max-age-hours 72]

Writes OUTDIR/<category>_NN.tsv. Columns: n, zone, store, cond, stock, price_egp, orig_price, age_h, title, url.
Out-of-stock, placeholder and not-a-real-offer rows are dropped. Same store+title keeps only the cheapest row.
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
    p.add_argument('outdir')
    p.add_argument('categories', nargs='+')
    p.add_argument('--chunk', type=int, default=250)
    p.add_argument('--max-age-hours', type=float)
    a = p.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    wanted = set(a.categories)
    rows = {c: {} for c in wanted}
    for l in findings.load(root):
        if l.category not in wanted: continue
        if l.price_egp is None or l.placeholder or l.comparison_only: continue
        if findings.not_a_real_offer(l) or l.stock == 'out_of_stock': continue
        age = findings.age_hours(l)
        if a.max_age_hours is not None and (age is None or age > a.max_age_hours): continue
        k = (l.zone, l.store, re.sub(r'\W+', ' ', l.raw_title.lower())[:80])
        cur = rows[l.category].get(k)
        if cur is None or l.price_egp < cur[0].price_egp: rows[l.category][k] = (l, age)
    for cat, d in rows.items():
        items = sorted(d.values(), key=lambda x: x[0].price_egp)
        for i in range(0, len(items), a.chunk):
            lines = []
            for n, (l, age) in enumerate(items[i:i + a.chunk], i + 1):
                t = re.sub(r'\s+', ' ', l.raw_title)[:150]
                lines.append('\t'.join(str(x) for x in (
                    n, l.zone, l.store, l.condition, l.stock, round(l.price_egp), '' if age is None else round(age), t, l.url)))
            (out / f'{cat}_{i // a.chunk + 1:02d}.tsv').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
        print(cat, len(items), 'rows ->', -(-len(items) // a.chunk), 'files')


main()
