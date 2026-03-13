from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from extensions import db
from models import User, Wallet
import bcrypt
import random
import string
from utils.otp import send_otp, verify_otp

auth_bp = Blueprint("auth", __name__)


def generate_wallet_number():
    return "PK" + "".join(random.choices(string.digits, k=10))


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    full_name = data.get("full_name")
    email     = data.get("email")
    phone     = data.get("phone")
    password  = data.get("password")
    pin       = data.get("pin")

    if not full_name or not email or not phone or not password or not pin:
        return jsonify({"error": "All fields are required"}), 400

    if len(pin) != 4 or not pin.isdigit():
        return jsonify({"error": "PIN must be 4 digits"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    # Check if email or phone already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    if User.query.filter_by(phone=phone).first():
        return jsonify({"error": "Phone already registered"}), 409

    try:
        # Hash password and PIN
        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        hashed_pin = bcrypt.hashpw(
            pin.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        # Create user
        user = User(
            full_name = full_name,
            email     = email,
            phone     = phone,
            password  = hashed_password,
            pin       = hashed_pin
        )
        db.session.add(user)
        db.session.flush()

        # Create wallet
        wallet = Wallet(
            user_id       = user.id,
            wallet_number = generate_wallet_number(),
            balance       = 0.00
        )
        db.session.add(wallet)
        db.session.commit()

        return jsonify({
            "message":       "Registration successful!",
            "wallet_number": wallet.wallet_number
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    email    = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not bcrypt.checkpw(
        password.encode("utf-8"),
        user.password.encode("utf-8")
    ):
        return jsonify({"error": "Invalid email or password"}), 401

    if user.is_blocked:
        return jsonify({"error": "Account is blocked"}), 403

    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        "message":      "Login successful!",
        "access_token": access_token,
        "user":         user.to_dict()
    }), 200

#OTP

@auth_bp.route("/send-otp", methods=["POST"])
@jwt_required()
def request_otp():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    data    = request.get_json()
    purpose = data.get("purpose", "verification")

    success = send_otp(user.phone, purpose)

    if success:
        return jsonify({
            "message": f"OTP sent to {user.phone}"
        }), 200

    return jsonify({"error": "Failed to send OTP"}), 500


@auth_bp.route("/verify-otp", methods=["POST"])
@jwt_required()
def confirm_otp():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    data    = request.get_json()
    otp     = data.get("otp")

    if not otp:
        return jsonify({"error": "OTP is required"}), 400

    valid, message = verify_otp(user.phone, otp)

    if valid:
        return jsonify({
            "message": message,
            "verified": True
        }), 200

    return jsonify({
        "error":    message,
        "verified": False
    }), 400
    @auth_bp.route('/setup-admin', methods=['POST'])
def setup_admin():
    data = request.get_json()
    secret = data.get('secret')
    
    # Secret key to protect this route
    if secret != 'payease-setup-2024':
        return jsonify({'error': 'Unauthorized'}), 401
    
    from models.user import User
    from models.wallet import Wallet
    import bcrypt
    import random
    
    # Check if admin already exists
    existing = User.query.filter_by(email='admin@payease.com').first()
    if existing:
        existing.is_admin = True
        existing.kyc_verified = True
        db.session.commit()
        return jsonify({'message': 'Admin updated!'})
    
    # Create admin
    hashed_password = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
    hashed_pin = bcrypt.hashpw('0000'.encode(), bcrypt.gensalt()).decode()
    
    admin = User(
        full_name='Admin',
        email='admin@payease.com',
        phone='03000000000',
        password=hashed_password,
        pin=hashed_pin,
        is_admin=True,
        kyc_verified=True
    )
    db.session.add(admin)
    db.session.flush()
    
    wallet = Wallet(
        user_id=admin.id,
        wallet_number='PK' + ''.join([str(random.randint(0,9)) for _ in range(10)]),
        balance=100000
    )
    db.session.add(wallet)
    db.session.commit()
    
    return jsonify({'message': 'Admin created successfully!'})