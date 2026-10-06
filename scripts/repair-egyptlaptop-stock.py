"""Repair stock from saved primary-page evidence without inventing fetch times.

Run with the monitor stopped. Its exclusive lock prevents concurrent writes
from the old parser while cached evidence is applied to existing listings.
"""
import fcntl
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from egypt_deals.adapters import jsonld
from egypt_deals.catalog_report import export_hardware
from egypt_deals.laptop_review import export_under_budget
from egypt_deals.model import now
from egypt_deals.storage import Database


def main():
    root = Path(__file__).resolve().parents[1]
    with (root / 'data/monitor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = next(s for s in json.loads((root / 'sources.json').read_text()) if s['id'] == 'egyptlaptop')
        source = {**source, '_scope': 'catalog'}
        db = Database(root / 'data/deals.sqlite3')
        changes, counts = [], Counter()
        try:
            listings = db.listings()
            for item in listings:
                if item.source != source['id']: continue
                counts['examined'] += 1
                path = root / 'data/cache/egyptlaptop' / (hashlib.sha256(item.url.encode()).hexdigest() + '.json')
                if not path.exists():
                    counts['missing_cached_page'] += 1
                    # Previously inferred stock is untrusted until re-fetched.
                    if item.stock == 'in_stock':
                        item.stock = 'unknown'
                        changes.append({'id': item.identity, 'url': item.url, 'old_stock': 'in_stock', 'stock': 'unknown', 'reason': 'no saved primary-page stock evidence'})
                else:
                    saved = json.loads(path.read_text())
                    scripts = re.findall(r'<script\b[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script\s*>', saved['body'], re.I | re.S)
                    # Parsing only structured blocks keeps the bulk repair
                    # quick; negative primary badges provide an extra veto.
                    structured = ''.join('<script type="application/ld+json">' + value + '</script>' for value in scripts)
                    parsed = jsonld(structured, source, saved['url'], saved['observed_at'])
                    exact = next((p for p in parsed if p.identity == item.identity), None)
                    new_stock = exact.stock if exact else 'unknown'
                    primary_id = re.search(r'name=[\"\']product_data\[(\d+)\]\[product_id\][\"\']', saved['body'])
                    if primary_id and re.search(r'id=[\"\']out_of_stock_info_' + primary_id.group(1) + r'[\"\']', saved['body']):
                        new_stock = 'out_of_stock'
                    old_stock = item.stock
                    item.stock = new_stock
                    if exact:
                        item.sku = item.sku or exact.sku
                        item.mpn = item.mpn or exact.mpn
                    counts['parsed_cached_pages'] += 1
                    if old_stock != new_stock:
                        changes.append({'id': item.identity, 'url': item.url, 'old_stock': old_stock, 'stock': new_stock,
                                        'evidence_observed_at': saved['observed_at'], 'reason': 'primary product structured data / badge'})
                with db.db:
                    db.db.execute('UPDATE listings SET payload=? WHERE id=?', (json.dumps(item.dict(), ensure_ascii=False), item.identity))
                    if item.stock != 'in_stock':
                        # Historical eligibility was inferred by the faulty
                        # parser and must not feed price-drop comparisons.
                        db.db.execute('UPDATE observations SET eligible=0 WHERE listing_id=?', (item.identity,))
                        db.db.execute('UPDATE alerts SET expired_at=? WHERE listing_id=? AND expired_at IS NULL', (now(), item.identity))
                if counts['examined'] % 500 == 0: print(json.dumps({'repair_progress': dict(counts)}), flush=True)
            counts['stock_changes'] = len(changes)
            counts['in_stock_to_unavailable'] = sum(c['old_stock'] == 'in_stock' and c['stock'] != 'in_stock' for c in changes)
            report = {'completed_at': now(), 'fetch_timestamps_preserved': True, **dict(counts), 'changes': changes}
            (root / 'data/stock-repair.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
            export_under_budget(listings, root)
            export_hardware(listings, root, db.statuses())
            print(json.dumps({k: v for k, v in report.items() if k != 'changes'}), flush=True)
        finally:
            db.close()


if __name__ == '__main__': main()
