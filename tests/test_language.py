import hashlib
import unittest
from unittest.mock import AsyncMock, patch

import httpx
import app as budget


class LanguagePreferenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.account = dict(id=7, household_id=1, username='sample', role='member', disabled_at=None, language='en')
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=budget.app), base_url='https://localhost',
            cookies={budget.SESSION_COOKIE:'sample-session'})
        self.csrf = hashlib.sha256(b'csrf:sample-session').hexdigest()

    async def asyncTearDown(self):
        await self.client.aclose()
        budget.session_cache.clear()

    async def test_save_only_current_account_and_clear_cached_sessions(self):
        budget.session_cache['old'] = (float('inf'), self.account.copy())
        budget.session_cache['other'] = (float('inf'), dict(self.account, id=8))
        with patch.object(budget, 'current_account', AsyncMock(return_value=self.account)), patch.object(budget.db, 'request', AsyncMock()) as db:
            for language in ('es', 'en'):
                response = await self.client.post('/account/language', data=dict(language=language, csrf_token=self.csrf, return_to='/?month=2026-04&person=3'), headers={'X-Requested-With':'ux-form'})
                self.assertEqual(response.json(), {'redirect':'/?month=2026-04&person=3'})
                db.assert_awaited_with('PATCH', 'accounts', params={'id':'eq.7'}, json={'language':language})
                self.assertIn(f'budget_bloom_language={language}', response.headers['set-cookie'])
        self.assertNotIn('old', budget.session_cache)
        self.assertIn('other', budget.session_cache)

    async def test_auth_csrf_and_supported_language_required(self):
        with patch.object(budget, 'current_account', AsyncMock(return_value=self.account)), patch.object(budget.db, 'request', AsyncMock()) as db:
            response = await self.client.post('/account/language', data=dict(language='fr', csrf_token=self.csrf))
            self.assertEqual(response.status_code, 400)
            response = await self.client.post('/account/language', data=dict(language='es', csrf_token='bad'))
            self.assertEqual(response.status_code, 403)
            db.assert_not_awaited()
        with patch.object(budget, 'current_account', AsyncMock(return_value=None)), patch.object(budget.db, 'request', AsyncMock()) as db:
            response = await self.client.post('/account/language', data=dict(language='es', csrf_token=self.csrf))
            self.assertEqual(response.status_code, 401)
            db.assert_not_awaited()

    async def test_external_return_destination_is_not_used(self):
        with patch.object(budget, 'current_account', AsyncMock(return_value=self.account)), patch.object(budget.db, 'request', AsyncMock()):
            response = await self.client.post('/account/language', data=dict(language='es', csrf_token=self.csrf, return_to='//example.com'))
            self.assertEqual(response.headers['location'], '/')

    async def test_fresh_session_reads_saved_language(self):
        with patch.object(budget.db, 'request', AsyncMock(return_value=[{'accounts':dict(self.account, language='es')}])) as db:
            from starlette.requests import Request
            account = await budget.current_account(Request({'type':'http','headers':[(b'cookie', f'{budget.SESSION_COOKIE}=new-session'.encode())]}))
            self.assertEqual(account['language'], 'es')
            self.assertIn('language', db.call_args.kwargs['params']['select'])

    async def test_sign_in_restores_preference_and_overrides_browser_language(self):
        self.client.cookies.set(budget.CSRF_COOKIE, 'anonymous-token')
        self.client.cookies.set('budget_bloom_language', 'es')
        for language in ('en', 'es'):
            row = dict(self.account, language=language, password_hash='mocked')
            with patch.object(budget.db, 'request', AsyncMock(side_effect=[[row], []])), \
                 patch.object(budget, 'password_matches', return_value=True), \
                 patch.object(budget, 'enforce_rate_limit', AsyncMock()), \
                 patch.object(budget, 'audit_event', AsyncMock()):
                response = await self.client.post('/login', data=dict(username='sample', password='not-a-real-password', csrf_token='anonymous-token'), headers={'X-Requested-With':'ux-form'})
            self.assertEqual(response.json(), {'redirect':'/'})
            self.assertTrue(any(f'budget_bloom_language={language}' in header for header in response.headers.get_list('set-cookie')))
            self.assertEqual(budget.session_cache[budget.session_token_hash(response.cookies[budget.SESSION_COOKIE])][1]['language'], language)

    async def test_rendering_defaults_to_english_and_translates_only_ui(self):
        for language, heading in (('en','Monthly budget'), ('es','Presupuesto mensual')):
            html = budget.templates.get_template('index.html').render(account=dict(self.account, language=language),
                active={'id':1,'name':'Our Home'}, selected_month='2026-09', current_month='2026-09',
                selected_person=None, people=[], entries=[], categories=[], income=0, expenses=0, balance=0)
            self.assertIn(f'<html lang="{language}">', html)
            self.assertIn(heading, html)
            self.assertIn('Our Home', html)
            self.assertIn('septiembre 2026' if language == 'es' else 'September 2026', html)
        html = budget.templates.get_template('login.html').render()
        self.assertIn('<html lang="en">', html)
        self.assertIn('Sign in to your household', html)


if __name__ == '__main__':
    unittest.main()
