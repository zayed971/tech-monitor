import pytest

from egypt_deals.facebook_burner import card_listing_zone, parse_price
from egypt_deals.model import now

URL = 'https://www.facebook.com/marketplace/item/999/?ref=search'
RATE = 50.0


@pytest.mark.parametrize('text,expected', [
    ('£13,000', (13000.0, 'EGP')), ('E£ 13,000', (13000.0, 'EGP')), ('EGP 9500', (9500.0, 'EGP')),
    ('١٣٬٠٠٠ جنيه', (13000.0, 'EGP')), ('AED 1,200', (1200.0, 'AED')), ('1,200 د.إ', (1200.0, 'AED')),
    ('Dhs 800', (800.0, 'AED')), ('SAR 900', (900.0, 'SAR')), ('٩٠٠ ر.س', (900.0, 'SAR')),
    ('SR 450', (450.0, 'SAR')), ('$450', (450.0, 'USD')), ('US$1,299.99', (1299.99, 'USD')),
    ('Free', (None, None)), ('Mansoura', (None, None)), ('', (None, None))])
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_egypt_card_stays_egp_and_unverified():
    i = card_listing_zone(URL, '£13,000\nUsed RTX 3060 12GB\nMansoura\nSELLER NAME', now(), 'EG', RATE)
    assert i.source == 'facebook-burner' and i.source_kind == 'used' and i.condition == 'used'
    assert i.currency == 'EGP' and i.price_egp == 13000 and i.zone == 'EG'
    assert i.stock == 'unknown' and i.verified_at is None and i.seller is None and not i.description
    assert 'SELLER NAME' not in str(i.dict())
    assert i.url == 'https://www.facebook.com/marketplace/item/999/'


def test_egypt_zone_rejects_foreign_currency():
    assert card_listing_zone(URL, '$450\nRTX 3060', now(), 'EG', RATE) is None


def test_uae_card_converted():
    i = card_listing_zone(URL, 'AED 1,800\nRTX 3070 8GB graphics card\nDubai', now(), 'UAE', RATE)
    assert i.zone == 'UAE' and i.currency == 'AED' and i.price_local == 1800
    assert i.price_egp == pytest.approx(1800 / 3.6725 * 50, abs=0.01)
    assert i.landed_egp is None and i.landed_status == 'unconfirmed'


def test_ksa_arabic_card():
    i = card_listing_zone(URL, '١٬٥٠٠ ر.س\nكارت شاشة RTX 3080\nالرياض', now(), 'KSA', RATE)
    assert i.currency == 'SAR' and i.price_local == 1500 and i.price_egp == pytest.approx(1500 / 3.75 * 50)


def test_us_card_and_new_condition():
    i = card_listing_zone(URL, '$450\nBrand new sealed RTX 4060\nBrooklyn, NY', now(), 'US', RATE)
    assert i.currency == 'USD' and i.price_egp == 22500 and i.condition == 'new'


def test_no_rate_leaves_price_egp_unknown():
    i = card_listing_zone(URL, 'SAR 900\nRTX 3060', now(), 'KSA', None)
    assert i.price_egp is None and i.price_local == 900


@pytest.mark.parametrize('zone,text', [('EG', 'Sold\n£13,000\nGPU'), ('EG', 'تم البيع\n١٣٠٠٠ جنيه\nGPU'),
                                       ('UAE', 'Pending\nAED 900\nGPU'), ('EG', 'No price\nGPU'),
                                       ('EG', '£1\nRTX 3060'), ('EG', '£13,000'), ('EG', 'Free\nRTX 3060'),
                                       ('EG', '')])
def test_sold_pending_junk_excluded(zone, text):
    assert card_listing_zone(URL, text, now(), zone, RATE) is None


def test_non_item_url_excluded():
    assert card_listing_zone('https://www.facebook.com/profile.php?id=1', '£13,000\nGPU', now(), 'EG', RATE) is None
