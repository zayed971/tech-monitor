"""One-shot diagnostic: show the first few Marketplace card text lines (price/title only) so the parser can be fixed.
Read only. Opens its own tab in the burner Chrome, one page load, closes it. Prints no seller names or cookies."""
import re
import sys
from playwright.sync_api import sync_playwright

city = sys.argv[1] if len(sys.argv) > 1 else 'mansoura'
query = sys.argv[2] if len(sys.argv) > 2 else 'RTX 3060'
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    try:
        page.goto(f'https://www.facebook.com/marketplace/{city}/search?query={query.replace(" ", "%20")}&exact=false',
                  wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(9000)
        print('url:', page.url)
        if re.search(r'checkpoint|login|challenge', page.url):
            print('STOP: login/checkpoint page'); sys.exit(0)
        cards = page.locator('a[href*="/marketplace/item/"]').evaluate_all(
            '(links) => links.map(a => ({href:a.getAttribute("href"), text:a.innerText})).filter(x => x.text)')
        print('cards with text:', len(cards))
        for c in cards[:4]:
            lines = [l.strip() for l in c['text'].splitlines() if l.strip()]
            print('--- card:', re.sub(r'\?.*', '', c['href'])[:60])
            for l in lines[:5]:
                print('   ', l[:70])
    finally:
        page.close()
