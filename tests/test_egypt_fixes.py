import httpx

from egypt_deals.adapters import collect
from egypt_deals.model import now

PRODUCT = ('<html><head><script type="application/ld+json">{"@type":"Product","name":"Test 16GB DDR5 RAM Kit",'
           '"offers":{"@type":"Offer","price":"1500","priceCurrency":"EGP","availability":"https://schema.org/InStock"}}'
           '</script></head><body><h1>Test 16GB DDR5 RAM Kit</h1></body></html>')


def make_client(sitemap, bad_url_exception=False):
    class Client:
        ttl = 0
        requests = 0
        def __init__(self): self.seen = []
        def get(self, url, private=False):
            self.seen.append(url)
            if url.endswith('/sitemap.xml'): return sitemap, url, now()
            if bad_url_exception and any(c in url for c in '\t\n '): raise httpx.InvalidURL('bad')
            return PRODUCT, url, now()
    return Client()


def test_sitemap_locations_with_trailing_whitespace_are_cleaned():
    # B.TECH publishes product URLs with a trailing tab; that crashed the whole source.
    sitemap = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
               '<url><loc>https://shop.example/en/p/kit-16gb-ddr5-ram\t</loc>'
               '<xhtml:link rel="alternate" hreflang="en" href="https://shop.example/en/p/kit-16gb-ddr5-ram\t"/></url></urlset>')
    source = {'id': 'x', 'name': 'X', 'base': 'https://shop.example', 'adapter': 'sitemap',
              'sitemap': '/sitemap.xml', 'product_url_regex': '/en/p/', 'prefer_english': True}
    client = make_client(sitemap, bad_url_exception=True)
    rows, status = collect(source, client, max_pages=2, max_details=2, scope='hardware')
    assert len(rows) == 1 and rows[0].price_egp == 1500
    assert all(u == u.strip() for u in client.seen)


def test_invalid_url_on_one_product_page_does_not_kill_the_source():
    sitemap = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               '<url><loc>https://shop.example/p/ddr5-ram-a</loc></url></urlset>')
    source = {'id': 'x', 'name': 'X', 'base': 'https://shop.example', 'adapter': 'sitemap', 'sitemap': '/sitemap.xml'}

    class Client(make_client(sitemap).__class__):
        def get(self, url, private=False):
            if 'ddr5-ram-a' in url: raise httpx.InvalidURL('bad')
            return super().get(url, private)
    rows, status = collect(source, Client(), max_pages=2, max_details=2, scope='hardware')
    assert rows == [] and status['status'] == 'blocked_or_failed'
    assert any('bad' in str(f) or 'bad' in f.get('reason', '') for f in status.get('failed_product_pages', []))


def test_amazon_product_page_price_and_stock_without_json_ld():
    from egypt_deals.adapters import product_html
    html = ('<html><body><span id="productTitle"> Hiksemi 8GB DDR3 Desktop RAM </span>'
            '<div id="corePrice_feature_div"><span class="a-offscreen">جنيه ‎777.00‎</span></div>'
            '<div id="availability"><span>متوفر</span></div></body></html>')
    source = {'id': 'amazon-eg', 'name': 'Amazon Egypt', 'base': 'https://www.amazon.eg', '_scope': 'hardware'}
    rows = product_html(html, source, 'https://www.amazon.eg/dp/B0CN4GS611', now())
    assert len(rows) == 1 and rows[0].price_egp == 777.0 and rows[0].stock == 'in_stock'
    # No price on the page means no row (never an invented price).
    assert product_html(html.replace('a-offscreen', 'x'), source, 'https://www.amazon.eg/dp/B0CN4GS611', now()) == []
    # Unknown availability wording stays unknown.
    odd = html.replace('متوفر', 'ships in 3 weeks')
    assert product_html(odd, source, 'https://www.amazon.eg/dp/B0CN4GS611', now())[0].stock == 'unknown'
