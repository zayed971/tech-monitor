"""Gulf and Egypt retail shops read through the already-running burner Chrome (CDP port 9222).

Decision D-009 (Zayed, 2026-10-07): shops whose robots.txt disallows search, or that draw results with JavaScript,
may be read by driving the burner Chrome like a person. Rules kept here:
  - read only, own tab (closed at the end), never logs in, never types a password, never solves a CAPTCHA;
  - at least 6 seconds between page loads on one site; at most 2 gentle scrolls per query;
  - a CAPTCHA, challenge, "unusual traffic", "access denied" or block page stops that site, is recorded, and the
    run moves on to the next site (no retry, no workaround).

Each site was looked at once in the real rendered browser (2026-10-07). Where the page loads its results from a
JSON call the browser itself makes, that JSON is parsed (it is exactly what the shop draws); otherwise the
page's own data or the labelled DOM is used:
  noon_*        DOM cards  [data-qa="plp-product-box*"]  (+ JSON-LD ItemList for the "isBuyable" flag)
  sharaf_ae     Algolia JSON the page loads (index products_index)
  jumbo         Algolia JSON the page loads after the visitor types in the search box (direct URL stays empty)
  extra_sa      Unbxd JSON the page loads
  jarir_sa      catalogv2 JSON + stock-availability JSON the page loads
  microless     Cloudflare "Just a moment" wall on the first look: recorded as a wall, never worked around
  dubizzle_ae   __NEXT_DATA__ redux payload of the search page
  dubizzle_eg   DOM cards (li > article, aria-labelled Price / Title)

Prices are exactly as shown. Currency is the printed code when there is one; many cards print only a symbol
glyph, then the zone currency is used and the listing carries a quality note. Stock only when the page says so,
payments only when the page data says so, condition only when the page says so.
"""
import json
import re
import time
from urllib.parse import quote, quote_plus, urljoin

from bs4 import BeautifulSoup

from .model import Listing, money, normalized, now
from . import zones

MIN_DELAY = 6.0
MAX_SCROLLS = 2

SOURCES = {
    'br_noon_ae': dict(zone='UAE', name='Noon UAE (burner)', kind='marketplace', currency='AED', base='https://www.noon.com',
                       site='noon', status='works'),
    'br_noon_sa': dict(zone='KSA', name='Noon Saudi (burner)', kind='marketplace', currency='SAR', base='https://www.noon.com',
                       site='noon', status='works'),
    'br_noon_eg': dict(zone='EG', name='Noon Egypt (burner)', kind='marketplace', currency='EGP', base='https://www.noon.com',
                       site='noon', status='works'),
    'br_sharaf_ae': dict(zone='UAE', name='Sharaf DG UAE (burner)', kind='retailer', currency='AED',
                         base='https://uae.sharafdg.com', site='sharaf', status='works'),
    'br_jumbo': dict(zone='UAE', name='Jumbo Electronics (burner)', kind='retailer', currency='AED',
                     base='https://www.jumbo.ae', site='jumbo', status='works'),
    'br_extra_sa': dict(zone='KSA', name='eXtra Saudi (burner)', kind='retailer', currency='SAR',
                        base='https://www.extra.com', site='extra', status='works'),
    'br_jarir_sa': dict(zone='KSA', name='Jarir Saudi (burner)', kind='retailer', currency='SAR',
                        base='https://www.jarir.com', site='jarir', status='works'),
    'br_microless': dict(zone='UAE', name='Microless UAE (burner)', kind='retailer', currency='AED',
                         base='https://uae.microless.com', site='microless', status='wall',
                         evidence='Cloudflare "Just a moment / Performing security verification" page on the first look'),
    'br_dubizzle_ae': dict(zone='UAE', name='Dubizzle UAE (burner)', kind='used', currency='AED',
                           base='https://uae.dubizzle.com', site='dubizzle_ae', status='works'),
    'br_dubizzle_eg': dict(zone='EG', name='Dubizzle Egypt (burner)', kind='used', currency='EGP',
                           base='https://www.dubizzle.com.eg', site='dubizzle_eg', status='works'),
}

NOON_PATH = {'br_noon_ae': 'uae-en', 'br_noon_sa': 'saudi-en', 'br_noon_eg': 'egypt-en'}

WALL_PATTERNS = re.compile(
    r'just a moment|performing security verification|verify(?:ing)? you are (?:a )?human|are you a (?:robot|human)|'
    r'pardon our interruption|access denied|unusual traffic|captcha|request blocked|attention required|'
    r'checking your browser|incapsula|temporarily blocked|security check', re.I)

