"""Offline tests for the burner-Chrome Gulf/Egypt parsers. Fixtures are small trimmed captures from 2026-10-07."""
import json
from pathlib import Path

import pytest

from egypt_deals import burner_retail_gulf as B

FIX = Path(__file__).parent / 'fixtures_burner_gulf'


def text(name): return (FIX / name).read_text(encoding='utf-8')
def js(name): return json.loads(text(name))


def check(rows, n=3):
    assert len(rows) == n
    for r in rows:
        assert r['title'] and r['url'].startswith('http') and r['price'] > 0


def test_noon_cards_and_flags():
    rows = B.parse_noon(text('noon_ae.html'))
    check(rows)
    assert rows[0]['url'].startswith('https://www.noon.com/uae-en/') and '?' not in rows[0]['url']
    assert rows[0]['price'] == 2499.0 and rows[0]['old_price'] is None
    assert rows[1]['price'] == 1799.0 and rows[1]['old_price'] == 2199.0
    assert rows[1]['currency'] is None                 # glyph only, no code printed
    assert rows[1]['stock'] == 'in_stock'              # JSON-LD says isBuyable


def test_noon_egypt_prints_currency():
    rows = B.parse_noon(text('noon_eg.html'))
    check(rows)
    assert all(r['currency'] == 'EGP' for r in rows)


def test_sharaf_algolia():
    rows = B.parse_sharaf([js('sharaf.json')])
    check(rows)
    assert rows[0]['price'] == 4199.0 and rows[0]['old_price'] == 4299.0 and rows[0]['stock'] == 'in_stock'
    assert rows[0]['url'].startswith('https://uae.sharafdg.com/product/')


def test_jumbo_algolia():
    rows = B.parse_jumbo([js('jumbo.json')])
    check(rows)
    assert rows[0]['currency'] == 'AED' and rows[0]['price'] == 4599.0 and rows[0]['old_price'] == 4699.0
    assert rows[0]['url'].startswith('https://www.jumbo.ae/') and rows[0]['url'].endswith('.html')


def test_extra_unbxd():
    rows = B.parse_extra([js('extra.json')])
    check(rows)
    assert rows[0]['currency'] == 'SAR' and rows[0]['price'] == 4399.0 and rows[0]['old_price'] == 4999.0
    assert rows[0]['stock'] == 'in_stock' and rows[0]['payments'] == ['installments']


def test_jarir_catalog_and_stock():
    rows = B.parse_jarir([js('jarir_catalog.json'), js('jarir_stock.json')])
    check(rows)
    assert rows[0]['price'] == 6499.0 and rows[0]['old_price'] == 8999.0   # final price, listed price kept as old
    assert rows[0]['url'] == 'https://www.jarir.com/sa-en/msi-crosshair-16-laptops-678218.html'
    assert [r['stock'] for r in rows] == ['in_stock', 'out_of_stock', 'unknown']   # third sku not in the stock reply
    assert 'cod' in rows[0]['payments']


def test_dubizzle_uae_next_data():
    rows = B.parse_dubizzle_ae(text('dubizzle_ae.html'))
    check(rows)
    assert all(r['currency'] == 'AED' for r in rows)
    assert 'dubizzle.com' in rows[0]['url']


def test_dubizzle_egypt_dom():
    rows = B.parse_dubizzle_eg(text('dubizzle_eg.html'))
    check(rows)
    assert all(r['currency'] == 'EGP' for r in rows)
    assert rows[0]['price'] == 48500.0 and rows[0]['sku'] == '209154809'


def test_jsonld_products_for_microless_if_readable():
    html = ('<script type="application/ld+json">{"@type":"Product","name":"Test GPU","url":"https://x.test/p1",'
            '"offers":{"price":"1,999.00","priceCurrency":"AED","availability":"https://schema.org/InStock"}}</script>')
    rows = B.parse_jsonld_products(html)
    assert rows[0]['price'] == 1999.0 and rows[0]['stock'] == 'in_stock'


@pytest.mark.parametrize('title,body,status,expect', [
    ('Just a moment...', 'Performing security verification', 200, True),
    ('Pardon Our Interruption', '', 200, True),
    ('Anything', 'Access Denied', 200, True),
    ('Anything', 'please solve the CAPTCHA', 200, True),
    ('Shop', 'results', 403, True),
    ('Online Shopping in Dubai', 'We use cookies to improve your experience', 200, False),
])
def test_wall_detection(title, body, status, expect):
    assert bool(B.wall_reason(title, body, status)) is expect


def test_listing_zones_and_honest_fields():
    rate = 50.0
    uae = B.to_listing('br_noon_ae', B.parse_noon(text('noon_ae.html'))[1], '2026-10-07T00:00:00+00:00', rate)
    assert uae.zone == 'UAE' and uae.currency == 'AED' and uae.price_local == 1799.0
    assert uae.price_egp == pytest.approx(1799 / 3.6725 * 50, abs=0.01)
    assert uae.landed_egp is None and uae.landed_status == 'unconfirmed' and uae.payments == []
    assert uae.source == 'br_noon_ae' and uae.stock == 'in_stock' and uae.verified_at
    assert any('currency not printed' in q for q in uae.quality_issues)
    eg = B.to_listing('br_noon_eg', B.parse_noon(text('noon_eg.html'))[0], '2026-10-07T00:00:00+00:00', rate)
    assert eg.zone == 'EG' and eg.currency == 'EGP' and eg.price_egp == eg.price_local
    used = B.to_listing('br_dubizzle_eg', B.parse_dubizzle_eg(text('dubizzle_eg.html'))[0], '2026-10-07T00:00:00+00:00', rate)
    assert used.zone == 'EG' and used.source_kind == 'used' and used.stock == 'unknown'


def test_source_ids_and_search_urls():
    assert all(s.startswith('br_') for s in B.SOURCES)
    assert len(B.SOURCES) == 10
    assert B.search_url('br_noon_sa', 'RTX 3060').startswith('https://www.noon.com/saudi-en/search?q=RTX%203060')
    assert B.search_url('br_dubizzle_eg', 'rtx 3060') == 'https://www.dubizzle.com.eg/en/ads/q-rtx-3060/'
