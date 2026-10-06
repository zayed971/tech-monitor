import json

import pytest

from egypt_deals.adapters import product_html
from egypt_deals.alerts import detect, verify_pending_stock
from egypt_deals.model import Listing, now
from egypt_deals.http import FetchError
from egypt_deals.storage import Database


SOURCE = {'id': 'egyptlaptop', 'name': 'Egypt Laptop', 'base': 'https://example.com', '_scope': 'catalog'}
TITLE = 'Crucial CT16G56C46S5 16GB DDR5-5600 SODIMM laptop RAM'


@pytest.mark.parametrize('product_type', ['https://schema.org/Product', 'http://schema.org/Product', ['Thing', 'https://schema.org/Product']])
def test_absolute_schema_product_stock_beats_recommended_item(product_type, tmp_path):
    data = {'@type': product_type, 'name': TITLE, 'sku': 'CT16G56C46S5',
            'offers': {'@type': 'https://schema.org/Offer', 'price': 2299, 'priceCurrency': 'EGP', 'availability': 'OutOfStock'}}
    html = '<script type="application/ld+json">' + json.dumps(data) + '</script>'
    html += f'<div class="ty-product-block"><h1>{TITLE}</h1><span class="ty-qty-out-of-stock">Out of stock</span></div>'
    html += '<div class="ty-product-list"><span class="ty-qty-in-stock">In stock</span></div>'
    item = product_html(html, SOURCE, 'https://example.com/ram', now())[0]
    assert item.stock == 'out_of_stock'
    assert item.sku == 'CT16G56C46S5'
    assert not item.eligible()
    db = Database(tmp_path / 'test.sqlite')
    rules = {'thresholds': [{'id': 'ram', 'category': 'ram', 'label': 'RAM', 'max_egp': 10000}], 'drop': {'id': 'drop', 'hours': 24, 'min_pct': 8}}
    assert detect([item], rules, db) == []
    assert not db.pending()
    db.close()


@pytest.mark.parametrize('main_stock, expected', [('Out of stock', 'out_of_stock'), ('غير متوفر', 'out_of_stock'), ('In stock', 'in_stock'), ('', 'unknown')])
def test_html_fallback_uses_main_product_not_recommendations(main_stock, expected):
    badge = f'<span class="ty-qty-out-of-stock">{main_stock}</span>' if main_stock else ''
    html = f'<div class="ty-product-block"><h1>{TITLE}</h1><span class="ty-price-num">2299</span>{badge}</div>'
    html += '<div class="ty-product-list"><span class="ty-price-num">15000</span><span class="ty-qty-in-stock">In stock</span></div>'
    item = product_html(html, SOURCE, 'https://example.com/ram', now())[0]
    assert item.stock == expected
    assert item.price_egp == 2299


def test_visible_sold_out_overrides_stale_in_stock_schema():
    data = {'@type': 'Product', 'name': TITLE, 'offers': {'price': 2299, 'priceCurrency': 'EGP', 'availability': 'InStock'}}
    html = '<script type="application/ld+json">' + json.dumps(data) + '</script>'
    html += f'<div class="ty-product-block"><h1>{TITLE}</h1><span class="ty-qty-out-of-stock">Out of stock</span></div>'
    assert not product_html(html, SOURCE, 'https://example.com/ram', now())[0].eligible()


def test_woocommerce_recommendation_sold_out_does_not_hide_available_main_product():
    data = {'@type': 'Product', 'name': TITLE, 'offers': {'price': 2299, 'priceCurrency': 'EGP', 'availability': 'InStock'}}
    html = '<script type="application/ld+json">' + json.dumps(data) + '</script>'
    html += '<div class="woocommerce-product-details__short-description"><h1>Marketing heading</h1></div>'
    html += '<form class="cart"><button class="single_add_to_cart_button">Add to cart</button></form>'
    html += '<div class="product-grid-item product"><p class="stock out-of-stock">Out of stock</p></div>'
    item = product_html(html, SOURCE, 'https://example.com/ram', now())[0]
    assert item.stock == 'in_stock' and item.eligible()


def test_absolute_aggregate_offer_never_becomes_buyable_listing():
    data = {'@type': 'https://schema.org/Product', 'name': TITLE,
            'offers': {'@type': 'https://schema.org/AggregateOffer', 'lowPrice': 2299, 'priceCurrency': 'EGP', 'availability': 'InStock'}}
    html = '<script type="application/ld+json">' + json.dumps(data) + '</script>'
    assert product_html(html, SOURCE, 'https://example.com/ram', now()) == []


@pytest.mark.parametrize('response', ['sold_out', 'price_changed', 'failed'])
def test_fresh_check_expires_alert_if_unavailable_changed_or_unverifiable(tmp_path, monkeypatch, response):
    (tmp_path / 'sources.json').write_text(json.dumps([{**SOURCE, 'adapter': 'sitemap'}]))
    db = Database(tmp_path / 'test.sqlite')
    item = Listing(store=SOURCE['name'], source=SOURCE['id'], url='https://example.com/ram', raw_title=TITLE,
                   price_egp=2299, stock='in_stock', verified_at=now()).finish()
    db.save([item], {'source': SOURCE['id']})
    db.queue('key', 'RAM bargain', item.identity, item.price_egp)
    class FakeClient:
        def __init__(self, *args, **kwargs): assert kwargs['ttl'] == 0
        def get(self, url):
            if response == 'failed': raise FetchError('network error')
            data = {'@type': 'https://schema.org/Product', 'name': TITLE,
                    'offers': {'price': 2299 if response == 'sold_out' else 9999, 'priceCurrency': 'EGP',
                               'availability': 'OutOfStock' if response == 'sold_out' else 'InStock'}}
            return '<script type="application/ld+json">' + json.dumps(data) + '</script>', url, now()
        def close(self): pass
    monkeypatch.setattr('egypt_deals.http.Client', FakeClient)
    outcome = verify_pending_stock(db, tmp_path)
    assert outcome['expired'] == 1
    assert not db.pending()
    updated = db.listings()[0]
    if response == 'failed': assert updated.stock == 'unknown' and not updated.eligible()
    if response == 'sold_out': assert updated.stock == 'out_of_stock' and not updated.eligible()
    if response == 'price_changed': assert updated.price_egp == 9999
    db.close()


def test_fresh_shopify_check_uses_exact_variant_and_cent_price(tmp_path, monkeypatch):
    source = {**SOURCE, 'adapter': 'shopify'}
    (tmp_path / 'sources.json').write_text(json.dumps([source]))
    db = Database(tmp_path / 'test.sqlite')
    item = Listing(store=SOURCE['name'], source=SOURCE['id'], url='https://example.com/products/ram?variant=2', raw_title=TITLE,
                   price_egp=2299, stock='in_stock', verified_at=now()).finish()
    db.save([item], {'source': SOURCE['id']})
    db.queue('key', 'RAM bargain', item.identity, item.price_egp)
    class FakeClient:
        def __init__(self, *args, **kwargs): assert kwargs['ttl'] == 0
        def get(self, url):
            assert url == 'https://example.com/products/ram.js'
            return json.dumps({'variants': [{'id': 1, 'price': 229900, 'available': True},
                                            {'id': 2, 'price': 229900, 'available': False}]}), url, now()
        def close(self): pass
    monkeypatch.setattr('egypt_deals.http.Client', FakeClient)
    outcome = verify_pending_stock(db, tmp_path)
    assert outcome['unavailable'] == 1 and outcome['expired'] == 1
    assert db.listings()[0].price_egp == 2299 and not db.listings()[0].eligible()
    db.close()