CURRENCY_CODES = {'AED', 'SAR', 'EGP', 'USD'}


def wall_reason(title, body_head, status=None):
    """Name the wall if the loaded page is one, else None. `body_head` is the first ~1500 visible characters."""
    if status in (403, 429):
        return f'HTTP {status} on the page load'
    m = WALL_PATTERNS.search(normalized(title) + ' ' + normalized(body_head)[:1500])
    return f'wall text "{m.group(0)}"' if m else None


def _num(value):
    """Positive float from a number or a price string, else None."""
    if isinstance(value, bool) or value is None: return None
    if isinstance(value, (int, float)): return float(value) if value > 0 else None
    v = money(value)
    return v if v and v > 0 else None


def _code(text):
    return next((w.upper() for w in re.findall(r'[A-Za-z]{3}', normalized(text)) if w.upper() in CURRENCY_CODES), None)


# ---------------------------------------------------------------- parsers: page data -> list of plain dicts

def parse_noon(html, base='https://www.noon.com'):
    soup = BeautifulSoup(html, 'html.parser')
    buyable = {}
    for tag in soup.find_all('script', type='application/ld+json'):
        try: data = json.loads(tag.string or '')
        except ValueError: continue
        for item in (data.get('itemListElement') or []) if isinstance(data, dict) else []:
            if isinstance(item, dict) and item.get('url') and 'isBuyable' in item:
                buyable[item['url'].split('?')[0]] = bool(item['isBuyable'])
    rows, seen = [], set()
    for card in soup.select('[data-qa="plp-product-box"]'):
        link = card.select_one('a[href]')
        name = card.select_one('[data-qa="plp-product-box-name"]')
        price_box = card.select_one('[data-qa="plp-product-box-price"]')
        if not (link and name and price_box): continue
        url = urljoin(base, link['href'].split('?')[0])
        amount = price_box.select_one('[class*="amount"]')
        price = _num(amount.get_text() if amount else None)
        if url in seen or price is None: continue
        seen.add(url)
        old = price_box.select_one('[class*="oldPrice"]')
        currency_span = price_box.select_one('[class*="currency"]')
        text = normalized(card.get_text(' '))
        rows.append(dict(url=url, title=normalized(name.get_text(' ')), price=price,
                         currency=_code(currency_span.get_text()) if currency_span else None,
                         old_price=_num(old.get_text()) if old else None,
                         stock='in_stock' if buyable.get(url) is True else 'unknown',
                         sku=(re.search(r'/(N\d+[A-Z]?)/p/?$', url) or [None, None])[1],
                         delivery='Free Delivery' if 'Free Delivery' in text else None))
    return rows


def _algolia_hits(bodies):
    for body in bodies:
        results = body.get('results') if isinstance(body, dict) and 'results' in body else [body]
        for result in results or []:
            for hit in (result or {}).get('hits') or []:
                if isinstance(hit, dict): yield hit


def parse_sharaf(bodies, base='https://uae.sharafdg.com'):
    rows, seen = [], set()
    for hit in _algolia_hits(bodies):
        title, url, price = hit.get('post_title'), hit.get('permalink'), _num(hit.get('price'))
        if not (title and url and price) or url in seen: continue
        seen.add(url)
        offers = hit.get('promotion_offer_json') or []
        regular = next((_num(o.get('regular_price')) for o in offers if isinstance(o, dict) and o.get('is_default')), None)
        rows.append(dict(url=url, title=title, price=price, currency=None,
                         old_price=regular if regular and regular > price else None,
                         stock='in_stock' if hit.get('in_stock') == 1 else 'out_of_stock' if hit.get('in_stock') == 0 else 'unknown',
                         sku=hit.get('main_sku') or hit.get('sku')))
    return rows


def parse_jumbo(bodies, base='https://www.jumbo.ae'):
    rows, seen = [], set()
    for hit in _algolia_hits(bodies):
        title, path = hit.get('name'), hit.get('url_path')
        aed = (hit.get('price') or {}).get('AED') or {}
        price = _num(aed.get('default'))
        if not (title and path and price): continue
        url = urljoin(base + '/', path)
        if url in seen: continue
        seen.add(url)
        old = _num(hit.get('cost')) or _num(aed.get('cost_formatted'))
        rows.append(dict(url=url, title=title, price=price, currency='AED',
                         old_price=old if old and old > price else None,
                         stock='in_stock' if hit.get('in_stock') == 1 else 'out_of_stock' if hit.get('in_stock') == 0 else 'unknown',
                         sku=hit.get('sku')))
    return rows


