"""US retail collectors that drive the already-running burner Chrome (CDP 9222) like a person (decision D-009, 2026-10-07).

Why a browser: these shops disallow search in robots.txt or answer plain HTTP with 403/503 (see global_us.py). Zayed said
to read them through the burner Chrome. The rules this module keeps:
  * read only; own tab, closed afterwards; never logs in, never types, never clicks anything but the page's own links;
  * at least 6 s between two page loads of the same site; at most 2 gentle scrolls per query;
  * a CAPTCHA, challenge, "unusual traffic", "access denied", "robot check" or block page ends that site's run, is
    recorded in the status as a wall, and nothing is retried or worked around.

Live look of 2026-10-07 (one search each, "rtx 3060 12gb"):
  works     ebay (li.s-card cards in the rendered HTML), bh (data-selenium="miniProductPage*" cards),
            bestbuy (li.product-list-item; the site's own `intl=nosplash` link skips the country picker; prices load late)
            backmarket (div[data-spec="product-info"] cards; at the first look it showed a Cloudflare check, a later load
            was a normal results page, so a run can stop at the check on a bad day)
  needs more amazon (first load: "Sorry! Something went wrong!"; later loads: real results, but for an Egypt-located browser
            most GPU cards show "See options" with no price and the few prices are in EGP, not USD; only "$" prices are kept)
  wall      newegg (/areyouahuman3 "Are you a human?"), microcenter, swappa (Cloudflare "Just a moment... Performing
            security verification"); these three were never seen unblocked
For the never-seen shops the parsers below are written from the shops' usual public markup and have NOT been checked against
a live page; they only run if the shop ever serves a real results page, and then only on what the page states.
Unknown stays unknown: stock, payments and ships_to_uae are only set when the page itself says so.
"""
import json
import re
import time
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from . import zones
from .model import Listing, money, normalized, now

CDP_URL = 'http://127.0.0.1:9222'
MIN_GAP = 6.0          # seconds between two page loads of one site (D-009)
MAX_SCROLLS = 2
PROBED = '2026-10-07'


def _src(name, kind, condition, probe_url, base, verdict, evidence, card, **extra):
    d = dict(zone='US', name=name, kind=kind, condition=condition, currency='USD', method='burner_cdp', probe_url=probe_url,
             base=base, verdict_2026_10_07=verdict, evidence=evidence, card=card, payments_claimed='unknown',
             ships_to_uae='unknown')
    d.update(extra)
    return d


EBAY_COND = '%7C'.join(['1500', '2000', '2010', '2020', '2030', '2500', '3000'])   # open box, refurbished grades, used

