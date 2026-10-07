"""One-screen health report: per source, last run verdict, rows, share of in-stock rows not re-verified in 24h.

Usage: .venv\\Scripts\\python.exe -X utf8 scripts\\health.py
Read-only. Opens the DB in read-only mode.
"""
import collections
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
now = datetime.now(timezone.utc)


def hrs(t):
    try:
        return (now - datetime.fromisoformat(str(t).replace('Z', '+00:00'))).total_seconds() / 3600
    except Exception:
        return None


db = sqlite3.connect(f'file:{ROOT / "data" / "deals.sqlite3"}?mode=ro', uri=True)
last = {}
for source, ran_at, payload in db.execute('select source, ran_at, payload from source_runs order by ran_at'):
    last[source] = (ran_at, json.loads(payload))

rows = collections.Counter()
stale = collections.Counter()
for (p,) in db.execute('select payload from listings'):
    d = json.loads(p)
    s = d.get('source')
    rows[s] += 1
    if d.get('stock') == 'in_stock':
        v = hrs(d.get('verified_at') or d.get('observed_at'))
        if v is None or v > 24:
            stale[s] += 1

print(f'{"source":22} {"last run":16} {"age h":>6} {"ok":>3} {"verdict":8} {"kept":>6} {"rows":>6} {"stale24":>7}')
for s in sorted(set(rows) | set(last)):
    ran_at, p = last.get(s, (None, {}))
    age = hrs(ran_at) if ran_at else None
    print(f'{s:22} {(ran_at or "never")[:16]:16} {age if age is None else round(age, 1)!s:>6} '
          f'{str(p.get("ok", "?")):>3} {str(p.get("verdict", ""))[:8]:8} {p.get("kept", ""):>6} {rows[s]:>6} {stale[s]:>7}')
bad = [s for s, (r, p) in last.items() if p.get('ok') is False]
print('\nFailing or walled last run:', ', '.join(bad) or 'none')
never = sorted(s for s in rows if s not in last)
print('Rows with no source_runs entry:', ', '.join(never) or 'none')
