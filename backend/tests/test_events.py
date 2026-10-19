import os, tempfile, unittest
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

folder = tempfile.TemporaryDirectory()
os.environ.update(DATABASE_URL='sqlite:///' + folder.name.replace('\\','/') + '/events.db', JWT_SECRET='event-test-secret-long-enough-for-signing', SEED_DEMO='false', BOT_TOKEN='', ADMIN_PASSWORD='events-test-admin-password')
from app.main import app, engine, SessionLocal
from app.event_models import Event, Ticket

class EventsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = TestClient(app); cls.client = cls.context.__enter__()
        cls.admin = cls.login('demo@curu.local', 'events-test-admin-password')
        cls.student = cls.register('student')
        cls.other = cls.register('other')
    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None,None,None); engine.dispose(); folder.cleanup()
    @classmethod
    def login(cls, email, password):
        result=cls.client.post('/api/auth/login',json={'email':email,'password':password}); assert result.status_code==200,result.text
        return {'Authorization':'Bearer '+result.json()['token']}
    @classmethod
    def register(cls, name):
        result=cls.client.post('/api/auth/register',json={'name':name,'email':name+'@test.com','password':'test-password','education_level':'college','contact':'+77001234567'}); assert result.status_code==201,result.text
        return {'Authorization':'Bearer '+result.json()['token']}
    def create(self, headers=None, **kwargs):
        data={'title':'Campus event','description':'A student event for testing','location':'College hall','capacity':3,'deadline_date':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'event_date':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(), **kwargs}
        return self.client.post('/api/events',json=data,headers=headers or self.admin)
    def test_free_private_capacity_and_replay(self):
        r=self.create(self.student,capacity=1); self.assertEqual(r.status_code,201,r.text); event=r.json()
        self.assertNotIn(event['id'],[e['id'] for e in self.client.get('/api/events').json()])
        self.assertEqual(self.client.post(f"/api/events/{event['id']}/launch",json={},headers=self.other).status_code,403)
        self.assertEqual(self.client.post(f"/api/events/{event['id']}/launch",json={},headers=self.student).status_code,200)
        with ThreadPoolExecutor(2) as pool:
            responses=list(pool.map(lambda h:self.client.post(f"/api/events/{event['id']}/tickets",json={},headers=h),[self.student,self.other]))
        self.assertEqual(sorted(r.status_code for r in responses),[201,409])
        ticket=next(r.json() for r in responses if r.status_code==201)
        code=ticket['qr_code_hash']; self.assertEqual(len(code),64)
        self.assertEqual(self.client.post('/api/tickets/verify',json={'qr_code_hash':code},headers=self.other).status_code,403)
        with ThreadPoolExecutor(2) as pool:
            scans=list(pool.map(lambda _:self.client.post('/api/tickets/verify',json={'qr_code_hash':code},headers=self.student),range(2)))
        self.assertEqual(sorted(r.status_code for r in scans),[200,409])
        self.assertIn('used',self.client.get('/api/events/'+event['id']+'/attendees',headers=self.student).text)
    def test_roles_interest_and_validation(self):
        self.assertEqual(self.create(self.student,is_private=False).status_code,403)
        self.assertEqual(self.create(self.student,ticket_price=100,target_budget=100).status_code,403)
        self.assertEqual(self.create(ticket_price=100,target_budget=1000,capacity=1).status_code,422)
        event=self.create().json()
        for _ in range(2): self.assertEqual(self.client.post('/api/events/'+event['id']+'/interest',headers=self.student).json()['interest_count'],1)
        self.assertNotIn('kaspi_details',self.client.get('/api/events/'+event['id']).json())
    def test_crowdfunding_confirm_and_review(self):
        event=self.create(ticket_price=100,target_budget=100,is_private=False).json(); eid=event['id']
        self.assertEqual(self.client.post(f'/api/events/{eid}/launch',json={},headers=self.admin).status_code,400)
        self.assertEqual(self.client.post(f'/api/events/{eid}/launch',json={'estimate':'Hall: 100','kaspi_details':'Cashier +77000000000'},headers=self.admin).status_code,200)
        self.assertEqual(self.client.get(f'/api/events/{eid}/payment').status_code,401)
        self.assertEqual(self.client.post(f'/api/events/{eid}/tickets',json={},headers=self.student).status_code,400)
        screenshot='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aE1cAAAAASUVORK5CYII='
        booked=self.client.post(f'/api/events/{eid}/tickets',json={'screenshot':screenshot},headers=self.student); self.assertEqual(booked.status_code,201,booked.text)
        tid=booked.json()['id']; self.assertIsNone(booked.json()['qr_code_hash'])
        self.assertEqual(self.client.post(f'/api/tickets/{tid}/approve',headers=self.other).status_code,403)
        self.assertEqual(self.client.post(f'/api/tickets/{tid}/approve',headers=self.admin).status_code,200)
        with SessionLocal() as db: db.get(Event,eid).deadline_date=datetime.now(timezone.utc)-timedelta(seconds=1); db.commit()
        self.assertEqual(self.client.get(f'/api/events/{eid}').json()['status'],'confirmed')
        ticket=next(t for t in self.client.get('/api/me/tickets',headers=self.student).json() if t['id']==tid)
        self.assertEqual(self.client.post('/api/tickets/verify',headers=self.admin,json={'qr_code_hash':ticket['qr_code_hash']}).status_code,200)
        with SessionLocal() as db: db.get(Event,eid).event_date=datetime.now(timezone.utc)-timedelta(seconds=1); db.commit()
        self.assertEqual(self.client.post(f'/api/events/{eid}/reviews',headers=self.student,json={'rating':5,'comment':'Great event'}).status_code,201)
        self.assertEqual(self.client.post(f'/api/events/{eid}/reviews',headers=self.student,json={'rating':5,'comment':'Again'}).status_code,409)
        self.assertEqual(self.client.post(f'/api/events/{eid}/reviews',headers=self.other,json={'rating':5,'comment':'Not there'}).status_code,403)
        self.assertEqual(len(self.client.get(f'/api/events/{eid}').json()['reviews']),1)
    def test_cancel_refund_and_notifications(self):
        event=self.create(ticket_price=100,target_budget=200).json(); eid=event['id']
        self.client.post(f'/api/events/{eid}/launch',json={'estimate':'Hall 200','kaspi_details':'Cashier'},headers=self.admin)
        with SessionLocal() as db:
            student_id=self.client.get('/api/me',headers=self.student).json()['id']
            t=Ticket(event_id=eid,user_id=student_id,status='paid'); db.add(t); db.get(Event,eid).deadline_date=datetime.now(timezone.utc)-timedelta(seconds=1); db.commit(); tid=t.id
        self.assertEqual(self.client.get(f'/api/events/{eid}').json()['status'],'cancelled')
        tickets=self.client.get('/api/me/tickets',headers=self.student).json(); ticket=next(t for t in tickets if t['id']==tid)
        self.assertEqual(ticket['status'],'refunded'); self.assertFalse(ticket['refund_completed']); self.assertIsNone(ticket['qr_code_hash'])
        notices=self.client.get('/api/me/event-notifications',headers=self.student).json(); self.assertTrue(any(n['event_id']==eid for n in notices))
        self.assertEqual(self.client.post('/api/tickets/'+tid+'/refund',headers=self.admin).status_code,200)
        self.assertEqual(self.client.post('/api/tickets/'+tid+'/approve',headers=self.admin).status_code,409)

if __name__=='__main__': unittest.main()
