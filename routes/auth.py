from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from extensions import db
from models import User, Wallet
import bcrypt
import random
import string
import os
import re
import resend
from datetime import datetime, timedelta

auth_bp = Blueprint("auth", __name__)

# ── OTP Store (in-memory, use Redis in production) ──
registration_otp_store = {}

# ── Resend setup ──
resend.api_key = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@payease.space')


def generate_wallet_number():
    return "PK" + "".join(random.choices(string.digits, k=10))


def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))


def is_valid_email_syntax(email):
    """Check if email has valid syntax"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def send_registration_otp_email(email, otp, full_name):
    """Send OTP email via Resend"""
    html_body = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

<tr><td style="background:linear-gradient(135deg,#1A73E8,#0052CC);padding:32px;text-align:center;">
<p style="color:#fff;font-size:32px;font-weight:bold;margin:0;letter-spacing:-0.5px;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Digital Wallet & Payment Services</p>
</td></tr>

<tr><td style="padding:36px 40px;">
<h2 style="color:#1A1A2E;font-size:22px;font-weight:bold;margin:0 0 8px 0;">Welcome, {full_name}! 👋</h2>
<p style="color:#888;font-size:14px;margin:0 0 28px 0;line-height:1.6;">
Thank you for joining PayEase! Please verify your email address to complete your registration.
Use the OTP below — it expires in <strong>5 minutes</strong>.
</p>

<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="background:#F0F4FF;border:2px dashed #1A73E8;border-radius:16px;padding:28px;text-align:center;">
<p style="color:#888;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 12px 0;">Verification Code</p>
<p style="color:#1A73E8;font-size:52px;font-weight:bold;letter-spacing:16px;margin:0;font-family:monospace;">{otp}</p>
<p style="color:#FF4444;font-size:12px;font-weight:600;margin:12px 0 0 0;">⏱ Expires in 5 minutes</p>
</td></tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;">
<tr><td style="background:#FFF8F0;border:1px solid #FFE0B2;border-radius:12px;padding:16px;">
<p style="color:#FF8C00;font-size:12px;font-weight:700;margin:0 0 4px 0;">🔒 Security Notice</p>
<p style="color:#888;font-size:12px;margin:0;line-height:1.5;">
Never share this code with anyone. PayEase will never ask for your OTP via phone or chat.
If you did not create this account, please ignore this email.
</p>
</td></tr>
</table>
</td></tr>

<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:20px 40px;text-align:center;">
<p style="color:#1A73E8;font-size:16px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">© 2026 PayEase Digital Wallet. All rights reserved.</p>
<p style="color:#AAB0C0;font-size:11px;margin:4px 0 0 0;">payease.space</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''

    try:
        resend.Emails.send({
            "from": f"PayEase <{SENDER_EMAIL}>",
            "to": [email],
            "subject": "PayEase — Verify Your Email Address",
            "html": html_body,
        })
        return True
    except Exception as e:
        print(f"Email sending failed: {str(e)}")
        return False


# ── STEP 1: Initiate Registration ──
@auth_bp.route("/register/initiate", methods=["POST"])
def initiate_register():
    """
    Step 1 of registration:
    - Validate email syntax
    - Check email not already registered
    - Generate OTP and send via email
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    full_name = data.get("full_name", "").strip()
    email     = data.get("email", "").strip().lower()
    phone     = data.get("phone", "").strip()
    password  = data.get("password", "")
    pin       = data.get("pin", "")

    # Validate required fields
    if not all([full_name, email, phone, password, pin]):
        return jsonify({"error": "All fields are required"}), 400

    # Validate PIN
    if len(pin) != 4 or not pin.isdigit():
        return jsonify({"error": "PIN must be 4 digits"}), 400

    # Validate password length
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    # Validate email syntax
    if not is_valid_email_syntax(email):
        return jsonify({"error": "Invalid email address format"}), 400

    # Check if email already registered
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    # Check if phone already registered
    if User.query.filter_by(phone=phone).first():
        return jsonify({"error": "Phone number already registered"}), 409

    # Generate OTP
    otp = generate_otp()

    # Store registration data + OTP temporarily
    registration_otp_store[email] = {
        "otp":       otp,
        "full_name": full_name,
        "email":     email,
        "phone":     phone,
        "password":  password,
        "pin":       pin,
        "expires":   datetime.utcnow() + timedelta(minutes=5),
        "verified":  False
    }

    # Try to send OTP email
    email_sent = send_registration_otp_email(email, otp, full_name)

    return jsonify({
        "message":    f"Verification code sent to {email}",
        "email":      email,
        "email_sent": email_sent,
        "dev_otp":    otp  # Remove in production
    }), 200