SOURCES = {
    'br_us_ebay': _src('eBay US (burner)', 'marketplace', 'used+refurbished',
                       'https://www.ebay.com/sch/i.html?_nkw={q}&LH_BIN=1&LH_ItemCondition=' + EBAY_COND, 'https://www.ebay.com',
                       'works', 'live look: li.s-card[data-listingid] cards with .s-card__title, .s-card__price, subtitle condition',
                       'li.s-card[data-listingid]'),
    'br_us_amazon': _src('Amazon US (burner)', 'marketplace', 'mixed', 'https://www.amazon.com/s?k={q}', 'https://www.amazon.com',
                         'needs_more', 'live look: real results, but this browser is located in Egypt: GPU cards show "See options" '
                                       'without a price and the few prices shown are EGP; only "$" prices are kept (2026-10-07). '
                                       'First load was a "Sorry! Something went wrong!" page.',
                         'div[data-component-type="s-search-result"]'),
    'br_us_newegg': _src('Newegg (burner)', 'shop', 'mixed', 'https://www.newegg.com/p/pl?d={q}', 'https://www.newegg.com',
                         'wall', 'live look: redirected to /areyouahuman3 "Are you a human?" (2026-10-07); stopped, not solved',
                         'div.item-cell'),
    'br_us_bh': _src('B&H Photo Video (burner)', 'shop', 'new', 'https://www.bhphotovideo.com/c/search?q={q}',
                     'https://www.bhphotovideo.com', 'works',
                     'live look: [data-selenium="miniProductPage"] cards; price split into dollars + sup cents; stock text per card',
                     '[data-selenium="miniProductPage"]'),
    'br_us_microcenter': _src('Micro Center (burner)', 'shop', 'new+open-box',
                              'https://www.microcenter.com/search/search_results.aspx?Ntt={q}', 'https://www.microcenter.com',
                              'wall', 'live look: Cloudflare "Just a moment... Performing security verification" (2026-10-07); stopped',
                              'li.product_wrapper'),
    'br_us_bestbuy': _src('Best Buy (burner)', 'shop', 'new+open-box',
                          'https://www.bestbuy.com/site/searchpage.jsp?st={q}&intl=nosplash', 'https://www.bestbuy.com',
                          'works', 'live look: li.product-list-item cards; customer price in data-testid="price-block-customer-price", '
                                   'filled in a few seconds after load', 'li.product-list-item'),
    'br_us_backmarket': _src('Back Market (burner)', 'refurb', 'refurbished', 'https://www.backmarket.com/en-us/search?q={q}',
                             'https://www.backmarket.com', 'works',
                             'live look: [data-test="product-title"] + [data-qa="productCardPrice"] cards ("Starting at" refurbished '
                             'price). First load of the day was a Cloudflare check (stopped there); a later load was a normal page',
                             '[data-test="product-title"]'),
    'br_us_swappa': _src('Swappa (burner)', 'marketplace', 'used', 'https://swappa.com/search?q={q}', 'https://swappa.com',
                         'wall', 'live look: Cloudflare "Just a moment... Performing security verification" (2026-10-07); stopped',
                         'div.listing_row, [data-listing-id]'),
}

# ---------------------------------------------------------------------------------------------- walls

WALL_URL = re.compile(r'areyouahuman|testchallengepage|/captcha|validateCaptcha|/blocked|/denied|challenge', re.I)
WALL_TITLE = re.compile(r'just a moment|are you a human|robot check|access denied|attention required|pardon our interruption|'
                        r'sorry! something went wrong|page not found.*amazon|captcha|security check|blocked', re.I)
WALL_TEXT = re.compile(r'performing security verification|verify(?:ing)? you are (?:a )?human|unusual traffic|'
                       r'enter the characters you see|not a robot|robot check|access denied|are you a human|'
                       r'can.t quite tell if you.re a person or a script|press (?:&|and) hold|automated access|'
                       r'to discuss automated access', re.I)


def detect_wall(url, title, text):
    """Reason string when the page is a CAPTCHA/challenge/block page, else None."""
    url, title, text = str(url or ''), normalized(title), normalized(text)[:2500]
    if WALL_URL.search(url.split('?')[0]) and not re.search(r'/itm/|/product/|/c/product', url): return 'challenge url: ' + url.split('?')[0][-60:]
    if WALL_TITLE.search(title): return 'wall page title: ' + title[:60]
    if WALL_TEXT.search(text): return 'wall text: ' + (WALL_TEXT.search(text).group(0))[:60]
    return None


# ---------------------------------------------------------------------------------------------- shared bits

def _listing(source_id, title, url, price, observed, *, condition='unknown', stock='unknown', rate, description='',
             brand=None, sku=None, mpn=None, images=None, old_price=None, payments=None, ships_to_uae='unknown',
             extra_used=None, shipping_text=None):
    meta = SOURCES[source_id]
    item = Listing(store=meta['name'], url=url, raw_title=title, price_egp=None, observed_at=observed, source=source_id,
                   source_kind='used' if meta['kind'] == 'used-p2p' else 'retailer', currency='USD', stock=stock,
                   verified_at=observed if stock != 'unknown' else None, condition=condition, description=description,
                   brand=brand, sku=sku, mpn=mpn, images=list(images or []), delivery_time=shipping_text)
    zones.foreign(item, 'US', rate, price_local=price, currency='USD', payments=payments)
    if old_price: item.old_price_egp = zones.to_egp(old_price, 'USD', rate)
    item.finish()
    item.used = {**item.used, 'ships_to_uae': ships_to_uae, 'via': 'burner_chrome', **(extra_used or {})}
    return item


