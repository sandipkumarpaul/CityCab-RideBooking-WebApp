from app import app, db
from models import User, DriverProfile, TrustedContact, Ride, Payment, Review, SOSAlert

def seed_database():
    with app.app_context():
        db.drop_all()
        db.create_all()

        admin = User(
            full_name="System Admin",
            email="admin@citycab.com",
            phone="+8801800000000",
            role="admin",
            wallet_balance=500.0
        )
        admin.set_password("admin123")
        db.session.add(admin)

        passenger = User(
            full_name="Sandip",
            email="sandip@example.com",
            phone="+8801711223344",
            role="passenger",
            wallet_balance=45.00
        )
        passenger.set_password("pass123")
        db.session.add(passenger)

        # Regional Community Responders Network across Dhaka
        responder1 = User(
            full_name="Tariqul Islam (Mohakhali & Banani Patrol)",
            email="responder@example.com",
            phone="+8801999887766",
            role="responder",
            wallet_balance=65.00
        )
        responder1.set_password("pass123")

        responder2 = User(
            full_name="Arif Chowdhury (Dhanmondi Civic Guard)",
            email="arif.responder@citycab.com",
            phone="+8801911224455",
            role="responder",
            wallet_balance=35.00
        )
        responder2.set_password("pass123")

        responder3 = User(
            full_name="Nusrat Jahan (Gulshan Volunteer Hero)",
            email="nusrat.responder@citycab.com",
            phone="+8801933446677",
            role="responder",
            wallet_balance=85.00
        )
        responder3.set_password("pass123")

        responder4 = User(
            full_name="Kamal Hossain (Uttara Security Patrol)",
            email="kamal.responder@citycab.com",
            phone="+8801955668899",
            role="responder",
            wallet_balance=25.00
        )
        responder4.set_password("pass123")

        db.session.add_all([responder1, responder2, responder3, responder4])

        driver1_user = User(
            full_name="Karim Rahman",
            email="karim@citycab.com",
            phone="+8801700112233",
            role="driver",
            wallet_balance=120.00
        )
        driver1_user.set_password("driver123")
        db.session.add(driver1_user)
        db.session.flush()

        driver1_profile = DriverProfile(
            user_id=driver1_user.id,
            vehicle_model="Toyota Axio",
            vehicle_tier="Comfort",
            license_plate="DKA-11-2233",
            is_available=True,
            approval_status="approved",
            current_lat=23.7885,
            current_lng=90.4030
        )
        db.session.add(driver1_profile)

        driver2_user = User(
            full_name="Rahim Uddin",
            email="rahim@citycab.com",
            phone="+8801700445566",
            role="driver",
            wallet_balance=85.00
        )
        driver2_user.set_password("driver123")
        db.session.add(driver2_user)
        db.session.flush()

        driver2_profile = DriverProfile(
            user_id=driver2_user.id,
            vehicle_model="Honda Grace",
            vehicle_tier="Economy",
            license_plate="DKA-55-9988",
            is_available=True,
            approval_status="approved",
            current_lat=23.7950,
            current_lng=90.4100
        )
        db.session.add(driver2_profile)

        driver3_user = User(
            full_name="Tanvir Hossain",
            email="tanvir@citycab.com",
            phone="+8801700778899",
            role="driver",
            wallet_balance=210.00
        )
        driver3_user.set_password("driver123")
        db.session.add(driver3_user)
        db.session.flush()

        driver3_profile = DriverProfile(
            user_id=driver3_user.id,
            vehicle_model="Toyota Camry",
            vehicle_tier="Premium",
            license_plate="DKA-99-0011",
            is_available=True,
            approval_status="approved",
            current_lat=23.8100,
            current_lng=90.4120
        )
        db.session.add(driver3_profile)

        driver4_user = User(
            full_name="Alamgir Kabir",
            email="alamgir@citycab.com",
            phone="+8801700223344",
            role="driver",
            wallet_balance=95.00
        )
        driver4_user.set_password("driver123")
        db.session.add(driver4_user)
        db.session.flush()

        driver4_profile = DriverProfile(
            user_id=driver4_user.id,
            vehicle_model="Bajaj RE 4S CNG",
            vehicle_tier="CNG",
            license_plate="DKA-77-3344",
            is_available=True,
            approval_status="approved",
            current_lat=23.7750,
            current_lng=90.3990
        )
        db.session.add(driver4_profile)

        driver5_user = User(
            full_name="Shakil Hasan",
            email="shakil@citycab.com",
            phone="+8801700556677",
            role="driver",
            wallet_balance=60.00
        )
        driver5_user.set_password("driver123")
        db.session.add(driver5_user)
        db.session.flush()

        driver5_profile = DriverProfile(
            user_id=driver5_user.id,
            vehicle_model="Yamaha FZ-S",
            vehicle_tier="Bike",
            license_plate="DKA-88-1122",
            is_available=True,
            approval_status="approved",
            current_lat=23.7920,
            current_lng=90.4080
        )
        db.session.add(driver5_profile)

        db.session.commit()

        tc1 = TrustedContact(user_id=passenger.id, contact_name="Family Emergency", contact_phone="+8801711000111")
        tc2 = TrustedContact(user_id=passenger.id, contact_name="Campus Security", contact_phone="+8801711000222")
        db.session.add_all([tc1, tc2])

        past_ride_1 = Ride(
            passenger_id=passenger.id,
            driver_id=driver1_user.id,
            pickup_address="Banani Road 11",
            dropoff_address="BRAC University, Mohakhali",
            pickup_lat=23.7937,
            pickup_lng=90.4066,
            dropoff_lat=23.7771,
            dropoff_lng=90.4043,
            distance_km=2.4,
            estimated_fare=12.50,
            vehicle_tier="Comfort",
            status="completed",
            payment_status="paid"
        )
        db.session.add(past_ride_1)

        past_ride_2 = Ride(
            passenger_id=passenger.id,
            driver_id=driver2_user.id,
            pickup_address="Gulshan 2 Circle",
            dropoff_address="Airport Terminal 1",
            pickup_lat=23.7979,
            pickup_lng=90.4144,
            dropoff_lat=23.8511,
            dropoff_lng=90.4074,
            distance_km=7.5,
            estimated_fare=18.50,
            vehicle_tier="Economy",
            status="completed",
            payment_status="paid"
        )
        db.session.add(past_ride_2)
        db.session.commit()

        payment1 = Payment(
            ride_id=past_ride_1.id,
            amount=12.50,
            payment_method="bkash",
            transaction_ref="TXN-BKASH-992201",
            status="completed"
        )
        payment2 = Payment(
            ride_id=past_ride_2.id,
            amount=18.50,
            payment_method="card",
            transaction_ref="TXN-DEMO-998811",
            status="completed"
        )
        db.session.add_all([payment1, payment2])

        review1 = Review(
            ride_id=past_ride_1.id,
            passenger_id=passenger.id,
            driver_id=driver1_user.id,
            rating=5,
            comment="Great smooth ride and very polite driver!"
        )
        review2 = Review(
            ride_id=past_ride_2.id,
            passenger_id=passenger.id,
            driver_id=driver2_user.id,
            rating=5,
            comment="Fast and on time! Highly recommended."
        )
        db.session.add_all([review1, review2])

        # Historical verified emergency rescues for responders
        past_sos_1 = SOSAlert(
            ride_id=past_ride_1.id,
            triggered_by=passenger.id,
            responder_id=responder1.id,
            alert_lat=23.7800,
            alert_lng=90.4010,
            status="rewarded",
            reward_amount=10.00
        )
        past_sos_2 = SOSAlert(
            ride_id=past_ride_2.id,
            triggered_by=passenger.id,
            responder_id=responder3.id,
            alert_lat=23.7970,
            alert_lng=90.4130,
            status="rewarded",
            reward_amount=10.00
        )
        past_sos_3 = SOSAlert(
            ride_id=past_ride_2.id,
            triggered_by=passenger.id,
            responder_id=responder1.id,
            alert_lat=23.8450,
            alert_lng=90.4020,
            status="rewarded",
            reward_amount=10.00
        )

        # Active emergency SOS incident for the live Responder Radar demo
        sos_alert = SOSAlert(
            ride_id=past_ride_1.id,
            triggered_by=passenger.id,
            alert_lat=23.7800,
            alert_lng=90.4010,
            status="active",
            reward_amount=10.00
        )
        db.session.add_all([past_sos_1, past_sos_2, past_sos_3, sos_alert])

        db.session.commit()

if __name__ == '__main__':
    seed_database()
