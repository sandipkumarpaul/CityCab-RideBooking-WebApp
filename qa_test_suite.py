import unittest
import json
from io import BytesIO
from app import app, db
from models import User, DriverProfile, TrustedContact, Ride, Payment, Review, SOSAlert

class CityCabComprehensiveQATest(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

        with app.app_context():
            db.session.rollback()
            db.drop_all()
            db.create_all()

            self.admin = User(full_name="System Admin", email="admin@citycab.com", phone="+8801800000000", role="admin", wallet_balance=500.0)
            self.admin.set_password("admin123")

            self.passenger = User(full_name="Sandip", email="sandip@example.com", phone="+8801711223344", role="passenger", wallet_balance=100.0)
            self.passenger.set_password("pass123")

            self.responder = User(full_name="Hero Responder", email="responder@example.com", phone="+8801999887766", role="responder", wallet_balance=20.0)
            self.responder.set_password("pass123")

            self.driver_user = User(full_name="Karim Rahman", email="karim@citycab.com", phone="+8801700112233", role="driver", wallet_balance=50.0)
            self.driver_user.set_password("driver123")

            db.session.add_all([self.admin, self.passenger, self.responder, self.driver_user])
            db.session.commit()

            self.driver_profile = DriverProfile(
                user_id=self.driver_user.id,
                vehicle_model="Toyota Axio",
                vehicle_tier="Comfort",
                license_plate="DKA-11-2233",
                is_available=True,
                approval_status="approved",
                current_lat=23.7885,
                current_lng=90.4030
            )
            db.session.add(self.driver_profile)

            self.contact = TrustedContact(user_id=self.passenger.id, contact_name="Mom", contact_phone="+8801711000999")
            db.session.add(self.contact)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.rollback()
            db.session.remove()
            db.drop_all()

    def login(self, email, password):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_01_authentication_flows(self):
        res = self.client.get('/login')
        self.assertEqual(res.status_code, 200)

        res = self.login('wrong@example.com', 'wrongpass')
        self.assertIn(b'Invalid email or password', res.data)

        res = self.login('sandip@example.com', 'pass123')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Sandip', res.data)
        self.logout()

        res = self.login('karim@citycab.com', 'driver123')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Karim Rahman', res.data)
        self.logout()

        res = self.login('admin@citycab.com', 'admin123')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'System Admin', res.data)
        self.logout()

    def test_02_rbac_authorization(self):
        self.login('sandip@example.com', 'pass123')
        res = self.client.get('/admin/dashboard', follow_redirects=True)
        self.assertIn(b'Access restricted', res.data)

        res = self.client.get('/driver/dashboard', follow_redirects=True)
        self.assertIn(b'Access restricted', res.data)
        self.logout()

        self.login('admin@citycab.com', 'admin123')
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)
        res = self.client.get('/admin/drivers')
        self.assertEqual(res.status_code, 200)
        res = self.client.get('/admin/users')
        self.assertEqual(res.status_code, 200)
        res = self.client.get('/admin/rides')
        self.assertEqual(res.status_code, 200)
        res = self.client.get('/admin/sos-logs')
        self.assertEqual(res.status_code, 200)
        self.logout()

    def test_03_fare_estimation_engine(self):
        self.login('sandip@example.com', 'pass123')
        res = self.client.post('/api/estimate_fare', json={
            'pickup_lat': 23.7937, 'pickup_lng': 90.4066,
            'dropoff_lat': 23.7771, 'dropoff_lng': 90.4043
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['distance_km'] > 0)
        self.assertIn('Bike', data['estimates'])
        self.assertIn('CNG', data['estimates'])
        self.assertIn('Economy', data['estimates'])
        self.assertIn('Comfort', data['estimates'])
        self.assertIn('Premium', data['estimates'])
        self.assertTrue(data['estimates']['Bike'] < data['estimates']['Comfort'])
        self.logout()

    def test_04_full_ride_booking_and_status_cycle(self):
        self.login('sandip@example.com', 'pass123')
        res = self.client.post('/api/request_ride', json={
            'pickup_address': 'Banani 11',
            'dropoff_address': 'BRAC University',
            'pickup_lat': 23.7937, 'pickup_lng': 90.4066,
            'dropoff_lat': 23.7771, 'dropoff_lng': 90.4043,
            'vehicle_tier': 'Comfort'
        })
        self.assertEqual(res.status_code, 200)
        ride_data = res.get_json()['ride']
        ride_id = ride_data['id']

        res = self.client.get(f'/api/ride/{ride_id}')
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f'/api/ride/{ride_id}/status', json={'status': 'en_route'})
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f'/api/ride/{ride_id}/status', json={'status': 'completed'})
        self.assertEqual(res.status_code, 200)
        self.logout()

    def test_05_gateway_payments(self):
        self.login('sandip@example.com', 'pass123')
        res = self.client.post('/api/request_ride', json={
            'pickup_address': 'Gulshan', 'dropoff_address': 'Airport',
            'pickup_lat': 23.7979, 'pickup_lng': 90.4144,
            'dropoff_lat': 23.8511, 'dropoff_lng': 90.4074,
            'vehicle_tier': 'Economy'
        })
        ride_id = res.get_json()['ride']['id']
        self.client.post(f'/api/ride/{ride_id}/status', json={'status': 'completed'})

        res_pay = self.client.post('/api/pay_ride', json={'ride_id': ride_id, 'payment_method': 'bkash'})
        self.assertEqual(res_pay.status_code, 200)
        data = res_pay.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['transaction_ref'].startswith('TXN-BKASH-'))
        self.logout()

    def test_06_sos_dispatch_and_responder_verification(self):
        self.login('sandip@example.com', 'pass123')
        res = self.client.post('/api/request_ride', json={
            'pickup_address': 'Banani', 'dropoff_address': 'Mohakhali',
            'pickup_lat': 23.7937, 'pickup_lng': 90.4066,
            'dropoff_lat': 23.7771, 'dropoff_lng': 90.4043,
            'vehicle_tier': 'Comfort'
        })
        ride_id = res.get_json()['ride']['id']

        res_sos = self.client.post('/api/trigger_sos', json={
            'ride_id': ride_id, 'alert_lat': 23.7800, 'alert_lng': 90.4010
        })
        self.assertEqual(res_sos.status_code, 200)
        alert_id = res_sos.get_json()['alert']['id']
        self.logout()

        self.login('responder@example.com', 'pass123')
        res_near = self.client.post(f'/api/respond_sos/{alert_id}', json={'user_lat': 23.7801, 'user_lng': 90.4011})
        self.assertEqual(res_near.status_code, 400)

        res_far = self.client.post(f'/api/respond_sos/{alert_id}', json={'user_lat': 23.7950, 'user_lng': 90.4120})
        self.assertEqual(res_far.status_code, 200)
        self.assertIn('Wallet Credit awarded', res_far.get_json()['message'])
        self.logout()

    def test_07_pdf_and_html_invoice_generation(self):
        self.login('sandip@example.com', 'pass123')
        res = self.client.post('/api/request_ride', json={
            'pickup_address': 'Banani', 'dropoff_address': 'Mohakhali',
            'pickup_lat': 23.7937, 'pickup_lng': 90.4066,
            'dropoff_lat': 23.7771, 'dropoff_lng': 90.4043,
            'vehicle_tier': 'Comfort'
        })
        ride_id = res.get_json()['ride']['id']

        res_html = self.client.get(f'/ride/{ride_id}/receipt')
        self.assertEqual(res_html.status_code, 200)
        self.assertIn(b'CityCab', res_html.data)

        res_pdf = self.client.get(f'/ride/{ride_id}/invoice')
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.headers.get('Content-Type'), 'application/pdf')
        self.assertTrue(len(res_pdf.data) > 500)
        self.logout()

    def test_08_driver_toggle_and_review_flow(self):
        self.login('sandip@example.com', 'pass123')
        res = self.client.post('/api/request_ride', json={
            'pickup_address': 'Banani', 'dropoff_address': 'Mohakhali',
            'pickup_lat': 23.7937, 'pickup_lng': 90.4066,
            'dropoff_lat': 23.7771, 'dropoff_lng': 90.4043,
            'vehicle_tier': 'Comfort'
        })
        ride_id = res.get_json()['ride']['id']

        res_rev = self.client.post('/api/submit_review', json={
            'ride_id': ride_id, 'rating': 5, 'comment': 'Excellent service!'
        })
        self.assertEqual(res_rev.status_code, 200)
        self.logout()

        self.login('karim@citycab.com', 'driver123')
        res_toggle = self.client.post('/api/driver/toggle_availability')
        self.assertEqual(res_toggle.status_code, 200)
        self.assertFalse(res_toggle.get_json()['is_available'])
        self.logout()

    def test_09_all_template_endpoints(self):
        self.login('sandip@example.com', 'pass123')
        for path in ['/passenger/dashboard', '/passenger/trips', '/passenger/safety', '/passenger/wallet', '/profile']:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f'Failed on {path}')
        self.logout()

        self.login('karim@citycab.com', 'driver123')
        for path in ['/driver/dashboard', '/driver/requests', '/driver/earnings', '/driver/reviews', '/profile']:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f'Failed on {path}')
        self.logout()

        self.login('responder@example.com', 'pass123')
        for path in ['/responder/dashboard', '/responder/alerts', '/responder/rewards', '/profile']:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f'Failed on {path}')
        self.logout()

        self.login('admin@citycab.com', 'admin123')
        for path in ['/admin/dashboard', '/admin/drivers', '/admin/users', '/admin/rides', '/admin/sos-logs', '/profile']:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f'Failed on {path}')
        self.logout()

if __name__ == '__main__':
    unittest.main()
