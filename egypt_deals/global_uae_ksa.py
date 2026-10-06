"""UAE and Saudi price collectors (new and used). Read only, plain HTTP, polite, robots-aware.

Probed live 2026-10-07 with egypt_deals.http.Client (honest user agent, robots.txt honoured):
  works          amazon_ae, amazon_sa (search HTML), opensooq_ae, opensooq_sa (embedded __NEXT_DATA__ JSON),
                 haraj_sa (JSON-LD search results)
  needs browser  sharaf_ae (results drawn by JavaScript from Algolia), jarir_sa (Nuxt app, no results in HTML)
  blocked        noon_ae, noon_sa, jumbo, extra_sa (robots.txt disallows the search URLs),
                 microless (robots.txt itself answers 403), dubizzle_ae (Imperva "Pardon Our Interruption" wall)
Blocked sites are never worked around: collect() returns no rows and a status saying why; the burner browser lane
(dark Chrome, port 9222) is the later route for them.

Rules kept: item price as shown; currency as shown; stock only when the page says so; condition only when the page
says so; payments only when the page says so (none of these search pages do); nothing invented.
"""
import json
import re
from urllib.parse import quote, quote_plus

from bs4 import BeautifulSoup

from .http import Client, FetchError
from .model import Listing, money, normalized, now
from . import zones

# payments_claimed: a claim needs an evidence URL; none was verified on these search pages, so it is 'unknown'.
SOURCES = {
    'amazon_ae': dict(zone='UAE', name='Amazon.ae', kind='marketplace', condition='new+renewed', currency='AED',
                      payments_claimed='unknown', base='https://www.amazon.ae', status='works'),
    'noon_ae': dict(zone='UAE', name='Noon UAE', kind='marketplace', condition='new', currency='AED',
                    payments_claimed='unknown', base='https://www.noon.com', status='blocked_robots',
                    evidence='https://www.noon.com/robots.txt: Disallow: /*/search/ and /*/search?'),
    'noon_sa': dict(zone='KSA', name='Noon Saudi', kind='marketplace', condition='new', currency='SAR',
                    payments_claimed='unknown', base='https://www.noon.com', status='blocked_robots',
                    evidence='https://www.noon.com/robots.txt: Disallow: /*/search/ and /*/search?'),
    'amazon_sa': dict(zone='KSA', name='Amazon.sa', kind='marketplace', condition='new+renewed', currency='SAR',
                      payments_claimed='unknown', base='https://www.amazon.sa', status='works'),
    'microless': dict(zone='UAE', name='Microless UAE', kind='retailer', condition='new', currency='AED',
                      payments_claimed='unknown', base='https://uae.microless.com', status='blocked_http',
                      evidence='https://uae.microless.com/robots.txt answers HTTP 403 to plain HTTP'),
    'sharaf_ae': dict(zone='UAE', name='Sharaf DG UAE', kind='retailer', condition='new', currency='AED',
                      payments_claimed='unknown', base='https://uae.sharafdg.com', status='needs_browser',
                      evidence='search page HTTP 200 but product cards are Mustache templates filled by Algolia JavaScript'),
    'jumbo': dict(zone='UAE', name='Jumbo Electronics', kind='retailer', condition='new', currency='AED',
                  payments_claimed='unknown', base='https://www.jumbo.ae', status='blocked_robots',
                  evidence='https://www.jumbo.ae/robots.txt: Disallow: /catalogsearch/ and /search?q='),
    'extra_sa': dict(zone='KSA', name='eXtra Saudi', kind='retailer', condition='new', currency='SAR',
                     payments_claimed='unknown', base='https://www.extra.com', status='blocked_robots',
                     evidence='https://www.extra.com/robots.txt: Disallow: /search and /*/search'),
    'jarir_sa': dict(zone='KSA', name='Jarir Saudi', kind='retailer', condition='new', currency='SAR',
                     payments_claimed='unknown', base='https://www.jarir.com', status='needs_browser',
                     evidence='search page HTTP 200 but the Nuxt payload holds menus only, no product results'),
    'opensooq_ae': dict(zone='UAE', name='OpenSooq UAE', kind='used', condition='used (per listing)', currency='AED',
                        payments_claimed='unknown', base='https://ae.opensooq.com', status='works'),
    'opensooq_sa': dict(zone='KSA', name='OpenSooq Saudi', kind='used', condition='used (per listing)', currency='SAR',
                        payments_claimed='unknown', base='https://sa.opensooq.com', status='works'),
    'dubizzle_ae': dict(zone='UAE', name='Dubizzle UAE', kind='used', condition='used (per listing)', currency='AED',
                        payments_claimed='unknown', base='https://uae.dubizzle.com', status='blocked_http',
                        evidence='search page HTTP 200 body is the Imperva "Pardon Our Interruption" interstitial'),
    'haraj_sa': dict(zone='KSA', name='Haraj', kind='used', condition='used (per listing)', currency='SAR',
                     payments_claimed='unknown', base='https://haraj.com.sa', status='works'),
}

