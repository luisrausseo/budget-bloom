import json
import struct
import unittest
from unittest.mock import AsyncMock, patch

import httpx
import app as budget


class PWARouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=budget.app), base_url='https://localhost')
        self.account = dict(id=7, household_id=1, username='synthetic-account', role='owner', language='en')

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_public_manifest_and_icons(self):
        with patch.object(budget.db, 'request', AsyncMock()) as db:
            response = await self.client.get('/manifest.webmanifest')
            db.assert_not_awaited()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'application/manifest+json')
        manifest = response.json()
        self.assertEqual(manifest['name'], 'Budget Bloom')
        self.assertEqual(manifest['start_url'], '/')
        self.assertEqual(manifest['scope'], '/')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual({icon['sizes'] for icon in manifest['icons']}, {'192x192', '512x512'})
        self.assertIn('maskable', {icon['purpose'] for icon in manifest['icons']})
        for icon in manifest['icons']:
            image = await self.client.get(icon['src'])
            self.assertEqual(image.headers['content-type'], 'image/png')
            self.assertEqual(image.content[:8], b'\x89PNG\r\n\x1a\n')
            width, height = struct.unpack('>II', image.content[16:24])
            self.assertEqual(f'{width}x{height}', icon['sizes'])
        apple = await self.client.get('/static/icons/apple-touch-icon.png')
        self.assertEqual(struct.unpack('>II', apple.content[16:24]), (180, 180))

    async def test_worker_scope_version_and_csp(self):
        with patch.object(budget.db, 'request', AsyncMock()) as db:
            response = await self.client.get('/sw.js')
            db.assert_not_awaited()
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/javascript', response.headers['content-type'])
        self.assertEqual(response.headers['service-worker-allowed'], '/')
        self.assertEqual(response.headers['cache-control'], 'no-cache')
        self.assertNotIn('__PWA_', response.text)
        self.assertIn(budget.PWA_VERSION, response.text)
        self.assertIn("manifest-src 'self'", response.headers['content-security-policy'])
        self.assertIn("worker-src 'self'", response.headers['content-security-policy'])
        self.assertIn("frame-ancestors 'none'", response.headers['content-security-policy'])
        self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
        assets = json.loads(response.text.split('const ASSETS = ', 1)[1].split(';', 1)[0])
        self.assertEqual(assets, [f'/static/{name}?v={budget.PWA_VERSION}' for name in budget.PWA_ASSETS])
        for asset in assets:
            result = await self.client.get(asset)
            self.assertEqual(result.status_code, 200, asset)

    async def test_private_pages_redirects_and_json_are_no_store(self):
        with patch.object(budget, 'current_account', AsyncMock(return_value=self.account)), \
             patch.object(budget.db, 'request', AsyncMock()) as db:
            db.return_value = {'household': None, 'entries': []}
            dashboard = await self.client.get('/')
            db.side_effect = [[{'id': 1, 'name': 'Synthetic household'}], []]
            groceries = await self.client.get('/groceries')
            db.side_effect = [[], []]
            security = await self.client.get('/security')
            login_redirect = await self.client.get('/login')
            unauthorized_form = await self.client.post('/account/language', data={
                'language': 'en', 'csrf_token': 'invalid'}, headers={'X-Requested-With': 'ux-form'})
        for response in (dashboard, groceries, security, login_redirect, unauthorized_form):
            self.assertIn('no-store', response.headers['cache-control'])
            self.assertIn('private', response.headers['cache-control'])
            self.assertIn('Cookie', response.headers['vary'])
        self.assertEqual(unauthorized_form.status_code, 403)
        with patch.object(budget, 'current_account', AsyncMock(return_value=None)):
            for path in ('/', '/groceries', '/security', '/login', '/register'):
                response = await self.client.get(path)
                self.assertIn('no-store', response.headers['cache-control'])
        for response in (dashboard, groceries, security):
            self.assertIn('href="/manifest.webmanifest"', response.text)
            self.assertIn('/static/pwa.js?v=', response.text)
        self.assertIn('scope:', (budget.BASE_DIR / 'static/pwa.js').read_text())


if __name__ == '__main__':
    unittest.main()
