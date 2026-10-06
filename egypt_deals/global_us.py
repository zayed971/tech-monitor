"""US price collectors (zone US): stores and marketplaces, new and used/refurbished.

Route: Zayed orders from a US store to a UAE address; the UAE traveler carries it to Egypt. Item prices stay in USD as shown
(`price_local`), converted to EGP with the stated rate; landed cost stays unconfirmed (see zones.py).

Probe results of 2026-10-07 (plain HTTP, polite, robots honoured; nothing worked around). Re-probed on every run, because
`collect` for a blocked source makes ONE request and records what came back:
  works         wisetek (Shopify JSON), techmikeny (JSON-LD on collection pages), pcliquidations (category pages),
                reddit_hardwareswap (only through the burner dark Chrome, own tab, read only)
  blocked       ebay (robots disallows /sch/, 403), amazon (503 bot wall), newegg (403 challenge), bh (robots + 403),
                microcenter (403), swappa (403), backmarket (robots disallows)
  no data       bestbuy (country-selector page for a non-US visitor, no products), laptopoutlet (legacy catalog of
                Windows 95/98/XP laptops, nothing in scope)
Rules kept: unknown stays unknown (stock, condition, payments, shipping to UAE); verified_at only when the page states stock.
"""
import json
import re
import time
from urllib.parse import quote, urljoin, urlsplit

from bs4 import BeautifulSoup

from . import zones
from .adapters import clean, nodes, schema_type, stock as schema_stock
from .http import Client, FetchError
from .model import Listing, money, normalized, now

CDP_URL = 'http://127.0.0.1:9222'
PROBED = '2026-10-07'
UAE_UNKNOWN = 'unknown (no shipping page checked states UAE; wisetek faq + shipping-policy do not mention it)'


def _src(name, kind, condition, method, probe_url, base, verdict, evidence, **extra):
    d = dict(zone='US', name=name, kind=kind, condition=condition, currency='USD', method=method, probe_url=probe_url,
             base=base, verdict_2026_10_07=verdict, evidence=evidence, payments_claimed='unknown',
             ships_to_uae='unknown')
    d.update(extra)
    return d


