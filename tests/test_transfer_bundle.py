import argparse
import importlib.util
import json
from pathlib import Path
import shutil
from zipfile import ZipFile

import pytest

from egypt_deals.model import Listing, now
from egypt_deals.storage import Database


@pytest.mark.skipif(shutil.which('zip') is None, reason='Cloud packaging requires zip')
def test_complete_transfer_preserves_ignored_runtime_and_last_database_changes(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / 'scripts/build-transfer-bundle.py'
    spec = importlib.util.spec_from_file_location('build_transfer', script)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    root = tmp_path / 'source'; root.mkdir()
    (root / 'data/cache').mkdir(parents=True)
    cache = root / 'data/cache/response.json'; cache.write_text('{"state":"before"}')
    (root / 'data/watch.json').write_text(json.dumps({'stop_at': '2026-10-26T22:17:33+00:00'}))
    (root / '.env').write_text('DUMMY_CONFIGURATION=local-transfer-test\n')
    (root / '.venv').mkdir(); (root / '.venv/linux-only.txt').write_text('original runtime')
    old = tmp_path / 'egypt-deals-local.zip'
    with ZipFile(old, 'w') as archive: archive.writestr('original-package.txt', 'unchanged')
    original = old.read_bytes()
    db = Database(root / 'data/deals.sqlite3')
    item = Listing(store='test', url='https://example.test/ram', raw_title='DDR5 RAM',
                   observed_at=now(), verified_at=now(), stock='in_stock', price_egp=5000).finish()
    db.save([item], {'source': 'test', 'listings': 1, 'status': 'ok'})
    monkeypatch.setattr(module, 'ROOT', root)
    args = argparse.Namespace(stage=tmp_path / 'stage', output=tmp_path / 'safety.zip',
                              include_private_settings=True, refresh=False, cloud_stopped=False, update_from=None)
    module.snapshot(args)
    stage = args.stage / 'egypt-deals'
    assert (stage / '.env').read_bytes() == (root / '.env').read_bytes()
    assert (stage / 'existing-packages/egypt-deals-local.zip').read_bytes() == original
    assert (stage / 'cloud-only/linux-python-runtime.tar.gz').exists()
    assert not (stage / '.venv').exists()
    cache.write_text('{"state":"after!"}')  # Same size; can change within one ZIP timestamp interval.
    item.observed_at = now(); item.price_egp = 4800
    db.save([item], {'source': 'test', 'listings': 1, 'status': 'ok'})
    db.queue('alert', 'saved alert', item.identity, item.price_egp)
    safety = args.output; args.output = tmp_path / 'final.zip'
    args.refresh = True; args.cloud_stopped = True; args.update_from = safety
    module.snapshot(args)
    db.close()
    with ZipFile(args.output) as archive:
        assert archive.read('egypt-deals/data/cache/response.json') == cache.read_bytes()
        manifest = json.loads(archive.read('egypt-deals/TRANSFER-MANIFEST.json'))
        assert manifest['cloud_monitor_stopped']
        assert manifest['database_counts']['observations'] == 2
        assert manifest['database_counts']['alerts'] == 1
        assert manifest['telegram_credentials_included']
        assert archive.read('egypt-deals/existing-packages/egypt-deals-local.zip') == original
    with ZipFile(safety) as archive:
        assert archive.read('egypt-deals/data/cache/response.json') == b'{"state":"before"}'