def _first_price(text):
    """Lowest dollar amount in the text as (amount, is_range)."""
    vals = [money(x) for x in re.findall(r'\$\s*[\d,]+(?:\.\d{1,2})?', text or '')]
    vals = [v for v in vals if v is not None]
    if not vals: return None, False
    return min(vals), len(vals) > 1 and bool(re.search(r'\bto\b', text or ''))


def _generic_ld(soup, source_id, observed, rate):
    """Product JSON-LD offers (any shop): used only for the walled shops if they ever serve real pages."""
    out = []
    for tag in soup.select('script[type="application/ld+json"]'):
        try: data = json.loads(tag.get_text())
        except (ValueError, TypeError): continue
        stack = [data]
        while stack:
            n = stack.pop()
            if isinstance(n, list): stack.extend(n); continue
            if not isinstance(n, dict): continue
            stack.extend(v for v in n.values() if isinstance(v, (list, dict)))
            t = n.get('@type')
            if not (t == 'Product' or (isinstance(t, list) and 'Product' in t)) or not n.get('name'): continue
            offers = n.get('offers') or {}
            for o in ([offers] if isinstance(offers, dict) else offers):
                if not isinstance(o, dict): continue
                price = money(o.get('price') or o.get('lowPrice'))
                if price is None or (o.get('priceCurrency') or 'USD') != 'USD': continue
                url = o.get('url') or n.get('url')
                if not url: continue
                av = str(o.get('availability', '')).lower()
                stock = 'in_stock' if 'instock' in av else 'out_of_stock' if 'outofstock' in av or 'soldout' in av else 'unknown'
                ic = str(o.get('itemCondition', '')).lower()
                cond = 'used' if 'used' in ic else 'refurbished' if 'refurb' in ic else 'new' if 'new' in ic else 'unknown'
                out.append(_listing(source_id, str(n['name']), urljoin(SOURCES[source_id]['base'], url), price, observed,
                                    condition=cond, stock=stock, rate=rate))
    return out


# ---------------------------------------------------------------------------------------------- eBay (checked live)

EBAY_COND_MAP = [(r'certified|refurbished|seller refurbished', 'refurbished'), (r'open box', 'open_box'),
                 (r'pre-?owned|used|for parts', 'used'), (r'brand new|^new\b', 'new')]


def parse_ebay(html, source_id='br_us_ebay', observed=None, rate=None):
    observed = observed or now()
    soup = BeautifulSoup(html, 'html.parser')
    out, seen = [], set()
    for card in soup.select('li.s-card[data-listingid]'):
        lid = card.get('data-listingid', '')
        if not re.fullmatch(r'\d{9,}', lid) or lid in seen: continue     # the first "Shop on eBay" card is a template (id 123456)
        title_el = card.select_one('.s-card__title')
        price_el = card.select_one('.s-card__price')
        if not title_el or not price_el: continue
        title = normalized(title_el.get_text(' ', strip=True))
        title = re.sub(r'\s*Opens in a new window or tab$', '', title, flags=re.I)
        if not title or title.lower() == 'shop on eBay'.lower(): continue
        price_text = normalized(price_el.get_text(' ', strip=True))
        rows = [normalized(x.get_text(' ', strip=True)) for x in card.select('.s-card__attribute-row')]
        subs = [normalized(x.get_text(' ', strip=True)) for x in card.select('.s-card__subtitle')]
        card_text = ' | '.join(subs + rows)
        if re.search(r'\b\d+\s+bids?\b|\bbid\b', card_text, re.I) and not re.search(r'buy it now', card_text, re.I): continue   # auction
        price, is_range = _first_price(price_text)
        if price is None: continue
        cond = 'unknown'
        for s in subs:
            hit = next((c for pat, c in EBAY_COND_MAP if re.search(pat, s, re.I)), None)
            if hit: cond = hit; break
        located = next((r for r in rows if r.lower().startswith('located in')), '')
        ship = next((r for r in rows if re.search(r'delivery|shipping', r, re.I)), None)
        note = ' | '.join(x for x in [', '.join(s for s in subs if s != subs[-1]) if len(subs) > 1 else '',
                                      located, ship and ('shown to an Egypt visitor: ' + ship)] if x)
        if is_range: note += (' | ' if note else '') + 'price range on page; lowest recorded: ' + price_text
        out.append(_listing(source_id, title, 'https://www.ebay.com/itm/' + lid, price, observed, condition=cond, rate=rate,
                            description=note, shipping_text=ship, extra_used={'listing_type': 'buy_it_now_or_best_offer'}))
        seen.add(lid)
    return out