def parse_extra(bodies, base='https://www.extra.com'):
    rows, seen = [], set()
    for body in bodies:
        for product in ((body or {}).get('response') or {}).get('products') or []:
            title = product.get('nameEn') or product.get('title')
            url, price = product.get('productUrl'), _num(product.get('sellingPrice') or product.get('price'))
            if not (title and url and price) or url in seen: continue
            seen.add(url)
            was = _num(product.get('wasPrice'))
            flag = str(product.get('inStockFlag', product.get('available', ''))).lower()
            installments = 'true' in (str(product.get('eligibleForTabby')).lower(), str(product.get('eligibleForTamara')).lower())
            rows.append(dict(url=url, title=title, price=price, currency=product.get('currency'),
                             old_price=was if was and was > price else None,
                             stock='in_stock' if flag == 'true' else 'out_of_stock' if flag == 'false' else 'unknown',
                             sku=product.get('productCode'), payments=['installments'] if installments else []))
    return rows


def parse_jarir(bodies, base='https://www.jarir.com/sa-en'):
    stock = {}
    products = []
    for body in bodies:
        data = (body or {}).get('data') if isinstance(body, dict) else None
        if isinstance(data, dict) and isinstance(data.get('hits'), dict):
            products += [h.get('_source') or {} for h in data['hits'].get('hits') or []]
        elif isinstance(data, dict) and isinstance(data.get('result'), list):
            for item in data['result']:
                if isinstance(item, dict) and 'sku_code' in item and 'stock_status' in item:
                    stock[str(item['sku_code'])] = bool(item['stock_status'])
    rows, seen = [], set()
    for src in products:
        path, title = src.get('url_path'), src.get('name')
        price = _num(src.get('jarir_final_price') or src.get('final_price') or src.get('price'))
        if not (path and title and price) or path in seen: continue
        seen.add(path)
        sku = str(src.get('GTM_sku') or src.get('sku') or '') or None
        listed = _num(src.get('price'))
        payments = []
        if src.get('cod_enable') == 1: payments.append('cod')
        if 1 in (src.get('installment_enable'), src.get('tabby_enable'), src.get('tamara_enable')): payments.append('installments')
        rows.append(dict(url=base.rstrip('/') + '/' + path.lstrip('/'), title=title, price=price, currency=None,
                         old_price=listed if listed and listed > price else None,
                         stock=('in_stock' if stock[sku] else 'out_of_stock') if sku in stock else 'unknown',
                         sku=sku, payments=payments))
    return rows


def parse_dubizzle_ae(html, base='https://uae.dubizzle.com'):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m: return []
    try: actions = json.loads(m.group(1))['props']['pageProps']['reduxWrapperActionsGIPP']
    except (ValueError, KeyError, TypeError): return []
    rows, seen = [], set()
    for action in actions:
        if not str(action.get('type', '')).startswith('listings/fetchListingDataForQuery'): continue
        for hit in (action.get('payload') or {}).get('hits') or []:
            name = (hit.get('name') or {}).get('en') if isinstance(hit.get('name'), dict) else hit.get('name')
            url = (hit.get('absolute_url') or {}).get('en') if isinstance(hit.get('absolute_url'), dict) else hit.get('absolute_url')
            price = _num(hit.get('price'))
            if not (name and url and price) or url in seen: continue
            seen.add(url)
            details = hit.get('details') or {}
            cond = ((details.get('Condition') or {}).get('en') or {}).get('value') if isinstance(details, dict) else None
            level = hit.get('stock_level')
            city = (hit.get('site') or {}).get('en') if isinstance(hit.get('site'), dict) else None
            rows.append(dict(url=url, title=name, price=price, currency='AED',
                             condition=('new' if str(cond).lower() == 'new' else 'used') if cond else 'unknown',
                             stock=level if level in ('in_stock', 'out_of_stock') else 'unknown',
                             sku=str(hit.get('id') or ''), city=city, old_price=_num(hit.get('pre_discount_price'))))
    return rows


def parse_dubizzle_eg(html, base='https://www.dubizzle.com.eg'):
    soup = BeautifulSoup(html, 'html.parser')
    rows, seen = [], set()
    for card in soup.select('li article'):
        link = card.find_parent('li').select_one('a[href*="/ad/"]') if card.find_parent('li') else None
        price_tag = card.select_one('[aria-label="Price"]')
        title_tag = card.select_one('[aria-label="Title"]')
        if not (link and price_tag and title_tag): continue
        url = urljoin(base, link['href'])
        price = _num(price_tag.get_text(' '))
        if url in seen or price is None: continue
        seen.add(url)
        rows.append(dict(url=url, title=normalized(title_tag.get_text(' ')), price=price,
                         currency=_code(price_tag.get_text(' ')), condition='unknown', stock='unknown',
                         sku=(re.search(r'ID(\d+)', url) or [None, None])[1]))
    return rows


