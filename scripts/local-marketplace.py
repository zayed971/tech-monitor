"""Bounded local Chrome browsing; the owner handles login and prompts."""
import argparse
import csv
import json
from pathlib import Path
import re
from urllib.parse import quote

from egypt_deals.marketplace_local import card_listing
from egypt_deals.model import now


def main():
    parser = argparse.ArgumentParser(description='Collect visible Marketplace product cards in your local Chrome')
    parser.add_argument('--query', action='append', help='Repeat for several searches; default: used gaming PC terms')
    parser.add_argument('--scrolls', type=int, default=3)
    parser.add_argument('--delay', type=float, default=5)
    args = parser.parse_args()
    if not 0 <= args.scrolls <= 20 or args.delay < 4: parser.error('Use 0–20 scrolls and at least 4 seconds delay')
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError:
        raise SystemExit('Install browser support first: python -m pip install -e ".[browser]"')
    root = Path(__file__).resolve().parents[1]
    output = root / 'data/facebook-local'; output.mkdir(parents=True, exist_ok=True)
    profile = root / 'data/local-chrome-profile'
    queries = args.query or ['كيسة كمبيوتر', 'تجميعة جيمنج', 'شاشة كمبيوتر', 'RTX 3060 12GB']
    captured, issues = {}, []
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(profile), channel='chrome', headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto('https://www.facebook.com/marketplace/', wait_until='domcontentloaded', timeout=60000)
            print('A separate Chrome profile is open. Log in there yourself.')
            print('Set Marketplace location to Mansoura/Egypt and ensure prices are in EGP.')
            input('After login and location setup, press Enter here to start the searches: ')
            for query in queries:
                page.goto('https://www.facebook.com/marketplace/search/?query=' + quote(query),
                          wait_until='domcontentloaded', timeout=60000)
                for step in range(args.scrolls + 1):
                    page.wait_for_timeout(args.delay * 1000)
                    # Read only listing links in the currently rendered page.
                    # No background API calls, contact/profile extraction or
                    # challenge bypass. Scrolls use ordinary visible browsing.
                    if re.search(r'/checkpoint|/login|/challenge', page.url):
                        issues.append({'query': query, 'reason': 'Login/challenge needs owner attention; collection stopped'})
                        break
                    cards = page.locator('a[href*="/marketplace/item/"]').evaluate_all(
                        '(links) => links.map(a => ({url:a.href,text:a.innerText})).filter(x => x.text)')
                    count = 0
                    for card in cards:
                        item = card_listing(card['url'], card['text'], now())
                        if item: captured[item.identity] = item; count += 1
                    print(json.dumps({'query': query, 'scroll': step, 'parsed_cards': count, 'unique_candidates': len(captured)}), flush=True)
                    if step < args.scrolls: page.mouse.wheel(0, 900)
                if issues and 'collection stopped' in issues[-1]['reason']: break
                if not count: issues.append({'query': query, 'reason': 'No priced product cards parsed; page layout or access needs review'})
        except Error as error:
            issues.append({'reason': 'Browser navigation/extraction failed: ' + type(error).__name__})
        finally:
            context.close()
    rows = sorted([item.dict() for item in captured.values()], key=lambda r: r['price_egp'])
    # These remain outside the verified-alert database until availability and
    # specs are confirmed. Never label a visible used advert as in stock.
    stamp = now().replace(':', '-')
    destination = output / ('candidates-' + stamp)
    destination.with_suffix('.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    fields = ['raw_title', 'price_egp', 'url', 'observed_at', 'condition', 'stock', 'category']
    with destination.with_suffix('.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); writer.writeheader()
        for row in rows:
            if row['raw_title'].startswith(('=', '+', '-', '@')): row = {**row, 'raw_title': "'" + row['raw_title']}
            writer.writerow(row)
    (output / 'latest-summary.json').write_text(json.dumps({'checked_at': now(), 'candidates': len(rows),
        'queries': queries, 'issues': issues, 'availability': 'Unconfirmed; visible listings are not verified stock',
        'profile_stays_local': True}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Saved {len(rows)} listing candidates to {output}. Availability remains unconfirmed.')


if __name__ == '__main__': main()