SEARCH_URL = {
    'amazon_ae': lambda q: 'https://www.amazon.ae/s?k=' + quote_plus(q),
    'amazon_sa': lambda q: 'https://www.amazon.sa/s?k=' + quote_plus(q),
    'noon_ae': lambda q: 'https://www.noon.com/uae-en/search/?q=' + quote(q),
    'noon_sa': lambda q: 'https://www.noon.com/saudi-en/search/?q=' + quote(q),
    'microless': lambda q: 'https://uae.microless.com/search/?query=' + quote_plus(q),
    'sharaf_ae': lambda q: 'https://uae.sharafdg.com/?q=' + quote_plus(q) + '&post_type=product',
    'jumbo': lambda q: 'https://www.jumbo.ae/catalogsearch/result/?q=' + quote_plus(q),
    'extra_sa': lambda q: 'https://www.extra.com/en-sa/search/?text=' + quote_plus(q),
    'jarir_sa': lambda q: 'https://www.jarir.com/sa-en/catalogsearch/result/?q=' + quote_plus(q),
    'opensooq_ae': lambda q: 'https://ae.opensooq.com/en/find?term=' + quote_plus(q),
    'opensooq_sa': lambda q: 'https://sa.opensooq.com/en/find?term=' + quote_plus(q),
    'dubizzle_ae': lambda q: 'https://uae.dubizzle.com/search/?keyword=' + quote_plus(q),
    'haraj_sa': lambda q: 'https://haraj.com.sa/search/' + quote(q),
}

CURRENCY_WORDS = {'AED', 'SAR', 'USD', 'EGP'}


def wall_reason(html):
    """Name the bot wall if the page is one, else None."""
    head = html[:6000].lower()
    if 'pardon our interruption' in head:
        return 'Imperva wall ("Pardon Our Interruption")'
    if 'enter the characters you see below' in html[:20000].lower() or 'api-services-support@amazon' in html[:20000].lower():
        return 'Amazon captcha page'
    return None


def price_text(text):
    """('AED', 1519.0) from 'AED 1,519.00' (also '1,519.00 SAR'). Currency None when no code is printed."""
    text = normalized(str(text).replace('\xa0', ' '))
    code = next((w for w in re.findall(r'[A-Za-z]{3}', text) if w.upper() in CURRENCY_WORDS), None)
    if not code and 'ريال' in text: code = 'SAR'    # Arabic "riyal" as Amazon.sa prints it
    if not code and 'درهم' in text: code = 'AED'    # Arabic "dirham"
    return (code.upper() if code else None), money(text)


# ---------------------------------------------------------------- parsers: html -> list of plain dicts

