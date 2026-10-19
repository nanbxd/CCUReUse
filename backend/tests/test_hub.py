import base64
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

folder = tempfile.TemporaryDirectory()
os.environ.update(DATABASE_URL='sqlite:///' + folder.name.replace('\\', '/') + '/hub.db', JWT_SECRET='caspianhub-test-secret-long-enough-for-signing', SEED_DEMO='false', BOT_TOKEN='', ADMIN_PASSWORD='hub-test-admin-password')
from app.main import app, engine, SessionLocal, migrate_hub_columns
from app.database.models import Listing, User
from app.event_models import Event
from app.ai.moderation_system_prompt import MODERATION_SYSTEM_PROMPT
from config import settings

PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aE1cAAAAASUVORK5CYII='

class HubTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = TestClient(app)
        cls.client = cls.context.__enter__()
        response = cls.client.post('/api/auth/login', json={'email': 'demo@curu.local', 'password': 'hub-test-admin-password'})
        assert response.status_code == 200, response.text
        cls.auth = {'Authorization': 'Bearer ' + response.json()['token']}
        cls.uid = response.json()['user']['id']

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)
        engine.dispose()
        folder.cleanup()

    def listing(self, **kwargs):
        return {'title': 'Student book', 'description': 'A physical textbook for students', 'category': 'Книги', 'condition': 'Хорошее', 'location': 'College hall', **kwargs}

    def event(self, **kwargs):
        clock = datetime.now(timezone.utc)
        return {'title': 'Campus conference', 'description': 'Talks and workshops for students', 'category': 'Конференция', 'location': 'College auditorium', 'capacity': 500, 'is_private': False, 'deadline_date': (clock + timedelta(days=1)).isoformat(), 'event_date': (clock + timedelta(days=2)).isoformat(), 'end_date': (clock + timedelta(days=2, hours=6)).isoformat(), 'banner': PNG, **kwargs}

    def test_market_price_persisted_moderated_and_filtered(self):
        with SessionLocal() as db:
            db.get(User, self.uid).contact = '@hub_test'
            db.commit()
        with patch.object(settings, 'agnes_api_key', 'test'), patch.object(settings, 'bot_token', '123:test'), patch.object(settings, 'support_chat_id', 123), patch('app.main.safe_moderate_listing', new_callable=AsyncMock, return_value=SimpleNamespace(decision='approve', reason='')), patch('app.main.notify_subscribers', new_callable=AsyncMock):
            paid = self.client.post('/api/listings', headers=self.auth, json=self.listing(price=15000))
            self.assertEqual(paid.status_code, 201, paid.text)
            self.assertEqual(paid.json()['price'], 15000)
            free = self.client.post('/api/listings', headers=self.auth, json=self.listing())
            self.assertEqual(free.status_code, 201, free.text)
            self.assertEqual(free.json()['price'], 0)
        paid_items = self.client.get('/api/listings?price_type=paid').json()
        free_items = self.client.get('/api/listings?price_type=free').json()
        self.assertIn(paid.json()['id'], [i['id'] for i in paid_items])
        self.assertNotIn(free.json()['id'], [i['id'] for i in paid_items])
        self.assertIn(free.json()['id'], [i['id'] for i in free_items])
        self.assertEqual(self.client.get('/api/listings/' + str(paid.json()['id'])).json()['price'], 15000)
        for invalid in (-1, 1.5, '1000', 100000001):
            self.assertEqual(self.client.post('/api/listings', headers=self.auth, json=self.listing(price=invalid)).status_code, 422)
        self.assertIn('for sale or for free', MODERATION_SYSTEM_PROMPT)

    def test_banner_roundtrip_private_exclusion_and_input_validation(self):
        created = self.client.post('/api/events', headers=self.auth, json=self.event())
        self.assertEqual(created.status_code, 201, created.text)
        eid = created.json()['id']
        self.assertEqual(self.client.get('/api/events/' + eid).json()['banner'], PNG)
        self.assertIsNotNone(created.json()['end_date'])
        public = self.client.get('/api/events?order=latest&limit=1').json()
        self.assertEqual(public[0]['id'], eid)
        self.assertEqual(public[0]['banner'], PNG)
        private = self.client.post('/api/events', headers=self.auth, json=self.event(is_private=True)).json()
        self.assertNotIn(private['id'], [e['id'] for e in self.client.get('/api/events?order=latest').json()])
        for banner in ('https://untrusted.test/image.svg', 'data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,YmFk'):
            self.assertEqual(self.client.post('/api/events', headers=self.auth, json=self.event(banner=banner)).status_code, 422)
        self.assertEqual(self.client.post('/api/events', headers=self.auth, json=self.event(end_date=datetime.now(timezone.utc).isoformat())).status_code, 422)
        self.assertEqual(self.client.get('/api/events?limit=1000').status_code, 422)

    def test_event_stays_active_until_end_and_qr_still_works(self):
        created = self.client.post('/api/events', headers=self.auth, json=self.event()).json()
        eid = created['id']
        self.assertEqual(self.client.post(f'/api/events/{eid}/launch', headers=self.auth, json={}).status_code, 200)
        ticket = self.client.post(f'/api/events/{eid}/tickets', headers=self.auth, json={}).json()
        with SessionLocal() as db:
            e = db.get(Event, eid)
            e.event_date = datetime.now(timezone.utc) - timedelta(hours=1)
            e.end_date = datetime.now(timezone.utc) + timedelta(hours=1)
            db.commit()
        self.assertEqual(self.client.get(f'/api/events/{eid}').json()['status'], 'confirmed')
        checked = self.client.post('/api/tickets/verify', headers=self.auth, json={'qr_code_hash': ticket['qr_code_hash']})
        self.assertEqual(checked.status_code, 200, checked.text)
        with SessionLocal() as db:
            db.get(Event, eid).end_date = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        self.assertEqual(self.client.get(f'/api/events/{eid}').json()['status'], 'completed')

    def test_startup_migration_is_idempotent(self):
        migrate_hub_columns()
        migrate_hub_columns()
        from sqlalchemy import inspect
        self.assertIn('price', [c['name'] for c in inspect(engine).get_columns('listings')])
        self.assertIn('banner', [c['name'] for c in inspect(engine).get_columns('events')])

if __name__ == '__main__':
    unittest.main()