SOURCES = {
    'us_ebay': _src('eBay US', 'marketplace', 'mixed', 'probe', 'https://www.ebay.com/sch/i.html?_nkw=rtx+3060+12gb&LH_BIN=1',
                    'https://www.ebay.com', 'blocked',
                    'robots.txt disallows /sch/ for this agent; plain GET returned HTTP 403 (2026-10-07)'),
    'us_amazon': _src('Amazon US', 'marketplace', 'mixed', 'probe', 'https://www.amazon.com/s?k=rtx+3060+12gb',
                      'https://www.amazon.com', 'blocked', 'plain GET returned HTTP 503 bot wall (2026-10-07)'),
    'us_newegg': _src('Newegg', 'marketplace', 'mixed', 'probe', 'https://www.newegg.com/p/pl?d=rtx+3060+12gb',
                      'https://www.newegg.com', 'blocked', 'HTTP 403 with an access challenge page (2026-10-07)'),
    'us_bh': _src('B&H Photo Video', 'shop', 'new+refurb', 'probe', 'https://www.bhphotovideo.com/c/search?q=rtx+3060+12gb',
                  'https://www.bhphotovideo.com', 'blocked', 'robots.txt disallows the search path; HTTP 403 challenge (2026-10-07)'),
    'us_microcenter': _src('Micro Center', 'shop', 'new+open-box', 'probe',
                           'https://www.microcenter.com/search/search_results.aspx?Ntt=rtx+3060+12gb',
                           'https://www.microcenter.com', 'blocked', 'robots.txt and pages return HTTP 403 challenge (2026-10-07)'),
    'us_bestbuy': _src('Best Buy', 'shop', 'new+open-box', 'probe', 'https://www.bestbuy.com/site/searchpage.jsp?st=rtx+3060+12gb',
                       'https://www.bestbuy.com', 'no_data',
                       'HTTP 200 but the page is the "Best Buy International: Select your Country" landing page, no products '
                       '(visitor outside the US); a US IP or the burner browser would be needed'),
    'us_backmarket': _src('Back Market', 'refurb', 'refurbished', 'probe', 'https://www.backmarket.com/en-us/search?q=laptop+rtx',
                          'https://www.backmarket.com', 'blocked', 'robots.txt disallows the search path; HTTP 403 (2026-10-07)'),
    'us_swappa': _src('Swappa', 'marketplace', 'used', 'probe', 'https://swappa.com/search?q=rtx', 'https://swappa.com',
                      'blocked', 'robots.txt and pages return HTTP 403 challenge (2026-10-07)'),
    'us_laptopoutlet': _src('LaptopOutlet.com', 'refurb-store', 'used/refurb', 'probe', 'https://laptopoutlet.com/',
                            'https://laptopoutlet.com', 'no_data',
                            'robots allows; home page lists Windows 95/98/XP-era laptops, no search, no structured data, '
                            'nothing in scope (2026-10-07)'),
    'us_wisetek': _src('Wisetek Market', 'refurb-store', 'refurbished', 'shopify_json',
                       'https://www.wisetekmarket.com/products.json?limit=250&page=1', 'https://www.wisetekmarket.com',
                       'works', 'Shopify /products.json is public and robots allows it; availability flag per variant',
                       ships_to_uae=UAE_UNKNOWN),
    'us_techmikeny': _src('TechMikeNY', 'refurb-store', 'used/refurb', 'ld_collections', 'https://techmikeny.com/collections/graphics-cards',
                          'https://techmikeny.com', 'works',
                          'robots disallows /search but allows /collections/<name>; Product JSON-LD with price and '
                          'availability sits on the collection pages',
                          collections=['graphics-cards', 'laptops', 'memory', 'monitors', 'hard-drives', 'desktops']),
    'us_pcliquidations': _src('PCLiquidations', 'refurb-store', 'refurbished', 'pcl_category',
                              'https://www.pcliquidations.com/refurbished-laptops', 'https://www.pcliquidations.com',
                              'works', 'robots disallows /-search/ and criteria URLs; plain category pages with ?start=N list '
                              'title, price and spec lines',
                              categories=['refurbished-laptops', 'refurbished-desktop-computers', 'refurbished-monitors']),
    'us_reddit_hardwareswap': _src('Reddit r/hardwareswap', 'used-p2p', 'used', 'reddit_cdp',
                                   'https://old.reddit.com/r/hardwareswap/search?q=rtx+3060&restrict_sr=1&sort=new',
                                   'https://old.reddit.com', 'needs_burner_browser',
                                   'plain HTTP and the public JSON are redirected to a login wall and disallowed by robots; '
                                   'only the burner dark Chrome (CDP 9222), own tab, read only',
                                   payments_claimed='per post only (PayPal G&S recorded when the post says so)'),
}

# ---------------------------------------------------------------------------------------------- matching

_STOP = {'inch', 'kit', 'the', 'a', 'for', 'and'}


def _norm(text):
    t = normalized(text).lower().replace('"', ' inch ').replace('″', ' inch ')
    t = re.sub(r'(\d)\s+(gb|tb)\b', r'\1\2', t)
    t = re.sub(r'(rtx|gtx|rx|ddr)\s+(\d)', r'\1\2', t)
    return t


def _tokens(query):
    return [x for x in re.findall(r'[a-z0-9.]+', _norm(query).replace('rtx ', 'rtx')) if x not in _STOP]


def matches(text, queries):
    """True when every meaningful word of at least one query appears in the text. No queries means keep everything."""
    if not queries: return True
    hay = _norm(text)
    hay_words = set(re.findall(r'[a-z0-9.]+', hay))
    for q in queries:
        toks = _tokens(q)
        if toks and all((t in hay_words) or (t in hay) for t in toks): return True
    return False


# ---------------------------------------------------------------------------------------------- common bits

def _listing(source_id, title, url, price, observed, *, condition='unknown', stock='unknown', rate, verified=False,
             description='', brand=None, sku=None, mpn=None, images=None, old_price=None, seller_kind=None, payments=None,
             ships_to_uae='unknown', extra_used=None, page_updated_at=None):
    meta = SOURCES[source_id]
    item = Listing(store=meta['name'], url=url, raw_title=title, price_egp=None, observed_at=observed, source=source_id,
                   source_kind=seller_kind or ('used' if meta['kind'] == 'used-p2p' else 'retailer'), currency='USD',
                   stock=stock, verified_at=observed if (verified and stock != 'unknown') else None, condition=condition,
                   description=description, brand=brand, sku=sku, mpn=mpn, images=list(images or []),
                   page_updated_at=page_updated_at)
    zones.foreign(item, 'US', rate, price_local=price, currency='USD', payments=payments)
    if old_price: item.old_price_egp = zones.to_egp(old_price, 'USD', rate)
    item.finish()
    item.used = {**item.used, 'ships_to_uae': ships_to_uae, **(extra_used or {})}
    return item


