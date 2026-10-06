"""Offline tests for egypt_deals.global_us parsers (fixtures are trimmed copies of the live page shapes of 2026-10-07)."""
import json
from pathlib import Path

import pytest

from egypt_deals import global_us as g
from egypt_deals.http import FetchError

RATE = 52.0
OBS = '2026-10-07T10:00:00+00:00'

SHOPIFY = {'products': [
    {'title': 'Lenovo Legion 5 16ARH7 16" 16GB 1TB SSD RTX 3060 (Refurbished - Good)', 'handle': 'lenovo-legion-5', 'vendor': 'Lenovo',
     'body_html': '<p>Refurbished laptop</p>', 'updated_at': '2026-10-01T00:00:00Z', 'images': [{'src': 'https://cdn/x.jpg'}],
     'variants': [{'id': 11, 'title': 'Default Title', 'price': '622.24', 'compare_at_price': '799.00', 'available': True, 'sku': 'S1'},
                  {'id': 12, 'title': 'Fair', 'price': '500.00', 'compare_at_price': None, 'available': False, 'sku': 'S2'}]},
    {'title': 'Dell Latitude 7420 14" i5', 'handle': 'latitude', 'vendor': 'Dell', 'body_html': '',
     'variants': [{'id': 21, 'title': 'Default Title', 'price': '300.00', 'available': None}]},
]}

LD = '''<html><head><script type="application/ld+json">{"@context":"https://schema.org/","@type":"Product",
"name":"Nvidia Tesla T4 16GB GDDR6 70W PCIe 3.0 x16 HHHL Single-Slot GPU",
"description":"vRAM Capacity: 16GB R2 Certifications: F4-Hardware Functional, Cosmetic: A, Signs of light use",
"url":"/products/nvidia-tesla-t4?Title=Default+Title","sku":"NVIDIA_TESLA_T4",
"offers":{"@type":"Offer","priceCurrency":"USD","price":"1094.95","availability":"https://schema.org/InStock",
"url":"/products/nvidia-tesla-t4?Title=Default+Title"}}</script>
<script type="application/ld+json">{"@type":"Product","name":"No stock info card","offers":{"@type":"Offer","priceCurrency":"USD","price":"20.00"}}</script>
<script type="application/ld+json">{"@type":"Product","name":"Euro card","offers":{"@type":"Offer","priceCurrency":"EUR","price":"20.00"}}</script>
</head></html>'''

PCL = '''<div class="itemTable itemBrowser">
<div class="item_square-medium" x-all-types="Grade A, Grade B, Grade C" x-in-types="Grade B, Grade C">
<div class="item_image"><a href="/hp-zbook-fury-17/p/164297" class="item_image"><img loading="lazy" src="https://images/x.jpg" alt="HP ZBook Fury 17 G8 17.3&quot; Mobile Workstation Laptop i7-11850H Windows 11"></a></div>
<div class="item_text"><h3 class="item_title"><a href="/hp-zbook-fury-17/p/164297" title="More information on HP ZBook Fury 17 G8 ...">HP ZBook Fury 17 G8 17.3&quot; Mobile Workstation Laptop i7-11850H...</a></h3></div>
<div class="price_box"><div class="browseLinePrice"> $799.99 <span>&ndash;</span> $899.99</div><div class="browsePriceStrike">$1,487.99</div></div>
<div class="item_spec"><div class="browse-spec"><div><span class="spec-name">Memory</span> <span class="spec-value">16GB DDR4</span></div>
<div><span class="spec-name">Storage</span> <span class="spec-value">256GB NVMe SSD</span></div></div></div></div>
<div class="item_square-medium" x-all-types="New" x-in-types="New">
<div class="item_image"><a href="/asus-chromebook-cr11-11/p/165144" class="item_image"><img src="https://images/y.jpg" alt="Asus Chromebook CR11 11.6&quot; Laptop Intel N150 8GB RAM 64GB eMMC"></a></div>
<div class="item_text"><h3 class="item_title"><a href="/asus-chromebook-cr11-11/p/165144">Asus Chromebook CR11</a></h3></div>
<div class="price_box"><div class="browseLinePrice"> $419.99</div></div></div></div>'''

