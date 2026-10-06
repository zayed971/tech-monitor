"""Print Zayed's top findings from the database. Read only. Example:
    .venv\\Scripts\\python.exe scripts\\top_findings.py --kind laptop --kind gpu --zone UAE --limit 10
"""
import argparse
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from egypt_deals import findings  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--budget', type=int, default=70000, help='EGP per device, monitor screen excluded')
    p.add_argument('--kind', action='append', choices=['laptop', 'gpu', 'pc', 'ram', 'ssd', 'cpu', 'motherboard', 'psu'])
    p.add_argument('--zone', action='append', choices=['EG', 'UAE', 'KSA', 'US'])
    p.add_argument('--condition', action='append', choices=['new', 'used', 'refurbished', 'open_box'])
    p.add_argument('--limit', type=int, default=10)
    p.add_argument('--max-age-hours', type=float, default=None)
    p.add_argument('--out', help='also write the markdown here')
    a = p.parse_args()
    text, _ = findings.report(root, a.budget, tuple(a.kind or ('laptop', 'gpu', 'pc', 'ram', 'ssd')), a.zone,
                              a.condition, a.limit, a.max_age_hours)
    sys.stdout.reconfigure(encoding='utf-8')
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
