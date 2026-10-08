from egypt_deals import findings
from egypt_deals.hardware import classify
from egypt_deals.model import Listing, extract_specs


def make(title, price, source='x', **kw):
    return Listing(store=source, url='https://example.test/' + title[:12], raw_title=title, price_egp=price, source=source, **kw).finish()


def test_new_only_shop_defaults_to_new_and_says_why():
    for source in ('2b', 'egyptlaptop', 'btech', 'br_noon_ae', 'br_us_bestbuy'):
        l = make('Logitech M171 Wireless Mouse', 500, source)
        assert (l.condition, l.condition_basis) == ('new', 'source_default')


def test_marketplaces_keep_unknown_condition():
    for source in ('amazon_ae', 'facebook-burner', 'qarenly', 'opensooq_ae'):
        assert make('Logitech M171 Wireless Mouse', 500, source).condition == 'unknown'


def test_title_wins_over_source_default():
    assert make('Dell Latitude Renewed', 9000, 'br_noon_eg').condition == 'refurbished'
    assert make('Dell Latitude used', 9000, '2b').condition == 'used'
    assert make('Monitor open-box', 3000, 'br_us_bestbuy').condition == 'open_box'


def test_storage_ignores_gpu_memory_and_pcie_generation():
    assert extract_specs('ASUS Vivobook 15 DDR5 8GB 512GB M.2 NVMe PCIe 4.0 SSD')['storage_gb'] == 512
    assert extract_specs('HP laptop i5-13420H 8GB RAM M.2 NVMe 512GB RTX 3050 6GB')['storage_gb'] == 512
    l = make('Gaming PC Ryzen 5 5600 | 32GB RAM | 1TB SSD | RTX 5060 Ti 8GB', 40000)
    assert l.category == 'pc' and l.specs['storage_gb'] == 1000 and l.specs['gpu_vram_gb'] == 8


def test_tiny_storage_on_a_computer_is_dropped_and_flagged():
    l = make('Gaming laptop Core i7 13620H 16GB RAM 8 SSD RTX 4060', 50000)
    assert l.specs['storage_gb'] in (None, 8) and (l.specs['storage_gb'] is None or l.quality_issues)


def test_implausible_psu_price_is_flagged_and_unusable():
    l = make('Creative 1800W 80 Plus White ATX Power Supply', 525, 'kimo')
    assert l.category == 'psu' and any('implausible' in q for q in l.quality_issues)
    assert findings.usable(l) is False
    assert not make('Cooler Master MWE Gold 750W 80 Plus Gold Power Supply', 3950, 'kimo').quality_issues


def test_camera_supply_and_mini_ups_are_not_pc_power_gear():
    assert classify('camera power supply 300w 12v 25a') == 'accessory'
    assert classify('mini dc ups 12v 36w for router') != 'ups'
    assert classify('javac bw600 line interactive ups 600va') == 'ups'


def test_wanted_ads_are_not_offers():
    for title in ('مطلوب كارت شاشه rtx 3060 12 gb', 'Buying RTX Graphic Card'):
        l = make(title, 9999, 'facebook-burner', source_kind='used')
        assert findings.not_a_real_offer(l) and findings.usable(l) is False
    assert not findings.not_a_real_offer(make('Zotac RTX 3060 12GB used', 12000, 'facebook-burner', source_kind='used'))


def test_stored_rows_are_refreshed_when_read():
    old = make('Logitech M171 Wireless Mouse', 500, '2b')
    old.condition, old.condition_basis = 'unknown', None
    assert old.refresh_on_read().condition == 'new'


def test_classifier_catches_graphics_cards_switches_fans_and_cases():
    assert classify('gigabyte gtx 1650 windforce oc 4g graphic card') == 'gpu'
    assert classify('tp-link ls1210gp desktop poe+ switch, 10-port gigabit ethernet') == 'network'
    assert classify('id-cooling as-140-argb-w 140mm argb pwm hydraulic bearing white fan') == 'cooler'
    assert classify('xpg starker air mid-tower chassis with magnetic mesh front panel white') == 'case'
    assert classify('oppo a6 dual sim 128gb 6gb ram 4g') == 'other'


def test_same_model_from_several_stores_folds_into_the_cheapest_row():
    rows = [make('Redragon K552-KR Kumara Mechanical Keyboard', p, s) for p, s in ((1450, 'a'), (1150, 'b'), (1399, 'c'))]
    for r in rows: r.stock, r.category = 'in_stock', 'ssd'
    picked = findings.pick(rows, 'cpu', 70000)
    assert picked == []
    keyed = {findings.model_key(findings.row(r)) for r in rows}
    assert len(keyed) == 1


def test_rate_limit_429_slows_the_host_and_retries_before_pausing(monkeypatch, tmp_path):
    import httpx
    from egypt_deals import http as h
    calls = []

    class Resp:
        def __init__(self, code): self.status_code, self.headers, self.text, self.is_redirect = code, {'retry-after': '1'}, '', False

    client = h.Client(tmp_path, delay=0)
    monkeypatch.setattr(h.time, 'sleep', lambda s: None)
    codes = iter([429, 429, 200])
    monkeypatch.setattr(client.http, 'get', lambda url: (calls.append(url), Resp(next(codes)))[1])
    assert client._request('https://slow.example/page').status_code == 200
    assert len(calls) == 3 and client.slow['slow.example'] == 4 and 'slow.example' not in client.blocked
    codes = iter([429, 429, 429])
    assert client._request('https://slow.example/again').status_code == 429
    assert 'slow.example' in client.blocked


def test_multi_capacity_storage_title_without_variant_is_flagged():
    l = make('Crucial P3 NVMe M.2 2280 SSD (500 GB / 1 TB / 2 TB)', 4200, 'elyamama')
    assert l.category == 'ssd' and findings.not_a_real_offer(l)
    ok = make('Crucial P3 NVMe M.2 2280 SSD 2TB', 10000, 'elyamama')
    assert not findings.not_a_real_offer(ok)
    chosen = make('Crucial P3 NVMe M.2 2280 SSD (500 GB / 1 TB / 2 TB)', 10000, 'elyamama', variant_title='2TB')
    assert not findings.not_a_real_offer(chosen)


def test_mislabeled_currency_on_an_egyptian_listing_is_not_trusted():
    l = make('Lenovo LOQ 15IRX10 laptop RTX 5060', 130800, 'pricena', currency='AED')
    assert findings.not_a_real_offer(l) and findings.usable(l) is False
    assert not findings.not_a_real_offer(make('Lenovo LOQ 15IRX10 laptop RTX 5060', 60000, 'compumarts'))


def test_spec_words_do_not_make_models_and_variants_split():
    from egypt_deals.findings import model_tokens
    assert model_tokens('Rapoo M50 Plus 3200 DPI Silent Black 2.4GHz Wireless Mouse') is None
    assert model_tokens('Logitech G502 Hero Gaming Mouse') != model_tokens('Logitech G502 X Plus Lightspeed')
    assert model_tokens('WD SN850X 1TB') != model_tokens('WD SN850X 2TB')