def reddit_card(flair='SELLING', title='[USA-TX] [H] RTX 3060 12GB [W] PayPal', body='Asking $200 shipped PayPal G&S. Timestamp.',
                trades='25'):
    return {'id': 't3_a', 'flair': flair, 'url': 'https://old.reddit.com/r/hardwareswap/comments/a/x/', 'title': title, 'author': 'u',
            'trades': trades, 'body': body}

REDDIT_HTML = ('<div data-fullname="t3_abc"><div><header class="search-result-header"><span class="linkflairlabel selling" title="SELLING">SELLING</span>'
               '<a href="https://old.reddit.com/r/hardwareswap/comments/abc/x/" class="search-title">[USA-CA] [H] RTX 3060 12GB [W] PayPal</a></header>'
               '<div class="search-result-meta"><a href="https://old.reddit.com/user/seller1" class="author"><span class="flair" title="Trades: 12">12</span></a></div>'
               '<div class="md"><p>$180 shipped, PayPal G&amp;S</p></div></div></div></div>')


def test_matches_words_and_units():
    assert g.matches('MSI GeForce RTX 3060 12 GB GDDR6', ['RTX 3060 12GB'])
    assert g.matches('Samsung 27" IPS Monitor', ['27 inch IPS monitor'])
    assert g.matches('Corsair DDR5 32GB (2x16GB) kit', ['DDR5 32GB kit'])
    assert not g.matches('RTX 3060 8GB', ['RTX 3060 12GB'])
    assert g.matches('anything', [])


def test_shopify_json_prices_stock_condition():
    items = g.parse_shopify_json(SHOPIFY, 'us_wisetek', OBS, RATE)
    assert len(items) == 3
    a, b, c = items
    assert (a.price_local, a.currency, a.price_egp) == (622.24, 'USD', round(622.24 * 52, 2))
    assert a.zone == 'US' and a.landed_egp is None and a.landed_status == 'unconfirmed'
    assert a.stock == 'in_stock' and a.verified_at == OBS and a.condition == 'refurbished'
    assert a.url == 'https://www.wisetekmarket.com/products/lenovo-legion-5?variant=11'
    assert a.old_price_egp == round(799 * 52, 2)
    assert b.stock == 'out_of_stock'
    assert c.stock == 'unknown' and c.verified_at is None and c.condition == 'unknown'   # nothing stated -> unknown
    assert a.payments == [] and a.used['ships_to_uae'] == 'unknown'


def test_shopify_json_query_filter():
    items = g.parse_shopify_json(SHOPIFY, 'us_wisetek', OBS, RATE, ['laptop RTX 3060'])
    assert [i.parent_title or i.raw_title for i in items] and all('Legion' in i.raw_title for i in items)
    assert g.parse_shopify_json(SHOPIFY, 'us_wisetek', OBS, RATE, ['RTX 4090']) == []


def test_ld_json_collection_page():
    items = g._ld_products(LD, 'https://techmikeny.com/collections/graphics-cards', 'us_techmikeny', OBS, RATE)
    assert len(items) == 2   # the EUR card is dropped, never converted by guess
    t4, bare = items
    assert t4.price_local == 1094.95 and t4.currency == 'USD' and t4.stock == 'in_stock' and t4.verified_at == OBS
    assert t4.condition == 'used'   # the page says "Signs of light use"
    assert t4.url == 'https://techmikeny.com/products/nvidia-tesla-t4?Title=Default+Title'
    assert bare.stock == 'unknown' and bare.verified_at is None and bare.condition == 'unknown'


def test_pcliquidations_category_cards():
    items = g.parse_pcl_category(PCL, 'us_pcliquidations', OBS, RATE)
    assert len(items) == 2
    z, c = items
    assert z.raw_title.startswith('HP ZBook Fury 17 G8 17.3" Mobile Workstation Laptop i7-11850H Windows 11')   # full title from alt, not the cut one
    assert z.price_local == 799.99 and 'price range' in z.description and z.condition == 'refurbished'
    assert z.url == 'https://www.pcliquidations.com/hp-zbook-fury-17/p/164297'
    assert z.stock == 'unknown' and z.verified_at is None
    assert z.old_price_egp == round(1487.99 * 52, 2)
    assert c.condition == 'new' and c.price_local == 419.99
    assert [i.url for i in g.parse_pcl_category(PCL, 'us_pcliquidations', OBS, RATE, ['zbook'])] == [z.url]


