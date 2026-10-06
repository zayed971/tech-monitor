"""Verify all transferred files and the SQLite history without network access."""
import hashlib
import json
from pathlib import Path
import sqlite3


def main():
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / 'TRANSFER-MANIFEST.json'
    if not manifest_path.exists(): raise SystemExit('Run this inside the extracted complete transfer package.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    errors = []
    for index, entry in enumerate(manifest['files'], 1):
        path = root / entry['path']
        if not path.is_file():
            errors.append('Missing file: ' + entry['path']); continue
        checksum = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''): checksum.update(chunk)
        if checksum.hexdigest() != entry['sha256']: errors.append('Changed file: ' + entry['path'])
        if index % 1000 == 0: print(f'Checked {index} files...', flush=True)
    with sqlite3.connect(f'file:{(root / "data/deals.sqlite3").as_posix()}?mode=ro', uri=True) as db:
        if [row[0] for row in db.execute('PRAGMA integrity_check')] != ['ok']:
            errors.append('SQLite integrity check failed')
        for table, expected in manifest['database_counts'].items():
            if table not in {'listings', 'observations', 'source_runs', 'alerts'}:
                errors.append('Unexpected database table in manifest'); continue
            if db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] != expected:
                errors.append('Database count changed: ' + table)
    if errors:
        for error in errors: print(error)
        raise SystemExit('Transfer verification failed. A running monitor legitimately changes runtime files; verify before starting it.')
    print(json.dumps({'integrity': 'ok', 'files_verified': len(manifest['files']),
                      'database_counts': manifest['database_counts'],
                      'cloud_monitor_stopped_at_snapshot': manifest['cloud_monitor_stopped']}, indent=2))


if __name__ == '__main__': main()
