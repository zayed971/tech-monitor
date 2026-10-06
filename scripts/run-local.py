"""Cross-platform launcher: one collector per database, Telegram opt-in."""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys


@contextmanager
def monitor_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0, 2)
            if lock.tell() == 0:
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            try: yield
            finally:
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try: yield
            finally: fcntl.flock(lock, fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--send', action='store_true', help='Enable Telegram after the cloud sender has stopped')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, '-m', 'egypt_deals.cli', 'watch', '--root', str(root),
               '--scope', 'hardware', '--max-pages', '150', '--max-details', '100',
               '--workers', '4', '--delay', '4', '--cache-ttl', '0', '--poll-seconds', '60']
    if args.send: command.append('--send')
    try:
        with monitor_lock(root / 'data/monitor.lock'):
            print('Local monitor started. Keep this window open and the PC awake.', flush=True)
            return subprocess.call(command, cwd=root, env={**os.environ, 'PYTHONUTF8': '1'})
    except BlockingIOError:
        raise SystemExit('A collector already holds this database lock.')
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__': sys.exit(main())
