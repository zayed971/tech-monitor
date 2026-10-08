"""Rank SSD and RAM listings by price per GB inside comparable classes, from export_for_scan.py TSV files. Read only.

    .venv\\Scripts\\python.exe -X utf8 scripts\\rank_storage_ram.py SCANDIR [--max-age 72] [--top 6] [--include-unknown-cond]

Class = SSD: nvme internal | sata internal | external; RAM: DDR gen + desktop/laptop. Each class is split by capacity band.
Default keeps new/refurbished/open_box/used rows with real stock info; "unknown" condition and unknown stock only with the flag.
"""
import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
p = argparse.ArgumentParser()
p.add_argument('scandir')
p.add_argument('--max-age', type=float, default=72)
p.add_argument('--top', type=int, default=6)
p.add_argument('--include-unknown-cond', action='store_true')
a = p.parse_args()

NOT_DRIVE = re.compile(r'enclosure|case\b|adapter|adaptor|converter|cable|reader|dock|bracket|heatsink|cooler|hub|caddy|holder|bay|screw|pad\b|kit for|empty|box only', re.I)
SERVER = re.compile(r'\becc\b|registered|rdimm|server|fb-?dimm', re.I)


def cap_gb(t):
    m = re.findall(r'(\d+(?:\.\d+)?)\s*(TB|GB|T\b|G\b)', t, re.I)
    caps = sorted({round(float(n) * (1000 if u[0].upper() == 'T' else 1)) for n, u in m})
    return caps


def ssd_class(t):
    tl = t.lower()
    if re.search(r'portable|external|\bt7\b|\bt9\b|\bt5\b|xs\d{3,4}|extreme|my passport|bolt|usb', tl) and not re.search(r'm\.?2\b.*internal', tl):
        return 'external'
    if re.search(r'nvme|m\.?2|pcie|gen ?[345]', tl): return 'nvme'
    if re.search(r'sata|2\.5', tl): return 'sata'
    return None


def ram_class(t):
    tl = t.lower()
    gen = 'ddr5' if 'ddr5' in tl else 'ddr4' if 'ddr4' in tl else 'ddr3' if 'ddr3' in tl else None
    if not gen: return None
    form = 'laptop' if re.search(r'so-?dimm|laptop|notebook', tl) else 'desktop'
    return f'{gen} {form}'


def ram_total(t):
    m = re.search(r'(\d+)\s*GB\s*\(?\s*(\d)\s*[x×]\s*(\d+)\s*GB', t, re.I) or None
    if m: return int(m.group(2)) * int(m.group(3))
    m = re.search(r'(\d)\s*[x×]\s*(\d+)\s*GB', t, re.I)
    if m: return int(m.group(1)) * int(m.group(2))
    c = cap_gb(t)
    return c[0] if len(c) == 1 else None


def load(prefix):
    rows = []
    for f in sorted(Path(a.scandir).glob(prefix + '_*.tsv')):
        for line in f.read_text(encoding='utf-8').splitlines():
            x = line.split('\t')
            rows.append(dict(zone=x[1], store=x[2], cond=x[3], stock=x[4], price=float(x[5]),
                             age=float(x[6]) if x[6] != '' else None, title=x[7], url=x[8]))
    return rows


def keep(r):
    if r['age'] is None or r['age'] > a.max_age: return False
    if r['store'].startswith('Facebook'): return False  # no spec, ad text only
    if not a.include_unknown_cond and (r['cond'] == 'unknown' or r['stock'] not in ('in_stock',)): return False
    return True


def show(title, items):
    print(f'\n### {title}')
    for gb, r in items:
        print(f"- {r['price']:,.0f} EGP ({r['price'] / gb:,.1f}/GB) | {r['zone']} {r['store'][:24]} | {r['cond']}/{r['stock']} | "
              f"{r['age']:.0f}h | {r['title'][:95]} | {r['url']}")


bands = [(0, 400, '<=256GB'), (400, 700, '512GB'), (700, 1500, '1TB'), (1500, 3000, '2TB'), (3000, 99999, '4TB+')]
ssd = {}
for r in filter(keep, load('ssd')):
    if NOT_DRIVE.search(r['title']): continue
    c = ssd_class(r['title']); caps = cap_gb(r['title'])
    if not c or len(caps) != 1 or caps[0] < 100 or caps[0] > 16000: continue
    ssd.setdefault(c, []).append((caps[0], r))
for c in ('nvme', 'sata', 'external'):
    for lo, hi, name in bands:
        if name == '<=256GB': continue
        items = sorted([(g, r) for g, r in ssd.get(c, []) if lo < g <= hi], key=lambda x: x[1]['price'] / x[0])[:a.top]
        if items: show(f'SSD {c} {name} (best EGP/GB)', items)
ram = {}
for r in filter(keep, load('ram')):
    if NOT_DRIVE.search(r['title']) or SERVER.search(r['title']): continue
    c = ram_class(r['title']); g = ram_total(r['title'])
    if not c or not g or g < 4 or g > 256: continue
    ram.setdefault(c, []).append((g, r))
for c in sorted(ram):
    for lo, hi, name in ((0, 8, '<=8GB'), (8, 16, '16GB'), (16, 32, '32GB'), (32, 64, '64GB'), (64, 999, '96GB+')):
        items = sorted([(g, r) for g, r in ram[c] if lo < g <= hi], key=lambda x: x[1]['price'] / x[0])[:a.top]
        if items and name != '<=8GB': show(f'RAM {c} {name} total (best EGP/GB)', items)