# ── STEP 2: Verify OTP & Complete Registration ──
@auth_bp.route("/register/verify", methods=["POST"])
def verify_and_register():
    """
    Step 2 of registration:
    - Verify OTP
    - Create user account
    - Create wallet
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = data.get("email", "").strip().lower()
    otp   = data.get("otp", "").strip()

    if not email or not otp:
        return jsonify({"error": "Email and OTP are required"}), 400

    # Check OTP store
    stored = registration_otp_store.get(email)

    if not stored:
        return jsonify({"error": "No pending registration found. Please start over."}), 400

    # Check expiry
    if datetime.utcnow() > stored["expires"]:
        del registration_otp_store[email]
        return jsonify({"error": "OTP has expired. Please register again."}), 400

    # Check OTP
    if stored["otp"] != otp:
        return jsonify({"error": "Invalid OTP. Please try again."}), 400

    # OTP verified — create user
    try:
        hashed_password = bcrypt.hashpw(
            stored["password"].encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        hashed_pin = bcrypt.hashpw(
            stored["pin"].encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        user = User(
            full_name = stored["full_name"],
            email     = stored["email"],
            phone     = stored["phone"],
            password  = hashed_password,
            pin       = hashed_pin
        )
        db.session.add(user)
        db.session.flush()

        wallet = Wallet(
            user_id       = user.id,
            wallet_number = generate_wallet_number(),
            balance       = 0.00
        )
        db.session.add(wallet)
        db.session.commit()

        # Clean up OTP store
        del registration_otp_store[email]

        return jsonify({
            "message":       "Registration successful! Welcome to PayEase!",
            "wallet_number": wallet.wallet_number
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ── RESEND OTP ──
@auth_bp.route("/register/resend-otp", methods=["POST"])
def resend_registration_otp():
    """Resend OTP for registration"""
    data  = request.get_json()
    email = data.get("email", "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    stored = registration_otp_store.get(email)
    if not stored:
        return jsonify({"error": "No pending registration found"}), 400

    # Generate new OTP
    otp = generate_otp()
    stored["otp"]     = otp
    stored["expires"] = datetime.utcnow() + timedelta(minutes=5)

    email_sent = send_registration_otp_email(email, otp, stored["full_name"])

    return jsonify({
        "message":    f"New OTP sent to {email}",
        "email_sent": email_sent,
        "dev_otp":    otp
    }), 200


# ── LOGIN ──
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not bcrypt.checkpw(
        password.encode("utf-8"),
        user.password.encode("utf-8")
    ):
        return jsonify({"error": "Invalid email or password"}), 401

    if user.is_blocked:
        return jsonify({"error": "Account is blocked. Contact support."}), 403

    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        "message":      "Login successful!",
        "access_token": access_token,
        "user":         user.to_dict()
    }), 200


# ── SETUP ADMIN ──
@auth_bp.route('/setup-admin', methods=['POST'])
def setup_admin():
    data   = request.get_json()
    secret = data.get('secret')

    if secret != 'payease-setup-2024':
        return jsonify({'error': 'Unauthorized'}), 401

    existing = User.query.filter_by(email='admin@payease.com').first()
    if existing:
        existing.is_admin     = True
        existing.kyc_verified = True
        db.session.commit()
        return jsonify({'message': 'Admin updated!'})

    hashed_password = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
    hashed_pin      = bcrypt.hashpw('0000'.encode(), bcrypt.gensalt()).decode()

    admin = User(
        full_name     = 'Admin',
        email         = 'admin@payease.com',
        phone         = '03000000000',
        password      = hashed_password,
        pin           = hashed_pin,
        is_admin      = True,
        kyc_verified  = True
    )
    db.session.add(admin)
    db.session.flush()

    wallet = Wallet(
        user_id       = admin.id,
        wallet_number = 'PK' + ''.join([str(random.randint(0, 9)) for _ in range(10)]),
        balance       = 100000
    )
    db.session.add(wallet)
    db.session.commit()

    return jsonify({'message': 'Admin created successfully!'})