def _status(source_id, **kw):
    s = dict(source=source_id, zone='US', name=SOURCES[source_id]['name'], verdict=None, evidence='', requests=0,
             parsed=0, kept=0, probe_url=SOURCES[source_id]['probe_url'], at=now(), ships_to_uae=SOURCES[source_id]['ships_to_uae'])
    s.update(kw)
    return s


def _classify_fetch_error(err):
    text = str(err)
    if 'robots.txt disallows' in text: return 'blocked', 'robots.txt disallows this URL for our agent'
    if 'HTTP 403' in text or 'HTTP 429' in text or 'HTTP 503' in text or 'HTTP 401' in text or 'challenge' in text or 'paused' in text:
        return 'blocked', text
    return 'error', text


def _get(client, url, status):
    status['requests'] = status.get('requests', 0) + 1
    return client.get(url)


def _ld_products(html, base_url, source_id, observed, rate):
    """Product JSON-LD offers, price/currency/availability exactly as the page states them."""
    out = []
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.select('script[type="application/ld+json"]'):
        try: data = json.loads(tag.get_text())
        except (ValueError, TypeError): continue
        for p in nodes(data):
            if not schema_type(p.get('@type'), 'Product') or not p.get('name'): continue
            offers = p.get('offers') or {}
            offers = [offers] if isinstance(offers, dict) else offers if isinstance(offers, list) else []
            for o in offers:
                if not isinstance(o, dict) or schema_type(o.get('@type'), 'AggregateOffer'): continue
                price = money(o.get('price'))
                if price is None or (o.get('priceCurrency') or 'USD') != 'USD': continue
                desc = clean(p.get('description', ''))
                state = schema_stock(o.get('availability'))
                item_cond = str(o.get('itemCondition', '')).lower()
                cond = 'used' if 'usedcondition' in item_cond else 'refurbished' if 'refurbishedcondition' in item_cond \
                    else 'new' if 'newcondition' in item_cond else 'unknown'
                if cond == 'unknown' and re.search(r'signs of (?:light |moderate |heavy )?use\b', desc, re.I): cond = 'used'
                images = p.get('image', [])
                images = [images] if isinstance(images, str) else images if isinstance(images, list) else []
                brand = p.get('brand')
                brand = brand.get('name') if isinstance(brand, dict) else brand
                url = urljoin(base_url, o.get('url') or p.get('url') or base_url)
                out.append(_listing(source_id, str(p['name']), url, price, observed, condition=cond, stock=state, rate=rate,
                                    verified=True, description=desc, sku=p.get('sku'), mpn=p.get('mpn'), images=images,
                                    brand=brand if brand and str(brand).lower() != SOURCES[source_id]['name'].lower() else None))
    return out


# ---------------------------------------------------------------------------------------------- Wisetek (Shopify JSON)

def parse_shopify_json(data, source_id, observed, rate, queries=None):
    base = SOURCES[source_id]['base']
    out = []
    for p in data.get('products', []):
        title = p.get('title') or ''
        desc = clean(p.get('body_html'))
        if not matches(title + ' ' + ' '.join(p.get('tags') or []) + ' ' + desc[:600], queries): continue
        for v in p.get('variants', []):
            price = money(v.get('price'))
            if price is None: continue
            suffix = '' if v.get('title') in {None, 'Default Title'} else ' - ' + v['title']
            avail = v.get('available')
            state = 'in_stock' if avail is True else 'out_of_stock' if avail is False else 'unknown'
            out.append(_listing(
                source_id, title + suffix, base + '/products/' + quote(p.get('handle', ''), safe='-._~%') + '?variant=' + str(v.get('id')),
                price, observed, stock=state, verified=True, rate=rate, description=desc, brand=p.get('vendor'), sku=v.get('sku'),
                images=[i['src'] for i in p.get('images', []) if 'src' in i], old_price=money(v.get('compare_at_price')),
                page_updated_at=p.get('updated_at')))
    return out


