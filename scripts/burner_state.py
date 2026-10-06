"""Read-only check of the burner Chrome (CDP 9222): is it logged in to Facebook? Prints only yes/no facts, no page text."""
import sys
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    ctx = browser.contexts[0]
    page = next((pg for pg in ctx.pages if 'facebook.com' in pg.url), None)
    if page is None:
        print('no facebook tab'); sys.exit(0)
    print('url:', page.url)
    login_form = page.locator('input[name="email"], input[name="pass"]').count()
    checkpoint = 'checkpoint' in page.url or 'login' in page.url
    nav_market = page.locator('a[href*="/marketplace/"]').count()
    cookies = [c['name'] for c in ctx.cookies('https://www.facebook.com') if c['name'] in ('c_user', 'xs')]
    print('login_form_fields:', login_form)
    print('checkpoint_or_login_url:', checkpoint)
    print('marketplace_links:', nav_market)
    print('session_cookies_present:', sorted(cookies))
