"""Verify RAM candidates from live public product pages and exact variants."""
import json
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

from egypt_deals.adapters import product_html, shopify
from egypt_deals.http import Client, FetchError
from egypt_deals.model import money

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT / 'data/ram-selected.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/ram-shortlist-verification.json')
    args = parser.parse_args()
    selected = json.loads(args.input.read_text())
    registry = {s['id']: s for s in json.loads((ROOT / 'sources.json').read_text())}
    groups = {}
    for row in selected:
        groups.setdefault(row['source'], []).append(row)

    def verify(group):
        source_id, rows = group
        source = {**registry[source_id], '_scope': 'catalog'}
        client = Client(ROOT / 'data/cache/ram-shortlist' / source_id, delay=4, ttl=0)
        results = []
        try:
            for row in rows:
                result = {'id': row['id'], 'url': row['url'], 'store': row['store'], 'previous_price_egp': row['price_egp']}
                try:
                    parts = urlsplit(row['url'])
                    if source['adapter'] == 'shopify':
                        target = urlunsplit((parts.scheme, parts.netloc, parts.path + '.js', '', ''))
                        body, _, stamp = client.get(target)
                        data = json.loads(body)
                        variant_id = parse_qs(parts.query).get('variant', [None])[0]
                        variant = next((v for v in data['variants'] if str(v['id']) == variant_id), None)
                        if variant is None: raise FetchError('Exact variant missing')
                        v = {**variant, 'price': money(variant.get('price')) / 100 if money(variant.get('price')) is not None else None,
                             'compare_at_price': money(variant.get('compare_at_price')) / 100 if money(variant.get('compare_at_price')) is not None else None}
                        parsed = shopify({'products': [{'title': data['title'], 'handle': parts.path.rsplit('/', 1)[-1],
                            'body_html': data.get('description'), 'vendor': data.get('vendor'), 'images': [], 'variants': [v]}]}, source, stamp)
                    else:
                        body, final, stamp = client.get(row['url'])
                        parsed = product_html(body, source, final, stamp)
                    # Retailers may embed an older Product block inside a
                    # description before the platform's current product data.
                    # Match the collector's final-per-identity precedence.
                    matching = [p for p in parsed if p.identity == row['id']]
                    exact = matching[-1] if matching else None
                    if exact is None: raise FetchError('Exact primary listing missing')
                    capacity_matches = exact.specs.get('ram_gb') == row['specs'].get('ram_gb') if row['category'] == 'ram' else exact.category == row['category']
                    type_matches = exact.specs.get('ram_type') == row['specs'].get('ram_type') if row['category'] == 'ram' else True
                    result.update(checked_at=stamp, stock=exact.stock, price_egp=exact.price_egp,
                                  status='confirmed' if exact.eligible() and capacity_matches and type_matches else 'excluded',
                                  listing=exact.dict())
                except (FetchError, ValueError, TypeError, KeyError) as error:
                    result.update(status='failed', reason=str(error))
                results.append(result)
                print(json.dumps({k: result.get(k) for k in ['id', 'store', 'status', 'stock', 'price_egp', 'reason']}), flush=True)
        finally:
            client.close()
        return results

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [r for group in pool.map(verify, groups.items()) for r in group]
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
