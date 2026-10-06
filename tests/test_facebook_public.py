import httpx

from egypt_deals.adapters import collect
from egypt_deals.http import Client
from egypt_deals.model import now
from egypt_deals.storage import Database


SOURCE = {
    'id': 'facebook-public', 'name': 'Facebook public probe',
    'base': 'https://www.facebook.com', 'kind': 'used',
    'adapter': 'facebook-public', 'paths': ['/marketplace/cairo/search/?query=pc'] * 8,
    'public_page_limit': 4, 'interval_hours': 24,
}


def test_disallowed_marketplace_is_not_requested_and_failure_waits_a_day(tmp_path):
    calls = []
    def respond(request):
        calls.append(request.url.path)
        assert request.url.path == '/robots.txt'
        return httpx.Response(200, text='User-agent: *\nDisallow: /marketplace/')
    client = Client(tmp_path / 'cache', delay=0, ttl=0)
    client.http.close()
    client.http = httpx.Client(transport=httpx.MockTransport(respond))
    rows, status = collect(SOURCE, client, max_pages=150, scope='hardware')
    client.close()
    assert not rows and calls == ['/robots.txt']
    assert status['status'] == 'blocked_or_failed' and status['pages'] == 0
    assert status['attempted_discovery_paths'] == 1
    db = Database(tmp_path / 'deals.db')
    db.save(rows, status)
    assert not db.due(SOURCE)
    db.close()


def test_public_cards_require_explicit_egp_and_do_not_confirm_stock(tmp_path):
    class Public:
        requests = 0
        def get(self, url, private=False):
            assert private
            self.requests += 1
            return '''<a href="/marketplace/item/123/">EGP 13000<br>Used RTX 3060 12GB<br>PRIVATE NAME</a>
                <a href="/marketplace/item/124/">£12000<br>Used RTX 3060 12GB</a>
                <a href="/marketplace/item/125/">$10000<br>Used RTX 3060 12GB</a>''', url, now()
    client = Public()
    rows, status = collect(SOURCE, client, max_pages=150, scope='hardware')
    assert client.requests == 4 and len(rows) == 1
    assert rows[0].source == 'facebook-public' and rows[0].price_egp == 13000
    assert not rows[0].eligible() and rows[0].stock == 'unknown'
    assert rows[0].seller is None and 'PRIVATE NAME' not in str(rows[0].dict())


def test_login_page_yields_failure_not_inventory():
    class Login:
        requests = 0
        def get(self, url, private=False):
            self.requests += 1
            return '<title>Log in to Facebook</title>', 'https://www.facebook.com/login/', now()
    rows, status = collect(SOURCE, Login(), scope='hardware')
    assert not rows and status['status'] == 'blocked_or_failed'
    assert 'owner attention' in status['errors'][0]
