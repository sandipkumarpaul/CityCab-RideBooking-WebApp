import unittest
from app import app, db, calculate_haversine, estimate_fare_amount
from models import User, DriverProfile, Ride, SOSAlert

class CityCabTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = app.test_client()
        with app.app_context():
            db.create_all()

            passenger = User(full_name="Test Passenger", email="testp@example.com", phone="+8801700000000", role="passenger", wallet_balance=50.0)
            passenger.set_password("pass123")

            responder = User(full_name="Test Responder", email="testr@example.com", phone="+8801711111111", role="passenger", wallet_balance=10.0)
            responder.set_password("pass123")

            driver_user = User(full_name="Test Driver", email="testd@example.com", phone="+8801722222222", role="driver")
            driver_user.set_password("driver123")
            db.session.add_all([passenger, responder, driver_user])
            db.session.commit()

            driver_profile = DriverProfile(user_id=driver_user.id, vehicle_model="Axio", vehicle_tier="Comfort", license_plate="TEST-123")
            db.session.add(driver_profile)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_haversine_and_fare_estimation(self):
        dist = calculate_haversine(23.7937, 90.4066, 23.7771, 90.4043)
        self.assertGreater(dist, 1.0)

        fare_econ = estimate_fare_amount(dist, 'Economy')
        fare_comf = estimate_fare_amount(dist, 'Comfort')
        fare_prem = estimate_fare_amount(dist, 'Premium')

        self.assertGreater(fare_comf, fare_econ)
        self.assertGreater(fare_prem, fare_comf)

    def test_user_login(self):
        response = self.client.post('/login', data={'email': 'testp@example.com', 'password': 'pass123'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_sos_reward_proximity_logic(self):
        with app.app_context():
            passenger = User.query.filter_by(email="testp@example.com").first()
            responder = User.query.filter_by(email="testr@example.com").first()

            ride = Ride(
                passenger_id=passenger.id,
                pickup_address="Banani 11", dropoff_address="BRAC Uni",
                pickup_lat=23.7937, pickup_lng=90.4066,
                dropoff_lat=23.7771, dropoff_lng=90.4043,
                distance_km=2.4, estimated_fare=12.0, vehicle_tier="Comfort"
            )
            db.session.add(ride)
            db.session.commit()

            alert = SOSAlert(
                ride_id=ride.id, triggered_by=passenger.id,
                alert_lat=23.7800, alert_lng=90.4010,
                status="active", reward_amount=10.0
            )
            db.session.add(alert)
            db.session.commit()

            self.client.post('/login', data={'email': 'testp@example.com', 'password': 'pass123'})
            resp = self.client.post(f'/api/respond_sos/{alert.id}', json={'user_lat': 23.8000, 'user_lng': 90.4100})
            self.assertEqual(resp.status_code, 400)

            self.client.get('/logout')
            self.client.post('/login', data={'email': 'testr@example.com', 'password': 'pass123'})
            resp2 = self.client.post(f'/api/respond_sos/{alert.id}', json={'user_lat': 23.7950, 'user_lng': 90.4120})
            self.assertEqual(resp2.status_code, 200)
            self.assertIn('Wallet Credit awarded', resp2.json['message'])

            updated_responder = User.query.filter_by(email="testr@example.com").first()
            self.assertEqual(updated_responder.wallet_balance, 20.0)

if __name__ == '__main__':
    unittest.main()
