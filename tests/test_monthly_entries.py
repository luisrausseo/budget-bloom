import unittest
from unittest.mock import AsyncMock, patch
from datetime import date

import httpx
import app as budget


class MonthlyEntryRoutes(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.account = {'id': 2, 'household_id': 1, 'username': 'member', 'role': 'member'}
        self.auth = patch.object(budget, 'current_account', AsyncMock(return_value=self.account))
        self.db = patch.object(budget.db, 'request', AsyncMock(return_value=True))
        self.auth.start()
        self.request_db = self.db.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=budget.app),
            base_url='https://localhost', cookies={budget.SESSION_COOKIE: 'test-session'})
        import hashlib
        self.csrf = hashlib.sha256(b'csrf:test-session').hexdigest()

    async def asyncTearDown(self):
        await self.client.aclose()
        self.auth.stop()
        self.db.stop()

    def form(self):
        return {'csrf_token': self.csrf, 'household_id': '1', 'month': '2026-04',
                'person_id': '3', 'category_id': '4', 'entry_type': 'expense',
                'description': 'April only', 'amount': '75.00', 'entry_date': '2026-04-15',
                'person_filter': '3'}

    async def test_edit_is_month_scoped_and_keeps_filter(self):
        response = await self.client.post('/entries/7/edit', data=self.form())
        self.assertEqual(response.status_code, 303)
        self.assertIn('person=3', response.headers['location'])
        self.request_db.assert_awaited_once_with('POST', 'rpc/edit_budget_entry_month', json={
            'p_entry_id': 7, 'p_household_id': 1, 'p_month': '2026-04-01',
            'p_person_id': 3, 'p_category_id': 4, 'p_entry_type': 'expense',
            'p_description': 'April only', 'p_amount': '75.00',
            'p_entry_date': '2026-04-15', 'p_recurring_monthly': False,
        })

    async def test_delete_passes_cutoff_month(self):
        response = await self.client.post('/entries/7/delete', data={**self.form(), 'ajax': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'deleted': True, 'entry_id': 7})
        self.request_db.assert_awaited_once_with('POST', 'rpc/delete_budget_entry_from_month', json={
            'p_entry_id': 7, 'p_household_id': 1, 'p_month': '2026-04-01'})

    async def test_nonexistent_occurrence_does_not_report_success(self):
        self.request_db.return_value = False
        response = await self.client.post('/entries/7/delete', data={**self.form(), 'ajax': 'true'})
        self.assertEqual(response.status_code, 404)

    async def test_household_and_csrf_checked_before_write(self):
        response = await self.client.post('/entries/7/edit', data={**self.form(), 'household_id': '99'})
        self.assertEqual(response.status_code, 403)
        response = await self.client.post('/entries/7/delete', data={**self.form(), 'csrf_token': 'bad'})
        self.assertEqual(response.status_code, 403)
        self.request_db.assert_not_awaited()

    async def test_dashboard_uses_effective_person_amount_and_date(self):
        entry = {'id': 7, 'household_id': 1, 'person_id': 3, 'category_id': 4,
            'entry_type': 'expense', 'description': 'April only', 'amount': 75,
            'entry_date': '2026-04-15', 'source_entry_date': '2026-01-31',
            'recurring_monthly': True, 'recurring_until': None, 'recurs_in_selected_month': True,
            'completed': False, 'month_override': True, 'people': {'name': 'Other member'},
            'categories': {'name': 'Utilities'}}
        self.request_db.return_value = {'household': {'id': 1, 'name': 'Home'},
            'people': [{'id': 2, 'name': 'Original member'}, {'id': 3, 'name': 'Other member'}],
            'categories': [{'id': 4, 'name': 'Utilities'}], 'entries': [entry]}
        response = await self.client.get('/?month=2026-04&person=3')
        self.assertEqual(response.status_code, 200)
        self.assertIn('$75.00', response.text)
        self.assertIn('2026-04-15', response.text)
        self.assertIn('data-month-end="2026-04-30"', response.text)
        self.assertIn('Previous months will be kept.', response.text)
        response = await self.client.get('/?month=2026-04&person=2')
        self.assertNotIn('data-entry-id="7"', response.text)


if __name__ == '__main__':
    unittest.main()