def parse_jsonld_products(html, base=''):
    """Best-effort for shops that put Product/ItemList offers in JSON-LD (used for Microless if it is ever readable)."""
    soup = BeautifulSoup(html, 'html.parser')
    rows, seen = [], set()
    def walk(node):
        if isinstance(node, list):
            for x in node: walk(x)
        elif isinstance(node, dict):
            if node.get('@type') == 'Product' and node.get('url') and node.get('name'):
                offer = node.get('offers') or {}
                offer = offer[0] if isinstance(offer, list) and offer else offer
                price = _num(offer.get('price')) if isinstance(offer, dict) else None
                if price and node['url'] not in seen:
                    seen.add(node['url'])
                    avail = str((offer or {}).get('availability', '')).lower()
                    rows.append(dict(url=node['url'], title=node['name'], price=price, currency=offer.get('priceCurrency'),
                                     stock='in_stock' if avail.endswith('instock') else 'out_of_stock' if avail.endswith('outofstock') else 'unknown'))
            for v in node.values(): walk(v)
    for tag in soup.find_all('script', type='application/ld+json'):
        try: walk(json.loads(tag.string or ''))
        except ValueError: pass
    return rows


# ---------------------------------------------------------------- per-site browser recipe

# capture: response URLs whose JSON the page itself loads and we parse. ready: when the page has drawn results.
SITE = {
    'noon': dict(parse=parse_noon, kind='html', ready='[data-qa="plp-product-box"]'),
    'sharaf': dict(parse=parse_sharaf, kind='json', capture=re.compile(r'algolia\.net/1/indexes/\*/queries')),
    'jumbo': dict(parse=parse_jumbo, kind='json', capture=re.compile(r'algolia\.net/1/indexes/[^/]+/query')),
    'extra': dict(parse=parse_extra, kind='json', capture=re.compile(r'search\.unbxd\.io/.*/search\?')),
    'jarir': dict(parse=parse_jarir, kind='json', capture=re.compile(r'/api/catalogv2/product/|/stock/getavailability')),
    'microless': dict(parse=parse_jsonld_products, kind='html', ready='script[type="application/ld+json"]'),
    'dubizzle_ae': dict(parse=parse_dubizzle_ae, kind='html', ready='#__NEXT_DATA__'),
    'dubizzle_eg': dict(parse=parse_dubizzle_eg, kind='html', ready='li article'),
}


def search_url(source_id, query):
    site = SOURCES[source_id]['site']
    if site == 'noon': return f"https://www.noon.com/{NOON_PATH[source_id]}/search?q={quote(query)}"
    if site == 'sharaf': return 'https://uae.sharafdg.com/?q=' + quote_plus(query) + '&post_type=product'
    if site == 'extra':
        return ('https://www.extra.com/en-sa/search?q=' + quote_plus(query) + '%3Arelevance%3Atype%3APRODUCT&text='
                + quote_plus(query) + '&pg=1&pageSize=24&sort=relevance')
    if site == 'jarir': return 'https://www.jarir.com/sa-en/catalogsearch/result/?q=' + quote_plus(query)
    if site == 'microless': return 'https://uae.microless.com/search/?query=' + quote_plus(query)
    if site == 'dubizzle_ae': return 'https://uae.dubizzle.com/search/?keyword=' + quote_plus(query)
    if site == 'dubizzle_eg': return 'https://www.dubizzle.com.eg/en/ads/q-' + quote(query.replace(' ', '-')) + '/'
    if site == 'jumbo': return 'https://www.jumbo.ae/'   # the query is typed into the shop's own search box
    raise KeyError(source_id)


# ---------------------------------------------------------------- rows -> Listing

def to_listing(source_id, row, observed, rate_usd_egp):
    meta = SOURCES[source_id]
    currency = row.get('currency') or meta['currency']
    listing = Listing(store=meta['name'], url=row['url'], raw_title=row['title'], price_egp=None, observed_at=observed,
                      source=source_id, source_kind=meta['kind'], stock=row.get('stock', 'unknown'),
                      condition=row.get('condition', 'unknown'), sku=row.get('sku'),
                      delivery_time=row.get('delivery'))
    zones.foreign(listing, meta['zone'], rate_usd_egp, price_local=row['price'], currency=currency,
                  payments=row.get('payments'))
    if row.get('old_price') and row['old_price'] > row['price']:
        listing.old_price_egp = zones.to_egp(row['old_price'], currency, rate_usd_egp)
    if listing.stock in ('in_stock', 'out_of_stock'): listing.verified_at = observed
    if row.get('currency') is None: listing.quality_issues.append('currency not printed as text on the card; zone currency assumed')
    if meta['kind'] == 'used' and row.get('city'): listing.used['city'] = row['city']
    return listing.finish()