# ---------------------------------------------------------------------------------------------- B&H (checked live)

def parse_bh(html, source_id='br_us_bh', observed=None, rate=None):
    observed = observed or now()
    soup = BeautifulSoup(html, 'html.parser')
    out, seen = [], set()
    for card in soup.select('[data-selenium="miniProductPage"]'):
        name = card.select_one('[data-selenium="miniProductPageProductName"]')
        link = card.select_one('a[data-selenium="miniProductPageProductNameLink"]') or card.select_one('a[href*="/c/product/"]')
        if not name or not link or not link.get('href'): continue
        first = card.select_one('[data-selenium="uppedDecimalPriceFirst"]')
        second = card.select_one('[data-selenium="uppedDecimalPriceSecond"]')
        if not first: continue
        dollars = re.sub(r'[^\d]', '', first.get_text())
        if not dollars: continue
        cents = re.sub(r'[^\d]', '', second.get_text()) if second else '00'
        price = float(f'{dollars}.{cents[:2] or "00"}')
        url = urljoin('https://www.bhphotovideo.com', link['href'])
        if url in seen: continue
        seen.add(url)
        st = card.select_one('[data-selenium="stockStatus"]')
        st_text = normalized(st.get_text(' ', strip=True)) if st else ''
        if re.search(r'in stock|ships (?:today|tomorrow)|available', st_text, re.I) and not re.search(r'out of stock|unavailable', st_text, re.I): stock = 'in_stock'
        elif re.search(r'out of stock|backorder|unavailable|sold out', st_text, re.I): stock = 'out_of_stock'
        else: stock = 'unknown'
        sku = card.select_one('[data-selenium="miniProductPageProductSkuInfo"]')
        sku_text = normalized(sku.get_text(' ', strip=True)) if sku else ''
        bh = re.search(r'BH\s*#\s*(\S+)', sku_text)
        mfr = re.search(r'MFR\s*#\s*(.+)$', sku_text)
        strike = card.select_one('[class*="strikeThrough"]')
        old = money(strike.get_text()) if strike and strike.get_text(strip=True) else None
        title = normalized(name.get_text(' ', strip=True))
        cond = 'refurbished' if re.search(r'\brefurbished\b', title, re.I) else 'used' if re.search(r'\bused\b', title, re.I) \
            else 'open_box' if re.search(r'open box', title, re.I) else 'new'
        out.append(_listing(source_id, title, url, price, observed, condition=cond, stock=stock, rate=rate,
                            sku=bh.group(1) if bh else None, mpn=mfr.group(1).strip() if mfr else None, old_price=old,
                            description='stock text on page: ' + st_text if st_text else ''))
    return out


# ---------------------------------------------------------------------------------------------- Best Buy (checked live)