def parse_amazon(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for card in soup.select('div[data-component-type="s-search-result"]'):
        asin = card.get('data-asin')
        head = card.select_one('h2')
        if not asin or not head: continue
        title = normalized(head.get('aria-label') or head.get_text(' '))
        now_price = card.select_one('.a-price:not(.a-text-price) .a-offscreen')
        old_price = card.select_one('.a-price.a-text-price .a-offscreen')
        currency, price = price_text(now_price.get_text()) if now_price else (None, None)
        _, old = price_text(old_price.get_text()) if old_price else (None, None)
        text = normalized(card.get_text(' '))
        stock, quantity = 'unknown', None
        left = re.search(r'Only (\d+) left in stock', text)
        if left: stock, quantity = 'in_stock', int(left.group(1))
        elif re.search(r'Currently unavailable', text, re.I): stock = 'out_of_stock'
        delivery = card.select_one('[data-cy="delivery-recipe"]')
        condition = 'refurbished' if re.search(r'\b(?:renewed|refurbished)\b', title, re.I) else 'unknown'
        rows.append(dict(url=base + '/dp/' + asin, title=title, price=price, currency=currency, old_price=old,
                         stock=stock, quantity=quantity, sku=asin, condition=condition,
                         delivery=normalized(delivery.get_text(' ')) if delivery else None,
                         sponsored=bool(card.select_one('.puis-sponsored-label-text'))))
    return rows


def next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


def parse_opensooq(html, base):
    data = next_data(html)
    if not data: return []
    items = ((data.get('props') or {}).get('pageProps') or {}).get('serpApiResponse', {}).get('listings', {}).get('items', [])
    rows = []
    for it in items:
        if not isinstance(it, dict) or not it.get('title') or not it.get('id'): continue
        currency, price = price_text(it.get('price_amount') or '')
        currency = it.get('price_currency_iso') or currency
        cps = ' '.join(str(x) for x in (it.get('cps') or [])).strip().lower()
        condition = 'used' if cps.startswith('used') else 'new' if cps.startswith('new') else 'unknown'
        rows.append(dict(url=f"{base}/en/search/{it['id']}", title=it['title'], price=price if price else None,
                         currency=currency, condition=condition, sku=str(it['id']),
                         description=it.get('masked_description') or '', page_updated_at=None,
                         city=it.get('city_label'), posted=it.get('posted_at'), category=it.get('highlights')))
    return rows


def parse_haraj(html, base):
    m = re.search(r'<script type="application/ld\+json" id="json-ld-search-results">(.*?)</script>', html, re.S)
    if not m: return []
    try: entries = json.loads(m.group(1))['mainEntity']['itemListElement']
    except (ValueError, KeyError, TypeError): return []
    rows = []
    for entry in entries:
        item = entry.get('item') or {}
        if item.get('@type') != 'Product' or not item.get('url') or not item.get('name'): continue
        offer = item.get('offers') or {}
        price = offer.get('price')
        price = float(price) if isinstance(price, (int, float)) and price > 0 else money(price) if isinstance(price, str) else None
        avail = str(offer.get('availability', '')).lower()
        stock = 'in_stock' if avail.endswith('instock') else 'out_of_stock' if avail.endswith('outofstock') else 'unknown'
        city = (offer.get('availableAtOrFrom') or {}).get('name')
        rows.append(dict(url=item['url'], title=item['name'], price=price or None, currency=offer.get('priceCurrency'),
                         stock=stock, description=item.get('description') or '', city=city,
                         images=[x for x in (item.get('image') or []) if isinstance(x, str)][:3]))
    return rows


PARSERS = {'amazon_ae': parse_amazon, 'amazon_sa': parse_amazon, 'opensooq_ae': parse_opensooq,
           'opensooq_sa': parse_opensooq, 'haraj_sa': parse_haraj}


# ---------------------------------------------------------------- rows -> Listing

def to_listing(source_id, row, observed, rate_usd_egp):
    meta = SOURCES[source_id]
    currency = row.get('currency') or meta['currency']   # never printed on the card: zone currency (pegged), flagged below
    listing = Listing(store=meta['name'], url=row['url'], raw_title=row['title'], price_egp=None, observed_at=observed,
                      source=source_id, source_kind=meta['kind'], stock=row.get('stock', 'unknown'),
                      quantity=row.get('quantity'), condition=row.get('condition', 'unknown'), sku=row.get('sku'),
                      delivery_time=row.get('delivery'), description=(row.get('description') or '')[:600],
                      images=row.get('images') or [])
    zones.foreign(listing, meta['zone'], rate_usd_egp, price_local=row.get('price'), currency=currency)
    if row.get('old_price') and row.get('price') and row['old_price'] > row['price']:
        listing.old_price_egp = zones.to_egp(row['old_price'], currency, rate_usd_egp)
    if listing.stock in ('in_stock', 'out_of_stock'): listing.verified_at = observed
    if row.get('currency') is None: listing.quality_issues.append('currency not printed on page; zone currency assumed')
    if meta['kind'] == 'used':
        listing.used.update({k: row[k] for k in ('city', 'posted') if row.get(k)})
    return listing.finish()


# ---------------------------------------------------------------- collection

def classify_failure(error):
    text = str(error)
    if 'robots.txt disallows' in text: return 'blocked_robots'
    if 'HTTP 403' in text or 'HTTP 429' in text or 'challenge' in text or 'paused after' in text: return 'blocked_http'
    return 'error'


def collect(source_id, queries, *, root, rate_usd_egp, max_items=60, client=None):
    """Returns (listings, status). `root` is the project folder (cache lives in root/data/cache_uae_ksa)."""
    from pathlib import Path
    meta = SOURCES[source_id]
    own = client is None
    client = client or Client(Path(root) / 'data' / 'cache_uae_ksa', delay=2.5, ttl=1800)
    client.delay = max(client.delay, 2)
    status = dict(source=source_id, name=meta['name'], zone=meta['zone'], state='unknown', started_at=now(),
                  queries_tried=0, pages_fetched=0, rows_parsed=0, listings=0, errors=[], evidence=meta.get('evidence'))
    listings, seen = [], set()
    try:
        for query in queries:
            if len(listings) >= max_items: break
            status['queries_tried'] += 1
            try:
                html, final_url, observed = client.get(SEARCH_URL[source_id](query))
            except FetchError as error:
                state = classify_failure(error)
                status['errors'].append(f'{query}: {error}')
                if state != 'error':
                    status['state'], status['evidence'] = state, status['evidence'] or str(error)
                    break
                continue
            status['pages_fetched'] += 1
            wall = wall_reason(html)
            if wall:
                status['state'], status['evidence'] = 'blocked_http', wall
                break
            parser = PARSERS.get(source_id)
            if not parser:
                status['state'] = 'needs_browser'
                status['evidence'] = f"{meta.get('evidence')}; HTTP 200, {len(html)} bytes fetched once to confirm"
                break
            rows = parser(html, meta['base'])
            status['rows_parsed'] += len(rows)
            for row in rows:
                if row['url'] in seen or row.get('price') is None: continue
                seen.add(row['url'])
                listings.append(to_listing(source_id, row, observed, rate_usd_egp))
                if len(listings) >= max_items: break
        if status['state'] == 'unknown':
            status['state'] = 'ok' if listings else ('error' if status['errors'] else 'ok_no_results')
    finally:
        if own: client.close()
    status['listings'] = len(listings)
    status['finished_at'] = now()
    return listings, status
