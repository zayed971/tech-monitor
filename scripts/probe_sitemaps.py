"""Probe registry shops that are neither Shopify nor WooCommerce: do they have a product sitemap and JSON-LD prices?

Polite (robots.txt respected, 3 s gap per host, stops on 403/429/challenge). Writes data/registry/probe_sitemaps.jsonl.
Usage: .venv\\Scripts\\python.exe -X utf8 -u scripts\\probe_sitemaps.py
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from egypt_deals.http import Client, FetchError  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
reg = ROOT / 'data' / 'registry'
out = reg / 'probe_sitemaps.jsonl'
done = set()
if out.exists():
    done = {json.loads(x)['domain'] for x in out.read_text(encoding='utf-8').splitlines() if x.strip()}
known = {}
for x in (reg / 'probe.jsonl').read_text(encoding='utf-8').splitlines():
    if x.strip():
        d = json.loads(x)
        known[d['domain']] = d['platform']
client = Client(ROOT / 'data' / 'cache_probe', delay=3, ttl=3600)
LOC = re.compile(r'<loc>\s*(?:<!\[CDATA\[)?\s*([^<\]\s]+)', re.I)
BAD = re.compile(r'categor|/tag|/blog|/page|/cart|/account|/login|/search|/brand|/contact|/about|\.(?:jpg|png|webp|pdf)', re.I)


def get(url):
    try:
        return client.get(url, private=True)[0], None
    except FetchError as e:
        return None, str(e)


def ld_product(html):
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(m.group(1).strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                if 'Product' in str(d.get('@type')):
                    offers = d.get('offers')
                    if isinstance(offers, list) and offers:
                        offers = offers[0]
                    if isinstance(offers, dict):
                        p = offers.get('price') or offers.get('lowPrice')
                        if p is None and isinstance(offers.get('priceSpecification'), dict):
                            p = offers['priceSpecification'].get('price')
                        return {'name': str(d.get('name'))[:60], 'price': p, 'currency': offers.get('priceCurrency'),
                                'availability': str(offers.get('availability'))[-20:], 'gtin': d.get('gtin13') or d.get('gtin') or d.get('mpn') or d.get('sku')}
                stack.extend(v for v in d.values() if isinstance(v, (dict, list)))
    return None


with out.open('a', encoding='utf-8', newline='\n') as fh:
    for dom, plat in known.items():
        if plat != 'unknown' or dom in done:
            continue
        base = 'https://' + dom
        res = {'domain': dom, 'sitemap': None, 'product_urls': 0, 'sample': None, 'ld': None, 'errors': []}
        body, err = get(base + '/sitemap.xml')
        if not body:
            for alt in ('/sitemap_index.xml', '/wp-sitemap.xml', '/sitemap-index.xml'):
                body, err2 = get(base + alt)
                if body:
                    res['sitemap'] = alt
                    break
            if not body:
                res['errors'].append('sitemap: ' + str(err))
        else:
            res['sitemap'] = '/sitemap.xml'
        urls = []
        if body:
            locs = LOC.findall(body)
            if re.search(r'<sitemapindex', body, re.I):
                kids = [u for u in locs if re.search(r'product', u, re.I)] or []
                res['children'] = len(locs)
                res['product_children'] = [urlsplit(u).path for u in kids[:6]]
                if kids:
                    b2, e2 = get(kids[0])
                    if b2:
                        urls = LOC.findall(b2)
                    else:
                        res['errors'].append('child: ' + str(e2))
            else:
                urls = locs
            urls = [u for u in urls if not BAD.search(u) and urlsplit(u).path.strip('/')]
            res['product_urls'] = len(urls)
            if urls:
                sample = urls[len(urls) // 2]
                res['sample'] = sample
                page, e3 = get(sample)
                if page:
                    res['ld'] = ld_product(page)
                else:
                    res['errors'].append('sample: ' + str(e3))
        fh.write(json.dumps(res, ensure_ascii=False) + '\n')
        fh.flush()
        print(dom, res['sitemap'], res['product_urls'], res['ld'], res['errors'][-1:])
client.close()