def parse_bestbuy(html, source_id='br_us_bestbuy', observed=None, rate=None):
    observed = observed or now()
    soup = BeautifulSoup(html, 'html.parser')
    out, seen = [], set()
    for card in soup.select('li.product-list-item'):
        link = next((a for a in card.select('a[href*="/product/"]')
                     if normalized(a.get_text()) and not normalized(a.get_text()).lower().startswith('rating')), None)
        if not link: continue
        url = urljoin('https://www.bestbuy.com', link['href'].split('#')[0])
        if url in seen: continue
        pe = card.select_one('[data-testid="price-block-customer-price"]')
        if not pe: continue                       # price not loaded yet or not shown: no price, no listing
        sr = pe.select_one('.sr-only')
        price, _ = _first_price(sr.get_text() if sr else pe.get_text())
        if price is None: continue
        seen.add(url)
        title = normalized(link.get_text(' ', strip=True)).replace('- ', '- ').replace('GIGABYTE- ', 'GIGABYTE - ')
        text = normalized(card.get_text(' ', strip=True))
        if re.search(r'\bAdd to cart\b', text): stock = 'in_stock'
        elif re.search(r'\bSold Out\b', text): stock = 'out_of_stock'
        else: stock = 'unknown'
        reg = card.select_one('[data-testid="price-block-regular-price"]')
        old = _first_price(reg.get_text())[0] if reg else None
        if old is not None and old <= price: old = None
        cond = 'open_box' if re.search(r'open[- ]box', text, re.I) else 'refurbished' if re.search(r'\brefurbished\b', text, re.I) else 'new'
        sku = card.get('data-product-id') or None
        ship = re.search(r'(Pick up[^$]{0,40}?|Get it[^$]{0,40}?|Shipping unavailable)(?=\s*(?:Add to cart|Compare|$|Get it|Pick up))', text)
        out.append(_listing(source_id, title, url, price, observed, condition=cond, stock=stock, rate=rate, sku=sku, old_price=old,
                            description='US delivery text on page: ' + ship.group(1).strip() if ship else ''))
    return out


# ---------------------------------------------------------------------------------------------- walled shops (unverified markup)

def parse_amazon(html, source_id='br_us_amazon', observed=None, rate=None):
    """Only cards with a "$" price are kept. Amazon shows EGP (or nothing, "See options") to this Egypt-located browser."""
    observed = observed or now()
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for card in soup.select('div[data-component-type="s-search-result"][data-asin]'):
        asin = card.get('data-asin')
        if not asin or re.search(r'\bSponsored\b', card.get_text(' ')[:200]): continue
        link = max(card.select('a[href*="/dp/"]'), key=lambda a: len(normalized(a.get_text())), default=None)
        if not link or not normalized(link.get_text()): continue
        brand = card.select_one('h2')
        title = normalized(link.get_text(' ', strip=True))
        if brand and normalized(brand.get_text()) and normalized(brand.get_text()).lower() not in title.lower():
            title = normalized(brand.get_text()) + ' ' + title
        price = None
        for el in card.select('.a-price:not(.a-text-price) .a-offscreen'):
            txt = normalized(el.get_text())
            if txt.startswith('$') or txt.startswith('US$'):
                price = money(txt); break
        if price is None: continue
        cond = 'refurbished' if re.search(r'\b(?:renewed|refurbished)\b', title, re.I) else 'used' if re.search(r'\bused\b', title, re.I) else 'unknown'
        out.append(_listing(source_id, title, 'https://www.amazon.com/dp/' + asin, price, observed,
                            condition=cond, rate=rate, sku=asin))
    return out or _generic_ld(soup, source_id, observed, rate)


def parse_newegg(html, source_id='br_us_newegg', observed=None, rate=None):
    observed = observed or now()
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for card in soup.select('div.item-cell'):
        a = card.select_one('a.item-title')
        pc = card.select_one('li.price-current')
        if not a or not a.get('href') or not pc: continue
        price, _ = _first_price(pc.get_text(' '))
        if price is None: continue
        promo = normalized(card.select_one('.item-promo').get_text(' ')) if card.select_one('.item-promo') else ''
        stock = 'out_of_stock' if re.search(r'out of stock', promo, re.I) else 'unknown'
        title = normalized(a.get_text(' ', strip=True))
        cond = 'refurbished' if re.search(r'refurbished|renewed', title, re.I) else 'open_box' if re.search(r'open box', title, re.I) else 'unknown'
        out.append(_listing(source_id, title, a['href'].split('?')[0], price, observed, condition=cond, stock=stock, rate=rate))
    return out or _generic_ld(soup, source_id, observed, rate)


