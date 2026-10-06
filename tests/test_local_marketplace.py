import importlib.util
from pathlib import Path

import pytest

from egypt_deals.marketplace_local import card_listing, item_url
from egypt_deals.model import now


URL = 'https://www.facebook.com/marketplace/item/12345/?ref=search'


def test_only_product_urls_survive():
    assert item_url(URL) == 'https://www.facebook.com/marketplace/item/12345/'
    assert item_url('https://www.facebook.com/profile.php?id=12345') is None
    assert item_url('https://facebook.com.attacker.test/marketplace/item/12345') is None


def test_visible_card_is_not_verified_stock_and_location_person_is_not_retained():
    item = card_listing(URL, '£13,000\nUsed RTX 3060 12GB\nPRIVATE SELLER NAME\nMansoura', now())
    assert item.price_egp == 13000 and item.raw_title == 'Used RTX 3060 12GB'
    assert not item.eligible() and item.stock == 'unknown'
    assert item.seller is None and not item.description
    assert 'PRIVATE SELLER NAME' not in str(item.dict())


def test_arabic_price_and_contact_redaction():
    item = card_listing(URL, '١٣٬٠٠٠ جنيه\nRTX 3060 12GB للتواصل 010 1234 5678\nMansoura', now())
    assert item.price_egp == 13000
    assert '1234' not in item.raw_title


@pytest.mark.parametrize('text', ['Sold\n£13,000\nGPU', 'تم البيع\n١٣٠٠٠ جنيه\nGPU',
                                '$13,000\nRTX 3060 12GB', '£1\nRTX 3060', 'No price\nGPU'])
def test_sold_wrong_currency_placeholder_or_unpriced_cards_excluded(text):
    assert card_listing(URL, text, now()) is None


def test_local_launcher_rejects_overlapping_collectors(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'scripts/run-local.py'
    spec = importlib.util.spec_from_file_location('run_local', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with module.monitor_lock(tmp_path / 'monitor.lock'):
        with pytest.raises(OSError):
            with module.monitor_lock(tmp_path / 'monitor.lock'): pass
