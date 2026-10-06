"""Zones, currencies and routes to Mansoura.

Zayed's routes (2026-10-07):
  EG   buy in Egypt, delivered or picked up locally.
  UAE  buy in the UAE; the UAE traveler carries it to Egypt.
  KSA  buy in Saudi Arabia; the Saudi traveler carries it to Egypt.
  US   order from a US store to a UAE address; the UAE traveler carries it to Egypt.

Rules: the item price is converted to EGP with a stated rate; the landed price stays None ("unconfirmed") until a real
quote exists, because shipping to the UAE, customs and baggage rules are unknown. Unknown is never zero.
"""
import json
from pathlib import Path

# AED and SAR are pegged to the dollar by their central banks.
PEG_PER_USD = {'USD': 1.0, 'AED': 3.6725, 'SAR': 3.75}

ZONE_ROUTE = {
    'EG': (None, 'domestic'),
    'UAE': ('Buy in the UAE; UAE traveler carries it to Egypt. Egypt customs and baggage rules unconfirmed.', 'unconfirmed'),
    'KSA': ('Buy in Saudi Arabia; Saudi traveler carries it to Egypt. Egypt customs and baggage rules unconfirmed.', 'unconfirmed'),
    'US': ('Order from a US store to a UAE address; UAE traveler carries it to Egypt. US-to-UAE shipping, UAE duty and '
           'Egypt customs unconfirmed.', 'unconfirmed'),
}
ZONE_CURRENCY = {'EG': 'EGP', 'UAE': 'AED', 'KSA': 'SAR', 'US': 'USD'}
ZONE_COUNTRY = {'EG': 'EG', 'UAE': 'AE', 'KSA': 'SA', 'US': 'US'}


def usd_egp(root):
    """The stored dollar rate (references.json, refreshed by `egypt_deals.cli fx`). None if missing."""
    try:
        return float(json.loads((Path(root) / 'references.json').read_text(encoding='utf-8'))['fx']['usd_egp'])
    except (OSError, KeyError, ValueError, TypeError):
        return None


def to_egp(amount, currency, rate_usd_egp):
    if amount is None or rate_usd_egp is None: return None
    if currency == 'EGP': return round(float(amount), 2)
    peg = PEG_PER_USD.get(currency)
    if not peg: return None
    return round(float(amount) / peg * rate_usd_egp, 2)


def foreign(listing, zone, rate_usd_egp, price_local=None, currency=None, payments=None):
    """Fill the zone fields of a Listing built from a foreign store. Call before `.finish()` or after, both work.

    `price_local` and `currency` are the numbers as shown on the page. The converted item price goes to price_egp.
    """
    currency = currency or ZONE_CURRENCY[zone]
    amount = price_local if price_local is not None else listing.price_local
    listing.zone = zone
    listing.country = ZONE_COUNTRY[zone]
    listing.currency = currency
    listing.price_local = amount
    listing.price_egp = to_egp(amount, currency, rate_usd_egp)
    route, status = ZONE_ROUTE[zone]
    listing.route = route
    listing.landed_status = status
    listing.landed_egp = None
    if payments: listing.payments = sorted(set(payments))
    return listing
