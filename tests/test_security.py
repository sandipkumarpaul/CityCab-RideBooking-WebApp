import unittest
from app import app, db
from models import User, DriverProfile, Ride, Review
from seed import seed_database


class CityCabSecurityTest(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

        with app.app_context():
            db.drop_all()
            db.create_all()

            admin = User(full_name="Admin", email="admin@test.com", phone="1", role="admin")
            owner = User(full_name="Owner", email="owner@test.com", phone="2", role="passenger", wallet_balance=100.0)
            other = User(full_name="Other", email="other@test.com", phone="3", role="passenger", wallet_balance=100.0)
            driver = User(full_name="Driver", email="driver@test.com", phone="4", role="driver")
            for user in (admin, owner, other, driver):
                user.set_password("pass123")
            db.session.add_all([admin, owner, other, driver])
            db.session.commit()

            db.session.add(DriverProfile(user_id=driver.id, vehicle_model="Axio",
                                         vehicle_tier="Comfort", license_plate="TEST-1"))
            db.session.commit()

        self.login('owner@test.com')
        res = self.client.post('/api/request_ride', json={'vehicle_tier': 'Comfort'})
        self.ride_id = res.get_json()['ride']['id']
        self.logout()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self, email, password='pass123'):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    def logout(self):
        self.client.get('/logout')

    def test_cannot_self_register_as_admin(self):
        self.client.post('/register', data={
            'full_name': 'Mallory', 'email': 'mallory@test.com', 'phone': '5',
            'password': 'pass123', 'role': 'admin'
        })
        with app.app_context():
            self.assertIsNone(User.query.filter_by(email='mallory@test.com').first())

    def test_can_register_as_responder(self):
        self.client.post('/register', data={
            'full_name': 'Helper', 'email': 'helper@test.com', 'phone': '6',
            'password': 'pass123', 'role': 'responder'
        })
        with app.app_context():
            self.assertEqual(User.query.filter_by(email='helper@test.com').first().role, 'responder')

    def test_other_passenger_cannot_touch_someone_elses_ride(self):
        self.login('other@test.com')
        self.assertEqual(self.client.get(f'/api/ride/{self.ride_id}').status_code, 403)
        self.assertEqual(self.client.post(f'/api/ride/{self.ride_id}/status', json={'status': 'cancelled'}).status_code, 403)
        self.assertEqual(self.client.post('/api/pay_ride', json={'ride_id': self.ride_id, 'payment_method': 'wallet'}).status_code, 403)
        self.assertEqual(self.client.post('/api/submit_review', json={'ride_id': self.ride_id, 'rating': 1}).status_code, 403)
        self.assertEqual(self.client.post('/api/trigger_sos', json={'ride_id': self.ride_id}).status_code, 403)

        with app.app_context():
            ride = db.session.get(Ride, self.ride_id)
            self.assertEqual(ride.payment_status, 'unpaid')
            self.assertNotEqual(ride.status, 'cancelled')
            self.assertEqual(User.query.filter_by(email='other@test.com').first().wallet_balance, 100.0)

    def test_passenger_cannot_accept_rides(self):
        with app.app_context():
            ride = db.session.get(Ride, self.ride_id)
            ride.status, ride.driver_id = 'requested', None
            db.session.commit()

        self.login('other@test.com')
        res = self.client.post(f'/api/driver/accept_ride/{self.ride_id}')
        self.assertEqual(res.status_code, 403)

    def test_review_validation(self):
        self.login('owner@test.com')
        res = self.client.post('/api/submit_review', json={'ride_id': self.ride_id, 'rating': 99})
        self.assertEqual(res.status_code, 400)

        res = self.client.post('/api/submit_review', json={'ride_id': str(self.ride_id), 'rating': '4'})
        self.assertEqual(res.status_code, 200)

        res = self.client.post('/api/submit_review', json={'ride_id': self.ride_id, 'rating': 5})
        self.assertEqual(res.status_code, 400)
        with app.app_context():
            self.assertEqual(Review.query.filter_by(ride_id=self.ride_id).count(), 1)

    def test_invalid_input_returns_400_instead_of_crashing(self):
        self.login('owner@test.com')
        res = self.client.post('/api/estimate_fare', json={'pickup_lat': 'north'})
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/request_ride', json={'vehicle_tier': 'Helicopter'})
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/pay_ride', json={'ride_id': self.ride_id, 'payment_method': 'crypto'})
        self.assertEqual(res.status_code, 400)

    def test_wallet_topup_rejects_non_finite_and_oversized_amounts(self):
        self.login('owner@test.com')
        for amount in ('inf', 'nan', '5000', '-10'):
            self.client.post('/wallet/topup', data={'amount': amount, 'payment_method': 'card'})
        self.client.post('/wallet/topup', data={'amount': '25', 'payment_method': 'card'})
        with app.app_context():
            self.assertEqual(User.query.filter_by(email='owner@test.com').first().wallet_balance, 125.0)

    def test_admin_cannot_delete_user_with_trip_history(self):
        self.login('admin@test.com')
        with app.app_context():
            owner_id = User.query.filter_by(email='owner@test.com').first().id
            other_id = User.query.filter_by(email='other@test.com').first().id

        res = self.client.post(f'/admin/user/delete/{owner_id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.client.post(f'/admin/user/delete/{other_id}')

        with app.app_context():
            self.assertIsNotNone(db.session.get(User, owner_id))
            self.assertIsNone(db.session.get(User, other_id))

    def test_seed_database_builds_demo_data(self):
        with app.app_context():
            seed_database()
            self.assertEqual(User.query.filter_by(role='admin').count(), 1)
            self.assertEqual(DriverProfile.query.count(), 5)
            self.assertTrue(User.query.filter_by(email='sandip@example.com').first().check_password('pass123'))


if __name__ == '__main__':
    unittest.main()
