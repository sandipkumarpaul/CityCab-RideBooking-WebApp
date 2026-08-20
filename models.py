from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='passenger')
    wallet_balance = db.Column(db.Float, default=50.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    driver_profile = db.relationship('DriverProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    trusted_contacts = db.relationship('TrustedContact', backref='user', cascade='all, delete-orphan')
    passenger_rides = db.relationship('Ride', foreign_keys='Ride.passenger_id', backref='passenger', lazy=True)
    driver_rides = db.relationship('Ride', foreign_keys='Ride.driver_id', backref='driver', lazy=True)
    reviews_given = db.relationship('Review', foreign_keys='Review.passenger_id', backref='passenger', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def total_spent(self):
        rides = Ride.query.filter_by(passenger_id=self.id, payment_status='paid').all()
        return round(sum(r.estimated_fare for r in rides), 2)

    @property
    def total_trips(self):
        return Ride.query.filter_by(passenger_id=self.id, status='completed').count()

    @property
    def total_rescues(self):
        return SOSAlert.query.filter_by(responder_id=self.id, status='rewarded').count()

    @property
    def total_rescue_rewards(self):
        alerts = SOSAlert.query.filter_by(responder_id=self.id, status='rewarded').all()
        return round(sum(a.reward_amount for a in alerts), 2)

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'wallet_balance': self.wallet_balance,
            'total_trips': self.total_trips,
            'total_spent': self.total_spent,
            'total_rescues': self.total_rescues,
            'total_rescue_rewards': self.total_rescue_rewards
        }

class DriverProfile(db.Model):
    __tablename__ = 'driver_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vehicle_model = db.Column(db.String(100), nullable=False)
    vehicle_tier = db.Column(db.String(20), nullable=False, default='Economy')
    license_plate = db.Column(db.String(30), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    approval_status = db.Column(db.String(20), default='approved')
    current_lat = db.Column(db.Float, default=23.7937)
    current_lng = db.Column(db.Float, default=90.4066)

    @property
    def average_rating(self):
        reviews = Review.query.filter_by(driver_id=self.user_id).all()
        if not reviews:
            return 5.0
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def rating_count(self):
        return Review.query.filter_by(driver_id=self.user_id).count()

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'driver_name': self.user.full_name if self.user else '',
            'vehicle_model': self.vehicle_model,
            'vehicle_tier': self.vehicle_tier,
            'license_plate': self.license_plate,
            'is_available': self.is_available,
            'approval_status': self.approval_status,
            'current_lat': self.current_lat,
            'current_lng': self.current_lng,
            'average_rating': self.average_rating,
            'rating_count': self.rating_count
        }

class TrustedContact(db.Model):
    __tablename__ = 'trusted_contacts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'contact_name': self.contact_name,
            'contact_phone': self.contact_phone
        }

class Ride(db.Model):
    __tablename__ = 'rides'

    id = db.Column(db.Integer, primary_key=True)
    passenger_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    pickup_address = db.Column(db.String(255), nullable=False)
    dropoff_address = db.Column(db.String(255), nullable=False)
    pickup_lat = db.Column(db.Float, default=23.7937)
    pickup_lng = db.Column(db.Float, default=90.4066)
    dropoff_lat = db.Column(db.Float, default=23.7771)
    dropoff_lng = db.Column(db.Float, default=90.4043)
    distance_km = db.Column(db.Float, nullable=False, default=3.5)
    estimated_fare = db.Column(db.Float, nullable=False, default=15.0)
    vehicle_tier = db.Column(db.String(20), nullable=False, default='Economy')
    status = db.Column(db.String(20), default='requested')
    payment_status = db.Column(db.String(20), default='unpaid')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    payments = db.relationship('Payment', backref='ride', lazy=True)
    reviews = db.relationship('Review', backref='ride', lazy=True)
    sos_alerts = db.relationship('SOSAlert', backref='ride', lazy=True)

    def to_dict(self):
        driver_info = None
        if self.driver:
            profile = self.driver.driver_profile
            driver_info = {
                'id': self.driver.id,
                'name': self.driver.full_name,
                'phone': self.driver.phone,
                'vehicle_model': profile.vehicle_model if profile else 'Standard Sedan',
                'license_plate': profile.license_plate if profile else 'DKA-0000',
                'current_lat': profile.current_lat if profile else self.pickup_lat,
                'current_lng': profile.current_lng if profile else self.pickup_lng,
                'average_rating': profile.average_rating if profile else 5.0
            }
        return {
            'id': self.id,
            'passenger_id': self.passenger_id,
            'passenger_name': self.passenger.full_name if self.passenger else '',
            'passenger_phone': self.passenger.phone if self.passenger else '',
            'driver_id': self.driver_id,
            'driver': driver_info,
            'pickup_address': self.pickup_address,
            'dropoff_address': self.dropoff_address,
            'pickup_lat': self.pickup_lat,
            'pickup_lng': self.pickup_lng,
            'dropoff_lat': self.dropoff_lat,
            'dropoff_lng': self.dropoff_lng,
            'distance_km': self.distance_km,
            'estimated_fare': self.estimated_fare,
            'vehicle_tier': self.vehicle_tier,
            'status': self.status,
            'payment_status': self.payment_status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('rides.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    transaction_ref = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'ride_id': self.ride_id,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'transaction_ref': self.transaction_ref,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('rides.id'), nullable=False)
    passenger_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'ride_id': self.ride_id,
            'passenger_name': self.passenger.full_name if self.passenger else '',
            'driver_name': self.driver.full_name if self.driver else '',
            'rating': self.rating,
            'comment': self.comment,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class SOSAlert(db.Model):
    __tablename__ = 'sos_alerts'

    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('rides.id'), nullable=False)
    triggered_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    responder_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    alert_lat = db.Column(db.Float, nullable=False)
    alert_lng = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='active')
    reward_amount = db.Column(db.Float, default=10.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trigger_user = db.relationship('User', foreign_keys=[triggered_by], backref='alerts_triggered')
    responder_user = db.relationship('User', foreign_keys=[responder_id], backref='alerts_responded')

    def to_dict(self):
        return {
            'id': self.id,
            'ride_id': self.ride_id,
            'triggered_by_name': self.trigger_user.full_name if self.trigger_user else '',
            'triggered_by_phone': self.trigger_user.phone if self.trigger_user else '',
            'responder_name': self.responder_user.full_name if self.responder_user else None,
            'alert_lat': self.alert_lat,
            'alert_lng': self.alert_lng,
            'status': self.status,
            'reward_amount': self.reward_amount,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
