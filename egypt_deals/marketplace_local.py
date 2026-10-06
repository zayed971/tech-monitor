"""Parse product cards visible to the owner in local Chrome.

No seller names, profiles, messages, phone numbers, cookies or raw page text
are exported. A visible advert is a candidate, not verified purchase stock.
"""
import re
from urllib.parse import urlsplit, urlunsplit

from .model import Listing, money, normalized, redact


def item_url(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in {'www.facebook.com', 'facebook.com'}:
        return None
    match = re.fullmatch(r'/marketplace/item/(\d+)/?', parts.path)
    return 'https://www.facebook.com/marketplace/item/' + match.group(1) + '/' if match else None


def card_listing(url, text, observed):
    url = item_url(url)
    if not url: return None
    lines = [normalized(line) for line in text.splitlines() if normalized(line)]
    if any(re.fullmatch(r'sold|pending|تم البيع|مباع|محجوز', line, re.I) for line in lines): return None
    for index, line in enumerate(lines):
        if re.search(r'[$€]|\b(?:USD|EUR|GBP|SAR|AED)\b', line, re.I): continue
        # EGP prices may use £ in an Egypt-configured Marketplace browser.
        if not re.search(r'£|\bEGP\b|جنيه|ج\.\s*م', line, re.I): continue
        price = money(line)
        if price is None or price < 100: continue
        remaining = lines[index + 1:]
        title = next((v for v in remaining if not re.fullmatch(r'[\d\s,.£]+', v)
                      and not re.match(r'^(?:£|EGP\b|جنيه|ج\.\s*م)', v, re.I)
                      and not re.fullmatch(r'Free|مجانا|مجاناً', v, re.I)), None)
        if not title: return None
        title = redact(title)
        return Listing(store='Facebook Marketplace — local browser', source='facebook-local', source_kind='used',
                       url=url, raw_title=title, price_egp=price, currency='EGP', stock='unknown',
                       condition='used', observed_at=observed, verified_at=None,
                       description='', seller=None).finish()
    return None
