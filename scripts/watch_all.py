"""Keep every lane collecting, forever, one job at a time. No alerts, nothing is sent anywhere.

    .venv\\Scripts\\python.exe scripts\\watch_all.py            # loop until you close the window or create data\\STOP_WATCH
    .venv\\Scripts\\python.exe scripts\\watch_all.py --once     # one pass of everything due, then exit

Lanes and how often (hours): Egyptian shops 4, UAE+KSA stores 3, US stores 4, Facebook Marketplace 8 per zone (a brand-new
burner account must be browsed slowly), Reddit is inside the US lane. A job only starts when free RAM is at least 2.5 GB.
The Facebook and Reddit lanes need the burner Chrome (CDP 9222) running and logged in; if it is not, they are skipped and
the reason is written to data/watch_all.log, never worked around.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / '.venv' / 'Scripts' / 'python.exe')
STATE = ROOT / 'data' / 'watch_all_state.json'
LOG = ROOT / 'data' / 'watch_all.log'
STOP = ROOT / 'data' / 'STOP_WATCH'

JOBS = [
    # name, hours between runs, command, needs burner Chrome
    ('egypt-shops', 4, ['-m', 'egypt_deals.cli', 'run', '--root', '.', '--scope', 'hardware', '--max-pages', '4',
                        '--max-details', '10', '--workers', '3', '--delay', '4'], False),
    ('uae-ksa-stores', 3, ['scripts/run_uae_ksa.py', '--source', 'amazon_ae', '--source', 'amazon_sa', '--source',
                           'opensooq_ae', '--source', 'opensooq_sa', '--source', 'haraj_sa', '--max-items', '900'], False),
    ('us-stores', 4, ['scripts/run_us.py', '--source', 'us_wisetek', '--source', 'us_techmikeny', '--source',
                      'us_pcliquidations', '--source', 'us_reddit_hardwareswap', '--max-items', '800'], True),
    ('burner-gulf-shops', 6, ['scripts/run_burner_gulf.py'], True),
    ('burner-us-shops', 8, ['scripts/run_burner_us.py'], True),
    ('facebook-EG', 8, ['scripts/run_facebook.py', '--zone', 'EG', '--city', 'mansoura', '--scrolls', '2', '--delay', '8'], True),
    ('facebook-UAE', 8, ['scripts/run_facebook.py', '--zone', 'UAE', '--city', 'dubai', '--scrolls', '2', '--delay', '8'], True),
    ('facebook-KSA', 8, ['scripts/run_facebook.py', '--zone', 'KSA', '--city', 'riyadh', '--scrolls', '2', '--delay', '8'], True),
]


def log(msg):
    line = f'{datetime.now().astimezone().isoformat(timespec="seconds")} {msg}'
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open('a', encoding='utf-8') as f: f.write(line + '\n')
    print(line, flush=True)


def free_ram_gb():
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [('l', ctypes.c_ulong), ('m', ctypes.c_ulong), ('tp', ctypes.c_ulonglong), ('ap', ctypes.c_ulonglong),
                    ('tpf', ctypes.c_ulonglong), ('apf', ctypes.c_ulonglong), ('tv', ctypes.c_ulonglong), ('av', ctypes.c_ulonglong),
                    ('ae', ctypes.c_ulonglong)]
    m = MS(); m.l = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ap / 2**30


def burner_up():
    try:
        urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=3).read()
        return True
    except Exception:
        return False


def load_state():
    try: return json.loads(STATE.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError): return {}


def save_state(state):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1), encoding='utf-8')


def due(state, name, hours):
    last = state.get(name)
    return last is None or time.time() - last >= hours * 3600


def run_job(name, args, needs_burner, state):
    if needs_burner and not burner_up():
        log(f'SKIP {name}: burner Chrome (port 9222) is not running')
        return
    if free_ram_gb() < 2.5:
        log(f'WAIT {name}: free RAM {free_ram_gb():.1f} GB < 2.5')
        return
    log(f'START {name}')
    t0 = time.time()
    r = subprocess.run([PY, '-X', 'utf8', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env={**__import__('os').environ, 'PYTHONUTF8': '1'})
    tail = (r.stdout or '').strip().splitlines()[-1:] or ['']
    log(f'END {name} exit={r.returncode} {time.time() - t0:.0f}s | {tail[0][:200]}')
    if r.returncode != 0 and r.stderr: log('  stderr: ' + r.stderr.strip().splitlines()[-1][:200])
    state[name] = time.time()
    save_state(state)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--once', action='store_true')
    a = ap.parse_args()
    state = load_state()
    log('watch_all started (no alerts; read only)')
    while not STOP.exists():
        ran = False
        for name, hours, args, burner in JOBS:
            if STOP.exists(): break
            if due(state, name, hours):
                run_job(name, args, burner, state); ran = True
        if a.once: break
        if not ran: time.sleep(120)
    log('watch_all stopped')


if __name__ == '__main__':
    sys.exit(main())
