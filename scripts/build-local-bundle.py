"""Create a credential-free local bundle with a consistent database backup."""
import json
from pathlib import Path
import sqlite3
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from egypt_deals.model import now


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root.parent / 'egypt-deals-local.zip'
    # Inventory captured before the DB snapshot may lag its checkpoints,
    # which is safe: the local collector can recheck those pages.
    states = {p.relative_to(root).as_posix(): p.read_bytes()
              for p in (root / 'data/harvest-state').glob('*.json')}
    files = [root / name for name in ['pyproject.toml', 'README.md', 'LOCAL-PC.md', 'HANDOFF.md', '.gitignore', '.env.example',
             'sources.json', 'rules.json', 'references.json', 'coverage.json', 'import-quote.example.json']]
    files += list(root.glob('*.cmd'))
    for directory in ['egypt_deals', 'tests', 'scripts']:
        files += list((root / directory).glob('*.py'))
    for directory in ['data/hardware', 'data/ram-top10', 'data/screen-top10', 'data/small-screen-top10']:
        files += [p for p in (root / directory).glob('*') if p.suffix in {'.json', '.csv', '.md'}]
    for name in ['data/watch.json', 'data/laptop-search.json', 'data/report.md', 'data/used-pc-candidates.json']:
        p = root / name
        if p.exists(): files.append(p)
    with tempfile.TemporaryDirectory() as temporary:
        backup = Path(temporary) / 'deals.sqlite3'
        source = sqlite3.connect(f'file:{root / "data/deals.sqlite3"}?mode=ro', uri=True)
        copy = sqlite3.connect(backup)
        try:
            source.backup(copy, pages=1024)
            check = copy.execute('PRAGMA quick_check').fetchone()[0]
            if check != 'ok': raise RuntimeError('Database backup failed its integrity check')
            counts = {'listings': copy.execute('SELECT COUNT(*) FROM listings').fetchone()[0],
                      'observations': copy.execute('SELECT COUNT(*) FROM observations').fetchone()[0]}
        finally:
            source.close(); copy.close()
        manifest = {'created_at': now(), 'database_integrity': check, **counts,
                    'telegram_credentials_included': False, 'browser_profiles_included': False,
                    'cloud_monitor_stopped': False, 'original_watch_deadline_preserved': True,
                    'facebook_live_account_tested': False}
        with ZipFile(destination, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
            for p in files:
                if p.exists(): archive.write(p, 'egypt-deals/' + p.relative_to(root).as_posix())
            for name, content in states.items(): archive.writestr('egypt-deals/' + name, content)
            archive.write(backup, 'egypt-deals/data/deals.sqlite3')
            archive.writestr('egypt-deals/LOCAL-BUNDLE-MANIFEST.json', json.dumps(manifest, indent=2))
        with ZipFile(destination) as archive:
            if any(name.endswith('/.env') or 'chrome-profile/' in name or '/.venv/' in name for name in archive.namelist()):
                raise RuntimeError('Disallowed private/runtime files in bundle')
            if archive.testzip() is not None: raise RuntimeError('Bundle CRC validation failed')
        print(json.dumps({'bundle': str(destination), 'size_mb': round(destination.stat().st_size / 1048576, 1), **manifest}), flush=True)


if __name__ == '__main__': main()
