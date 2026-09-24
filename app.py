import os
import math
from datetime import datetime
from functools import wraps
from io import BytesIO

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, DriverProfile, TrustedContact, Ride, Payment, Review, SOSAlert
from seed import seed_database

load_dotenv()

app = Flask(__name__)
# The fallback key is for local development only; set SECRET_KEY in production.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'citycab-dev-secret-key')

db_url = os.environ.get('DATABASE_URL', 'sqlite:///citycab.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def init_database():
    """Create tables and load the demo dataset the first time the app starts."""
    db.create_all()
    if os.environ.get('CITYCAB_AUTO_SEED', '1') == '1' and User.query.count() == 0:
        seed_database()

with app.app_context():
    try:
        init_database()
    except Exception:
        app.logger.exception('Database initialisation failed')

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None

def role_required(*roles):
    """Restrict a view to the given user roles, redirecting everyone else home."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                flash('Access restricted to authorised accounts only.', 'warning')
                return redirect(url_for('index'))
            return view(*args, **kwargs)
        return wrapped
    return decorator

def can_access_ride(ride):
    return current_user.role == 'admin' or current_user.id in (ride.passenger_id, ride.driver_id)

def ride_forbidden():
    return jsonify({'status': 'error', 'message': 'You do not have access to this ride'}), 403

def get_ride_from_payload(data):
    try:
        return db.session.get(Ride, int(data.get('ride_id')))
    except (TypeError, ValueError):
        return None

def calculate_haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

INDUSTRY_TIER_CONFIG = {
    'Bike': {
        'base_fare': 1.20,
        'per_km_rate': 0.85,
        'per_min_rate': 0.10,
        'booking_fee': 0.50,
        'min_fare': 3.00,
        'avg_speed_kmh': 30.0
    },
    'CNG': {
        'base_fare': 2.00,
        'per_km_rate': 1.20,
        'per_min_rate': 0.15,
        'booking_fee': 0.80,
        'min_fare': 4.00,
        'avg_speed_kmh': 20.0
    },
    'Economy': {
        'base_fare': 3.00,
        'per_km_rate': 1.50,
        'per_min_rate': 0.25,
        'booking_fee': 1.20,
        'min_fare': 5.00,
        'avg_speed_kmh': 25.0
    },
    'Comfort': {
        'base_fare': 4.50,
        'per_km_rate': 2.20,
        'per_min_rate': 0.35,
        'booking_fee': 1.50,
        'min_fare': 7.00,
        'avg_speed_kmh': 25.0
    },
    'Premium': {
        'base_fare': 7.00,
        'per_km_rate': 3.50,
        'per_min_rate': 0.50,
        'booking_fee': 2.00,
        'min_fare': 10.00,
        'avg_speed_kmh': 25.0
    }
}

def calculate_industry_fare(distance_km, tier, surge_multiplier=1.0):
    config = INDUSTRY_TIER_CONFIG.get(tier, INDUSTRY_TIER_CONFIG['Economy'])
    estimated_duration_min = round((distance_km / config['avg_speed_kmh']) * 60, 1)
    estimated_duration_min = max(estimated_duration_min, 3.0)

    base = config['base_fare']
    distance_cost = distance_km * config['per_km_rate']
    time_cost = estimated_duration_min * config['per_min_rate']
    booking_fee = config['booking_fee']

    subtotal = base + distance_cost + time_cost + booking_fee
    subtotal_with_surge = subtotal * surge_multiplier

    final_fare = max(subtotal_with_surge, config['min_fare'])
    final_fare = round(final_fare, 2)

    return {
        'final_fare': final_fare,
        'distance_km': distance_km,
        'duration_min': estimated_duration_min,
        'surge_multiplier': surge_multiplier,
        'breakdown': {
            'base_fare': round(base, 2),
            'distance_cost': round(distance_cost, 2),
            'time_cost': round(time_cost, 2),
            'booking_fee': round(booking_fee, 2),
            'min_fare_enforced': final_fare == config['min_fare']
        }
    }

def estimate_fare_amount(distance_km, tier):
    res = calculate_industry_fare(distance_km, tier)
    return res['final_fare']

VEHICLE_TIERS = list(INDUSTRY_TIER_CONFIG)
SELF_REGISTER_ROLES = ('passenger', 'driver', 'responder')
PAYMENT_METHODS = ('bkash', 'nagad', 'card', 'wallet')
MAX_TOPUP_AMOUNT = 1000.0
MIN_PASSWORD_LENGTH = 4
SOS_REWARD_AMOUNT = 10.0
SOS_MIN_RESPONDER_DISTANCE_KM = 1.0

def parse_route_coordinates(data):
    """Read pickup/dropoff coordinates from a JSON body, defaulting to the demo route in Dhaka."""
    coords = (
        float(data.get('pickup_lat', 23.7937)),
        float(data.get('pickup_lng', 90.4066)),
        float(data.get('dropoff_lat', 23.7771)),
        float(data.get('dropoff_lng', 90.4043)),
    )
    if not all(math.isfinite(c) for c in coords):
        raise ValueError('Coordinates must be finite numbers')
    return coords

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'driver':
            return redirect(url_for('driver_dashboard'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'responder':
            return redirect(url_for('responder_dashboard'))
        return redirect(url_for('passenger_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'passenger')

        if role not in SELF_REGISTER_ROLES:
            flash('Please choose a valid account type.', 'danger')
            return render_template('register.html')

        if not (full_name and email and phone):
            flash('Name, email and phone number are required.', 'danger')
            return render_template('register.html')

        if len(password) < MIN_PASSWORD_LENGTH:
            flash(f'Password must be at least {MIN_PASSWORD_LENGTH} characters.', 'danger')
            return render_template('register.html')

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('An account with this email already exists.', 'danger')
            return render_template('register.html')

        user = User(full_name=full_name, email=email, phone=phone, role=role, wallet_balance=50.0)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        if role == 'driver':
            vehicle_model = request.form.get('vehicle_model', '').strip() or 'Toyota Axio'
            vehicle_tier = request.form.get('vehicle_tier', 'Comfort')
            if vehicle_tier not in VEHICLE_TIERS:
                vehicle_tier = 'Comfort'
            license_plate = request.form.get('license_plate', '').strip() or 'DKA-12-3456'
            driver_prof = DriverProfile(
                user_id=user.id,
                vehicle_model=vehicle_model,
                vehicle_tier=vehicle_tier,
                license_plate=license_plate,
                approval_status='approved',
                current_lat=23.7937,
                current_lng=90.4066
            )
            db.session.add(driver_prof)
            db.session.commit()

        contact = TrustedContact(user_id=user.id, contact_name='Emergency Support', contact_phone='+8801700000000')
        db.session.add(contact)
        db.session.commit()

        login_user(user)
        flash('Account registered successfully! You are now logged in.', 'success')
        return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', '').strip() or current_user.full_name
        current_user.phone = request.form.get('phone', '').strip() or current_user.phone
        db.session.commit()
        flash('Profile updated successfully.', 'success')

    contacts = TrustedContact.query.filter_by(user_id=current_user.id).all()
    user_rides = Ride.query.filter_by(passenger_id=current_user.id).order_by(Ride.created_at.desc()).limit(15).all()
    return render_template('profile.html', user=current_user, contacts=contacts, rides=user_rides)

@app.route('/profile/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not current_user.check_password(current_password):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('profile'))

    if len(new_password) < MIN_PASSWORD_LENGTH:
        flash(f'New password must be at least {MIN_PASSWORD_LENGTH} characters.', 'danger')
        return redirect(url_for('profile'))

    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('profile'))

    current_user.set_password(new_password)
    db.session.commit()
    flash('Password changed successfully!', 'success')
    return redirect(url_for('profile'))

@app.route('/trusted_contact/add', methods=['POST'])
@login_required
def add_trusted_contact():
    name = request.form.get('contact_name', '').strip()
    phone = request.form.get('contact_phone', '').strip()
    if name and phone:
        contact = TrustedContact(user_id=current_user.id, contact_name=name, contact_phone=phone)
        db.session.add(contact)
        db.session.commit()
        flash('Trusted contact added.', 'success')
    return redirect(request.referrer or url_for('profile'))

@app.route('/trusted_contact/delete/<int:contact_id>', methods=['POST'])
@login_required
def delete_trusted_contact(contact_id):
    contact = db.session.get(TrustedContact, contact_id)
    if contact and contact.user_id == current_user.id:
        db.session.delete(contact)
        db.session.commit()
        flash('Trusted contact removed.', 'info')
    return redirect(request.referrer or url_for('profile'))

@app.route('/wallet/topup', methods=['POST'])
@login_required
def topup_wallet():
    try:
        amount = float(request.form.get('amount', 0))
        payment_method = request.form.get('payment_method', 'card').lower()
        if not math.isfinite(amount) or amount > MAX_TOPUP_AMOUNT:
            flash(f'Top-up amount must be between $1 and ${MAX_TOPUP_AMOUNT:.0f}.', 'warning')
        elif amount > 0:
            current_user.wallet_balance += amount
            db.session.commit()
            prefix = "BKASH" if payment_method == 'bkash' else ("NAGAD" if payment_method == 'nagad' else "CARD")
            txn_ref = f"TXN-TOPUP-{prefix}-{int(datetime.utcnow().timestamp())}"
            method_display = "bKash Mobile Pay" if payment_method == 'bkash' else ("Nagad Digital Pay" if payment_method == 'nagad' else "Credit/Debit Card")
            flash(f'Successfully recharged ${amount:.2f} to your CityCab Wallet via {method_display}! (Transaction ID: {txn_ref})', 'success')
        else:
            flash('Top-up amount must be greater than zero.', 'warning')
    except ValueError:
        flash('Invalid top-up amount. Please enter a valid number.', 'danger')
    return redirect(request.referrer or url_for('index'))

@app.route('/passenger/dashboard')
@login_required
def passenger_dashboard():
    active_ride = Ride.query.filter(
        Ride.passenger_id == current_user.id,
        Ride.status.in_(['requested', 'accepted', 'en_route'])
    ).order_by(Ride.created_at.desc()).first()

    recent_rides = Ride.query.filter_by(passenger_id=current_user.id)\
        .order_by(Ride.created_at.desc()).limit(10).all()

    contacts = TrustedContact.query.filter_by(user_id=current_user.id).all()

    return render_template('passenger_dashboard.html', active_ride=active_ride, recent_rides=recent_rides, contacts=contacts)

@app.route('/passenger/trips')
@login_required
def passenger_trips():
    all_rides = Ride.query.filter_by(passenger_id=current_user.id).order_by(Ride.created_at.desc()).all()
    completed_rides = [r for r in all_rides if r.status == 'completed']
    total_spent = sum(r.estimated_fare for r in completed_rides if r.payment_status == 'paid')
    return render_template('passenger_trips.html', all_rides=all_rides, completed_rides=completed_rides, total_spent=total_spent)

@app.route('/passenger/safety')
@login_required
def passenger_safety():
    active_ride = Ride.query.filter(
        Ride.passenger_id == current_user.id,
        Ride.status.in_(['requested', 'accepted', 'en_route'])
    ).order_by(Ride.created_at.desc()).first()
    contacts = TrustedContact.query.filter_by(user_id=current_user.id).all()
    return render_template('passenger_safety.html', active_ride=active_ride, contacts=contacts)

@app.route('/passenger/wallet')
@login_required
def passenger_wallet():
    rides = Ride.query.filter_by(passenger_id=current_user.id).all()
    ride_ids = [r.id for r in rides]
    payments = Payment.query.filter(Payment.ride_id.in_(ride_ids)).order_by(Payment.created_at.desc()).all() if ride_ids else []
    return render_template('passenger_wallet.html', payments=payments)

@app.route('/driver/dashboard')
@role_required('driver', 'admin')
def driver_dashboard():
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    requested_rides = Ride.query.filter_by(status='requested').order_by(Ride.created_at.desc()).all()
    active_ride = Ride.query.filter(
        Ride.driver_id == current_user.id,
        Ride.status.in_(['accepted', 'en_route'])
    ).first()
    completed_rides = Ride.query.filter_by(driver_id=current_user.id, status='completed').order_by(Ride.created_at.desc()).all()
    total_earnings = sum(r.estimated_fare for r in completed_rides)
    reviews_received = Review.query.filter_by(driver_id=current_user.id).order_by(Review.created_at.desc()).limit(10).all()

    return render_template('driver_dashboard.html',
                           profile=profile,
                           requested_rides=requested_rides,
                           active_ride=active_ride,
                           completed_rides=completed_rides,
                           total_earnings=total_earnings,
                           reviews=reviews_received)

@app.route('/driver/requests')
@role_required('driver', 'admin')
def driver_requests():
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    requested_rides = Ride.query.filter_by(status='requested').order_by(Ride.created_at.desc()).all()
    return render_template('driver_requests.html', profile=profile, requested_rides=requested_rides)

@app.route('/driver/earnings')
@role_required('driver', 'admin')
def driver_earnings():
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    completed_rides = Ride.query.filter_by(driver_id=current_user.id, status='completed').order_by(Ride.created_at.desc()).all()
    total_earnings = sum(r.estimated_fare for r in completed_rides)
    return render_template('driver_earnings.html', profile=profile, completed_rides=completed_rides, total_earnings=total_earnings)

@app.route('/driver/reviews')
@role_required('driver', 'admin')
def driver_reviews():
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    reviews_received = Review.query.filter_by(driver_id=current_user.id).order_by(Review.created_at.desc()).all()
    return render_template('driver_reviews.html', profile=profile, reviews=reviews_received)

@app.route('/responder/dashboard')
@login_required
def responder_dashboard():
    alerts = SOSAlert.query.filter_by(status='active').order_by(SOSAlert.created_at.desc()).all()
    return render_template('responder_dashboard.html', alerts=alerts)

@app.route('/responder/alerts')
@login_required
def responder_alerts():
    alerts = SOSAlert.query.filter_by(status='active').order_by(SOSAlert.created_at.desc()).all()
    return render_template('responder_alerts.html', alerts=alerts)

@app.route('/responder/rewards')
@login_required
def responder_rewards():
    responded_alerts = SOSAlert.query.filter_by(responder_id=current_user.id).order_by(SOSAlert.created_at.desc()).all()
    return render_template('responder_rewards.html', responded_alerts=responded_alerts)

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    total_users = User.query.count()
    total_drivers = DriverProfile.query.count()
    total_rides = Ride.query.count()
    total_revenue = sum(r.estimated_fare for r in Ride.query.filter_by(payment_status='paid').all())

    active_rides = Ride.query.filter(Ride.status.in_(['requested', 'accepted', 'en_route'])).order_by(Ride.created_at.desc()).all()
    all_rides = Ride.query.order_by(Ride.created_at.desc()).limit(20).all()
    drivers = DriverProfile.query.all()
    all_users = User.query.order_by(User.created_at.desc()).all()
    recent_sos = SOSAlert.query.order_by(SOSAlert.created_at.desc()).limit(10).all()
    recent_reviews = Review.query.order_by(Review.created_at.desc()).limit(10).all()

    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           total_drivers=total_drivers,
                           total_rides=total_rides,
                           total_revenue=total_revenue,
                           active_rides=active_rides,
                           all_rides=all_rides,
                           drivers=drivers,
                           all_users=all_users,
                           recent_sos=recent_sos,
                           reviews=recent_reviews)

@app.route('/admin/drivers')
@role_required('admin')
def admin_drivers():
    drivers = DriverProfile.query.all()
    return render_template('admin_drivers.html', drivers=drivers)

@app.route('/admin/responders')
@role_required('admin')
def admin_responders():
    responders = User.query.filter_by(role='responder').order_by(User.created_at.desc()).all()
    total_rescues = sum(r.total_rescues for r in responders)
    total_rewards_paid = sum(r.total_rescue_rewards for r in responders)
    return render_template('admin_responders.html', responders=responders, total_rescues=total_rescues, total_rewards_paid=total_rewards_paid)

@app.route('/admin/users')
@role_required('admin')
def admin_users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', all_users=all_users)

@app.route('/admin/rides')
@role_required('admin')
def admin_rides():
    all_rides = Ride.query.order_by(Ride.created_at.desc()).all()
    return render_template('admin_rides.html', all_rides=all_rides)

@app.route('/admin/sos-logs')
@role_required('admin')
def admin_sos_logs():
    recent_sos = SOSAlert.query.order_by(SOSAlert.created_at.desc()).all()
    return render_template('admin_sos_logs.html', recent_sos=recent_sos)

@app.route('/admin/driver/approve/<int:driver_id>', methods=['POST'])
@role_required('admin')
def admin_approve_driver(driver_id):
    profile = db.session.get(DriverProfile, driver_id)
    if profile:
        profile.approval_status = 'approved'
        db.session.commit()
        flash(f'Driver {profile.user.full_name} approved.', 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/driver/reject/<int:driver_id>', methods=['POST'])
@role_required('admin')
def admin_reject_driver(driver_id):
    profile = db.session.get(DriverProfile, driver_id)
    if profile:
        profile.approval_status = 'rejected'
        db.session.commit()
        flash(f'Driver {profile.user.full_name} rejected.', 'warning')
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/user/delete/<int:user_id>', methods=['POST'])
@role_required('admin')
def admin_delete_user(user_id):
    if user_id == current_user.id:
        flash('You cannot delete your own admin account.', 'danger')
        return redirect(request.referrer or url_for('admin_dashboard'))

    user = db.session.get(User, user_id)
    if user and (user.passenger_rides or user.driver_rides or user.reviews_given
                 or user.alerts_triggered or user.alerts_responded):
        # Rides, reviews and SOS logs reference users by non-nullable foreign keys,
        # so accounts with history are kept for audit purposes.
        flash(f'{user.full_name} has trip or SOS history and cannot be deleted.', 'warning')
    elif user:
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.full_name} removed from platform.', 'info')
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/api/estimate_fare', methods=['POST'])
@login_required
def api_estimate_fare():
    data = request.get_json(silent=True) or {}
    try:
        pickup_lat, pickup_lng, dropoff_lat, dropoff_lng = parse_route_coordinates(data)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid pickup or dropoff coordinates'}), 400

    distance = calculate_haversine(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)

    estimates = {}
    detailed_breakdowns = {}
    for tier in VEHICLE_TIERS:
        res = calculate_industry_fare(distance, tier)
        estimates[tier] = res['final_fare']
        detailed_breakdowns[tier] = res

    return jsonify({
        'status': 'success',
        'distance_km': distance,
        'estimates': estimates,
        'breakdowns': detailed_breakdowns
    })

@app.route('/api/request_ride', methods=['POST'])
@login_required
def api_request_ride():
    data = request.get_json(silent=True) or {}
    pickup_address = str(data.get('pickup_address') or 'Banani Road 11')[:255]
    dropoff_address = str(data.get('dropoff_address') or 'BRAC University, Mohakhali')[:255]
    vehicle_tier = data.get('vehicle_tier', 'Comfort')
    if vehicle_tier not in VEHICLE_TIERS:
        return jsonify({'status': 'error', 'message': 'Unknown vehicle tier'}), 400
    try:
        pickup_lat, pickup_lng, dropoff_lat, dropoff_lng = parse_route_coordinates(data)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid pickup or dropoff coordinates'}), 400

    distance_km = calculate_haversine(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
    fare = estimate_fare_amount(distance_km, vehicle_tier)

    existing_unfulfilled = Ride.query.filter_by(passenger_id=current_user.id, status='requested').all()
    for r in existing_unfulfilled:
        r.status = 'cancelled'

    new_ride = Ride(
        passenger_id=current_user.id,
        pickup_address=pickup_address,
        dropoff_address=dropoff_address,
        pickup_lat=pickup_lat,
        pickup_lng=pickup_lng,
        dropoff_lat=dropoff_lat,
        dropoff_lng=dropoff_lng,
        distance_km=distance_km,
        estimated_fare=fare,
        vehicle_tier=vehicle_tier,
        status='requested',
        payment_status='unpaid'
    )
    db.session.add(new_ride)
    db.session.commit()

    # Find available approved drivers matching requested vehicle tier
    matching_drivers = DriverProfile.query.filter_by(is_available=True, approval_status='approved', vehicle_tier=vehicle_tier).all()
    if not matching_drivers:
        # Fallback to all available approved drivers
        matching_drivers = DriverProfile.query.filter_by(is_available=True, approval_status='approved').all()

    if matching_drivers:
        # Sort by proximity to passenger pickup location
        matching_drivers.sort(key=lambda d: calculate_haversine(pickup_lat, pickup_lng, d.current_lat, d.current_lng))
        assigned_driver = matching_drivers[0]
        new_ride.driver_id = assigned_driver.user_id
        new_ride.status = 'accepted'
        db.session.commit()

    return jsonify({'status': 'success', 'ride': new_ride.to_dict()})

@app.route('/api/ride/<int:ride_id>')
@login_required
def api_get_ride(ride_id):
    ride = db.session.get(Ride, ride_id)
    if not ride:
        return jsonify({'status': 'error', 'message': 'Ride not found'}), 404
    if not can_access_ride(ride):
        return ride_forbidden()
    return jsonify({'status': 'success', 'ride': ride.to_dict()})

@app.route('/api/ride/<int:ride_id>/status', methods=['POST'])
@login_required
def api_update_ride_status(ride_id):
    ride = db.session.get(Ride, ride_id)
    if not ride:
        return jsonify({'status': 'error', 'message': 'Ride not found'}), 404
    if not can_access_ride(ride):
        return ride_forbidden()
    if ride.status in ('completed', 'cancelled'):
        return jsonify({'status': 'error', 'message': f'Ride is already {ride.status}'}), 400

    data = request.get_json(silent=True) or {}
    new_status = data.get('status')
    if new_status in ['accepted', 'en_route', 'completed', 'cancelled']:
        ride.status = new_status
        if new_status in ['completed', 'cancelled'] and ride.driver_id:
            profile = DriverProfile.query.filter_by(user_id=ride.driver_id).first()
            if profile:
                profile.is_available = True
        db.session.commit()
        return jsonify({'status': 'success', 'ride': ride.to_dict()})
    return jsonify({'status': 'error', 'message': 'Invalid status'}), 400

@app.route('/api/driver/toggle_availability', methods=['POST'])
@login_required
def api_driver_toggle_availability():
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        profile.is_available = not profile.is_available
        db.session.commit()
        return jsonify({'status': 'success', 'is_available': profile.is_available})
    return jsonify({'status': 'error', 'message': 'Profile not found'}), 404

@app.route('/api/driver/accept_ride/<int:ride_id>', methods=['POST'])
@login_required
def api_driver_accept_ride(ride_id):
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    if current_user.role != 'driver' or not profile or profile.approval_status != 'approved':
        return jsonify({'status': 'error', 'message': 'Only approved drivers can accept rides'}), 403

    ride = db.session.get(Ride, ride_id)
    if not ride or ride.status != 'requested':
        return jsonify({'status': 'error', 'message': 'Ride is no longer available'}), 400

    ride.driver_id = current_user.id
    ride.status = 'accepted'
    profile.is_available = False
    db.session.commit()

    return jsonify({'status': 'success', 'ride': ride.to_dict()})

@app.route('/api/pay_ride', methods=['POST'])
@login_required
def api_pay_ride():
    data = request.get_json(silent=True) or {}
    payment_method = str(data.get('payment_method', 'card')).lower()
    if payment_method not in PAYMENT_METHODS:
        return jsonify({'status': 'error', 'message': 'Unsupported payment method'}), 400

    ride = get_ride_from_payload(data)
    if not ride:
        return jsonify({'status': 'error', 'message': 'Ride not found'}), 404
    if ride.passenger_id != current_user.id:
        return ride_forbidden()

    if ride.payment_status == 'paid':
        return jsonify({'status': 'error', 'message': 'Ride is already paid'}), 400

    if payment_method == 'wallet':
        if current_user.wallet_balance < ride.estimated_fare:
            return jsonify({'status': 'error', 'message': 'Insufficient wallet balance. Please top up your wallet.'}), 400
        current_user.wallet_balance -= ride.estimated_fare

    txn_ref = f"TXN-{payment_method.upper()}-{int(datetime.utcnow().timestamp())}"

    payment = Payment(
        ride_id=ride.id,
        amount=ride.estimated_fare,
        payment_method=payment_method,
        transaction_ref=txn_ref,
        status='completed'
    )
    ride.payment_status = 'paid'

    # Drivers receive 85% of the fare; the remaining 15% is the platform commission.
    if ride.driver_id:
        driver_user = db.session.get(User, ride.driver_id)
        if driver_user:
            driver_user.wallet_balance += ride.estimated_fare * 0.85

    db.session.add(payment)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Payment successfully verified and authorized via {payment_method.upper()} Gateway!',
        'transaction_ref': payment.transaction_ref,
        'wallet_balance': current_user.wallet_balance
    })

@app.route('/api/submit_review', methods=['POST'])
@login_required
def api_submit_review():
    data = request.get_json(silent=True) or {}
    try:
        rating = int(data.get('rating', 5))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Rating must be a number from 1 to 5'}), 400
    if not 1 <= rating <= 5:
        return jsonify({'status': 'error', 'message': 'Rating must be a number from 1 to 5'}), 400
    comment = str(data.get('comment') or '').strip()

    ride = get_ride_from_payload(data)
    if not ride:
        return jsonify({'status': 'error', 'message': 'Ride not found'}), 404
    if ride.passenger_id != current_user.id:
        return ride_forbidden()

    if not ride.driver_id:
        return jsonify({'status': 'error', 'message': 'No driver assigned to this ride'}), 400

    if Review.query.filter_by(ride_id=ride.id).first():
        return jsonify({'status': 'error', 'message': 'You have already reviewed this ride'}), 400

    review = Review(
        ride_id=ride.id,
        passenger_id=current_user.id,
        driver_id=ride.driver_id,
        rating=rating,
        comment=comment
    )
    db.session.add(review)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Thank you for rating your ride!'})

@app.route('/api/trigger_sos', methods=['POST'])
@login_required
def api_trigger_sos():
    data = request.get_json(silent=True) or {}
    ride = get_ride_from_payload(data)
    if not ride:
        return jsonify({'status': 'error', 'message': 'Ride not found'}), 404
    if not can_access_ride(ride):
        return ride_forbidden()

    try:
        alert_lat = float(data.get('alert_lat', ride.pickup_lat))
        alert_lng = float(data.get('alert_lng', ride.pickup_lng))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid alert coordinates'}), 400

    existing_alert = SOSAlert.query.filter_by(ride_id=ride.id, status='active').first()
    if not existing_alert:
        existing_alert = SOSAlert(
            ride_id=ride.id,
            triggered_by=current_user.id,
            alert_lat=alert_lat,
            alert_lng=alert_lng,
            status='active',
            reward_amount=SOS_REWARD_AMOUNT
        )
        db.session.add(existing_alert)
        db.session.commit()

    return jsonify({
        'status': 'success',
        'message': 'EMERGENCY SOS DISPATCHED! Trusted contacts notified via SMS simulation.',
        'alert': existing_alert.to_dict()
    })

@app.route('/api/active_sos_alerts')
@login_required
def api_active_sos_alerts():
    alerts = SOSAlert.query.filter_by(status='active').all()
    result = []

    user_lat = request.args.get('lat', 23.7771, type=float)
    user_lng = request.args.get('lng', 90.4043, type=float)

    for alert in alerts:
        distance = calculate_haversine(user_lat, user_lng, alert.alert_lat, alert.alert_lng)
        is_eligible_for_reward = (alert.triggered_by != current_user.id) and (distance >= SOS_MIN_RESPONDER_DISTANCE_KM)

        alert_data = alert.to_dict()
        alert_data['distance_km'] = distance
        alert_data['is_eligible_for_reward'] = is_eligible_for_reward
        result.append(alert_data)

    return jsonify({'status': 'success', 'alerts': result})

@app.route('/api/respond_sos/<int:alert_id>', methods=['POST'])
@login_required
def api_respond_sos(alert_id):
    alert = db.session.get(SOSAlert, alert_id)
    if not alert or alert.status != 'active':
        return jsonify({'status': 'error', 'message': 'Alert is no longer active'}), 400

    if alert.triggered_by == current_user.id:
        return jsonify({'status': 'error', 'message': 'You cannot claim reward on your own SOS trigger!'}), 400

    data = request.get_json(silent=True) or {}
    try:
        user_lat = float(data.get('user_lat', 23.7950))
        user_lng = float(data.get('user_lng', 90.4120))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid responder coordinates'}), 400
    distance = calculate_haversine(user_lat, user_lng, alert.alert_lat, alert.alert_lng)

    # Anti-fraud rule: responders must be dispatched from at least 1 km away, so a
    # passenger (or someone riding with them) cannot claim the reward for their own alert.
    if distance < SOS_MIN_RESPONDER_DISTANCE_KM:
        return jsonify({
            'status': 'error',
            'message': f'Reward verification requires responder to be at least {SOS_MIN_RESPONDER_DISTANCE_KM:.1f} km away to prevent fraud. You are currently {distance:.2f} km away.'
        }), 400

    alert.responder_id = current_user.id
    alert.status = 'rewarded'
    current_user.wallet_balance += alert.reward_amount
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Thank you for responding! Emergency spot verified. ${alert.reward_amount:.2f} Wallet Credit awarded to your account.',
        'wallet_balance': current_user.wallet_balance
    })

@app.route('/ride/<int:ride_id>/invoice')
@login_required
def generate_invoice(ride_id):
    ride = db.session.get(Ride, ride_id)
    if not ride:
        flash('Ride not found.', 'danger')
        return redirect(url_for('index'))

    if not can_access_ride(ride):
        flash('Unauthorized access to trip invoice.', 'danger')
        return redirect(url_for('index'))

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        p.setFont("Helvetica-Bold", 20)
        p.drawString(100, 750, "CityCab Ride Invoice & Receipt")

        p.setFont("Helvetica", 12)
        p.drawString(100, 720, f"Invoice #: INV-CITY-{ride.id:05d}")
        p.drawString(100, 700, f"Date: {ride.created_at.strftime('%B %d, %Y %I:%M %p')}")

        p.line(100, 685, 500, 685)

        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, 660, "Trip Summary")

        p.setFont("Helvetica", 12)
        p.drawString(100, 635, f"Passenger: {ride.passenger.full_name}")
        p.drawString(100, 615, f"Driver: {ride.driver.full_name if ride.driver else 'N/A'}")
        p.drawString(100, 595, f"Pickup: {ride.pickup_address}")
        p.drawString(100, 575, f"Dropoff: {ride.dropoff_address}")
        p.drawString(100, 555, f"Distance: {ride.distance_km:.2f} km")
        p.drawString(100, 535, f"Vehicle Tier: {ride.vehicle_tier}")

        p.line(100, 515, 500, 515)

        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, 490, "Payment Details")

        p.setFont("Helvetica", 12)
        p.drawString(100, 465, f"Base & Distance Fare: ${ride.estimated_fare:.2f}")
        p.drawString(100, 445, f"Payment Status: {ride.payment_status.upper()}")
        p.drawString(100, 425, f"Total Paid: ${ride.estimated_fare:.2f}")

        p.setFont("Helvetica-Oblique", 10)
        p.drawString(100, 350, "Thank you for riding with CityCab! Safe journeys ahead.")

        p.showPage()
        p.save()

        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"CityCab_Invoice_Ride_{ride.id}.pdf", mimetype='application/pdf')
    except Exception:
        return render_template('invoice.html', ride=ride)

@app.route('/ride/<int:ride_id>/receipt')
@login_required
def view_html_receipt(ride_id):
    ride = db.session.get(Ride, ride_id)
    if not ride:
        flash('Ride not found.', 'danger')
        return redirect(url_for('index'))
    if not can_access_ride(ride):
        flash('Unauthorized access to receipt.', 'danger')
        return redirect(url_for('index'))
    return render_template('invoice.html', ride=ride)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