def _collect_shopify(source_id, queries, client, rate, max_items, status, max_pages=12):
    base = SOURCES[source_id]['base']
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        text, final, observed = _get(client, f'{base}/products.json?limit=250&page={page}', status)
        data = json.loads(text)
        products = data.get('products', [])
        status['parsed'] += len(products)
        for it in parse_shopify_json(data, source_id, observed, rate, queries):
            if it.url not in seen:
                seen.add(it.url); out.append(it)
        if len(products) < 250 or len(out) >= max_items: break
    return out


# ---------------------------------------------------------------------------------------------- TechMikeNY (collection JSON-LD)

def _collect_collections(source_id, queries, client, rate, max_items, status, max_pages=4):
    meta = SOURCES[source_id]
    out, seen = [], set()
    for name in meta['collections']:
        for page in range(1, max_pages + 1):
            url = f"{meta['base']}/collections/{name}" + (f'?page={page}' if page > 1 else '')
            try: text, final, observed = _get(client, url, status)
            except FetchError as e:
                if page == 1: raise
                break
            items = _ld_products(text, final, source_id, observed, rate)
            status['parsed'] += len(items)
            new = 0
            for it in items:
                if it.url in seen: continue
                seen.add(it.url); new += 1
                if matches(it.raw_title + ' ' + it.description, queries): out.append(it)
            if not new or len(out) >= max_items: break
        if len(out) >= max_items: break
    return out


# ---------------------------------------------------------------------------------------------- PCLiquidations (category pages)

def parse_pcl_category(html, source_id, observed, rate, queries=None):
    base = SOURCES[source_id]['base']
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for card in soup.select('div.item_square-medium'):
        link = card.select_one('h3.item_title a') or card.select_one('a.item_image')
        img = card.select_one('a.item_image img')
        if not link or not link.get('href'): continue
        # The visible title is cut with "..."; the image alt carries the full title.
        title = normalized((img.get('alt') if img and img.get('alt') else '') or link.get('title', '').removeprefix('More information on ') or link.get_text())
        price_box = card.select_one('.browseLinePrice')
        prices = [money(x) for x in re.findall(r'\$\s*[\d,]+(?:\.\d+)?', price_box.get_text(' ')) ] if price_box else []
        prices = [x for x in prices if x is not None]
        if not prices: continue
        strike = card.select_one('.browsePriceStrike')
        specs = ' '.join(f"{n.get_text(strip=True)}: {v.get_text(strip=True)}" for n, v in
                         zip(card.select('.spec-name'), card.select('.spec-value')))
        all_types = card.get('x-all-types', '')
        in_types = card.get('x-in-types', '')
        cond = 'refurbished' if 'grade' in all_types.lower() else 'new' if all_types.strip().lower() == 'new' else 'unknown'
        note = specs
        if len(prices) > 1: note += f' | price range on page: ${min(prices):,.2f} - ${max(prices):,.2f} (lowest recorded)'
        if all_types: note += f' | grades listed: {all_types}; grades marked in: {in_types}'
        if not matches(title + ' ' + specs, queries): continue
        out.append(_listing(source_id, title, urljoin(base, link['href']), min(prices), observed, condition=cond, rate=rate,
                            description=note, old_price=money(strike.get_text()) if strike else None,
                            images=[img['src']] if img and img.get('src') else []))
    return out


def _collect_pcl(source_id, queries, client, rate, max_items, status, max_pages=4):
    meta = SOURCES[source_id]
    out, seen = [], set()
    for cat in meta['categories']:
        for page in range(max_pages):
            url = f"{meta['base']}/{cat}" + (f'?start={24 * page}' if page else '')
            text, final, observed = _get(client, url, status)
            status['parsed'] += text.count('class="item_square-medium')
            items = parse_pcl_category(text, source_id, observed, rate, queries)
            new = [i for i in items if i.url not in seen]
            seen.update(i.url for i in new); out.extend(new)
            if text.count('class="item_square-medium') < 24 or len(out) >= max_items: break
        if len(out) >= max_items: break
    return out


# ---------------------------------------------------------------------------------------------- Reddit (burner Chrome, CDP)

