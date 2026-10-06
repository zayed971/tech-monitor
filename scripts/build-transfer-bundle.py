"""Snapshot the complete project for Windows, including ignored runtime data.

This is separate from the older, reduced, credential-free local bundle.
Run once before stopping the cloud process, and again afterwards with --refresh.
Credentials are copied as opaque files only when explicitly requested.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
import time
from zipfile import ZipFile

from egypt_deals.model import now


ROOT = Path(__file__).resolve().parents[1]
GENERATED = {'.venv', '.pytest_cache', '__pycache__', 'egypt_deals.egg-info'}
TRANSIENT = {'data/deals.sqlite3', 'data/deals.sqlite3-wal', 'data/deals.sqlite3-shm',
             'data/deals.sqlite3-journal', 'data/monitor.lock', 'data/monitor.pid'}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def same_file(source, target):
    if not target.exists(): return False
    left, right = source.stat(), target.stat()
    return left.st_size == right.st_size and left.st_mtime_ns == right.st_mtime_ns


def copy_atomic(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.transfer-copy')
    shutil.copy2(source, temporary)
    temporary.replace(target)


def snapshot(args):
    start = time.monotonic()
    stage = args.stage.resolve() / 'egypt-deals'
    stage.mkdir(parents=True, exist_ok=True)
    stage.chmod(0o700)
    source_files = []
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [name for name in dirs if name not in GENERATED]
        for name in names:
            path = Path(base) / name
            relative = path.relative_to(ROOT).as_posix()
            if relative in TRANSIENT: continue
            if relative == '.env' and not args.include_private_settings: continue
            source_files.append((path, relative))
    # Capture inventories before the database: an interrupted checkpoint can
    # lag its committed rows, but must never get ahead of them in the snapshot.
    source_files.sort(key=lambda item: (not item[1].startswith('data/harvest-state/'), item[1]))
    changed = 0
    for index, (source, relative) in enumerate(source_files, 1):
        target = stage / relative
        if not args.refresh or not same_file(source, target):
            copy_atomic(source, target)
            changed += 1
        if index % 1000 == 0:
            print(json.dumps({'stage': 'copy', 'files_seen': index, 'changed_files': changed,
                              'elapsed_seconds': round(time.monotonic() - start)}), flush=True)
    # Machine-specific Python files remain preserved, away from the Windows
    # .venv which Setup-Windows.cmd recreates for the correct operating system.
    runtime = stage / 'cloud-only/linux-python-runtime.tar.gz'
    runtime.parent.mkdir(exist_ok=True)
    runtime_temporary = runtime.with_name(runtime.name + '.tmp')
    with tarfile.open(runtime_temporary, 'w:gz', compresslevel=3) as archive:
        for path in ROOT.iterdir():
            if path.name in GENERATED: archive.add(path, arcname=path.name)
        for path in ROOT.rglob('__pycache__'):
            if '.venv' not in path.parts:
                archive.add(path, arcname=path.relative_to(ROOT).as_posix())
    runtime_temporary.replace(runtime)
    for name in ['monitor.pid', 'monitor.lock']:
        path = ROOT / 'data' / name
        if path.exists(): copy_atomic(path, stage / 'cloud-only' / name)
    (stage / 'data/monitor.lock').write_bytes(b'')
    legacy = []
    for name in ['egypt-deals-local.zip', 'egypt-deals.zip']:
        source = ROOT.parent / name
        if not source.exists(): continue
        target = stage / 'existing-packages' / name
        if not same_file(source, target): copy_atomic(source, target)
        legacy.append({'name': name, 'bytes': source.stat().st_size, 'sha256': digest(source)})
    backup = stage / 'data/deals.sqlite3.transfer-copy'
    if backup.exists(): backup.unlink()
    source = sqlite3.connect(f'file:{ROOT / "data/deals.sqlite3"}?mode=ro', uri=True, timeout=60)
    target = sqlite3.connect(backup)
    try:
        source.backup(target, pages=1024)
        check = [row[0] for row in target.execute('PRAGMA integrity_check')]
        if check != ['ok']: raise RuntimeError('SQLite snapshot integrity check failed')
        counts = {name: target.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0]
                  for name in ['listings', 'observations', 'source_runs', 'alerts']}
    finally:
        source.close(); target.close()
    backup.replace(stage / 'data/deals.sqlite3')
    files = []
    for index, path in enumerate(sorted(stage.rglob('*')), 1):
        if not path.is_file() or path.name == 'TRANSFER-MANIFEST.json': continue
        relative = path.relative_to(stage).as_posix()
        files.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': digest(path)})
        if index % 1000 == 0:
            print(json.dumps({'stage': 'hash', 'files_hashed': len(files),
                              'elapsed_seconds': round(time.monotonic() - start)}), flush=True)
    manifest = {
        'created_at': now(), 'original_project_root': str(ROOT), 'prepared_project_root': str(stage),
        'database_integrity': 'ok', 'database_counts': counts,
        'cloud_monitor_stopped': args.cloud_stopped,
        'original_watch_deadline': json.loads((stage / 'data/watch.json').read_text())['stop_at'],
        'telegram_credentials_included': args.include_private_settings and (stage / '.env').exists(),
        'ignored_runtime_data_included': True,
        'linux_runtime_preserved_at': 'cloud-only/linux-python-runtime.tar.gz',
        'existing_packages': legacy, 'payload_files': len(files),
        'payload_bytes': sum(item['bytes'] for item in files), 'files': files,
        'notes': ['This private package is for the owner; it includes Telegram configuration when requested.',
                  'Run Setup-Windows.cmd to recreate the Windows Python environment.',
                  'SQLite is an online backup, not a raw copy of an active database.',
                  'Temporary process IDs and the former lock are archival; the local lock is empty.',
                  'All ignored cache, reports, crawl queues, observation and alert history are preserved.'],
    }
    (stage / 'TRANSFER-MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.update_from:
        with ZipFile(args.update_from) as archive:
            previous = json.loads(archive.read('egypt-deals/TRANSFER-MANIFEST.json'))
        previous_hashes = {item['path']: item['sha256'] for item in previous['files']}
        changed_paths = ['egypt-deals/' + item['path'] for item in files
                         if previous_hashes.get(item['path']) != item['sha256']]
        changed_paths.append('egypt-deals/TRANSFER-MANIFEST.json')
        if any('\n' in name for name in changed_paths): raise RuntimeError('Unsupported newline in ZIP file name')
        if output.exists(): output.unlink()
        # Replace named changed files unconditionally. ZIP timestamps have
        # two-second precision, so -u can miss a freshly changed checkpoint.
        # --out copies unchanged compressed entries straight into a separate
        # archive. It preserves the safety ZIP without needing a third full
        # archive's worth of temporary space during an in-place update.
        command = ['zip', '-q', '-3', str(args.update_from.resolve()), '--out', str(output), '-@']
        print(json.dumps({'stage': 'update_archive', 'output': str(output)}), flush=True)
        subprocess.run(command, cwd=args.stage, input='\n'.join(changed_paths) + '\n', text=True, check=True)
    else:
        temporary = output.with_name(output.stem + '.partial.zip')
        if temporary.exists(): temporary.unlink()
        print(json.dumps({'stage': 'create_archive', 'output': str(output)}), flush=True)
        subprocess.run(['zip', '-q', '-r', '-3', str(temporary), 'egypt-deals'], cwd=args.stage, check=True)
        temporary.chmod(0o600)
        temporary.replace(output)
    output.chmod(0o600)
    print(json.dumps({'stage': 'verify_archive', 'bytes': output.stat().st_size}), flush=True)
    with ZipFile(output) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)): raise RuntimeError('Duplicate archive entries')
        expected = {'egypt-deals/' + item['path'] for item in files}
        if not expected.issubset(names): raise RuntimeError('Missing archived files')
        # Verify every file against the snapshot, not just ZIP CRCs.
        for index, item in enumerate(files, 1):
            result = hashlib.sha256()
            with archive.open('egypt-deals/' + item['path']) as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                    result.update(chunk)
            if result.hexdigest() != item['sha256']:
                raise RuntimeError('Archive hash mismatch: ' + item['path'])
            if index % 1000 == 0:
                print(json.dumps({'stage': 'verify_archive', 'files_verified': index,
                                  'elapsed_seconds': round(time.monotonic() - start)}), flush=True)
        if archive.read('egypt-deals/TRANSFER-MANIFEST.json') != (stage / 'TRANSFER-MANIFEST.json').read_bytes():
            raise RuntimeError('Archive manifest did not update')
    checksum = digest(output)
    output.with_suffix(output.suffix + '.sha256').write_text(checksum + '  ' + output.name + '\n', encoding='utf-8')
    result = {'bundle': str(output), 'project_root': str(stage), 'bytes': output.stat().st_size,
              'sha256': checksum, 'payload_files': len(files), 'database_counts': counts,
              'cloud_monitor_stopped': args.cloud_stopped, 'integrity': 'ok',
              'elapsed_seconds': round(time.monotonic() - start)}
    output.with_suffix('.verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, default=ROOT.parent / 'egypt-deals-transfer')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--include-private-settings', action='store_true')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--cloud-stopped', action='store_true')
    parser.add_argument('--update-from', type=Path)
    args = parser.parse_args()
    if not shutil.which('zip'): parser.error('The transfer builder requires the cloud zip utility')
    snapshot(args)


if __name__ == '__main__': main()