def test_reddit_cards_parse():
    cards = g.parse_reddit_cards(REDDIT_HTML)
    assert len(cards) == 1 and cards[0]['flair'] == 'SELLING' and cards[0]['trades'] == '12'
    assert '$180 shipped' in cards[0]['body']


def test_reddit_listing_keeps_good_post():
    it = g.reddit_listing(reddit_card(), OBS, RATE)
    assert it.price_local == 200.0 and it.currency == 'USD' and it.price_egp == 10400.0
    assert it.payments == ['paypal'] and it.stock == 'unknown' and it.verified_at is None
    assert it.source == 'us_reddit_hardwareswap' and it.zone == 'US'


@pytest.mark.parametrize('card,why', [
    (reddit_card(flair='WANTED'), 'not selling'),
    (reddit_card(flair='BUYING'), 'not selling'),
    (reddit_card(body='$200 friends and family only'), 'scam pattern'),
    (reddit_card(body='I can reshipper this, $200'), 'scam pattern'),
    (reddit_card(trades='None'), 'zero trade history'),
    (reddit_card(body='$200 for parts, not working'), 'parts/broken'),
    (reddit_card(title='[H] 3x RTX 3060 lot of cards'), 'multi-item'),
    (reddit_card(body='message me'), 'no price'),
    (reddit_card(body='$100 card, $200 other, $300 third'), 'several prices'),
])
def test_reddit_listing_drops(card, why):
    drops = {}
    assert g.reddit_listing(card, OBS, RATE, drops) is None
    assert any(why in k for k in drops)


class FakeClient:
    def __init__(self, behaviour): self.behaviour = behaviour
    def get(self, url, **kw):
        if isinstance(self.behaviour, Exception): raise self.behaviour
        return self.behaviour, url, OBS
    def close(self): pass


@pytest.mark.parametrize('error,verdict', [
    (FetchError('robots.txt disallows requested URL'), 'blocked'),
    (FetchError('HTTP 403'), 'blocked'),
    (FetchError('HTTP 503'), 'blocked'),
    (FetchError('access challenge'), 'blocked'),
    (FetchError('robots unavailable: HTTP 403'), 'blocked'),
])
def test_blocked_sources_are_recorded_not_worked_around(tmp_path, error, verdict):
    listings, status = g.collect('us_ebay', ['RTX 3060'], root=tmp_path, rate_usd_egp=RATE, client=FakeClient(error))
    assert listings == [] and status['verdict'] == verdict and status['ok'] is False
    assert status['source'] == 'us_ebay' and status['requests'] == 1 and status['evidence']


def test_probe_page_without_products_is_no_data(tmp_path):
    html = '<html><title>Best Buy International: Select your Country</title></html>'
    listings, status = g.collect('us_bestbuy', [], root=tmp_path, rate_usd_egp=RATE, client=FakeClient(html))
    assert listings == [] and status['verdict'] == 'no_data' and 'Select your Country' in status['evidence']


def test_collect_wisetek_with_fake_client_and_status(tmp_path):
    listings, status = g.collect('us_wisetek', ['laptop RTX 3060'], root=tmp_path, rate_usd_egp=RATE,
                                 client=FakeClient(json.dumps(SHOPIFY)))
    assert status['verdict'] == 'works' and status['kept'] == 2 and status['parsed'] == 2
    assert {l.source for l in listings} == {'us_wisetek'}


def test_sources_metadata_complete():
    for sid, m in g.SOURCES.items():
        assert m['zone'] == 'US' and m['currency'] == 'USD' and m['name'] and m['kind'] and m['condition']
        assert m['payments_claimed'] and m['ships_to_uae'] and m['evidence'] and m['probe_url'].startswith('https://')
    assert len(g.SOURCES) == 13
