import random
import string
import os
import resend
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models.user import User

otp_bp = Blueprint('otp', __name__)

# ── OTP Store (in-memory) ──
otp_store = {}

# ── Resend setup ──
resend.api_key = os.environ.get('RESEND_API_KEY', 're_iEscg1G9_F2ehzTnWiYSXTub3K4fMoWeW')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@payease.space')


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


def send_otp_email(email, otp, purpose, full_name='User'):
    """Send OTP via Resend email"""

    purpose_labels = {
        'change_password': 'Change Password',
        'change_pin':      'Change PIN',
        'forgot_password': 'Reset Password',
        'verification':    'Verification',
    }
    label = purpose_labels.get(purpose, 'Verification')

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
<h2 style="color:#1A1A2E;font-size:22px;font-weight:bold;margin:0 0 8px 0;">Hello, {full_name}! 👋</h2>
<p style="color:#888;font-size:14px;margin:0 0 28px 0;line-height:1.6;">
You requested a verification code for <strong>{label}</strong>.
Use the code below — it expires in <strong>5 minutes</strong>.
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
If you did not request this, please ignore this email.
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
            "from":    f"PayEase <{SENDER_EMAIL}>",
            "to":      [email],
            "subject": f"PayEase — Your {label} Code",
            "html":    html_body,
        })
        return True
    except Exception as e:
        print(f"Email error: {str(e)}")
        return False


# ── SEND OTP ──
@otp_bp.route('/send', methods=['POST'])
@jwt_required()
def send_otp():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data    = request.get_json()
    purpose = data.get('purpose', 'verification')

    otp     = generate_otp()
    expiry  = datetime.utcnow() + timedelta(minutes=5)

    otp_store[user.email] = {
        'otp':     otp,
        'expiry':  expiry,
        'purpose': purpose,
        'used':    False
    }

    email_sent = send_otp_email(user.email, otp, purpose, user.full_name)

    return jsonify({
        'message':    f'Verification code sent to {user.email}',
        'email':      user.email,
        'email_sent': email_sent,
    }), 200


# ── CHANGE PASSWORD ──
@otp_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    import bcrypt
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data         = request.get_json()
    otp          = data.get('otp', '').strip()
    new_password = data.get('new_password', '')

    if not otp or not new_password:
        return jsonify({'error': 'OTP and new password are required'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    record = otp_store.get(user.email)
    if not record:
        return jsonify({'error': 'No OTP found. Please request a new one.'}), 400
    if record['used']:
        return jsonify({'error': 'OTP already used'}), 400
    if datetime.utcnow() > record['expiry']:
        return jsonify({'error': 'OTP expired. Please request a new one.'}), 400
    if record['otp'] != otp:
        return jsonify({'error': 'Invalid OTP'}), 400

    otp_store[user.email]['used'] = True

    hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user.password = hashed
    db.session.commit()

    return jsonify({'message': 'Password changed successfully!'}), 200


# ── CHANGE PIN ──
@otp_bp.route('/change-pin', methods=['POST'])
@jwt_required()
def change_pin():
    import bcrypt
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data    = request.get_json()
    otp     = data.get('otp', '').strip()
    new_pin = data.get('new_pin', '')

    if not otp or not new_pin:
        return jsonify({'error': 'OTP and new PIN are required'}), 400

    if len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({'error': 'PIN must be 4 digits'}), 400

    record = otp_store.get(user.email)
    if not record:
        return jsonify({'error': 'No OTP found. Please request a new one.'}), 400
    if record['used']:
        return jsonify({'error': 'OTP already used'}), 400
    if datetime.utcnow() > record['expiry']:
        return jsonify({'error': 'OTP expired. Please request a new one.'}), 400
    if record['otp'] != otp:
        return jsonify({'error': 'Invalid OTP'}), 400

    otp_store[user.email]['used'] = True

    hashed = bcrypt.hashpw(new_pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user.pin = hashed
    db.session.commit()

    return jsonify({'message': 'PIN changed successfully!'}), 200


# ── FORGOT PASSWORD — SEND OTP (no JWT) ──
@otp_bp.route('/forgot-password/send', methods=['POST'])
def forgot_password_send():
    data  = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'No account found with this email'}), 404

    otp    = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=5)

    otp_store[email] = {
        'otp':     otp,
        'expiry':  expiry,
        'purpose': 'forgot_password',
        'used':    False
    }

    email_sent = send_otp_email(email, otp, 'forgot_password', user.full_name)

    return jsonify({
        'message':    f'Reset code sent to {email}',
        'email_sent': email_sent,
    }), 200


# ── FORGOT PASSWORD — RESET (no JWT) ──
@otp_bp.route('/forgot-password/reset', methods=['POST'])
def forgot_password_reset():
    import bcrypt
    data         = request.get_json()
    email        = data.get('email', '').strip().lower()
    otp          = data.get('otp', '').strip()
    new_password = data.get('new_password', '')

    if not all([email, otp, new_password]):
        return jsonify({'error': 'All fields are required'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    record = otp_store.get(email)
    if not record:
        return jsonify({'error': 'No OTP found. Please request a new one.'}), 400
    if record['used']:
        return jsonify({'error': 'OTP already used'}), 400
    if datetime.utcnow() > record['expiry']:
        return jsonify({'error': 'OTP expired. Please request a new one.'}), 400
    if record['otp'] != otp:
        return jsonify({'error': 'Invalid OTP'}), 400

    otp_store[email]['used'] = True

    hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user.password = hashed
    db.session.commit()

    return jsonify({'message': 'Password reset successfully!'}), 200

