"""Offline parser tests for egypt_deals.burner_retail_us on small captured pages (tests/fixtures_burner_us/, 2026-10-07).

Captured with the burner Chrome, then stripped of scripts, images, seller names and tracking query strings.
"""
from pathlib import Path

import pytest

from egypt_deals import burner_retail_us as br

FIX = Path(__file__).parent / 'fixtures_burner_us'
RATE = 50.0


def page(name):
    return (FIX / name).read_text(encoding='utf-8')


def test_sources_cover_the_eight_sites_with_prefix():
    assert list(br.SOURCES) == ['br_us_ebay', 'br_us_amazon', 'br_us_newegg', 'br_us_bh', 'br_us_microcenter',
                                'br_us_bestbuy', 'br_us_backmarket', 'br_us_swappa']
    assert set(br.PARSERS) == set(br.SOURCES)
    assert all(s['ships_to_uae'] == 'unknown' and s['currency'] == 'USD' for s in br.SOURCES.values())


def test_ebay_skips_template_card_and_reads_condition_price_url():
    items = br.parse_ebay(page('ebay_cards.html'), rate=RATE)
    assert len(items) == 4                                   # the "Shop on eBay" template card (id 123456) is not a listing
    first = items[0]
    assert first.url == 'https://www.ebay.com/itm/820076566776'
    assert first.price_local == 387.0 and first.currency == 'USD' and first.price_egp == 19350.0
    assert first.condition == 'open_box'
    assert first.zone == 'US' and first.landed_egp is None and first.landed_status == 'unconfirmed'
    assert first.stock == 'unknown' and first.verified_at is None          # card never states stock
    assert first.payments == []                                            # card never states payments
    assert first.used['ships_to_uae'] == 'unknown'                         # delivery shown is for an Egypt visitor, not UAE
    assert 'Located in China' in first.description
    assert {i.condition for i in items} == {'open_box', 'new'}
    assert all('Opens in a new window' not in i.raw_title for i in items)
    assert all(i.source == 'br_us_ebay' for i in items)


def test_bh_split_price_and_stock_text():
    items = br.parse_bh(page('bh_cards.html'), rate=RATE)
    assert [i.price_local for i in items] == [299.99, 459.99]
    assert items[0].url.startswith('https://www.bhphotovideo.com/c/product/1622182-REG/')
    assert items[0].raw_title == 'MSI GeForce RTX 3060 VENTUS 2X OC Graphics Card'
    assert all(i.stock == 'out_of_stock' and i.verified_at for i in items)   # page says "Temporarily Out of Stock"
    assert items[0].sku == 'MSG3060V2X12' and items[0].mpn == 'G3060V2X12C'
    assert items[0].condition == 'new'


def test_bestbuy_prices_stock_and_clean_url():
    items = br.parse_bestbuy(page('bestbuy_cards.html'), rate=RATE)
    assert [i.price_local for i in items] == [399.0, 279.99, 481.2, 487.99]
    assert all(i.stock == 'in_stock' and '#' not in i.url and i.url.startswith('https://www.bestbuy.com/product/') for i in items)
    assert items[0].raw_title.startswith('GIGABYTE - NVIDIA GeForce RTX 3060 12GB')
    assert items[0].old_price_egp is None or items[0].old_price_egp > items[0].price_egp


def test_bestbuy_card_without_loaded_price_is_dropped():
    html = page('bestbuy_cards.html').replace('data-testid="price-block-customer-price"', 'data-testid="x"')
    assert br.parse_bestbuy(html, rate=RATE) == []


def test_backmarket_refurbished_starting_price():
    items = br.parse_backmarket(page('backmarket_cards.html'), rate=RATE)
    assert [i.price_local for i in items] == [635.0, 938.0, 970.0]
    assert all(i.condition == 'refurbished' and i.url.startswith('https://www.backmarket.com/en-us/p/') for i in items)
    assert 'Versus $1,499.00 new' in items[0].description


def test_amazon_keeps_only_dollar_prices():
    html = page('amazon_cards.html')
    # captured as shown to the Egypt-located burner: "See options" without a price, or an EGP price -> nothing in USD
    assert br.parse_amazon(html, rate=RATE) == []
    # derived page (not a capture): the same first card with a "$" price block added
    derived = html.replace('<h2', '<span class="a-price"><span class="a-offscreen">$329.99</span></span><h2', 1)
    assert derived != html
    items = br.parse_amazon(derived, rate=RATE)
    assert items and items[0].price_local == 329.99 and items[0].url.startswith('https://www.amazon.com/dp/')
    assert 'GeForce RTX 3060' in items[0].raw_title


def test_amazon_egp_price_is_never_read_as_dollars():
    card = ('<div data-component-type="s-search-result" data-asin="B000TEST01"><h2><span>ACME</span></h2>'
            '<a href="/x/dp/B000TEST01/ref">Widget 32GB DDR5</a>'
            '<span class="a-price"><span class="a-offscreen">EGP\xa026,227.49</span></span></div>')
    assert br.parse_amazon(card, rate=RATE) == []


@pytest.mark.parametrize('url,title,text,expect', [
    ('https://www.newegg.com/areyouahuman3?itn=true', 'Are you a human?', "we can't quite tell if you're a person or a script", True),
    ('https://www.microcenter.com/search/x', 'Just a moment...', 'Performing security verification', True),
    ('https://www.backmarket.com/testchallengepage?next=x', 'Just a moment...', '', True),
    ('https://www.amazon.com/s?k=x', 'Sorry! Something went wrong!', '', True),
    ('https://www.amazon.com/errors/validateCaptcha', 'Amazon.com', 'Enter the characters you see below', True),
    ('https://www.ebay.com/sch/i.html?_nkw=x', 'Rtx 3060 12GB for sale | eBay', 'Skip to Main content Results Filters', False),
    ('https://www.bhphotovideo.com/c/search?q=x', 'rtx 3060 12gb | B&H Photo Video', 'Please update your browser', False),
    ('https://www.bestbuy.com/site/searchpage.jsp?st=x&intl=nosplash', 'rtx 3060 12gb - Best Buy', 'Techtober Sale', False),
])
def test_wall_detection(url, title, text, expect):
    assert bool(br.detect_wall(url, title, text)) is expect


def test_generic_json_ld_used_only_for_stated_values():
    html = ('<script type="application/ld+json">{"@type":"Product","name":"Test GPU 12GB","offers":{"price":"250.00",'
            '"priceCurrency":"USD","url":"/p/1","availability":"https://schema.org/InStock","itemCondition":"UsedCondition"}}</script>')
    items = br.parse_generic(html, 'br_us_swappa', rate=RATE)
    assert len(items) == 1 and items[0].condition == 'used' and items[0].stock == 'in_stock'
    assert items[0].url == 'https://swappa.com/p/1' and items[0].payments == []