def parse_microcenter(html, source_id='br_us_microcenter', observed=None, rate=None):
    observed = observed or now()
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for card in soup.select('li.product_wrapper'):
        a = card.select_one('h2 a, a.productClickItemV2')
        if not a or not a.get('href'): continue
        price, _ = _first_price((card.select_one('.price') or card).get_text(' '))
        if price is None: continue
        text = normalized(card.get_text(' '))
        stock = 'in_stock' if re.search(r'\bin stock\b', text, re.I) else 'out_of_stock' if re.search(r'sold out|out of stock', text, re.I) else 'unknown'
        title = normalized(a.get('data-name') or a.get_text(' ', strip=True))
        cond = 'open_box' if re.search(r'open box', text, re.I) else 'unknown'
        out.append(_listing(source_id, title, urljoin('https://www.microcenter.com', a['href']), price, observed, condition=cond, stock=stock, rate=rate))
    return out or _generic_ld(soup, source_id, observed, rate)


def parse_backmarket(html, source_id='br_us_backmarket', observed=None, rate=None):
    """Back Market cards: title span, link, "Starting at" refurbished price (dollars and cents in separate spans)."""
    observed = observed or now()
    soup = BeautifulSoup(html, 'html.parser')
    out, seen = [], set()
    for title_el in soup.select('[data-test="product-title"]'):
        node = title_el
        for _ in range(8):
            node = node.parent
            if node is None: break
            if node.select_one('[data-qa="productCardPrice"]') and node.select_one('a[href*="/p/"]') \
                    and len(node.select('[data-test="product-title"]')) == 1:
                break
        if node is None: continue
        link = node.select_one('a[href*="/p/"]')
        price_el = node.select_one('[data-qa="productCardPrice"]')
        m = re.search(r'\$([\d,]+(?:\.\d{1,2})?)', re.sub(r'\s+', '', price_el.get_text())) if price_el else None
        if not link or not m: continue
        url = urljoin('https://www.backmarket.com', link['href'])
        if url in seen: continue
        seen.add(url)
        versus = re.search(r'Versus\s*\$[\d,]+(?:\.\d\d)?\s*new', normalized(node.get_text(' ', strip=True)))
        out.append(_listing(source_id, normalized(title_el.get_text(' ', strip=True)), url, money(m.group(1)), observed,
                            condition='refurbished', rate=rate,
                            description='Refurbished "Starting at" price (best grade/seller combination listed)'
                                        + ('; ' + versus.group(0) if versus else '')))
    return out or _generic_ld(soup, source_id, observed, rate)


def parse_generic(html, source_id, observed=None, rate=None):
    return _generic_ld(BeautifulSoup(html, 'html.parser'), source_id, observed or now(), rate)


PARSERS = {'br_us_ebay': parse_ebay, 'br_us_bh': parse_bh, 'br_us_bestbuy': parse_bestbuy, 'br_us_amazon': parse_amazon,
           'br_us_newegg': parse_newegg, 'br_us_microcenter': parse_microcenter,
           'br_us_backmarket': parse_backmarket,
           'br_us_swappa': lambda h, source_id='br_us_swappa', observed=None, rate=None: parse_generic(h, source_id, observed, rate)}

# ---------------------------------------------------------------------------------------------- driver

# CSS to wait for before reading, per site (cards that carry a price); a short grace follows.
READY = {'br_us_bestbuy': 'li.product-list-item [data-testid="price-block-customer-price"]',
         'br_us_bh': '[data-selenium="miniProductPage"]', 'br_us_ebay': 'li.s-card[data-listingid]'}


