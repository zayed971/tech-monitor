"""Probe registry shops: which expose a Shopify /products.json or WooCommerce store API.

Polite (robots.txt respected, 3 s gap per host, stops on 403/429). Writes data/registry/probe.jsonl.
Usage: .venv\\Scripts\\python.exe -X utf8 scripts\\probe_shops.py [registry.jsonl ...]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from egypt_deals.http import Client, FetchError  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
reg = ROOT / 'data' / 'registry'
files = [Path(a) for a in sys.argv[1:]] or [reg / 'egypt_shops.jsonl']
out = reg / 'probe.jsonl'
done = set()
if out.exists():
    done = {json.loads(l)['domain'] for l in out.read_text(encoding='utf-8').splitlines() if l.strip()}
client = Client(ROOT / 'data' / 'cache_probe', delay=3, ttl=3600)


def attempt(url):
    try:
        body, final, _ = client.get(url, private=True)
        return body, None
    except FetchError as e:
        return None, str(e)


with out.open('a', encoding='utf-8', newline='\n') as fh:
    for f in files:
        for line in f.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            dom = r['domain'].lower().removeprefix('www.')
            if dom in done:
                continue
            base = 'https://' + dom
            res = {'domain': dom, 'platform': 'unknown', 'products_seen': None, 'errors': []}
            body, err = attempt(base + '/products.json?limit=3')
            if body:
                try:
                    p = json.loads(body).get('products')
                    if isinstance(p, list):
                        res.update(platform='shopify', products_seen=len(p))
                        if p:
                            v = (p[0].get('variants') or [{}])[0]
                            res['sample'] = [p[0].get('title'), v.get('price')]
                except ValueError:
                    pass
            else:
                res['errors'].append('shopify: ' + str(err))
            if res['platform'] == 'unknown':
                body, err = attempt(base + '/wp-json/wc/store/v1/products?per_page=2')
                if body:
                    try:
                        p = json.loads(body)
                        if isinstance(p, list):
                            res.update(platform='woo', products_seen=len(p))
                            if p:
                                res['sample'] = [p[0].get('name'), (p[0].get('prices') or {}).get('price'),
                                                 (p[0].get('prices') or {}).get('currency_code')]
                    except ValueError:
                        pass
                else:
                    res['errors'].append('woo: ' + str(err))
            fh.write(json.dumps(res, ensure_ascii=False) + '\n')
            fh.flush()
            print(dom, res['platform'], res.get('sample') or res['errors'][-1:])
client.close()