# ---------------------------------------------------------------- collection

def _sleep_until(last_load, delay):
    wait = last_load + delay - time.time()
    if wait > 0: time.sleep(wait)


def _ready(page, spec, captured):
    if spec['kind'] == 'json': return bool(captured)
    try: return page.locator(spec['ready']).count() > 0
    except Exception: return False


def _read_json(captured):
    out = []
    for response in captured:
        try: out.append(response.json())
        except Exception: pass
    return out


def collect(source_id, queries, *, root=None, rate_usd_egp=None, max_items=60, cdp='http://127.0.0.1:9222',
            delay=MIN_DELAY, page=None):
    """Returns (listings, status). Opens its own tab (or uses `page` when the runner shares one) and closes the
    tab it opened. Stops at the first wall on this site. `root` is accepted for symmetry with global_uae_ksa."""
    meta = SOURCES[source_id]
    spec = SITE[meta['site']]
    delay = max(float(delay), MIN_DELAY)
    status = dict(source=source_id, name=meta['name'], zone=meta['zone'], state='unknown', started_at=now(),
                  queries_tried=0, pages_fetched=0, rows_parsed=0, listings=0, errors=[], evidence=meta.get('evidence'))
    listings, seen = [], set()
    own_playwright = None
    own_page = page is None
    try:
        if page is None:
            from playwright.sync_api import sync_playwright
            own_playwright = sync_playwright().start()
            browser = own_playwright.chromium.connect_over_cdp(cdp)
            page = browser.contexts[0].new_page()    # our own tab only
            try: page.set_viewport_size({'width': 1366, 'height': 900})   # a new tab can come up 2 px tall; size our tab only
            except Exception: pass
        captured = []
        if spec['kind'] == 'json':
            page.on('response', lambda r: captured.append(r) if spec['capture'].search(r.url) else None)
        last_load = 0.0
        for query in queries:
            if len(listings) >= max_items: break
            status['queries_tried'] += 1
            del captured[:]
            _sleep_until(last_load, delay)
            try:
                response = page.goto(search_url(source_id, query), wait_until='domcontentloaded', timeout=60000)
                last_load = time.time()
                status['pages_fetched'] += 1
                time.sleep(4)
                if meta['site'] == 'jumbo':
                    box = page.locator('input.search-textbox:visible').first
                    box.wait_for(state='visible', timeout=25000)
                    box.click(timeout=15000)
                    page.keyboard.type(query, delay=90); time.sleep(1); page.keyboard.press('Enter')
                reason = wall_reason(page.title(), page.evaluate("() => (document.body ? document.body.innerText : '').slice(0, 1500)"),
                                     response.status if response else None)
                if reason:
                    status['state'], status['evidence'] = 'wall', reason + ' at ' + page.url.split('?')[0]
                    break
                for _ in range(18):                      # wait for the shop to draw its results
                    if _ready(page, spec, captured): break
                    time.sleep(1)
                for _ in range(MAX_SCROLLS):             # gentle scrolling, at most twice
                    page.mouse.wheel(0, 900); time.sleep(2.5)
                time.sleep(1.5)
                rows = spec['parse'](_read_json(captured) if spec['kind'] == 'json' else page.content())
            except Exception as error:
                status['errors'].append(f'{query}: {type(error).__name__}: {str(error)[:120]}')
                continue
            status['rows_parsed'] += len(rows)
            observed = now()
            for row in rows:
                if row['url'] in seen or row.get('price') is None: continue
                seen.add(row['url'])
                listings.append(to_listing(source_id, row, observed, rate_usd_egp))
                if len(listings) >= max_items: break
        if status['state'] == 'unknown':
            status['state'] = 'ok' if listings else ('error' if status['errors'] else 'ok_no_results')
    except Exception as error:
        status['state'] = 'error'
        status['errors'].append(f'{type(error).__name__}: {str(error)[:160]}')
    finally:
        if own_page and page is not None:
            try: page.close()
            except Exception: pass
        if own_playwright is not None:
            try: own_playwright.stop()
            except Exception: pass
    status['listings'] = len(listings)
    status['finished_at'] = now()
    return listings, status
