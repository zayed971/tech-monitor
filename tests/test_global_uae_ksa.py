from pathlib import Path

import pytest

from egypt_deals import global_uae_ksa as G
from egypt_deals.storage import Database

FIX = Path(__file__).parent / 'fixtures_uae_ksa'
RATE = 50.0


def read(name):
    return (FIX / name).read_text(encoding='utf-8')


def test_sources_have_required_metadata():
    assert len(G.SOURCES) == 13
    for source_id, meta in G.SOURCES.items():
        assert {'zone', 'name', 'kind', 'condition', 'currency', 'payments_claimed'} <= set(meta), source_id
        assert meta['zone'] in {'UAE', 'KSA'} and source_id in G.SEARCH_URL
        if meta['status'] != 'works': assert meta.get('evidence'), source_id


def test_price_text():
    assert G.price_text('AED\xa01,519.00') == ('AED', 1519.0)
    assert G.price_text('2,600 AED') == ('AED', 2600.0)
    assert G.price_text('1,990.00') == (None, 1990.0)
    assert G.price_text('‏1,990.00 ريال') == ('SAR', 1990.0)


def test_amazon_ae_cards():
    rows = G.parse_amazon(read('amazon_ae.html'), 'https://www.amazon.ae')
    assert len(rows) == 2
    first = rows[0]
    assert first['url'] == 'https://www.amazon.ae/dp/B08W8DGK3X'
    assert 'RTX 3060' in first['title'] and first['price'] == 1519.0 and first['currency'] == 'AED'
    assert first['stock'] == 'in_stock' and first['quantity'] == 2          # page says "Only 2 left in stock"
    assert rows[1]['stock'] == 'unknown'                                     # no stock sentence: stays unknown
    assert all(r['condition'] == 'unknown' for r in rows)


def test_amazon_sa_cards_arabic_titles():
    rows = G.parse_amazon(read('amazon_sa.html'), 'https://www.amazon.sa')
    assert len(rows) == 2 and rows[0]['currency'] == 'SAR' and rows[0]['price'] > 0


def test_opensooq_json():
    rows = G.parse_opensooq(read('opensooq_ae.html'), 'https://ae.opensooq.com')
    assert rows and all(r['url'].startswith('https://ae.opensooq.com/en/search/') for r in rows)
    assert all(r['currency'] == 'AED' and r['price'] for r in rows)
    assert {r['condition'] for r in rows} <= {'used', 'new', 'unknown'}
    sa = G.parse_opensooq(read('opensooq_sa.html'), 'https://sa.opensooq.com')
    assert sa and sa[0]['currency'] == 'SAR'


def test_haraj_json_ld():
    rows = G.parse_haraj(read('haraj_sa.html'), 'https://haraj.com.sa')
    assert len(rows) == 4
    assert rows[0]['url'].startswith('https://haraj.com.sa/') and rows[0]['currency'] == 'SAR'
    assert rows[0]['price'] == 950.0 and rows[0]['stock'] == 'in_stock'


def test_wall_detection():
    assert 'Imperva' in G.wall_reason(read('dubizzle_wall.html'))
    assert G.wall_reason('<html>ok</html>') is None


def test_listing_conversion_amazon_and_used():
    row = G.parse_amazon(read('amazon_ae.html'), 'https://www.amazon.ae')[0]
    listing = G.to_listing('amazon_ae', row, '2026-10-07T00:00:00+00:00', RATE)
    assert listing.zone == 'UAE' and listing.currency == 'AED' and listing.price_local == 1519.0
    assert listing.price_egp == round(1519.0 / 3.6725 * RATE, 2)
    assert listing.landed_egp is None and listing.landed_status == 'unconfirmed'
    assert listing.source == 'amazon_ae' and listing.source_kind == 'marketplace'
    assert listing.stock == 'in_stock' and listing.verified_at
    assert listing.payments == [] and listing.condition == 'unknown'
    used = G.parse_haraj(read('haraj_sa.html'), 'https://haraj.com.sa')[0]
    listing = G.to_listing('haraj_sa', used, '2026-10-07T00:00:00+00:00', RATE)
    assert listing.zone == 'KSA' and listing.source_kind == 'used' and listing.seller is None


class FakeClient:
    delay = 2

    def __init__(self, pages): self.pages, self.asked = pages, []

    def get(self, url, **kw):
        self.asked.append(url)
        return self.pages, url, '2026-10-07T00:00:00+00:00'

    def close(self): pass


def test_collect_dedupes_caps_and_saves(tmp_path):
    client = FakeClient(read('haraj_sa.html'))
    listings, status = G.collect('haraj_sa', ['rtx 3060', 'rtx 3070'], root=tmp_path, rate_usd_egp=RATE, max_items=10,
                                 client=client)
    assert status['state'] == 'ok' and status['source'] == 'haraj_sa'
    assert len(listings) == len({l.url for l in listings}) == 4          # second query returns same rows: deduped
    capped, _ = G.collect('haraj_sa', ['a'], root=tmp_path, rate_usd_egp=RATE, max_items=2, client=client)
    assert len(capped) == 2
    db = Database(tmp_path / 'deals.sqlite3')
    db.save(listings, status)
    assert len(db.listings()) == 4


def test_collect_reports_wall_and_browser_sources(tmp_path):
    _, status = G.collect('dubizzle_ae', ['x'], root=tmp_path, rate_usd_egp=RATE, client=FakeClient(read('dubizzle_wall.html')))
    assert status['state'] == 'blocked_http' and 'Imperva' in status['evidence']
    _, status = G.collect('sharaf_ae', ['x'], root=tmp_path, rate_usd_egp=RATE, client=FakeClient('<html>templates only</html>'))
    assert status['state'] == 'needs_browser'


def test_collect_robots_block(tmp_path):
    from egypt_deals.http import FetchError

    class Blocked(FakeClient):
        def get(self, url, **kw): raise FetchError('robots.txt disallows requested URL')

    listings, status = G.collect('noon_ae', ['x'], root=tmp_path, rate_usd_egp=RATE, client=Blocked(''))
    assert listings == [] and status['state'] == 'blocked_robots' and status['evidence']
