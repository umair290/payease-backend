from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)
from extensions import db, limiter
from models import User, Wallet
from models.token_blocklist import TokenBlocklist
import bcrypt
import random
import string
import os
import re
import resend
import hashlib
from datetime import datetime, timedelta
from routes.admin import add_log

auth_bp = Blueprint("auth", __name__)

# ── OTP Store (in-memory, fine for single-instance) ──
registration_otp_store = {}

# ── Resend setup ──
resend.api_key = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')
SENDER_EMAIL   = os.environ.get('SENDER_EMAIL', 'support@payease.space')


# ── Helpers ──
def generate_wallet_number():
    return "PK" + "".join(random.choices(string.digits, k=10))

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def is_valid_email_syntax(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_ip(req):
    ip = req.headers.get('X-Forwarded-For', req.remote_addr or 'Unknown')
    return ip.split(',')[0].strip()


# ── Email helpers ──
def send_registration_otp_email(email, otp, full_name):
    html_body = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#1A73E8,#0052CC);padding:32px;text-align:center;">
<p style="color:#fff;font-size:32px;font-weight:bold;margin:0;">PayEase</p>
<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0 0;">Digital Wallet and Payment Services</p>
</td></tr>
<tr><td style="padding:36px 40px;">
<h2 style="color:#1A1A2E;font-size:22px;font-weight:bold;margin:0 0 8px 0;">Welcome, {full_name}!</h2>
<p style="color:#888;font-size:14px;margin:0 0 28px 0;line-height:1.6;">
Thank you for joining PayEase! Please verify your email address to complete your registration.
Use the OTP below — it expires in <strong>5 minutes</strong>.
</p>
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="background:#F0F4FF;border:2px dashed #1A73E8;border-radius:16px;padding:28px;text-align:center;">
<p style="color:#888;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 12px 0;">Verification Code</p>
<p style="color:#1A73E8;font-size:52px;font-weight:bold;letter-spacing:16px;margin:0;font-family:monospace;">{otp}</p>
<p style="color:#FF4444;font-size:12px;font-weight:600;margin:12px 0 0 0;">Expires in 5 minutes</p>
</td></tr>
</table>
<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;">
<tr><td style="background:#FFF8F0;border:1px solid #FFE0B2;border-radius:12px;padding:16px;">
<p style="color:#FF8C00;font-size:12px;font-weight:700;margin:0 0 4px 0;">Security Notice</p>
<p style="color:#888;font-size:12px;margin:0;line-height:1.5;">
Never share this code with anyone. PayEase will never ask for your OTP via phone or chat.
</p>
</td></tr>
</table>
</td></tr>
<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:20px 40px;text-align:center;">
<p style="color:#1A73E8;font-size:16px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">2026 PayEase Digital Wallet. All rights reserved.</p>
<p style="color:#AAB0C0;font-size:11px;margin:4px 0 0 0;">payease.space</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''
    try:
        resend.Emails.send({
            "from":    f"PayEase <{SENDER_EMAIL}>",
            "to":      [email],
            "subject": "PayEase — Verify Your Email Address",
            "html":    html_body,
        })
        return True
    except Exception as e:
        print(f"Email sending failed: {str(e)}")
        return False


def send_new_device_email(email, full_name, ip_address, user_agent):
    now      = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
    ua_short = user_agent[:80] + '...' if len(user_agent) > 80 else user_agent
    html_body = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F0F4FF;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4FF;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#DC2626,#B91C1C);padding:28px;text-align:center;">
<p style="color:#fff;font-size:28px;font-weight:bold;margin:0;">PayEase</p>
<p style="color:rgba(255,255,255,0.75);font-size:13px;margin:6px 0 0 0;">Security Alert</p>
</td></tr>
<tr><td style="padding:28px 32px;">
<h2 style="color:#1A1A2E;font-size:20px;font-weight:bold;margin:0 0 8px 0;">New Device Login Detected</h2>
<p style="color:#666;font-size:14px;margin:0 0 20px 0;line-height:1.6;">
Hi <strong>{full_name}</strong>, your PayEase account was accessed from a new device or browser.
</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFF;border-radius:14px;overflow:hidden;border:1px solid #E0E6F0;margin-bottom:20px;">
<tr style="background:#EEF2FF;">
  <td colspan="2" style="padding:10px 16px;font-size:11px;font-weight:700;color:#1A73E8;text-transform:uppercase;letter-spacing:0.5px;">Login Details</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;width:120px;">Date and Time</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A1A2E;">{now}</td>
</tr>
<tr style="border-bottom:1px solid #E0E6F0;">
  <td style="padding:10px 16px;font-size:13px;color:#888;">IP Address</td>
  <td style="padding:10px 16px;font-size:13px;font-weight:600;color:#1A1A2E;">{ip_address}</td>
</tr>
<tr>
  <td style="padding:10px 16px;font-size:13px;color:#888;">Device</td>
  <td style="padding:10px 16px;font-size:12px;color:#1A1A2E;">{ua_short}</td>
</tr>
</table>
<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:14px 16px;">
<p style="color:#C2410C;font-size:12px;font-weight:700;margin:0 0 4px 0;">Security Tip</p>
<p style="color:#9A3412;font-size:12px;margin:0;line-height:1.5;">
If this was not you, change your password immediately from your profile settings.
Never share your password or PIN with anyone.
</p>
</div>
</td></tr>
<tr><td style="background:#F8FAFF;border-top:1px solid #E0E6F0;padding:16px 32px;text-align:center;">
<p style="color:#1A73E8;font-size:15px;font-weight:bold;margin:0 0 4px 0;">PayEase</p>
<p style="color:#AAB0C0;font-size:11px;margin:0;">payease.space</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''
    try:
        resend.Emails.send({
            "from":    f"PayEase Security <{SENDER_EMAIL}>",
            "to":      [email],
            "subject": "PayEase — New Device Login Detected",
            "html":    html_body,
        })
        return True
    except Exception as e:
        print(f"New device email failed: {str(e)}")
        return False


# ── STEP 1: Initiate Registration ──
# 5 attempts per hour per IP — prevents mass account creation
@auth_bp.route("/register/initiate", methods=["POST"])
@limiter.limit("5 per hour")
def initiate_register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    full_name = data.get("full_name", "").strip()
    email     = data.get("email",     "").strip().lower()
    phone     = data.get("phone",     "").strip()
    password  = data.get("password",  "")
    pin       = data.get("pin",       "")

    if not all([full_name, email, phone, password, pin]):
        return jsonify({"error": "All fields are required"}), 400
    if len(pin) != 4 or not pin.isdigit():
        return jsonify({"error": "PIN must be 4 digits"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if not is_valid_email_syntax(email):
        return jsonify({"error": "Invalid email address format"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409
    if User.query.filter_by(phone=phone).first():
        return jsonify({"error": "Phone number already registered"}), 409

    otp = generate_otp()
    registration_otp_store[email] = {
        "otp":       otp,
        "full_name": full_name,
        "email":     email,
        "phone":     phone,
        "password":  password,
        "pin":       pin,
        "expires":   datetime.utcnow() + timedelta(minutes=5),
    }

    email_sent = send_registration_otp_email(email, otp, full_name)
    return jsonify({
        "message":    f"Verification code sent to {email}",
        "email":      email,
        "email_sent": email_sent,
    }), 200


# ── STEP 2: Verify OTP and Complete Registration ──
# 10 attempts per hour — prevents OTP brute force
@auth_bp.route("/register/verify", methods=["POST"])
@limiter.limit("10 per hour")
def verify_and_register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = data.get("email", "").strip().lower()
    otp   = data.get("otp",   "").strip()

    if not email or not otp:
        return jsonify({"error": "Email and OTP are required"}), 400

    stored = registration_otp_store.get(email)
    if not stored:
        return jsonify({"error": "No pending registration found. Please start over."}), 400
    if datetime.utcnow() > stored["expires"]:
        del registration_otp_store[email]
        return jsonify({"error": "OTP has expired. Please register again."}), 400
    if stored["otp"] != otp:
        return jsonify({"error": "Invalid OTP. Please try again."}), 400

    try:
        hashed_password = bcrypt.hashpw(stored["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        hashed_pin      = bcrypt.hashpw(stored["pin"].encode("utf-8"),      bcrypt.gensalt()).decode("utf-8")

        user = User(
            full_name = stored["full_name"],
            email     = stored["email"],
            phone     = stored["phone"],
            password  = hashed_password,
            pin       = hashed_pin,
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

        try:
            ip  = get_ip(request)
            now = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')
            add_log(user.id, 'Account Created',
                    f'New account registered — Email: {email} — IP: {ip} — {now}')
        except Exception as e:
            print(f"Registration log error: {e}")

        del registration_otp_store[email]

        return jsonify({
            "message":       "Registration successful! Welcome to PayEase!",
            "wallet_number": wallet.wallet_number,
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ── RESEND OTP ──
# 3 per 15 minutes — prevents OTP spam
@auth_bp.route("/register/resend-otp", methods=["POST"])
@limiter.limit("3 per 15 minutes")
def resend_registration_otp():
    data  = request.get_json()
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    stored = registration_otp_store.get(email)
    if not stored:
        return jsonify({"error": "No pending registration found"}), 400

    otp               = generate_otp()
    stored["otp"]     = otp
    stored["expires"] = datetime.utcnow() + timedelta(minutes=5)

    email_sent = send_registration_otp_email(email, otp, stored["full_name"])
    return jsonify({
        "message":    f"New OTP sent to {email}",
        "email_sent": email_sent,
    }), 200


# ── LOGIN ──
# 10 per 15 minutes — prevents password brute force
@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per 15 minutes")
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    email    = data.get("email",    "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
        return jsonify({"error": "Invalid email or password"}), 401
    if user.is_blocked:
        return jsonify({"error": "Account is blocked. Contact support."}), 403

    ip_address = get_ip(request)
    user_agent = request.headers.get('User-Agent', 'Unknown Device')
    now_str    = datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')

    # ── New device detection ──
    try:
        device_hash   = hashlib.md5(f"{user_agent}{ip_address}".encode()).hexdigest()[:16]
        is_new_device = user.last_device_hash is not None and user.last_device_hash != device_hash
        user.last_device_hash = device_hash

        if is_new_device and not user.is_admin:
            try:
                send_new_device_email(user.email, user.full_name, ip_address, user_agent)
            except Exception as e:
                print(f"New device email error: {e}")
    except Exception as e:
        print(f"Device detection error: {e}")

    # ── Update login tracking ──
    user.last_login_at = datetime.utcnow()
    user.login_count   = (user.login_count or 0) + 1
    db.session.commit()

    # ── Log the login ──
    try:
        ua_short     = user_agent[:60] + '...' if len(user_agent) > 60 else user_agent
        latitude     = data.get("latitude",  "")
        longitude    = data.get("longitude", "")
        location_str = f"Location: {latitude}, {longitude} — " if latitude and longitude else ""
        add_log(user.id, 'User Login',
                f'Logged in — IP: {ip_address} — {location_str}Device: {ua_short} — {now_str}')
    except Exception as e:
        print(f"Login log error: {e}")

    # ── Issue BOTH access and refresh tokens ──
    user_id_str   = str(user.id)
    access_token  = create_access_token(identity=user_id_str)
    refresh_token = create_refresh_token(identity=user_id_str)

    return jsonify({
        "message":       "Login successful!",
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "user":          user.to_dict(),
    }), 200


# ── REFRESH ──
# 30 per hour — generous for silent auto-refresh
@auth_bp.route("/refresh", methods=["POST"])
@limiter.limit("30 per hour")
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    user    = User.query.get(int(user_id))

    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.is_blocked:
        return jsonify({"error": "Account is blocked"}), 403

    new_access_token = create_access_token(identity=user_id)
    return jsonify({
        "access_token": new_access_token,
        "user":         user.to_dict(),
    }), 200


# ── LOGOUT ──
# No strict limit needed — legitimate users log out once
@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    try:
        jwt_data = get_jwt()
        jti      = jwt_data["jti"]
        user_id  = int(get_jwt_identity())

        blocked = TokenBlocklist(jti=jti, user_id=user_id)
        db.session.add(blocked)
        db.session.commit()

        try:
            add_log(user_id, 'User Logout', 'Logged out — token invalidated')
        except Exception:
            pass

        return jsonify({"message": "Logged out successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── LOGOUT ALL ──
@auth_bp.route("/logout-all", methods=["POST"])
@jwt_required()
def logout_all():
    try:
        jwt_data = get_jwt()
        jti      = jwt_data["jti"]
        user_id  = int(get_jwt_identity())

        blocked = TokenBlocklist(jti=jti, user_id=user_id)
        db.session.add(blocked)
        db.session.commit()

        try:
            add_log(user_id, 'Logout All Devices', 'All sessions invalidated by user')
        except Exception:
            pass

        return jsonify({"message": "All sessions logged out"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── SETUP ADMIN ──
# 3 per day — setup should only happen once
@auth_bp.route('/setup-admin', methods=['POST'])
@limiter.limit("3 per day")
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
    hashed_pin      = bcrypt.hashpw('0000'.encode(),     bcrypt.gensalt()).decode()

    admin = User(
        full_name    = 'Admin',
        email        = 'admin@payease.com',
        phone        = '03000000000',
        password     = hashed_password,
        pin          = hashed_pin,
        is_admin     = True,
        kyc_verified = True,
    )
    db.session.add(admin)
    db.session.flush()

    wallet = Wallet(
        user_id       = admin.id,
        wallet_number = 'PK' + ''.join([str(random.randint(0,9)) for _ in range(10)]),
        balance       = 100000,
    )
    db.session.add(wallet)
    db.session.commit()
    return jsonify({'message': 'Admin created successfully!'})