SCAM = re.compile(r'reshipp|parcel[- ]forward|freight[- ]forward|package[- ]forward|ship7|friends\s*(?:and|&)\s*family|'
                  r'f\s*&\s*f\b|no\s*(?:buyer)?\s*protection|western union|wire transfer|gift ?card|zelle only|crypto only', re.I)
MULTI = re.compile(r'part(?:ing|s)?[- ]out|bundle|lot of|multiple (?:gpus|items|laptops)|\bx\d\s*(?:rtx|gtx)|'
                   r'\d\s*x\s*(?:rtx|gtx)|everything must go|clearing out', re.I)
BROKEN = re.compile(r'for parts|not working|broken|cracked|defective|as[- ]is|no (?:post|display)|dead\b', re.I)


def parse_reddit_cards(html):
    out = []
    for m in re.finditer(r'data-fullname="(t3_\w+)"><div><header class="search-result-header">'
                         r'<span class="linkflairlabel[^"]*"[^>]*>([^<]*)</span>'
                         r'<a href="([^"]+)"[^>]*>([^<]+)</a></header>'
                         r'<div class="search-result-meta">.*?<a href="[^"]*/user/([^"/]+)"[^>]*>.*?'
                         r'title="Trades:\s*(\w+)"', html, re.S):
        post_id, flair, url, title, author, trades = m.groups()
        nxt = html.find('data-fullname="t3_', m.end())
        body_html = html[m.end():nxt if nxt > 0 else m.end() + 8000]
        bm = re.search(r'<div class="md">(.*?)</div>\s*</div>\s*</div>', body_html, re.S)
        body = re.sub(r'<[^>]+>', ' ', bm.group(1)) if bm else ''
        body = re.sub(r'&amp;', '&', re.sub(r'\s+', ' ', body)).strip()
        out.append(dict(id=post_id, flair=flair.strip(), url=url, title=title.strip().replace('&amp;', '&'), author=author,
                        trades=trades, body=body[:2000]))
    return out


def reddit_listing(card, observed, rate, drops=None):
    """Card -> Listing, or None (dropped; reason counted in `drops`). Only SELLING posts, scam pattern removed."""
    drops = drops if drops is not None else {}
    def drop(why):
        drops[why] = drops.get(why, 0) + 1
        return None
    text = card['title'] + ' | ' + card['body']
    if card['flair'].upper() != 'SELLING': return drop('not selling (wanted/buying/other)')
    if SCAM.search(text): return drop('scam pattern')
    if re.match(r'^\d+$', card.get('trades', '')): trades = int(card['trades'])
    else: trades = 0 if card.get('trades', '').lower() in ('none', '') else 1
    if trades == 0: return drop('zero trade history')
    if BROKEN.search(text): return drop('parts/broken')
    if MULTI.search(text): return drop('multi-item post (price unreliable)')
    amounts = {float(x.replace(',', '')) for x in re.findall(r'\$\s?([\d,]{2,6})(?:\.\d{2})?\b', text)}
    if not amounts: return drop('no price stated')
    if len(amounts) > 2: return drop('several prices in one post (price unreliable)')
    pm = re.search(r'\$\s?([\d,]{2,6})(?:\.\d{2})?\b', text)
    price = float(pm.group(1).replace(',', ''))
    if price <= 30: return drop('price out of range')
    low = text.lower()
    cond = 'new' if re.search(r'\b(?:sealed|brand new|bnib|new in box)\b', low) else 'unknown'
    payments = ['paypal'] if re.search(r'paypal\s*(?:g\s*&\s*s|goods)|goods\s*(?:and|&)\s*services', low) else None
    url = card['url'] if card['url'].startswith('http') else 'https://old.reddit.com' + card['url']
    return _listing('us_reddit_hardwareswap', card['title'], url, price, observed, condition=cond, stock='unknown', rate=rate,
                    description=card['body'], payments=payments, seller_kind='used',
                    extra_used=dict(seller_trades_flair=card.get('trades'), flair='SELLING', price_source='first $ amount in title/body'))


