"""Real Chromium + FastAPI PWA checks with synthetic data and no Supabase access.

Run: python tests/pwa_browser.py (Playwright + Chromium required).
"""
import asyncio
import socket
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, patch

import uvicorn
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app as budget


async def account_for(request):
    token = request.cookies.get(budget.SESSION_COOKIE)
    if token not in ('synthetic-a', 'synthetic-b'):
        return None
    number = 1 if token.endswith('a') else 2
    return dict(id=number, household_id=number, username=f'Synthetic account {number}', role='owner', language='en')


async def synthetic_db(method, table, **kwargs):
    if table == 'rpc/get_budget_dashboard_monthly':
        number = kwargs['json']['p_household_id']
        return dict(household=dict(id=number, name=f'Private household {number}'), people=[], categories=[], entries=[])
    if table == 'households':
        return [dict(id=1, name='Synthetic grocery household')]
    return []


async def main():
    # Bind an unused loopback port; keep the existing application/security stack.
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(budget.app, log_level='error', loop='asyncio'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    with patch.object(budget, 'current_account', account_for), \
         patch.object(budget.db, 'request', AsyncMock(side_effect=synthetic_db)) as db:
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                await asyncio.sleep(.05)
            assert server.started
            origin = f'http://localhost:{port}'
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                context = await browser.new_context(viewport={'width': 390, 'height': 844})
                await context.add_cookies([dict(name=budget.SESSION_COOKIE, value='synthetic-a', url=origin)])
                page = await context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                await page.goto(origin)
                await page.evaluate('navigator.serviceWorker.ready')
                await page.wait_for_function('navigator.serviceWorker.controller !== null')
                scope = await page.evaluate('(async () => (await navigator.serviceWorker.ready).scope)()')
                assert scope == origin + '/'
                cdp = await context.new_cdp_session(page)
                manifest = await cdp.send('Page.getAppManifest')
                assert not manifest['errors'], manifest['errors']
                assert 'standalone' in manifest['data']
                await page.goto(origin + '/security')
                await expect(page.get_by_role('heading', name='Change password')).to_be_visible()
                await context.set_offline(True)
                await expect(page.get_by_role('heading', name="You're offline")).to_be_visible()
                await page.goto(origin + '/security')
                await expect(page.get_by_role('heading', name="You're offline")).to_be_visible()
                assert 'Synthetic account' not in await page.content()
                assert 'Private household' not in await page.content()
                # Also verify offline navigation and the CSS work for a cached fallback.
                assert await page.locator('body').evaluate("el => getComputedStyle(el).backgroundColor") == 'rgb(245, 244, 237)'
                await page.goto(origin + '/?month=2026-01')
                await expect(page.get_by_role('heading', name="You're offline")).to_be_visible()
                await context.set_offline(False)
                await page.goto(origin)
                await expect(page.locator('body')).to_have_attribute('data-household', '1')
                other_tab = await context.new_page()
                await other_tab.goto(origin)
                await expect(other_tab.locator('body')).to_have_attribute('data-household', '1')
                await page.locator('.account-dropdown summary').click()
                await page.locator('form[action="/logout"] button').click()
                await expect(page.get_by_role('heading', name='Sign in to your household')).to_be_visible()
                await expect(other_tab.get_by_role('heading', name='Sign in to your household')).to_be_visible()
                await other_tab.close()
                await context.add_cookies([dict(name=budget.SESSION_COOKIE, value='synthetic-b', url=origin)])
                await page.goto(origin)
                await expect(page.locator('body')).to_have_attribute('data-household', '2')
                await page.go_back()
                await page.wait_for_load_state()
                assert 'Private household 1' not in await page.content()
                await page.goto(origin)
                await page.goto(origin + '/groceries')
                await context.set_offline(True)
                await expect(page.get_by_role('heading', name="You're offline")).to_be_visible()
                entries = await page.evaluate('''async () => {
                  const result = [];
                  for (const name of await caches.keys()) {
                    const cache = await caches.open(name);
                    for (const request of await cache.keys()) {
                      const response = await cache.match(request);
                      result.push({url: request.url, type: response.headers.get('content-type'),
                        text: (response.headers.get('content-type') || '').startsWith('image/') ? '' : await response.text()});
                    }
                  }
                  return result;
                }''')
                assert len(entries) == len(budget.PWA_ASSETS)
                for item in entries:
                    assert item['url'].startswith(origin + '/static/'), item['url']
                    assert 'Private household' not in item['text']
                    assert 'Synthetic account' not in item['text']
                await context.set_offline(False)
                await context.clear_cookies()
                for width in (320, 390, 768, 1280):
                    await page.set_viewport_size(dict(width=width, height=844))
                    await page.goto(origin + '/login')
                    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                assert not errors, errors
                await browser.close()
            # All DB calls were intercepted; no real account or key was used.
            assert db.await_count > 0
        finally:
            server.should_exit = True
            await asyncio.to_thread(thread.join, 5)
            sock.close()
    print('PWA browser checks passed: manifest, root scope, offline DOM/reload/navigation, styled fallback, logout across tabs/account switching, public-only caches, login layouts.')


if __name__ == '__main__':
    asyncio.run(main())
