"""Read-only Facebook Marketplace collector that drives the already-running burner Chrome (CDP 9222).

Never logs in, never types, never clicks sellers/messages/save. Opens its own tab, closes it after, and stops at the
first sign of a login, checkpoint, challenge or "temporarily blocked" page. A visible advert is a candidate, never
verified stock. Only listing fields are kept: no seller, profile, phone, message or raw HTML.
"""
import re
import time
from urllib.parse import quote

from .marketplace_local import item_url
from .model import Listing, money, normalized, now, redact
from .zones import ZONE_CURRENCY, foreign

SOURCE = 'facebook-burner'
STOP_URL = re.compile(r'checkpoint|/login|challenge|/recover', re.I)
BLOCK_TEXT = re.compile(r'temporarily blocked|temporarily restricted|we limit how often|suspicious activity|'
                        r'confirm your identity|محظور مؤقتا|تم تقييد', re.I)
CURRENCY_PATTERNS = [
    ('AED', r'\bAED(?![A-Za-z])|\bDhs?(?![A-Za-z])\.?|د\.\s*إ|درهم'),
    ('SAR', r'\bSAR(?![A-Za-z])|\bSR(?![A-Za-z])|ر\.\s*س|ريال'),
    ('EGP', r'\bEGP(?![A-Za-z])|\bE£|جنيه|ج\.\s*م|£'),
    ('USD', r'\bUSD(?![A-Za-z])|\bUS\$|\$'),
]
NUMBER = r'(\d[\d,٬]*(?:[.٫]\d+)?)'
NEW_WORDS = re.compile(r'\bbrand new\b|\bnew in box\b|\bsealed\b|\bnib\b|\bnew\b|جديد|متبرشم|زيرو', re.I)
USED_WORDS = re.compile(r'\bused\b|\bas new\b|\blike new\b|مستعمل|كسر زيرو', re.I)
SOLD = re.compile(r'sold|pending|تم البيع|مباع|محجوز', re.I)
PRICE_ONLY = re.compile(r'^[\d\s,.]+$')
DEFAULT_QUERIES = ['RTX 3060 12GB', 'RTX 3090', 'RTX 4070', 'gaming laptop', 'gaming PC', 'Ryzen 7',
                   'RAM DDR4 32GB', 'NVMe SSD 1TB', 'كارت شاشة', 'لاب توب جيمنج', 'تجميعة جيمنج']


def parse_price(text):
    """Return (amount, currency) for the earliest price in `text`, or (None, None)."""
    text = normalized(text)
    best = None
    for currency, pattern in CURRENCY_PATTERNS:
        for m in re.finditer(pattern, text, re.I):
            after = re.match(r'\s*' + NUMBER, text[m.end():])
            before = re.search(NUMBER + r'\s*$', text[:m.start()])
            for hit, pos in ((after, m.start()), (before, before.start() if before else 0)):
                if hit:
                    amount = money(hit.group(1))
                    if amount is not None and (best is None or pos < best[0]):
                        best = (pos, amount, currency)
                    break
    return (best[1], best[2]) if best else (None, None)


def card_listing_zone(url, text, observed, zone, rate_usd_egp):
    """A Listing from one visible card, or None for non-item links, sold/pending, unpriced or junk cards."""
    url = item_url(url)
    if not url or zone not in ZONE_CURRENCY: return None
    lines = [normalized(l) for l in str(text or '').splitlines() if normalized(l)]
    if any(SOLD.fullmatch(l) for l in lines): return None
    for index, line in enumerate(lines):
        amount, currency = parse_price(line)
        if amount is None: continue
        if zone == 'EG' and currency != 'EGP': continue
        if amount < (100 if currency == 'EGP' else 10): continue
        title = next((v for v in lines[index + 1:] if parse_price(v)[0] is None and not PRICE_ONLY.fullmatch(v)
                      and not re.fullmatch(r'Free|مجانا|مجاناً', v, re.I)), None)
        if not title: return None
        title = redact(title)
        card_text = ' '.join(lines)
        condition = 'new' if NEW_WORDS.search(card_text) and not USED_WORDS.search(card_text) else 'used'
        item = Listing(store='Facebook Marketplace (burner) ' + zone, source=SOURCE, source_kind='used', url=url,
                       raw_title=title, price_egp=amount if zone == 'EG' else None, currency=currency,
                       stock='unknown', condition=condition, observed_at=observed, verified_at=None,
                       description='', seller=None)
        if zone != 'EG':
            foreign(item, zone, rate_usd_egp, price_local=amount, currency=currency)
        else:
            item.zone, item.country, item.price_local = 'EG', 'EG', amount
        return item.finish()
    return None


def _blocked(page):
    if STOP_URL.search(page.url): return 'stopped: landed on ' + page.url.split('?')[0]
    try:
        head = page.evaluate("() => (document.body ? document.body.innerText : '').slice(0, 1500)")
    except Exception:
        return None
    if BLOCK_TEXT.search(head): return 'stopped: Facebook block/limit message shown'
    return None


def collect(zone, city_slug, queries, *, scrolls=2, delay=8, rate_usd_egp=None, cdp='http://127.0.0.1:9222'):
    """Returns (listings, status). Opens and closes its own tab; stops at the first login/checkpoint/block sign."""
    from playwright.sync_api import sync_playwright
    delay = max(float(delay), 6.0)
    scrolls = max(0, min(int(scrolls), 20))
    captured, errors = {}, []
    status = {'source': SOURCE, 'status': 'ok', 'listings': 0, 'pages': 0, 'errors': errors, 'zone': zone,
              'queries': list(queries), 'city': city_slug, 'final_urls': [], 'cards_seen': 0}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp)
        page = browser.contexts[0].new_page()   # our own tab only
        try:
            stop = False
            for query in queries:
                url = 'https://www.facebook.com/marketplace/%s/search?query=%s&exact=false' % (quote(city_slug), quote(query))
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                status['pages'] += 1
                for step in range(scrolls + 1):
                    time.sleep(delay)
                    reason = _blocked(page)
                    if reason:
                        status['status'] = 'stopped'; errors.append({'query': query, 'reason': reason}); stop = True
                        break
                    cards = page.locator('a[href*="/marketplace/item/"]').evaluate_all(
                        '(links) => links.map(a => ({url:a.href,text:a.innerText})).filter(x => x.text)')
                    status['cards_seen'] = max(status['cards_seen'], len(cards))
                    for card in cards:
                        item = card_listing_zone(card['url'], card['text'], now(), zone, rate_usd_egp)
                        if item: captured[item.identity] = item
                    if step < scrolls:
                        page.mouse.wheel(0, 900)
                status['final_urls'].append(page.url.split('?')[0])
                if stop: break
        except Exception as error:
            status['status'] = 'error'; errors.append({'reason': type(error).__name__})
        finally:
            try: page.close()
            except Exception: pass
    status['listings'] = len(captured)
    return list(captured.values()), status