def _collect_reddit(source_id, queries, rate, max_items, status, delay):
    from playwright.sync_api import sync_playwright
    out, seen, drops = [], set(), {}
    with sync_playwright() as p:
        try: browser = p.chromium.connect_over_cdp(CDP_URL, timeout=8000)
        except Exception as e:
            status.update(verdict='needs_burner_browser', evidence=f'burner dark Chrome not reachable at {CDP_URL} ({type(e).__name__}); start launch-agent-chrome.ps1')
            return out
        page = browser.contexts[0].new_page()
        try:
            for q in queries:
                url = f"https://old.reddit.com/r/hardwareswap/search?q={quote(q).replace('%20', '+')}&restrict_sr=1&sort=new"
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=25000)
                    page.wait_for_timeout(1500)
                    html = page.content()
                    status['requests'] += 1
                except Exception as e:
                    status.setdefault('errors', []).append(f'{q}: {type(e).__name__}')
                    continue
                if 'reddit.com/login' in page.url or 'log in' in page.title().lower():
                    status.update(verdict='needs_burner_browser', evidence='burner Chrome is logged out of Reddit; stopped, tell Zayed (no login attempted)')
                    break
                observed = now()
                cards = parse_reddit_cards(html)
                status['parsed'] += len(cards)
                for c in cards:
                    if c['id'] in seen: continue
                    seen.add(c['id'])
                    if not matches(c['title'], queries):
                        drops['query words not in title'] = drops.get('query words not in title', 0) + 1
                        continue
                    it = reddit_listing(c, observed, rate, drops)
                    if it: out.append(it)
                if len(out) >= max_items: break
                time.sleep(max(delay, 2.5))
        finally:
            page.close()
            try: browser.close()  # detaches from CDP; the Chrome process itself keeps running
            except Exception: pass
    status['dropped'] = drops
    status['via_burner_browser'] = True
    return out


# ---------------------------------------------------------------------------------------------- probe-only sources

def _collect_probe(source_id, client, rate, status):
    """One live request. If a blocked/empty site ever starts returning Product JSON-LD, those offers are kept."""
    meta = SOURCES[source_id]
    text, final, observed = _get(client, meta['probe_url'], status)
    title = BeautifulSoup(text, 'html.parser').title
    status['page_title'] = normalized(title.get_text()) if title else ''
    items = _ld_products(text, final, source_id, observed, rate)
    status['parsed'] = len(items)
    if not items:
        status.update(verdict='no_data', evidence=f"HTTP 200 but no product data on the probe page (title: {status['page_title'][:80]!r}); {meta['evidence']}")
    return items


# ---------------------------------------------------------------------------------------------- entry point

def collect(source_id, queries, *, root, rate_usd_egp, max_items=200, client=None, delay=3.0):
    """Returns (listings, status). status['verdict'] is works | blocked | needs_burner_browser | no_data | error."""
    if source_id not in SOURCES: raise KeyError(source_id)
    from pathlib import Path
    meta = SOURCES[source_id]
    status = _status(source_id, queries=list(queries or []))
    own = client is None
    if own: client = Client(Path(root) / 'data' / 'cache' / 'us', delay=max(2.0, delay))
    listings = []
    try:
        method = meta['method']
        if method == 'shopify_json': listings = _collect_shopify(source_id, queries, client, rate_usd_egp, max_items, status)
        elif method == 'ld_collections': listings = _collect_collections(source_id, queries, client, rate_usd_egp, max_items, status)
        elif method == 'pcl_category': listings = _collect_pcl(source_id, queries, client, rate_usd_egp, max_items, status)
        elif method == 'reddit_cdp': listings = _collect_reddit(source_id, queries or ['rtx'], rate_usd_egp, max_items, status, delay)
        else: listings = _collect_probe(source_id, client, rate_usd_egp, status)
    except FetchError as e:
        verdict, evidence = _classify_fetch_error(e)
        status.update(verdict=verdict, evidence=f'{evidence} (probe {meta["probe_url"]})')
    except (ValueError, KeyError) as e:
        status.update(verdict='error', evidence=f'unexpected page shape: {type(e).__name__}: {e}')
    finally:
        if own: client.close()
    listings = listings[:max_items]
    status['kept'] = len(listings)
    if status['verdict'] is None:
        status['verdict'] = 'works' if (listings or status['parsed']) else 'no_data'
        status['evidence'] = status['evidence'] or meta['evidence']
    status['ok'] = status['verdict'] == 'works'
    status['usd_egp'] = rate_usd_egp
    return listings, status
