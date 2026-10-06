import hashlib
import os
import re
import json
from urllib.parse import parse_qs, urlsplit, urlunsplit

import httpx

from .http import FetchError

def verify_pending_stock(db, root, delay=4):
    """Recheck the exact public product/variant before a queued alert is sent.

    A failed verification clears eligibility; it cannot reuse an old stock
    claim. Cached price history is not a substitute for current availability.
    """
    from .adapters import product_html
    from .http import Client
    from .model import money
    wanted = {row['listing_id'] for row in db.pending()}
    if not wanted: return {'checked': 0, 'unavailable': 0, 'failed': 0}
    sources = json.loads((root / 'sources.json').read_text())
    listings = {l.identity: l for l in db.listings()}
    registry = {s['id']: s for s in sources}
    result = {'checked': 0, 'unavailable': 0, 'failed': 0}
    client = Client(root / 'data/cache/alert-stock-checks', delay=delay, ttl=0)
    try:
        for identity in wanted:
            item = listings.get(identity)
            if item is None: continue
            source = registry.get(item.source)
            try:
                if not source or source.get('kind') in {'aggregator', 'used'}:
                    raise FetchError('No exact primary-product stock verifier')
                if source['adapter'] == 'shopify':
                    parts = urlsplit(item.url)
                    variant_id = parse_qs(parts.query).get('variant', [None])[0]
                    body, _, stamp = client.get(urlunsplit((parts.scheme, parts.netloc, parts.path + '.js', '', '')))
                    product = json.loads(body)
                    if not isinstance(product, dict): raise FetchError('Invalid Shopify product response')
                    variant = next((v for v in product.get('variants', []) if str(v.get('id')) == variant_id), None)
                    if variant is None: raise FetchError('Exact Shopify variant not found')
                    item.price_egp = money(variant.get('price')) / 100 if money(variant.get('price')) is not None else None
                    item.stock = 'in_stock' if variant.get('available') is True else 'out_of_stock' if variant.get('available') is False else 'unknown'
                    item.observed_at = item.verified_at = stamp
                else:
                    body, url, stamp = client.get(item.url)
                    parsed = product_html(body, {**source, '_scope': 'catalog'}, url, stamp)
                    exact = next((p for p in parsed if p.identity == identity), None)
                    if exact is None: raise FetchError('Exact product not found on primary page')
                    item.price_egp, item.stock = exact.price_egp, exact.stock
                    item.observed_at = item.verified_at = stamp
                    item.quality_issues = list(dict.fromkeys(item.quality_issues + exact.quality_issues))
                result['checked'] += 1
                if item.stock != 'in_stock': result['unavailable'] += 1
                with db.db:
                    db.db.execute('INSERT OR REPLACE INTO observations VALUES(?,?,?,?)', (identity, item.observed_at, item.price_egp, int(item.eligible())))
            except (FetchError, ValueError, TypeError, KeyError, httpx.InvalidURL):
                item.stock = 'unknown'
                item.verified_at = None
                result['failed'] += 1
            with db.db:
                db.db.execute('UPDATE listings SET payload=? WHERE id=?', (json.dumps(item.dict(), ensure_ascii=False), identity))
    finally:
        client.close()
    result['expired'] = db.expire_invalid()
    return result

def matches(listing, rule):
    if listing.category!=rule['category']: return False
    if rule.get('condition') and listing.condition!=rule['condition']: return False
    if rule.get('title_regex') and not re.search(rule['title_regex'],listing.raw_title,re.I): return False
    for key,expected in rule.get('specs',{}).items():
        value=listing.specs.get(key)
        if isinstance(expected,str):
            if str(value).casefold()!=expected.casefold(): return False
        elif value!=expected: return False
    return True

def detect(listings, rules, db):
    found=[]
    for l in listings:
        if not l.eligible(): continue
        laptop_watch=rules.get('laptop_watch',{})
        tracked=bool(laptop_watch and l.category=='laptop' and l.price_egp<=laptop_watch['max_egp'])
        catalog_watch=rules.get('hardware_watch',{})
        if l.category in catalog_watch.get('categories',[]) and l.price_egp<=catalog_watch.get('max_egp',70000):tracked=True
        for rule in rules['thresholds']:
            if not matches(l,rule): continue
            tracked=True
            if l.price_egp<=rule['max_egp']:
                found.append((rule['id'],l,f"{rule['label']}: {l.price_egp:,.0f} EGP (target ≤ {rule['max_egp']:,.0f})"))
        if tracked:
            drop=rules['drop']
            previous=db.previous(l,drop['hours'])
            if previous and (1-l.price_egp/previous)*100 >= drop['min_pct']-1e-9:
                found.append((drop['id'],l,f"Price down {(1-l.price_egp/previous)*100:.1f}% within 24h: {previous:,.0f} → {l.price_egp:,.0f} EGP"))
    output=[]
    for rule,l,reason in found:
        key=hashlib.sha256(f'{rule}|{l.identity}|{l.price_egp}'.encode()).hexdigest()
        message=f'{reason}\n{l.store}: {l.raw_title}\n{l.url}'
        added=db.queue(key,message,l.identity,l.price_egp)
        output.append({'rule':rule,'listing_id':l.identity,'price_egp':l.price_egp,'message':message,'new':added})
    return output

def send_pending(db):
    expired=db.expire_invalid()
    token,chat=os.environ.get('TELEGRAM_BOT_TOKEN'),os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat: return {'sent':0,'status':'credentials_missing','pending':len(db.pending())}
    if not db.pending():return {'sent':0,'status':'ok','pending':0,'expired':expired}
    count,skipped=0,0
    listings={l.identity:l for l in db.listings()}
    for row in db.pending():
        listing=listings.get(row['listing_id'])
        if listing is None or not listing.eligible() or listing.price_egp != row['price']:
            skipped+=1
            continue
        try:
            response=httpx.post(f'https://api.telegram.org/bot{token}/sendMessage',json={'chat_id':chat,'text':row['message'],'link_preview_options':{'is_disabled':True}},timeout=20)
            if response.status_code != 200 or not response.json().get('ok'):
                return {'sent':count,'status':'telegram_rejected','pending':len(db.pending())}
        except (httpx.HTTPError, ValueError):
            return {'sent':count,'status':'telegram_network_error','pending':len(db.pending())}
        db.sent(row['key'])
        count+=1
    return {'sent':count,'status':'ok','pending':len(db.pending()),'stale_skipped':skipped,'expired':expired}