def _status(source_id, queries):
    meta = SOURCES[source_id]
    return dict(source=source_id, zone='US', name=meta['name'], verdict=None, evidence='', requests=0, parsed=0, kept=0,
                probe_url=meta['probe_url'].replace('{q}', 'rtx+3060+12gb'), at=now(), ships_to_uae=meta['ships_to_uae'],
                queries=list(queries or []), via_burner_browser=True, walls=[], errors=[], cards_seen=0)


def collect(source_id, queries, *, root=None, rate_usd_egp=None, max_items=200, cdp=CDP_URL, delay=7.0):
    """Returns (listings, status). status['verdict'] is works | wall | no_data | error | needs_burner_browser."""
    if source_id not in SOURCES: raise KeyError(source_id)
    from playwright.sync_api import sync_playwright
    meta, parse = SOURCES[source_id], PARSERS[source_id]
    queries = list(queries or ['rtx 3060 12gb'])
    delay = max(float(delay), MIN_GAP)
    status = _status(source_id, queries)
    found = {}
    with sync_playwright() as p:
        try: browser = p.chromium.connect_over_cdp(cdp, timeout=8000)
        except Exception as e:
            status.update(verdict='needs_burner_browser', ok=False, usd_egp=rate_usd_egp,
                          evidence=f'burner dark Chrome not reachable at {cdp} ({type(e).__name__}); start launch-agent-chrome.ps1')
            return [], status
        page = browser.contexts[0].new_page()      # our own tab only
        last_load = 0.0
        try:
            for query in queries:
                wait = delay - (time.monotonic() - last_load)
                if last_load and wait > 0: time.sleep(wait)
                url = meta['probe_url'].replace('{q}', quote_plus(query))
                try:
                    last_load = time.monotonic()
                    page.goto(url, wait_until='domcontentloaded', timeout=45000)
                    status['requests'] += 1
                    time.sleep(3.5)
                    head = page.evaluate("() => (document.body ? document.body.innerText : '').slice(0, 2500)")
                    reason = detect_wall(page.url, page.title(), head)
                    if reason:
                        status['walls'].append({'query': query, 'reason': reason}); break
                    ready = READY.get(source_id) or meta['card'].split(',')[0]
                    try: page.wait_for_selector(ready, timeout=20000, state='attached')
                    except Exception: pass
                    time.sleep(2.0)
                    for _ in range(MAX_SCROLLS):
                        page.mouse.wheel(0, 900); time.sleep(2.5)
                    head = page.evaluate("() => (document.body ? document.body.innerText : '').slice(0, 2500)")
                    reason = detect_wall(page.url, page.title(), head)
                    if reason:
                        status['walls'].append({'query': query, 'reason': reason}); break
                    html = page.content()
                    status['cards_seen'] = max(status['cards_seen'], len(BeautifulSoup(html, 'html.parser').select(meta['card'])))
                    items = parse(html, source_id, now(), rate_usd_egp)
                    status['parsed'] += len(items)
                    for it in items:
                        it.used = {**it.used, 'query': query}
                        found.setdefault(it.url, it)
                except Exception as e:
                    status['errors'].append(f'{query}: {type(e).__name__}')
                if len(found) >= max_items: break
        finally:
            try: page.close()
            except Exception: pass
            try: browser.close()   # detaches from CDP; the Chrome process keeps running
            except Exception: pass
    listings = list(found.values())[:max_items]
    status['kept'] = len(listings)
    if status['walls'] and not listings:
        status.update(verdict='wall', evidence='stopped at a wall, nothing worked around: ' + status['walls'][0]['reason'])
    elif listings:
        status.update(verdict='works', evidence=meta['evidence'] + ('; wall on a later query: ' + status['walls'][0]['reason'] if status['walls'] else ''))
    elif status['errors']:
        status.update(verdict='error', evidence='; '.join(status['errors'][:3]))
    else:
        status.update(verdict='no_data', evidence=f"page loaded, no wall; {status['cards_seen']} result cards seen, none with a usable "
                                                  'USD price (prices hidden or in another currency for this browser location, or empty results)')
    status['ok'] = status['verdict'] == 'works'
    status['usd_egp'] = rate_usd_egp
    return listings, status
