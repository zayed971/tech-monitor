"""Build global_sources_seed.csv: UAE, Saudi and US sources for the tech monitor.

Seeds come from files that already exist (ebay_laptop_scrape research, cheap_tech markets.csv) plus a short list of
well-known majors written from general knowledge. Everything is marked verified=no until a real fetch and a payment-page
read prove it. Nothing here is a price. Run from the project root: python scripts/build_global_sources_seed.py
"""
import collections
import csv
import json
import os
from urllib.parse import urlparse

EBAY_RESEARCH = 'C:/PROJECTS/ebay_laptop_scrape/research'
MARKETS = 'C:/PROJECTS/cheap_tech/data/markets.csv'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'global_sources_seed.csv')
FIELDS = ['zone', 'country', 'name', 'domain', 'kind', 'condition', 'payments_claimed', 'domestic_delivery',
          'seed_source', 'verified', 'notes']

rows = []


def add(zone, country, name, domain, kind, condition, payments, delivery, seed, note=''):
    rows.append(dict(zone=zone, country=country, name=name, domain=domain, kind=kind, condition=condition,
                     payments_claimed=payments, domestic_delivery=delivery, seed_source=seed,
                     verified='no (seed)', notes=note))


country_map = {'UAE': ('UAE', 'AE'), 'Saudi Arabia': ('KSA', 'SA'), 'USA': ('US', 'US')}
for fname in ('asia_mea.json', 'north_america_oceania.json'):
    with open(os.path.join(EBAY_RESEARCH, fname), encoding='utf-8') as fh:
        for x in json.load(fh)['candidates']:
            c = x.get('country')
            if c in country_map:
                zone, cc = country_map[c]
                used = x.get('type') in ('classifieds', 'refurb-store', 'b2b', 'auction')
                add(zone, cc, x['name'], urlparse(x['url']).netloc.replace('www.', ''), x.get('type', ''),
                    'used/refurb' if used else 'mixed', 'unknown', 'yes',
                    'ebay_laptop_scrape/research (2026-09-22)')

with open(MARKETS, encoding='utf-8') as fh:
    for x in csv.DictReader(fh):
        bc = x['base_country']
        dom = x['domain'].lower()
        egypt_shop = (x['ships_to_egypt'] == 'domestic_eg' or 'egypt' in dom or dom.endswith('.com.eg')
                      or dom.startswith('eg.'))
        if bc in ('AE', 'US') and not egypt_shop:
            pay = ','.join(k for k, v in (('paypal', x['payment_paypal']), ('cod', x['payment_cod']),
                                          ('card', x['payment_card'])) if v and v.lower() in ('yes', 'true', 'y'))
            add('UAE' if bc == 'AE' else 'US', bc, x['market'], x['domain'], x['type'], 'mixed', pay or 'unknown',
                'yes', 'cheap_tech/data/markets.csv (2026-10-03)')

known = [
    ('UAE', 'AE', 'Amazon.ae', 'amazon.ae', 'marketplace', 'new+renewed'),
    ('UAE', 'AE', 'Noon UAE', 'noon.com', 'marketplace', 'new+renewed'),
    ('UAE', 'AE', 'Microless', 'microless.com', 'shop', 'new'),
    ('UAE', 'AE', 'Jumbo Electronics', 'jumbo.ae', 'shop', 'new'),
    ('UAE', 'AE', 'Dubizzle UAE', 'uae.dubizzle.com', 'classifieds', 'used'),
    ('UAE', 'AE', 'OpenSooq UAE', 'ae.opensooq.com', 'classifieds', 'used'),
    ('KSA', 'SA', 'Amazon.sa', 'amazon.sa', 'marketplace', 'new+renewed'),
    ('KSA', 'SA', 'Noon Saudi', 'noon.com/saudi-en', 'marketplace', 'new+renewed'),
    ('KSA', 'SA', 'eXtra', 'extra.com', 'shop', 'new'),
    ('KSA', 'SA', 'Jarir', 'jarir.com', 'shop', 'new'),
    ('KSA', 'SA', 'Haraj', 'haraj.com.sa', 'classifieds', 'used'),
    ('KSA', 'SA', 'OpenSooq Saudi', 'sa.opensooq.com', 'classifieds', 'used'),
    ('US', 'US', 'Amazon US', 'amazon.com', 'marketplace', 'new+renewed'),
    ('US', 'US', 'eBay US', 'ebay.com', 'marketplace', 'new+used'),
    ('US', 'US', 'Newegg', 'newegg.com', 'shop', 'new+open-box'),
    ('US', 'US', 'B&H', 'bhphotovideo.com', 'shop', 'new'),
    ('US', 'US', 'Micro Center', 'microcenter.com', 'shop', 'new+open-box'),
    ('US', 'US', 'Best Buy', 'bestbuy.com', 'shop', 'new+open-box'),
    ('US', 'US', 'Back Market', 'backmarket.com', 'refurb', 'refurbished'),
    ('US', 'US', 'Swappa', 'swappa.com', 'used', 'used'),
    ('US', 'US', 'Reddit r/hardwareswap', 'reddit.com/r/hardwareswap', 'used-p2p', 'used'),
    ('US', 'US', 'Facebook Marketplace US (burner)', 'facebook.com/marketplace', 'classifieds', 'used'),
    ('UAE', 'AE', 'Facebook Marketplace UAE (burner)', 'facebook.com/marketplace', 'classifieds', 'used'),
    ('KSA', 'SA', 'Facebook Marketplace KSA (burner)', 'facebook.com/marketplace', 'classifieds', 'used'),
    ('EG', 'EG', 'Facebook Marketplace Egypt (burner)', 'facebook.com/marketplace', 'classifieds', 'used'),
]
for zone, cc, name, domain, kind, cond in known:
    add(zone, cc, name, domain, kind, cond, 'unknown', 'yes', 'general knowledge (unchecked)')

seen, out = {}, []
for r in rows:
    key = (r['zone'], r['domain'].lower().rstrip('/'))
    if key in seen:
        seen[key]['seed_source'] += ' + ' + r['seed_source']
        continue
    seen[key] = r
    out.append(r)

with open(OUT, 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(out)
print(len(out), dict(collections.Counter(r['zone'] for r in out)))
